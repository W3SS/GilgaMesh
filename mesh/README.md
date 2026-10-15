# Mesh Iron Rail — inicialização dos nodes

Kit para ligar todas as máquinas da tailnet entre si (SSH por chave via Tailscale) e deixar
o `claude remote-control` rodando em cada projeto, para coordenar tudo pelo app Claude no celular.

Este kit **complementa** a arquitetura v2.x do Iron Rail (Kong na VPS, A2A nativo do Hermes,
`mesh.yaml` no Gitea); não a substitui. Diagnóstico, histórico e procedimentos: [RUNBOOK.md](RUNBOOK.md).

- `doctor.sh`: diagnóstico somente leitura (rode no Mac Mini).
- `claude-mesh-mcp.sh`: liga o Claude Code do nó aos MCPs da malha pelo Kong.
- `ai-memory-check.sh`: verifica a integração com o ai-memory neste nó (somente leitura). Análise e requisitos: [AI-MEMORY.md](AI-MEMORY.md).

## Nodes (`nodes.conf`)

| Alias | Máquina | IP Tailscale | SO | Script |
| :-- | :-- | :-- | :-- | :-- |
| phone | poco-x7-pro | 100.114.188.55 | Android | — (só cliente, ver abaixo) |
| wsl | creative-wsl | 100.104.74.53 | Linux (WSL) | `bootstrap-linux.sh` |
| desktop | desktop-p765rni | 100.85.202.56 | Windows | `bootstrap-windows.ps1` |
| florence | florence | 100.120.199.60 | **não identificado** | nenhum até identificar |
| gateway | iron-gateway | 100.89.141.115 | **fantasma** (remover do tailnet) | nenhum |
| macmini | mac-mini-de-wendel | 100.115.122.50 | macOS | `bootstrap-macos.sh` |
| vps1 | srv1819753 | 100.118.63.44 | Linux (VPS) | `bootstrap-linux.sh` |
| macbook | wendels-macbook-air | 100.89.49.96 | macOS | `bootstrap-macos.sh` |

`florence` e `iron-gateway` ficam fora da config SSH (`os` = `unknown`/`retired`) até você
identificar o primeiro e remover o segundo. Preencha `ssh_user` onde o login for diferente.
As chaves autorizadas levam `from="100.64.0.0/10"`, como pedem os testes SEC-04/SEC-10.

## Passo a passo

Em **cada máquina**: `git clone` do repositório, `git checkout ccr-83bac4ec-zl1bi8`, `cd mesh`.

1. **Rodar o bootstrap** (uma vez por máquina)
   - macOS: `./bootstrap-macos.sh --service --start` (Mac mini: acrescente `--keep-awake`)
   - Linux/WSL/VPS: `./bootstrap-linux.sh --service --start`
     (VPS nova: `TS_AUTHKEY=tskey-... ./bootstrap-linux.sh ...` evita o login interativo no Tailscale)
   - Windows (PowerShell como Administrador):
     `.\bootstrap-windows.ps1 -Projects 'C:\caminho\projeto' -StartService -Start -TailnetOnly`
   - Defina os projetos em `mesh/local.env` (copie de `local.env.example`) em macOS/Linux.
2. **Fazer login no Claude Code** uma vez (`claude` → `/login`). Nas VPS, abra o link no celular.
3. **Trocar chaves públicas**: o bootstrap grava `mesh/pubkeys/<node>.pub`. Faça commit e push
   desses arquivos (chaves públicas, seguras para versionar), depois `git pull` nas outras máquinas.
4. **Aplicar**: `./meshctl.sh sync` (Unix) ou rode `bootstrap-windows.ps1` de novo (Windows).
5. **Verificar**: `./meshctl.sh status` (Unix) ou `.\mesh-status.ps1` (Windows).

Depois disso qualquer node faz `ssh macmini`, `ssh vps1`, `ssh desktop`… e
`./meshctl.sh run all 'uptime'` executa em todos.

## O que cada script faz

- Garante Tailscale conectado e SSH server ativo, liberado só na interface/faixa da tailnet
  (no Linux com `ufw` ativo apenas **adiciona** a regra; nada é removido, para não te trancar fora).
- Gera `~/.ssh/id_ed25519_mesh`, escreve um bloco gerenciado em `~/.ssh/config` com todos os
  outros nodes e autoriza as chaves de `pubkeys/`. É idempotente: pode rodar de novo à vontade.
- Instala o Claude Code se faltar (VPS) e sobe `claude remote-control` em `tmux`
  (macOS/Linux) ou em janelas/tarefas agendadas (Windows), uma por projeto.
  Com `--service` / `-StartService` volta sozinho após reboot/login.

## Celular (poco-x7-pro)

Não precisa de script: o app Claude mostra as sessões `remote-control` de cada máquina e o
Tailscale já o coloca na tailnet. Opcional: no Termux, `pkg install openssh git`, copie o
`mesh/` e rode `./meshctl.sh sync` para ter os mesmos atalhos SSH (gere a chave com
`ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_mesh` e grave a `.pub` em `pubkeys/phone.pub`).

## Observações

- Tailscale na App Store do macOS não oferece o SSH server do Tailscale; por isso usamos o
  OpenSSH nativo ("Login Remoto") com chaves.
- WSL precisa de `systemd=true` em `/etc/wsl.conf` para o sshd/tailscaled iniciarem sozinhos.
- Se o repositório for público, lembre que `nodes.conf` expõe os IPs `100.x` (só roteáveis dentro
  da tailnet) e nomes de máquina; mantenha-o privado se isso importar.
- Estes scripts não foram executados nas suas máquinas (a sessão na nuvem não alcança a tailnet);
  a lógica de config SSH/chaves foi testada localmente, e os de macOS/Windows/systemd precisam
  de um primeiro teste real em cada máquina.
