#!/usr/bin/env bash
# Bootstrap do mesh em Linux (VPS, WSL: creative-wsl, florence, iron-gateway).
# Uso: ./bootstrap-linux.sh [--service] [--start]
#   --service  instala serviço systemd (usuário) que sobe o claude remote-control no boot
#   --start    sobe o claude remote-control agora (tmux)
# Variáveis: TS_AUTHKEY=tskey-... faz o `tailscale up` sem login interativo (VPS novas).
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

SERVICE=0; START=0
for a in "$@"; do
  case "$a" in
    --service) SERVICE=1 ;; --start) START=1 ;;
    *) die "opção desconhecida: $a" ;;
  esac
done
[ "$(uname -s)" = Linux ] || die "Este script é para Linux."

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
HAS_SYSTEMD=0; [ -d /run/systemd/system ] && HAS_SYSTEMD=1

pkg_install() {
  if   command -v apt-get >/dev/null 2>&1; then $SUDO apt-get update -qq && $SUDO apt-get install -y -qq "$@"
  elif command -v dnf     >/dev/null 2>&1; then $SUDO dnf install -y -q "$@"
  elif command -v yum     >/dev/null 2>&1; then $SUDO yum install -y -q "$@"
  elif command -v pacman  >/dev/null 2>&1; then $SUDO pacman -S --noconfirm --needed "$@"
  else die "Gerenciador de pacotes não suportado; instale manualmente: $*"; fi
}

# Dependências básicas
need=()
for c in curl git tmux; do command -v "$c" >/dev/null 2>&1 || need+=("$c"); done
command -v sshd >/dev/null 2>&1 || [ -x /usr/sbin/sshd ] || need+=("openssh-server")
[ "${#need[@]}" -gt 0 ] && { log "Instalando: ${need[*]}"; pkg_install "${need[@]}"; }

# Tailscale
if ! command -v tailscale >/dev/null 2>&1; then
  log "Instalando Tailscale"
  curl -fsSL https://tailscale.com/install.sh | $SUDO sh
fi
if ! tailscale status >/dev/null 2>&1; then
  [ "$HAS_SYSTEMD" = 1 ] || die "Sem systemd (WSL?). Habilite em /etc/wsl.conf: [boot] systemd=true, rode 'wsl --shutdown' e repita."
  $SUDO systemctl enable --now tailscaled
  if [ -n "${TS_AUTHKEY:-}" ]; then
    $SUDO tailscale up --authkey "$TS_AUTHKEY"
  else
    log "Autentique no Tailscale (abrirá uma URL):"
    $SUDO tailscale up
  fi
fi

SELF="$(resolve_self)"
log "Máquina: $SELF"

# SSH server
if [ "$HAS_SYSTEMD" = 1 ]; then
  $SUDO systemctl enable --now ssh 2>/dev/null || $SUDO systemctl enable --now sshd
else
  $SUDO service ssh start 2>/dev/null || warn "Não consegui iniciar o sshd (sem systemd). Inicie manualmente."
fi

# Firewall: só ADICIONA permissão do SSH pela interface da tailnet (nunca remove regras).
if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -q 'Status: active'; then
  $SUDO ufw allow in on tailscale0 to any port 22 proto tcp >/dev/null
  log "ufw: SSH liberado na interface tailscale0"
fi

mesh_setup_identity "$SELF"
mesh_install_claude

if [ "$SERVICE" = 1 ]; then
  [ "$HAS_SYSTEMD" = 1 ] || die "--service requer systemd."
  UNIT_DIR="$HOME/.config/systemd/user"; mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/gilgamesh-claude.service" <<UNIT
[Unit]
Description=Gilgamesh mesh: claude remote-control em tmux
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/bin/bash $MESH_DIR/start-claude.sh
ExecStop=-/usr/bin/tmux kill-session -t ${MESH_TMUX_SESSION:-claude-rc}

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload
  systemctl --user enable --now gilgamesh-claude.service
  $SUDO loginctl enable-linger "$USER" || warn "Não consegui habilitar linger; o serviço só subirá após login."
  log "Serviço systemd (usuário) instalado: gilgamesh-claude.service"
fi

[ "$START" = 1 ] && [ "$SERVICE" = 0 ] && mesh_start_claude

cat <<MSG

Pronto em $SELF. Próximos passos:
  1. Se ainda não logou no Claude Code: rode 'claude' e use /login (em VPS sem navegador, siga o link no celular).
  2. Faça commit/push de mesh/pubkeys/$SELF.pub (ou copie para as outras máquinas).
  3. Em cada máquina: ./meshctl.sh sync  e depois  ./meshctl.sh status
MSG
