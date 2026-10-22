#!/usr/bin/env bash
# Cria o usuário e uma chave `aim_` por nó no servidor ai-memory. Roda NO SERVIDOR (VPS).
#
#   AI_MEMORY_AUTH_TOKEN=<token root> ./ai-memory-provision.sh            # mostra o plano, não muda nada
#   AI_MEMORY_AUTH_TOKEN=<token root> ./ai-memory-provision.sh --apply    # cria o que falta
#
# Opções:
#   --user NOME     usuário dono de todas as chaves (padrão: wendel)
#   --nodes "a b"   rótulos das chaves, um por nó (padrão: "macmini macbook wsl vps")
#   --out DIR       onde gravar as chaves (padrão: ~/ai-memory-keys, modo 0700)
#   --apply         executa; sem isto só mostra o plano
#
# Servidor em Docker: AI_MEMORY_BIN="docker exec -i -e AI_MEMORY_AUTH_TOKEN ai-memory ai-memory"
# O servidor precisa estar no ar (a CLI conversa com ele por HTTP).
#
# Por que `user add` e não `user add-human`: o add-human liga o modo "login humano" e, a partir daí, o
# servidor SE RECUSA a reiniciar sem um usuário root com senha ou um AI_MEMORY_AUTH__RECOVERY_TOKEN.
# Uma atualização do contêiner ou um reboot da VPS derrubaria a memória de todos os nós. O `user add`
# mantém o servidor no modo só-máquina (sem senha, sem console web). Ele também emite um token legado
# que funciona como bearer; este script o revoga na hora e nunca o mostra.
#
# As chaves só existem no momento da criação. Cada uma vai para um arquivo 0600 em --out e NUNCA é
# impressa. Depois de aplicada em cada nó, apague o arquivo (ai-memory-switch.sh --delete-remote faz isso).
set -euo pipefail

USER_NAME=wendel
NODES="macmini macbook wsl vps"
OUT="$HOME/ai-memory-keys"
APPLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --user)  USER_NAME="${2:?--user precisa de um nome}"; shift 2 ;;
    --nodes) NODES="${2:?--nodes precisa de uma lista}"; shift 2 ;;
    --out)   OUT="${2:?--out precisa de um diretório}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
die()  { printf '\033[1;31m[provision]\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m[provision]\033[0m %s\n' "$*" >&2; }

[ -n "${AI_MEMORY_AUTH_TOKEN:-}" ] || die "defina AI_MEMORY_AUTH_TOKEN com o token root do servidor."
printf '%s' "$USER_NAME" | grep -Eq '^[a-z0-9][a-z0-9._-]*$' || die "nome de usuário inválido: $USER_NAME"
for n in $NODES; do printf '%s' "$n" | grep -Eq '^[a-z0-9][a-z0-9._-]*$' || die "rótulo inválido: $n"; done

read -r -a AIM <<< "${AI_MEMORY_BIN:-ai-memory}"
command -v "${AIM[0]}" >/dev/null 2>&1 || die "${AIM[0]} não encontrado (use AI_MEMORY_BIN para Docker)."
URL="${AI_MEMORY_SERVER_URL:-http://127.0.0.1:49374}"

ERRF="$(mktemp)"; trap 'rm -f "$ERRF"' EXIT
aim() {
  if ! "${AIM[@]}" "$@" 2>"$ERRF"; then
    grep -v -E 'INFO|^\s*[0-9]+:|^\s+at |Stack backtrace|^\s*$' "$ERRF" >&2 || true
    die "falhou: ai-memory $1 $2"
  fi
}

code="$(curl -s -m 8 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $AI_MEMORY_AUTH_TOKEN" "$URL/admin/status" || true)"
case "$code" in
  200) ;;
  401|403) die "o servidor recusou o token (HTTP $code). É o token root?" ;;
  *) die "servidor inalcançável em $URL (HTTP $code). Ele está no ar?" ;;
esac

users_json="$(aim user list --json)"
keys_json="$(aim api-key list --json)"

# Entrada: users_json e keys_json em variáveis de ambiente (nunca em argv).
plan="$(USERS="$users_json" KEYS="$keys_json" UNAME="$USER_NAME" NODES="$NODES" python3 -I - <<'PY'
import json, os
users = json.loads(os.environ["USERS"] or "[]")
keys = json.loads(os.environ["KEYS"] or "[]")
name = os.environ["UNAME"]
u = next((x for x in users if x["username"] == name), None)
print("user_exists=%d" % (1 if u else 0))
print("human_mode=%d" % (1 if any(x.get("has_password") for x in users) else 0))
uid = u["id"] if u else None
live = {k["label"] for k in keys if k["user_id"] == uid and not k.get("revoked_at")}
for n in os.environ["NODES"].split():
    print("node_%s=%s" % (n.replace("-", "_").replace(".", "_"), "have" if n in live else "missing"))
legacy = [k["id"] for k in keys if k["user_id"] == uid and k["label"] == "legacy-user-token" and not k.get("revoked_at")]
print("legacy=%s" % (legacy[0] if legacy else ""))
PY
)"
get() { printf '%s\n' "$plan" | sed -n "s/^$1=//p"; }

say "Servidor: $URL"
say "Usuário:  $USER_NAME ($([ "$(get user_exists)" = 1 ] && echo existe || echo 'será criado'))"
[ "$(get human_mode)" = 1 ] && warn "há usuários com senha: o servidor está em modo login humano e precisa de root com senha ou RECOVERY_TOKEN para reiniciar."
missing=()
for n in $NODES; do
  st="$(get "node_$(printf '%s' "$n" | tr '.-' '__')")"
  if [ "$st" = have ]; then say "  $n: chave ativa já existe (nada a fazer; para trocar: ai-memory api-key rotate <id>)"
  else say "  $n: chave será criada"; missing+=("$n"); fi
done
legacy_id="$(get legacy)"
[ -n "$legacy_id" ] && say "Token legado do usuário (funciona como bearer): será revogado."

if [ "$APPLY" -ne 1 ]; then say; say "Plano apenas. Rode com --apply para executar."; exit 0; fi

if [ "$(get user_exists)" != 1 ]; then
  aim user add --username "$USER_NAME" >/dev/null
  say "usuário $USER_NAME criado"
  keys_json="$(aim api-key list --json)"
  users_json="$(aim user list --json)"
  legacy_id="$(USERS="$users_json" KEYS="$keys_json" UNAME="$USER_NAME" python3 -I - <<'PY'
import json, os
users = json.loads(os.environ["USERS"]); keys = json.loads(os.environ["KEYS"])
uid = next(x["id"] for x in users if x["username"] == os.environ["UNAME"])
print(next((k["id"] for k in keys if k["user_id"] == uid and k["label"] == "legacy-user-token" and not k.get("revoked_at")), ""))
PY
)"
fi
if [ -n "$legacy_id" ]; then
  aim api-key revoke --yes "$legacy_id" >/dev/null
  say "token legado revogado"
fi

umask 077
mkdir -p "$OUT"; chmod 700 "$OUT"
for n in "${missing[@]:-}"; do
  [ -n "$n" ] || continue
  if [ -e "$OUT/$n.key" ]; then die "$OUT/$n.key já existe; mova-o antes de recriar a chave de $n."; fi
  # O segredo passa por variável de ambiente do python, nunca pela tela.
  aim api-key add --username "$USER_NAME" --label "$n" --json | python3 -I -c '
import json, sys
tok = json.load(sys.stdin)["token"]
assert tok.startswith("aim_"), "resposta sem token aim_"
sys.stdout.write(tok)
' > "$OUT/$n.key.tmp"
  mv "$OUT/$n.key.tmp" "$OUT/$n.key"
  chmod 600 "$OUT/$n.key"
  say "chave de $n gravada em $OUT/$n.key"
done

[ "${#missing[@]}" -gt 0 ] || { say; say "Nada novo a criar."; exit 0; }
say
say "Próximo passo, em cada nó (a chave não passa pela tela):"
say "  ./ai-memory-switch.sh <nó> --key-from-ssh <alias-da-vps>:$OUT/<nó>.key --apply --delete-remote"
