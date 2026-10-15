#!/usr/bin/env bash
# Liga o Claude Code deste nó aos recursos da malha pelo Kong, como se fossem locais.
# Usa a mesma chave de consumer do Hermes deste nó (x-iron-key); a ACL do Kong decide
# o que cada nó alcança (ex.: o consumer inference não lê o vault pelo gateway, GW-08).
#   IRON_KEY=<chave do consumer deste nó> ./claude-mesh-mcp.sh
# Variáveis: MESH_GATEWAY (padrão http://gateway.mesh.w3ss.sh:8000)
set -euo pipefail
GW="${MESH_GATEWAY:-http://gateway.mesh.w3ss.sh:8000}"
: "${IRON_KEY:?defina IRON_KEY com a chave do consumer deste nó (fica no .env do Hermes)}"
command -v claude >/dev/null 2>&1 || { echo "claude não instalado" >&2; exit 1; }

for route in vault creative projects; do
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "x-iron-key: $IRON_KEY" "$GW/mcp/$route" || true)"
  case "$code" in
    401|403) echo "[mesh] /mcp/$route: negado para este consumer ($code), pulando"; continue ;;
    000)     echo "[mesh] /mcp/$route: gateway inalcançável, pulando"; continue ;;
  esac
  claude mcp remove --scope user "iron-$route" >/dev/null 2>&1 || true
  claude mcp add --transport http --scope user "iron-$route" "$GW/mcp/$route" --header "x-iron-key: $IRON_KEY"
  echo "[mesh] iron-$route registrado (HTTP $code)"
done
claude mcp list
