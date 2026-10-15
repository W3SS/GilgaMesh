#!/usr/bin/env bash
# Coordenação do mesh a partir de qualquer node Unix (macOS/Linux/WSL/Termux).
#   meshctl.sh list                     lista os nodes
#   meshctl.sh sync                     git pull + atualiza ssh config e authorized_keys
#   meshctl.sh status                   testa SSH em todos os nodes
#   meshctl.sh run <alias|all> <cmd>    executa comando remoto
set -uo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=6)
SELF="${MESH_SELF:-$(self_node || true)}"

targets() { # imprime "alias" dos nodes alcançáveis por SSH, exceto esta máquina
  local name alias ip os user
  while IFS='|' read -r name alias ip os user; do
    [ "$name" = "$SELF" ] && continue
    [ "$os" = "android" ] && continue
    echo "$alias"
  done < <(nodes)
}

case "${1:-help}" in
  list)
    printf '%-22s %-9s %-16s %-8s\n' NAME ALIAS IP OS
    nodes | while IFS='|' read -r name alias ip os user; do
      mark=""; [ "$name" = "$SELF" ] && mark=" (esta)"
      printf '%-22s %-9s %-16s %-8s%s\n' "$name" "$alias" "$ip" "$os" "$mark"
    done ;;
  sync)
    git -C "$MESH_DIR" pull --ff-only || warn "git pull falhou; usando pubkeys locais."
    [ -n "$SELF" ] || die "Máquina não identificada em nodes.conf."
    write_ssh_config "$SELF"
    authorize_pubkeys ;;
  status)
    [ -n "$SELF" ] || warn "Máquina não identificada; testando todos."
    for t in $(targets); do
      if out="$(ssh "${SSH_OPTS[@]}" "$t" 'hostname' 2>&1)"; then
        printf '\033[32m✔\033[0m %-9s %s\n' "$t" "$out"
      else
        printf '\033[31m✘\033[0m %-9s %s\n' "$t" "$(echo "$out" | tail -n1)"
      fi
    done ;;
  run)
    [ $# -ge 3 ] || die "uso: meshctl.sh run <alias|all> <comando...>"
    who="$2"; shift 2
    if [ "$who" = all ]; then list="$(targets)"; else list="$who"; fi
    for t in $list; do
      printf '\033[1;36m== %s ==\033[0m\n' "$t"
      ssh "${SSH_OPTS[@]}" "$t" "$@" || warn "$t: falhou"
    done ;;
  *) sed -n '2,7p' "$0" ;;
esac
