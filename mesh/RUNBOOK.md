# Runbook da malha Iron Rail

Estado em 15/10/2026. Este documento junta o que está no app Tailscale hoje, o que os
relatórios de 03 a 05/10 registraram (Blueprint v2.1, Agentes v2.3, Status v2.4,
Caderno de Auditoria) e as sessões de agosto. A fonte da verdade da arquitetura continua
sendo `iron-rail-gateway/mesh.yaml` (Gitea da VPS). Este arquivo é o manual de operação.

> **Limite desta análise.** A sessão que escreveu este runbook roda na nuvem e não alcança
> a tailnet. O estado "hoje" vem do print do app Tailscale (12:51 de 15/10). O estado dos
> serviços vem da última auditoria registrada (04/10, 75 de 84 testes). Para validar ao vivo,
> rode `./doctor.sh` no Mac Mini (seção 6).

## 1. Nós

| Alias | Máquina | IP | Papel (v2.4) | Tailscale 15/10 | Auditoria 04/10 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| macmini | mac-mini-de-wendel | 100.115.122.50 | LLM (Ollama + MLX), vault canônico, agentes 24/7, Telegram central | online | OK, hub da auditoria |
| vps1 | srv1819753 | 100.118.63.44 | Kong, Gitea, Kuma, restic, ai-memory, Qdrant, vigia mesh-verify | online | OK |
| macbook | wendels-macbook-air | 100.89.49.96 | programação (KISUKE) e escrita local (NANAO), coordenação | online | firewall desligado (SEC-11) |
| wsl | creative-wsl | 100.104.74.53 | estúdio: ComfyUI, creative-mcp, GPU, Hermes do PC | online | OK |
| desktop | desktop-p765rni | 100.85.202.56 | Windows só administração (Hermes nativo desligado) | online | Defender sem varredura (SEC-08) |
| phone | poco-x7-pro | 100.114.188.55 | Telegram (briefing, alertas, aprovações) e app Claude | online | — |
| gateway | iron-gateway | 100.89.141.115 | **fantasma**: sidecar do Kong abandonado | offline | NET-03 pendente |
| florence | florence | 100.120.199.60 | **desconhecido**: não aparece em nenhum documento até 05/10 | online | — |

## 2. Componentes

| Componente | Onde | Como os outros nós usam | Último estado conhecido |
| :-- | :-- | :-- | :-- |
| Kong (gateway de serviços) | vps1, porta 8000 só tailnet | rotas `/llm/v1`, `/mlx/v1`, `/mcp/vault`, `/mcp/creative`, `/mcp/projects`, `/cloud/v1`; chave por nó no header `x-iron-key` | GW-01 a GW-08 OK em 04/10; `/cloud/v1` sem token configurado |
| LLM local | macmini (Ollama 127.0.0.1 + MLX), edge :11435 com token | sempre pelo Kong, por alias: `iron-reason`, `iron-fast`, `iron-story`, `iron-story-rapido`, `iron-embed` | INF-01 a INF-10 OK |
| Hermes Agent | macmini, vps1, wsl, macbook (39 perfis, 4 gateways) | cada nó roda o próprio gateway Hermes | HER-01 OK; **HER-03 falha** (rotinas fora do estado da spec) |
| A2A | Hermes nativo, porta 9900 em cada nó, token por par (ADR-03) | delegação agente → agente direto pelo IP da tailnet | HER-07 OK (cartões publicados) |
| Orca v1 (CA, A2A, hub) | legado | não usar | desligado (SEC-13 OK) |
| A2A por NATS (`iron_rail.a2a.*`, agosto) | legado v1 | não usar; substituído pelo ADR-03 | — |
| Morning brief | 06:30: ichigo (saúde) → omaeda (custo) → oracle (junta) → nota Daily + Telegram | leitura de e-mail por IMAP somente leitura (himalaya) | OPS-09 OK; **sem prova de execução na v2** (rotinas nascem pausadas e HER-03 falha) |
| Claude Code | todos os nós com tela + VPS | `claude remote-control` por projeto, MCP da malha pelo Kong (`claude-mesh-mcp.sh`) | sem canal entre nós até hoje |
| ai-memory | vps1, só tailnet, token obrigatório | perfis de código por MCP | MEM-01 OK |

## 3. Diagnóstico e ações

Ordem por risco. "Você" = precisa do operador; "doctor" = verificável com `./doctor.sh`.

**P0. Hoje**

1. **Identificar `florence`** (você). Nó online que nenhum documento conhece. No console do
   Tailscale (Machines → florence) veja SO, dono e data de entrada. Se não for seu, remova e
   gire a chave de autenticação. Se for seu, cadastre em `mesh.yaml` e em `nodes.conf`
   com a tag certa. Enquanto as tags da política v2.2 não valerem (NET-04), ele alcança
   qualquer porta dos outros nós.
2. **Aplicar a política v2.2 do Tailscale e as tags** (você, NET-04). Colar
   `scripts/01c_tailscale_policy_v22.hujson` em Access controls e etiquetar os nós.
   Sem isso, a ACL do Kong é a única barreira entre os nós.
3. **Remover `iron-gateway`** (você, NET-03). Machines → iron-gateway → Remove.
4. **Rodar o diagnóstico ao vivo** no Mac Mini: `./doctor.sh` e, se algo falhar,
   `./doctor.sh --full`.

**P1. Esta semana**

5. **Morning brief** (HER-03). No Mac Mini: `hermes -p oracle cron list`,
   `hermes -p ichigo cron list` (VPS) e `hermes -p omaeda cron list` (VPS). Ligue uma a uma
   (estado pausado é o padrão). Teste fora da agenda com `hermes -p <perfil> cron run <id>`.
   Pronto quando sair 7 dias seguidos (critério do Blueprint).
6. **Firewall do MacBook** (SEC-11) com exceção para o Python do Hermes, senão o A2A cai.
7. **Senha do SMB em texto puro** no plist do MacBook (SEC-15) e **troca das credenciais
   expostas** em 04/10 (MiniMax, SMB, tokens do edge).
8. **Varredura do Defender** no Windows (SEC-08): `Start-MpScan -ScanType FullScan`.

**P2. Para a malha parecer uma máquina só**

9. **Claude Code em cada nó com remote-control** (seção 5) para comandar tudo pelo celular.
10. **MCP da malha no Claude Code** de cada nó: `IRON_KEY=<chave do nó> ./claude-mesh-mcp.sh`.
11. **Discos USB direto no Mac Mini** (EXP-007): backup, vault e SMB ganham ~10×.

## 4. O que já foi feito

| Data | O quê | Evidência |
| :-- | :-- | :-- |
| 25/04 | Chave `id_ed25519_ironrail` gerada no Mac Mini | `iron-rail-prime-ssh-setup.sh` (Drive) |
| 08/06 | Script de SSH para os nós acessarem o Hermes PRIME | `iron-rail-prime-ssh-setup.sh` |
| 05/06 | Morning brief da v1 gerado pelo akashic às 06:00 | `2026-06-05_0600-morning-brief.md` (Drive) |
| 14/06 | Inventário: 44 perfis Hermes, 31 crons globais | `iron-rail-swarm-master-inventory-v4.md` |
| 03–04/08 | RAG híbrido (BM25 + Qdrant + grafo), embed incremental, A2A por NATS validado; achados: portas do Windows e do MacBook fechadas, `~/.ssh/config` com IPs inexistentes, 4 LaunchAgents com erro 78 | sessão "Ironrail setup com Tailscale" |
| 03/10 | Blueprint v2.1: Kong na VPS, A2A nativo :9900, edge com token, vault só leitura para agentes | artifact Iron Rail Blueprint |
| 04/10 | v2.4: política de eventos destrutivos em 39 perfis, ai-memory na VPS, dev containers, MLX robusto, backup no Expansion, auditoria 75/84 | artifacts Status e Caderno de Auditoria |
| 15/10 | Kit `mesh/` (SSH entre nós, remote-control, doctor, MCP pelo Kong) | este repositório, branch `ccr-83bac4ec-zl1bi8` |

**Scripts citados como aplicados nos relatórios de outubro** (repositório `iron-rail-gateway`):
`07_setup_macmini_inference.sh`, `08_setup_vps_gateway.sh apply`, `10_dns_w3ss.sh`,
`12_place_profiles.py`, `12_move_profiles.sh`, `13_create_cron_jobs.py`,
`14_mesh_ui_password.sh`, `16_vault_readonly.py`, `policy/deploy-policy.sh`,
`audit/install-audit.sh`, `macbook/escrita/instalar.sh`, `devcontainers/build-images.sh`,
`jobs/email-setup.sh`. **Ainda não aplicado:** `01c_tailscale_policy_v22.hujson`.

**Scripts deste kit:** nenhum foi executado nas máquinas até 15/10 (nenhuma chave em
`mesh/pubkeys/`, nenhuma sessão remote-control ativa).

## 5. Configuração que mantém os nós conversando

Invariantes. Se um deles quebrar, a malha degrada.

- **Tailscale**: todos os nós na tailnet `tail8c343a.ts.net`; política v2.2 com tags
  (`tag:inference`, `tag:projects`, `tag:creative`); tailnet lock assinando nós novos.
- **Nomes**: `*.mesh.w3ss.sh` resolvem para IPs 100.x (NET-05). Nunca use `mac-mini.orca`.
- **Kong** (vps1): Admin API só em `127.0.0.1:8001`; um consumer por nó; plugins key-auth,
  acl, rate-limiting, request-size-limiting; nada publicado em `0.0.0.0` pelo Docker.
- **Edge do Mac Mini** (:11435) exige token; Ollama e MLX só em `127.0.0.1`.
- **A2A**: porta 9900 em cada nó, presa ao IP da tailnet, token por par.
- **SSH**: chaves com `from="100.64.0.0/10"`; VPS sem senha; ufw negando entrada.
- **Agendamento**: Mac Mini não dorme (`pmset -a sleep 0 autorestart 1 womp 1`); estúdio
  acorda por Wake-on-LAN; um bot do Telegram por gateway (HER-11).
- **Modelos por alias** (`iron-*`), nunca pelo nome base.

## 6. Procedimentos

**Checagem diária (2 min, Mac Mini)**

```bash
cd ~/GilgaMesh/mesh && git pull && ./doctor.sh
```

**Entrar um nó novo**

1. Tailscale: entrar, assinar com `tailscale lock sign nodekey:…` no MacBook, pôr a tag.
2. Cadastrar em `mesh.yaml` (Gitea) e em `mesh/nodes.conf`.
3. Rodar o bootstrap do sistema (`bootstrap-macos.sh`, `bootstrap-linux.sh`,
   `bootstrap-windows.ps1`), commitar `pubkeys/<nó>.pub`, `./meshctl.sh sync` nos outros.
4. Se tiver Hermes: consumer novo no Kong (`08_setup_vps_gateway.sh apply`) e token A2A por par.
5. `./doctor.sh --full`.

**Kong fora do ar** (GW-01): `ssh vps1 'docker logs --tail 50 iron-kong'`; agentes caem
para o edge do Mac Mini pela LAN (modo degradado, ADR-05).

**A2A falhando**: `nc -z <ip> 9900`; firewall do MacBook (SEC-11); token do par; cartão A2A
(HER-07).

**Morning brief não chegou**: `hermes -p oracle cron list`; saúde do ichigo e custo do
omaeda na VPS (se a VPS cair, o brief sai com "saúde: sem dados"); `OPS-09` para o IMAP.

**Rodar a auditoria fora da agenda** (Mac Mini):
`hermes -p grimjow cron run 2bf12eab836a`.

## 7. Usar a malha como uma máquina só

| Quero | Uso | Funciona de |
| :-- | :-- | :-- |
| Um LLM local | `http://gateway.mesh.w3ss.sh:8000/llm/v1` ou `/mlx/v1` com `x-iron-key`, modelo por alias | qualquer nó |
| Gerar imagem, vídeo, áudio | MCP `/mcp/creative` (estúdio) | MacBook e Mac Mini |
| Ler o segundo cérebro | MCP `/mcp/vault` (só leitura) | MacBook, VPS, estúdio |
| Delegar a outro agente | A2A do Hermes, porta 9900 | qualquer nó com Hermes |
| Abrir shell em outro nó | `ssh macmini`, `ssh vps1`, `ssh wsl` (este kit) | qualquer nó |
| Comandar pelo celular | app Claude → sessões `remote-control`; Telegram para aprovar | celular |
| Rodar algo em todos | `./meshctl.sh run all '<comando>'` | Mac Mini ou MacBook |
