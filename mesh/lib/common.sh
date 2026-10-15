#!/usr/bin/env bash
# Funções compartilhadas pelos scripts do mesh (macOS / Linux / WSL / VPS).

MESH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODES_FILE="${MESH_NODES_FILE:-$MESH_DIR/nodes.conf}"
PUBKEYS_DIR="$MESH_DIR/pubkeys"
MESH_KEY="$HOME/.ssh/id_ed25519_mesh"
BEGIN_MARK="# >>> gilgamesh-mesh >>>"
END_MARK="# <<< gilgamesh-mesh <<<"

# shellcheck disable=SC1091
[ -f "$MESH_DIR/local.env" ] && . "$MESH_DIR/local.env"

log()  { printf '\033[1;36m[mesh]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[mesh]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[mesh]\033[0m %s\n' "$*" >&2; exit 1; }

nodes() { grep -vE '^[[:space:]]*(#|$)' "$NODES_FILE"; }

# Só nós conhecidos e com SSH entram na config (fora: celular, fantasma e não identificado).
is_ssh_target() { case "$1" in macos|linux|windows) return 0 ;; *) return 1 ;; esac; }

# Mesma regra dos testes SEC-04/SEC-10: chave da malha só vale vinda da tailnet.
KEY_PREFIX='from="100.64.0.0/10"'

tailscale_bin() {
  if command -v tailscale >/dev/null 2>&1; then echo tailscale; return 0; fi
  local app=/Applications/Tailscale.app/Contents/MacOS/Tailscale
  if [ -x "$app" ]; then echo "$app"; return 0; fi
  return 1
}

self_ip() {
  local ts
  ts="$(tailscale_bin)" || return 0
  "$ts" ip -4 2>/dev/null | head -n1
}

# Nome (coluna name) desta máquina em nodes.conf, casando por IP da tailnet ou hostname.
self_node() {
  local ip host name alias nip os user
  ip="$(self_ip || true)"
  host="$(hostname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')"
  while IFS='|' read -r name alias nip os user; do
    if { [ -n "$ip" ] && [ "$ip" = "$nip" ]; } || [ "$host" = "$name" ]; then
      echo "$name"; return 0
    fi
  done < <(nodes)
}

resolve_self() {
  local s="${MESH_SELF:-$(self_node)}"
  [ -n "$s" ] || die "Não identifiquei esta máquina em nodes.conf (hostname: $(hostname -s)). Rode com MESH_SELF=<name>."
  echo "$s"
}

write_ssh_config() {
  local self="$1" cfg="$HOME/.ssh/config" tmp block name alias ip os user
  mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
  touch "$cfg"; chmod 600 "$cfg"
  block="$BEGIN_MARK"$'\n'"# Gerado por mesh/ — edite nodes.conf, não este bloco."$'\n'
  while IFS='|' read -r name alias ip os user; do
    [ "$name" = "$self" ] && continue
    is_ssh_target "$os" || continue
    if [ "$alias" = "$name" ]; then block+="Host $name"$'\n'; else block+="Host $alias $name"$'\n'; fi
    block+="  HostName $ip"$'\n'
    [ -n "$user" ] && block+="  User $user"$'\n'
    block+="  IdentityFile ~/.ssh/id_ed25519_mesh"$'\n'
    block+="  IdentitiesOnly yes"$'\n'
    block+="  ServerAliveInterval 30"$'\n'
    block+="  StrictHostKeyChecking accept-new"$'\n'
  done < <(nodes)
  block+="$END_MARK"
  tmp="$(mktemp)"
  awk -v b="$BEGIN_MARK" -v e="$END_MARK" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$cfg" > "$tmp"
  printf '%s\n' "$block" >> "$tmp"
  cat "$tmp" > "$cfg"; rm -f "$tmp"
  log "~/.ssh/config atualizado (bloco gilgamesh-mesh)"
}

authorize_pubkeys() {
  local ak="$HOME/.ssh/authorized_keys" f key n=0
  mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
  touch "$ak"; chmod 600 "$ak"
  for f in "$PUBKEYS_DIR"/*.pub; do
    [ -e "$f" ] || continue
    key="$(cat "$f")"
    if ! grep -qF "$key" "$ak"; then echo "$KEY_PREFIX $key" >> "$ak"; n=$((n+1)); fi
  done
  log "authorized_keys: $n chave(s) nova(s) autorizada(s)"
}

mesh_setup_identity() {
  local self="$1"
  mkdir -p "$HOME/.ssh" "$PUBKEYS_DIR"; chmod 700 "$HOME/.ssh"
  if [ ! -f "$MESH_KEY" ]; then
    log "Gerando chave SSH do mesh: $MESH_KEY"
    ssh-keygen -q -t ed25519 -N "" -C "mesh-$self" -f "$MESH_KEY"
  fi
  cp "$MESH_KEY.pub" "$PUBKEYS_DIR/$self.pub"
  write_ssh_config "$self"
  authorize_pubkeys
}

mesh_install_claude() {
  export PATH="$HOME/.local/bin:$PATH"
  if command -v claude >/dev/null 2>&1; then
    log "Claude Code já instalado: $(claude --version 2>/dev/null | head -n1)"
    return 0
  fi
  log "Instalando Claude Code (instalador oficial)"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
  command -v claude >/dev/null 2>&1 || warn "claude não está no PATH; abra um novo shell."
}

# Sobe `claude remote-control` em tmux, uma janela por projeto de $MESH_PROJECTS.
mesh_start_claude() {
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
  local session="${MESH_TMUX_SESSION:-claude-rc}" first=1 dir win
  command -v tmux >/dev/null 2>&1 || die "tmux não encontrado."
  command -v claude >/dev/null 2>&1 || die "claude não encontrado; rode o bootstrap primeiro."
  if tmux has-session -t "$session" 2>/dev/null; then
    log "Sessão tmux '$session' já existe (tmux attach -t $session)"; return 0
  fi
  for dir in ${MESH_PROJECTS:-$HOME/projects}; do
    mkdir -p "$dir"
    win="$(basename "$dir")"
    # Se o claude sair (ex.: sem login), mantém o shell aberto para diagnóstico.
    local cmd='claude remote-control; echo; echo "[mesh] claude saiu. Se pediu login, rode: claude /login"; exec "${SHELL:-bash}"'
    if [ "$first" = 1 ]; then
      tmux new-session -d -s "$session" -n "$win" -c "$dir" "$cmd"; first=0
    else
      tmux new-window -t "$session" -n "$win" -c "$dir" "$cmd"
    fi
    log "remote-control iniciado em $dir (janela tmux '$win')"
  done
}
