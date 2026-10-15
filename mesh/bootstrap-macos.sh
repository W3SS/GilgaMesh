#!/usr/bin/env bash
# Bootstrap do mesh no macOS (MacBook Air, Mac mini).
# Uso: ./bootstrap-macos.sh [--service] [--start] [--keep-awake]
#   --service     instala LaunchAgent que sobe o claude remote-control no login
#   --start       sobe o claude remote-control agora (tmux)
#   --keep-awake  impede suspensão quando ligado na tomada (recomendado p/ Mac mini)
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

SERVICE=0; START=0; AWAKE=0
for a in "$@"; do
  case "$a" in
    --service) SERVICE=1 ;; --start) START=1 ;; --keep-awake) AWAKE=1 ;;
    *) die "opção desconhecida: $a" ;;
  esac
done
[ "$(uname -s)" = Darwin ] || die "Este script é para macOS."

SELF="$(resolve_self)"
log "Máquina: $SELF"

TS="$(tailscale_bin || true)"
[ -n "$TS" ] || die "Tailscale não encontrado. Instale o app (tailscale.com/download/mac) e faça login."
"$TS" status >/dev/null 2>&1 || die "Tailscale instalado mas desconectado. Abra o app e conecte."

# SSH server ("Login Remoto"). Pode exigir Full Disk Access para o Terminal.
if ! sudo systemsetup -getremotelogin 2>/dev/null | grep -qi ': on'; then
  log "Ativando Login Remoto (SSH)"
  sudo systemsetup -setremotelogin on || warn "Falhou. Ative em Ajustes > Geral > Compartilhamento > Login Remoto."
fi

# tmux via Homebrew
if ! command -v tmux >/dev/null 2>&1; then
  command -v brew >/dev/null 2>&1 || die "Instale o Homebrew (brew.sh) ou o tmux manualmente."
  brew install tmux
fi

mesh_setup_identity "$SELF"
mesh_install_claude

if [ "$AWAKE" = 1 ]; then
  log "Desativando suspensão quando na tomada"
  sudo pmset -c sleep 0
fi

if [ "$SERVICE" = 1 ]; then
  PLIST="$HOME/Library/LaunchAgents/com.gilgamesh.mesh.claude.plist"
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.gilgamesh.mesh.claude</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$MESH_DIR/start-claude.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>AbandonProcessGroup</key><true/>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StandardErrorPath</key><string>/tmp/gilgamesh-mesh.err</string>
  <key>StandardOutPath</key><string>/tmp/gilgamesh-mesh.out</string>
</dict></plist>
PL
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  log "LaunchAgent instalado: $PLIST"
fi

[ "$START" = 1 ] && [ "$SERVICE" = 0 ] && mesh_start_claude

cat <<MSG

Pronto em $SELF. Próximos passos:
  1. Se ainda não logou no Claude Code: rode 'claude' e use /login.
  2. Faça commit/push de mesh/pubkeys/$SELF.pub (ou copie para as outras máquinas).
  3. Em cada máquina: ./meshctl.sh sync  e depois  ./meshctl.sh status
MSG
