#!/usr/bin/env bash
# Diagnóstico rápido e SOMENTE LEITURA da malha Iron Rail. Rode no Mac Mini (hub).
#   ./doctor.sh            resumo para ler no celular
#   ./doctor.sh --full     também roda o caderno de auditoria completo (84 testes)
# Não muda nada: só lê tailscale, portas, launchctl, hermes cron list e o caderno existente.
set -uo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

FULL=0; [ "${1:-}" = "--full" ] && FULL=1
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[31mFALHA\033[0m %s\n' "$*"; }
info() { printf '  \033[33m--\033[0m   %s\n' "$*"; }
sec()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

probe() { # probe <ip> <porta>
  if [ "$(uname -s)" = Darwin ]; then nc -z -G 3 "$1" "$2" >/dev/null 2>&1
  else nc -z -w 3 "$1" "$2" >/dev/null 2>&1; fi
}

sec "1. Tailnet"
TS="$(tailscale_bin || true)"
if [ -z "$TS" ]; then bad "tailscale não encontrado"; else
  "$TS" status --json 2>/dev/null | python3 -c '
import sys, json
known = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if not line or line.startswith("#"): continue
    name, alias, ip, os_, *_ = line.split("|")
    known[name] = os_
d = json.load(sys.stdin)
peers = [d["Self"]] + list((d.get("Peer") or {}).values())
for p in peers:
    name = p["DNSName"].split(".")[0].lower()
    online = "online" if (p is d["Self"] or p.get("Online")) else "OFFLINE"
    tag = known.get(name, "FORA DO REGISTRO")
    alert = "  <- identificar" if tag in ("unknown", "FORA DO REGISTRO") else ("  <- remover do tailnet" if tag == "retired" else "")
    ip = p["TailscaleIPs"][0]
    print("  %-22s %-16s %-8s %s%s" % (name, ip, online, tag, alert))
' "$NODES_FILE" || bad "não consegui ler tailscale status --json"
fi

sec "2. Portas da malha (vistas daqui)"
if ! command -v nc >/dev/null 2>&1; then info "nc não instalado: sondas de porta puladas"; else
# nó|ip|porta|serviço — política de portas do caderno de 04/10 (Blueprint v2.1/v2.4)
while IFS='|' read -r node ip port svc; do
  if probe "$ip" "$port"; then ok "$node:$port $svc"; else bad "$node:$port $svc"; fi
done <<'P'
macmini|100.115.122.50|11435|edge (Ollama/MLX via token)
macmini|100.115.122.50|8767|vault-mcp
macmini|100.115.122.50|9900|Hermes A2A
vps1|100.118.63.44|8000|Kong (proxy)
vps1|100.118.63.44|3001|Uptime Kuma
wsl|100.104.74.53|9900|Hermes A2A (estúdio)
wsl|100.104.74.53|8765|creative-mcp
macbook|100.89.49.96|9900|Hermes A2A (coordenador; ok falhar se fechado)
P
if probe 100.118.63.44 8001; then bad "vps1:8001 Admin API do Kong ABERTA na tailnet (GW-04)"; else ok "vps1:8001 Admin API do Kong fechada"; fi
fi

sec "3. Serviços locais (Mac Mini)"
if command -v launchctl >/dev/null 2>&1; then
  launchctl list 2>/dev/null | awk '$3 ~ /iron|hermes|mlx|edge|vault/ {print}' | while read -r pid code label; do
    if [ "$code" = 0 ] || [ "$pid" != "-" ]; then ok "$label (pid $pid)"; else bad "$label saiu com código $code"; fi
  done
  if launchctl list 2>/dev/null | grep -qi orca; then bad "serviço legado Orca ainda carregado (SEC-13)"; else ok "nenhum serviço Orca v1 carregado"; fi
else info "launchctl indisponível (não é macOS)"; fi

sec "4. Rotinas Hermes do morning brief"
if command -v hermes >/dev/null 2>&1; then
  for p in oracle ichigo omaeda; do
    out="$(hermes -p "$p" cron list 2>&1 | grep -iE 'brief|saude|saúde|health|custo|cost' | head -3)"
    if [ -n "$out" ]; then printf '  %s:\n%s\n' "$p" "$(echo "$out" | sed 's/^/      /')"; else info "$p: nenhuma rotina de briefing listada neste nó"; fi
  done
  VAULT="${MESH_VAULT:-/Volumes/iron-heart/r2d2}"
  hoje="$(find "$VAULT/00-INBOX/agents/oracle" -type f -mtime -1 2>/dev/null | head -1)"
  if [ -n "$hoje" ]; then ok "nota do oracle nas últimas 24 h: ${hoje#"$VAULT"/}"; else bad "nenhuma nota do oracle nas últimas 24 h em 00-INBOX/agents/oracle"; fi
else info "hermes não está no PATH deste shell"; fi

sec "5. Claude Code"
if command -v claude >/dev/null 2>&1; then ok "claude $(claude --version 2>/dev/null | head -n1)"; else bad "claude não instalado"; fi
if command -v tmux >/dev/null 2>&1 && tmux has-session -t "${MESH_TMUX_SESSION:-claude-rc}" 2>/dev/null; then
  ok "remote-control rodando (tmux ${MESH_TMUX_SESSION:-claude-rc})"
else info "remote-control não está rodando aqui (./start-claude.sh)"; fi

AUDIT="$HOME/.iron-rail/audit/audit-run.py"
sec "6. Caderno de auditoria"
if [ -f "$AUDIT" ]; then
  PY=/opt/homebrew/bin/python3; [ -x "$PY" ] || PY=python3
  if [ "$FULL" = 1 ]; then "$PY" "$AUDIT" --no-vault
  else "$PY" "$AUDIT" --only NET-01,NET-03,NET-04,GW-01,GW-02,GW-03,GW-07,INF-06,INF-07,HER-01,HER-03,HER-07,SEC-13,OPS-05,OPS-09 --no-vault
  fi
else info "audit-run.py não encontrado (rode no Mac Mini)"; fi
