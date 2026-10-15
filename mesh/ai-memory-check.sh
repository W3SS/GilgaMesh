#!/usr/bin/env bash
# Verificação SOMENTE LEITURA da integração ai-memory neste nó.
#   AI_MEMORY_SERVER_URL=https://memory.mesh.w3ss.sh AI_MEMORY_AUTH_TOKEN=aim_... ./ai-memory-check.sh
# Confere: servidor e autenticação, marcador .ai-memory.toml dos projetos, Claude Code
# (MCP e hooks) e perfis Hermes (plugin, MCP, hooks). Não escreve nada em lugar nenhum.
set -uo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

URL="${AI_MEMORY_SERVER_URL:-https://memory.mesh.w3ss.sh}"
TOKEN="${AI_MEMORY_AUTH_TOKEN:-${AI_MEMORY_API_KEY:-}}"
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
bad()  { printf '  \033[31mFALHA\033[0m %s\n' "$*"; }
info() { printf '  \033[33m--\033[0m    %s\n' "$*"; }
sec()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

sec "1. Servidor ($URL)"
code_noauth="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "$URL/admin/status" || true)"
case "$code_noauth" in
  401|403) ok "sem token é recusado ($code_noauth)" ;;
  000)     bad "servidor inalcançável (tailnet conectada? nome resolve?)" ;;
  200)     bad "responde SEM token: autenticação desligada (teste MEM-01 reprovaria)" ;;
  *)       info "sem token: HTTP $code_noauth" ;;
esac
if [ -n "$TOKEN" ]; then
  code="$(curl -s -m 8 -o /tmp/aim-status.$$ -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$URL/admin/status" || true)"
  case "$code" in
    200) ok "token aceito em /admin/status"; python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("        ", json.dumps(d)[:300])' /tmp/aim-status.$$ 2>/dev/null ;;
    403) bad "403 em /admin/*: com usuários no servidor, /admin é só do root. O plugin do Hermes usa /admin/search e /admin/write-page, então falha com chave aim_." ;;
    401) bad "token recusado" ;;
    *)   bad "HTTP $code em /admin/status" ;;
  esac
  rm -f /tmp/aim-status.$$
  hc="$(curl -s -m 8 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$URL/handoff" || true)"
  [ "$hc" = 200 ] && ok "/handoff acessível com este token (continuidade entre sessões)" || info "/handoff: HTTP $hc"
else
  info "AI_MEMORY_AUTH_TOKEN não definido: testes autenticados pulados"
fi

sec "2. Projetos deste nó (.ai-memory.toml)"
for dir in ${MESH_PROJECTS:-$HOME/projects}; do
  [ -d "$dir" ] || { info "$dir não existe"; continue; }
  m="$dir/.ai-memory.toml"
  if [ ! -f "$m" ]; then bad "$dir sem marcador: o projeto vira '$(basename "$dir")' e diverge entre nós"; continue; fi
  ws="$(sed -n 's/^workspace *= *"\(.*\)"/\1/p' "$m" | head -1)"
  pj="$(sed -n 's/^project *= *"\(.*\)"/\1/p' "$m" | head -1)"
  idn="$(sed -n 's/^identity *= *"\(.*\)"/\1/p' "$m" | head -1)"
  br="$(grep -c 'inject_on_session_start' "$m")"
  [ -n "$ws" ] && [ -n "$pj" ] && ok "$dir -> $ws/$pj" || bad "$dir: marcador sem workspace+project (clientes estáticos exigem os dois)"
  [ -n "$idn" ] && ok "  identity = $idn" || info "  sem identity (usa o remote git normalizado)"
  [ "$br" -gt 0 ] && ok "  briefing no início da sessão ligado" || bad "  [briefing] inject_on_session_start ausente: a sessão não recebe o resumo do projeto"
  git -C "$dir" ls-files --error-unmatch .ai-memory.toml >/dev/null 2>&1 && ok "  marcador versionado no git (igual em todos os nós)" || info "  marcador fora do git: cada nó pode divergir"
done

sec "3. Claude Code"
export PATH="$HOME/.local/bin:$PATH"
if command -v claude >/dev/null 2>&1; then
  claude mcp list 2>/dev/null | grep -qi 'ai-memory' && ok "MCP ai-memory registrado" || bad "MCP ai-memory não registrado (ai-memory install-mcp --client claude-code --apply)"
  grep -qs 'ai-memory' "$HOME/.claude/settings.json" && ok "hooks ai-memory em ~/.claude/settings.json" || bad "sem hooks ai-memory (ai-memory install-hooks --agent claude-code --apply)"
else info "claude não instalado"; fi
command -v ai-memory >/dev/null 2>&1 && ok "binário: $(ai-memory --version 2>/dev/null | head -1)" || info "binário ai-memory ausente (ok se este nó só usa MCP remoto)"

sec "4. Perfis Hermes"
root="${HERMES_HOME:-$HOME/.hermes}/profiles"
if [ -d "$root" ]; then
  tot=0; com=0
  for p in "$root"/*/; do
    n="$(basename "$p")"; [ "$n" = _retired ] && continue
    tot=$((tot+1))
    cfg="$p/config.yaml"; has_mcp=0; has_hook=0; has_json=0
    grep -qs 'ai-memory' "$cfg" && has_mcp=1
    grep -qs 'ai-memory hook' "$cfg" && has_hook=1
    [ -f "$p/ai-memory.json" ] && has_json=1
    if [ $((has_mcp+has_hook+has_json)) -gt 0 ]; then
      com=$((com+1)); printf '  %-14s mcp=%s hooks=%s plugin-config=%s\n' "$n" "$has_mcp" "$has_hook" "$has_json"
    fi
  done
  info "$com de $tot perfis têm alguma ligação com o ai-memory (os demais ficam sem memória compartilhada)"
else info "sem perfis Hermes neste nó ($root)"; fi
