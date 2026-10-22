#!/usr/bin/env bash
# Troca o token root pela chave `aim_` deste nó nos clientes do ai-memory (hooks do Claude Code, MCP do
# Claude Code e perfis Hermes). Roda em CADA nó. Sem --apply só mostra o que mudaria.
#
#   ./ai-memory-switch.sh macbook --key-from-ssh vps1:~/ai-memory-keys/macbook.key            # plano
#   ./ai-memory-switch.sh macbook --key-from-ssh vps1:~/ai-memory-keys/macbook.key --apply --delete-remote
#
# Origem da chave (uma das três; a chave nunca vai para a linha de comando nem para a tela):
#   --key-from-ssh HOST:CAMINHO   lê com `ssh HOST cat CAMINHO` (use os atalhos do meshctl: vps1, macmini...)
#   --key-file ARQUIVO            lê de um arquivo local
#   --key-stdin                   lê a primeira linha da entrada padrão
#
# Opções:
#   --server-url URL      padrão: $AI_MEMORY_SERVER_URL ou https://memory.mesh.w3ss.sh
#   --data-dir DIR        diretório de dados do cliente (padrão: o que o `ai-memory` informa)
#   --old-token-file F    arquivo com o token root antigo, se o auth-token do cliente não existir mais
#   --hermes-set          grava AI_MEMORY_AUTH_TOKEN no .env dos perfis Hermes que usam o ai-memory
#   --delete-remote       depois de aplicar e verificar, apaga o arquivo de origem do --key-from-ssh
#   --apply               executa; sem isto só mostra o plano
#
# O que ele faz, em ordem:
#   1. Confirma no servidor que a chave é de USUÁRIO (/handoff aceita, /admin recusa). Se for o token root
#      ou se for recusada, para antes de mexer em qualquer coisa.
#   2. Faz cópia de segurança de tudo que vai mudar, em <data_dir>/.switch-backup-<hora> (0700).
#   3. Grava <data_dir>/auth-token e auth-header (0600), que os hooks nativos e de shell leem.
#   4. Troca o token root antigo, quando aparece escrito, nestes lugares de CLIENTE: ~/.claude.json,
#      ~/.claude/settings.json, .env e config.yaml dos perfis Hermes, LaunchAgents e units systemd de usuário.
#      Não toca em arquivos do SERVIDOR (secrets/ai-memory.env, docker compose): o servidor continua com o root.
#   5. Verifica de novo usando os arquivos gravados e lista os gateways Hermes que precisam reiniciar
#      (ele não reinicia nada sozinho).
set -euo pipefail

NODE="${1:-}"; [ -n "$NODE" ] && [ "${NODE#-}" = "$NODE" ] || { sed -n '2,29p' "$0"; exit 2; }
shift
KEY_SRC=""; KEY_ARG=""; SERVER_URL="${AI_MEMORY_SERVER_URL:-https://memory.mesh.w3ss.sh}"
DATA_DIR_OPT=""; OLD_TOKEN_FILE=""; HERMES_SET=0; DELETE_REMOTE=0; APPLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --key-from-ssh) KEY_SRC=ssh;   KEY_ARG="${2:?--key-from-ssh precisa de HOST:CAMINHO}"; shift 2 ;;
    --key-file)     KEY_SRC=file;  KEY_ARG="${2:?--key-file precisa de um arquivo}"; shift 2 ;;
    --key-stdin)    KEY_SRC=stdin; shift ;;
    --server-url)   SERVER_URL="${2:?}"; shift 2 ;;
    --data-dir)     DATA_DIR_OPT="${2:?}"; shift 2 ;;
    --old-token-file) OLD_TOKEN_FILE="${2:?}"; shift 2 ;;
    --hermes-set)   HERMES_SET=1; shift ;;
    --delete-remote) DELETE_REMOTE=1; shift ;;
    --apply)        APPLY=1; shift ;;
    -h|--help)      sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
bad()  { printf '  \033[31mFALHA\033[0m %s\n' "$*"; }
info() { printf '  \033[33m--\033[0m    %s\n' "$*"; }
die()  { printf '\033[1;31m[switch]\033[0m %s\n' "$*" >&2; exit 1; }

[ -n "$KEY_SRC" ] || die "diga de onde vem a chave: --key-from-ssh, --key-file ou --key-stdin."
printf '%s' "$NODE" | grep -Eq '^[a-z0-9][a-z0-9._-]*$' || die "nome de nó inválido: $NODE"
SERVER_URL="${SERVER_URL%/}"

# ------------------------------------------------------------------ 1. ler a chave
REMOTE_HOST=""; REMOTE_PATH=""
case "$KEY_SRC" in
  ssh)
    REMOTE_HOST="${KEY_ARG%%:*}"; REMOTE_PATH="${KEY_ARG#*:}"
    [ -n "$REMOTE_HOST" ] && [ "$REMOTE_HOST" != "$KEY_ARG" ] || die "use HOST:CAMINHO em --key-from-ssh."
    printf '%s' "$REMOTE_PATH" | grep -Eq '^[A-Za-z0-9_./~-]+$' || die "caminho remoto com caracteres não permitidos: $REMOTE_PATH"
    printf '%s' "$REMOTE_HOST" | grep -Eq '^[A-Za-z0-9_.@-]+$' || die "host inválido: $REMOTE_HOST"
    KEY="$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$REMOTE_HOST" cat "$REMOTE_PATH")" || die "não consegui ler $REMOTE_PATH em $REMOTE_HOST."
    ;;
  file)  [ -r "$KEY_ARG" ] || die "não consigo ler $KEY_ARG."; KEY="$(head -n1 "$KEY_ARG")" ;;
  stdin) IFS= read -r KEY || [ -n "$KEY" ] ;;
esac
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
printf '%s' "$KEY" | grep -Eq '^aim_[A-Za-z0-9_-]{20,}$' || die "o conteúdo lido não parece uma chave aim_."

fp() { if command -v sha256sum >/dev/null 2>&1; then sha256sum; else shasum -a 256; fi | cut -c1-8; }
KEY_FP="$(printf '%s' "$KEY" | fp)"

# curl com o cabeçalho vindo da entrada padrão: o segredo não aparece no `ps`.
hcode() { # hcode <caminho> [arquivo-de-cabecalho]
  if [ -n "${2:-}" ]; then curl -s -m 10 -o /dev/null -w '%{http_code}' -H @"$2" "$SERVER_URL$1" || true
  else printf 'Authorization: Bearer %s\n' "$KEY" | curl -s -m 10 -o /dev/null -w '%{http_code}' -H @- "$SERVER_URL$1" || true; fi
}

say "Nó: $NODE   Servidor: $SERVER_URL   Chave: aim_…$(printf '%s' "$KEY" | tail -c 4) (sha256 $KEY_FP)"
say; say "1. Chave no servidor"
h="$(hcode /handoff)"; a="$(hcode /admin/status)"
case "$h/$a" in
  200/403) ok "chave de usuário válida (/handoff 200, /admin 403)" ;;
  200/200) die "esta chave abre /admin: é o token ROOT, não uma chave de usuário. Nada foi alterado." ;;
  401/*)   die "o servidor recusou a chave (401). Foi revogada ou veio de outro servidor. Nada foi alterado." ;;
  000/*)   die "servidor inalcançável em $SERVER_URL. A tailnet está conectada? Nada foi alterado." ;;
  *)       die "resposta inesperada (/handoff=$h, /admin=$a). Nada foi alterado." ;;
esac

# ------------------------------------------------------------------ 2. onde estão os arquivos
default_data_dir() {
  if [ "$(uname -s)" = Darwin ]; then printf '%s\n' "$HOME/Library/Application Support/ai-memory"
  else printf '%s\n' "${XDG_DATA_HOME:-$HOME/.local/share}/ai-memory"; fi
}
find_data_dir() {
  if [ -n "$DATA_DIR_OPT" ]; then printf '%s\n' "$DATA_DIR_OPT"; return; fi
  if [ -n "${AI_MEMORY_DATA_DIR:-}" ]; then printf '%s\n' "$AI_MEMORY_DATA_DIR"; return; fi
  if command -v ai-memory >/dev/null 2>&1; then
    d="$(ai-memory status 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | sed -n 's/.*data_dir=\([^ ]*\).*/\1/p' | head -1 || true)"
    if [ -n "$d" ]; then printf '%s\n' "$d"; return; fi
  fi
  default_data_dir
}
DATA="$(find_data_dir)"
say; say "2. Cliente neste nó"
say "  diretório de dados: $DATA"
[ -d "$DATA" ] || { info "ainda não existe; será criado"; }
[ -f "$DATA/db/memory.sqlite" ] && info "este diretório tem um banco: o nó hospeda um servidor. O servidor continua com o token root; só os clientes mudam."

OLD=""
if [ -n "$OLD_TOKEN_FILE" ]; then OLD="$(tr -d '[:space:]' < "$OLD_TOKEN_FILE")"
elif [ -f "$DATA/auth-token" ]; then OLD="$(tr -d '[:space:]' < "$DATA/auth-token")"; fi
if [ -n "$OLD" ] && [ "$OLD" = "$KEY" ]; then ok "o cliente já usa esta chave"; fi
if [ -n "$OLD" ]; then say "  token atual do cliente: sha256 $(printf '%s' "$OLD" | fp)"; else info "sem auth-token anterior (instalação nova ou sem hooks)"; fi

# Lugares de CLIENTE onde o token antigo costuma aparecer escrito.
HH="${HERMES_HOME:-$HOME/.hermes}"
candidates=("$HOME/.claude.json" "$HOME/.claude/settings.json")
profiles=("$HH")
for p in "$HH"/profiles/*/; do [ -d "$p" ] && [ "$(basename "$p")" != _retired ] && profiles+=("${p%/}"); done
for p in "${profiles[@]}"; do candidates+=("$p/.env" "$p/config.yaml" "$p/ai-memory.json"); done
for f in "$HOME"/Library/LaunchAgents/*.plist "$HOME"/.config/systemd/user/*.service; do [ -f "$f" ] && candidates+=("$f"); done

contains_old() { [ -n "$OLD" ] && [ -f "$1" ] && grep -qF -- "$OLD" "$1" 2>/dev/null; }
to_replace=()
if [ -n "$OLD" ] && [ "$OLD" != "$KEY" ]; then
  for f in "${candidates[@]}"; do contains_old "$f" && to_replace+=("$f"); done
fi
if [ "${#to_replace[@]}" -gt 0 ]; then
  say "  arquivos com o token antigo escrito (serão trocados):"; for f in "${to_replace[@]}"; do say "    $f"; done
else
  info "nenhum arquivo de cliente com o token antigo escrito"
fi

hermes_targets=()
if [ "$HERMES_SET" -eq 1 ]; then
  for p in "${profiles[@]}"; do
    if grep -qs 'ai-memory' "$p/config.yaml" 2>/dev/null || [ -f "$p/ai-memory.json" ]; then hermes_targets+=("$p"); fi
  done
  if [ "${#hermes_targets[@]}" -gt 0 ]; then say "  perfis Hermes que receberão AI_MEMORY_AUTH_TOKEN no .env:"; for p in "${hermes_targets[@]}"; do say "    $p"; done
  else info "nenhum perfil Hermes com ai-memory encontrado em $HH"; fi
fi

if [ "$APPLY" -ne 1 ]; then
  say; say "Plano apenas. Nada foi alterado. Rode com --apply para executar."
  exit 0
fi

# ------------------------------------------------------------------ 3. aplicar
umask 077
TS="$(date +%Y%m%d-%H%M%S)"
BK="$DATA/.switch-backup-$TS"
mkdir -p "$DATA"; chmod 700 "$DATA" 2>/dev/null || true
mkdir -p "$BK"; chmod 700 "$BK"
say; say "3. Aplicando (cópias em $BK)"

backup() { local f="$1" b; [ -f "$f" ] || return 0; b="$BK/$(printf '%s' "$f" | tr '/ ' '__')"; cp -p "$f" "$b"; chmod 600 "$b"; }
atomic_write() { # atomic_write <arquivo> <conteudo-com-printf-formato> <args...>
  local f="$1" fmt="$2"; shift 2
  local tmp; tmp="$(mktemp "$f.XXXXXX")"
  printf "$fmt" "$@" > "$tmp"; chmod 600 "$tmp"; mv "$tmp" "$f"
}

backup "$DATA/auth-token"; backup "$DATA/auth-header"
atomic_write "$DATA/auth-token" '%s' "$KEY"
atomic_write "$DATA/auth-header" 'Authorization: Bearer %s\n' "$KEY"
ok "gravados $DATA/auth-token e auth-header (0600)"

for f in "${to_replace[@]:-}"; do
  [ -n "$f" ] || continue
  backup "$f"
  OLD_T="$OLD" NEW_T="$KEY" python3 -I - "$f" <<'PY'
import os, sys
path = sys.argv[1]
mode = os.stat(path).st_mode & 0o777
data = open(path, encoding="utf-8", errors="surrogateescape").read()
old, new = os.environ["OLD_T"], os.environ["NEW_T"]
out = data.replace(old, new)
tmp = path + ".switch.tmp"
with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as fh:
    fh.write(out)
os.chmod(tmp, mode)
os.replace(tmp, path)
PY
  ok "token trocado em $f"
done

for p in "${hermes_targets[@]:-}"; do
  [ -n "$p" ] || continue
  envf="$p/.env"; backup "$envf"
  KEY_T="$KEY" python3 -I - "$envf" <<'PY'
import os, sys
path = sys.argv[1]
line = "AI_MEMORY_AUTH_TOKEN=" + os.environ["KEY_T"]
lines = open(path).read().splitlines() if os.path.exists(path) else []
done = False
out = []
for l in lines:
    if l.lstrip().startswith("AI_MEMORY_AUTH_TOKEN=") or l.lstrip().startswith("export AI_MEMORY_AUTH_TOKEN="):
        if not done:
            out.append(line); done = True
    else:
        out.append(l)
if not done:
    out.append(line)
tmp = path + ".switch.tmp"
with open(tmp, "w") as fh:
    fh.write("\n".join(out) + "\n")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY
  ok "AI_MEMORY_AUTH_TOKEN gravado em $envf"
done

# ------------------------------------------------------------------ 4. verificar
say; say "4. Verificação com os arquivos gravados"
h2="$(hcode /handoff "$DATA/auth-header")"; a2="$(hcode /admin/status "$DATA/auth-header")"
if [ "$h2/$a2" = "200/403" ]; then ok "auth-header autentica como usuário (/handoff 200, /admin 403)"
else bad "auth-header deu /handoff=$h2, /admin=$a2. Restaure as cópias em $BK."; exit 1; fi

if [ -n "$OLD" ] && [ "$OLD" != "$KEY" ]; then
  left=()
  for f in "${candidates[@]}"; do contains_old "$f" && left+=("$f"); done
  if [ "${#left[@]}" -gt 0 ]; then bad "o token antigo ainda aparece em: ${left[*]}"; else ok "o token antigo não aparece mais nos arquivos de cliente"; fi
fi

if [ "$DELETE_REMOTE" -eq 1 ] && [ "$KEY_SRC" = ssh ]; then
  if ssh -o BatchMode=yes "$REMOTE_HOST" "shred -u $REMOTE_PATH 2>/dev/null || rm -f $REMOTE_PATH"; then ok "arquivo de origem apagado em $REMOTE_HOST"
  else info "não consegui apagar $REMOTE_PATH em $REMOTE_HOST; apague à mão"; fi
fi

say; say "5. Reinicie para valer (o script não reinicia nada)"
found=0
if [ "$(uname -s)" = Darwin ]; then
  for f in "$HOME"/Library/LaunchAgents/*hermes*.plist; do
    [ -f "$f" ] || continue; found=1
    l="$(sed -n 's:.*<key>Label</key><string>\(.*\)</string>.*:\1:p;' "$f" | head -1)"
    [ -n "$l" ] || l="$(basename "$f" .plist)"
    say "  launchctl kickstart -k gui/$(id -u)/$l"
  done
else
  for u in $(systemctl --user list-unit-files 2>/dev/null | awk '/hermes/ {print $1}'); do found=1; say "  systemctl --user restart $u"; done
fi
[ "$found" -eq 1 ] || say "  (nenhum gateway Hermes encontrado; reinicie o que usa o ai-memory neste nó)"
say "  Sessões do Claude Code já abertas continuam com a credencial antiga até serem reabertas."
say "  As cópias em $BK guardam o token ROOT antigo: apague-as quando tudo estiver funcionando (rm -rf '$BK')."
say; say "Depois: AI_MEMORY_SERVER_URL=$SERVER_URL AI_MEMORY_AUTH_TOKEN=\$(cat '$DATA/auth-token') ./ai-memory-check.sh"
