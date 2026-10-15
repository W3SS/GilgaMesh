# ai-memory no Iron Rail: análise e requisitos

15/10/2026. Objetivo: todos os agentes (Claude Code e Hermes, em todos os nós) retomam o trabalho
de onde outra sessão parou e conseguem deixar recados uns para os outros, como se fossem uma só máquina.

## 0. O que foi verificado e o que não foi

| Verificado (código e documentação) | Não verificado (sem acesso à tailnet) |
| :-- | :-- |
| `W3SS/ai-memory` commit `fc4da03` de 04/10, versão 2.5.2 (fork de `akitaonrails/ai-memory`) | O servidor real em `memory.mesh.w3ss.sh` (versão, config, usuários) |
| Plugin `MrLuciano/ai-memory-hermes-plugin` commit `4f2028a` de 30/09 | Se o plugin do Hermes está instalado e em que perfis |
| O que o Status de 04/10 diz: ai-memory 2.5.2 na VPS, só tailnet, token obrigatório, backup diário de 14 dias, perfis de código ligados por MCP e hooks em modo allowlist, NANAO fora | Quais perfis são "de código" e o que a allowlist contém |
| Testes do Caderno: MEM-01 (token) e BKP-07 (backup) passam | Qualquer teste de continuidade entre nós: **não existe** |

`./ai-memory-check.sh` fecha essa lacuna em cada nó (somente leitura).

## 1. O que o ai-memory entrega

Ciclo: **capturar → consolidar → recuperar → passar o bastão.**

1. Hooks de cada agente registram prompts, chamadas de ferramenta e limites de sessão, já sanitizados.
2. No fim da sessão viram páginas markdown num wiki em git (sem LLM por padrão).
3. A sessão seguinte, de qualquer agente e de qualquer máquina, recebe um resumo do projeto e pode buscar tudo.
4. O **handoff** é o bastão: "onde parei, o que falhou, o que está aberto". É consumido uma vez só.

Canais entre agentes:

| Canal | Para quê | Limites |
| :-- | :-- | :-- |
| Páginas do projeto | Conhecimento compartilhado, todos que acessam o projeto leem e escrevem | O escopo é `(workspace, projeto)`. Não existe permissão por página |
| Handoff | Continuar a mesma tarefa em outra sessão ou outro agente | Dono único (usuário), entregue uma vez, por pasta (`cwd`). O campo `to_agent` existe mas **não é usado** na entrega |
| Mensagens (`memory_message_*`) | Um agente pede algo a outro projeto sem ler o código dele | Endereçadas a **projeto**, não a agente. Fila de 256. O destino já precisa existir. O texto é tratado como não confiável. **Não acorda ninguém** |

Conclusão: o ai-memory é o canal **assíncrono e durável**. O A2A do Hermes (porta 9900) continua sendo
o canal **síncrono**. Um não substitui o outro.

## 2. Requisitos que precisam ser refinados no Iron Rail

Do mais importante para o menos.

### R1. A mesma identidade de projeto em todos os nós
Sem configuração, o projeto é o **nome da pasta**. `/Users/w3ss/projetos/gilgamesh`,
`/home/r2d2/gilgamesh` e `C:\dev\gilgamesh` dão resultados diferentes ou colidem com outro
repositório de mesmo nome. Os agentes não enxergariam a memória uns dos outros.

Correção: versionar em cada repositório um `.ai-memory.toml` com os dois campos (clientes estáticos exigem os dois):

```toml
workspace = "iron-rail"        # contexto: iron-rail, gamedev, blog, ...
project   = "gilgamesh"        # nome estável, igual em todos os nós
identity  = "w3ss/gilgamesh"   # chave de roteamento, independe da pasta

[briefing]
inject_on_session_start = "true"   # a sessão nova já começa com o resumo do projeto
max_chars = 4000
```

O `mesh.yaml` deve passar a ser o registro de quais `workspace/project` existem.
`ai-memory-check.sh` aponta quem está sem marcador.

### R2. Um dono, uma chave por nó
Handoffs são **do usuário que os criou**. Se cada nó entrar com um usuário diferente, a sessão do
MacBook nunca consegue assumir o bastão deixado no Mac Mini.

- Um usuário humano (`wendel`) e **uma chave `aim_` por nó** (`macmini`, `macbook`, `wsl`, `vps`),
  cada uma revogável sozinha:
  `ai-memory user add-human --username wendel ...` e `ai-memory api-key add --username wendel --label macbook`.
- Não compartilhe o token root entre os 39 perfis: ele também faz tudo em `/admin`.
- Guarde a chave em arquivo `0600` (o `install-hooks` já grava em `<data_dir>/auth-token`) ou no Keychain.
  Nunca no `config.yaml` (teste HER-08).
- O pepper do servidor (`[auth].token_pepper`) não pode mudar depois de emitir chaves, e entra no backup de configuração.

### R3. Armadilha: o plugin do Hermes quebra com chave de usuário
O plugin chama `/admin/search`, `/admin/write-page` e `/admin/status`. Quando o servidor tem usuários,
**todo `/admin/*` é só do root**. Com chave `aim_` essas chamadas dão 403: o Hermes perde busca e escrita,
mas `/hook` e `/handoff` continuam funcionando, então a falha parece parcial.

Opções:
- **Recomendada:** ajustar o plugin (você tem o fork em W3SS) para buscar por `GET /api/v1/search` e
  escrever pelo MCP (`memory_write_page`). Ambos aceitam chave de usuário.
- Provisória: usar o token root só nos gateways Hermes. Funciona, mas dá a todos os perfis poder de apagar.
- Não criar usuários no servidor até resolver isto, se hoje tudo roda com o token único.

`./ai-memory-check.sh` mostra o 403 quando acontece.

### R4. Hermes precisa de duas ligações, não de uma
- O **plugin** cuida do ciclo da sessão (recuperar, capturar turnos, fechar sessão, entregar o handoff).
- O **MCP** é o que dá ao agente as ferramentas de handoff e de mensagens. O plugin só expõe
  buscar, escrever e status. O Hermes também **ignora a saída dos hooks de início de sessão**,
  então o aviso "há mensagens na caixa de entrada" não chega sozinho: o perfil precisa chamar
  `memory_message_list` e `memory_handoff_list`.
- Rotinas agendadas e subagentes são tratados como "não principais": **não escrevem e não consomem o bastão**.
  Isso é bom para segurança, mas significa que as ~30 rotinas do Iron Rail não geram memória no
  ai-memory. Elas continuam usando o caminho cron-to-vault. A cadeia do morning brief
  (ichigo → omaeda → oracle) fica fora do ai-memory.
- A confirmar: se uma chamada A2A recebida entra como sessão principal ou não principal.

### R5. O bastão pode ser levado pela sessão errada
Quem abrir sessão primeiro na pasta consome o handoff, inclusive uma sessão interativa sem relação.
A correção ("oferecer, não consumir", issue #959) está só em design. Num mesh com bots, Telegram e
vários harnesses na mesma pasta, isso acontece.

Mitigações: um projeto por papel quando faz sentido (um agente não abre sessão no projeto do outro);
usar `memory_handoff_begin` manual para o que importa e conferir com `memory_handoff_list` antes de aceitar;
pedidos entre agentes por **mensagem** (não por bastão); evitar `ai-memory run` em scripts.

### R6. Fronteira entre o vault e o ai-memory
Hoje a memória está em quatro lugares: vault (Obsidian, canônico), Qdrant do AKASHIC, `state.db` de
cada perfil Hermes e o ai-memory. Sem regra, cada agente acha uma coisa diferente.

| Camada | O que guarda | Quem escreve |
| :-- | :-- | :-- |
| Vault | O que é **verdade**: decisões, notas, referência | Você; agentes só em `00-INBOX/agents/<agente>/` via cron-to-vault |
| ai-memory | O que **aconteceu**: sessões, falhas, onde parou, decisões em andamento | Hooks e plugin, automático |
| `state.db` do perfil | Conversa bruta do perfil | O próprio Hermes, local |
| Qdrant/AKASHIC | Índice semântico do vault | AKASHIC |

Promoção: páginas `_rules/` e decisões do ai-memory viram **propostas** em `00-INBOX/agents/<agente>/`
(AIZEN, no ciclo semanal) e você aprova. É a mesma regra "agente não edita nota humana" que já existe.

### R7. Privacidade do que é capturado
O ai-memory guarda tudo o que o agente vê, incluindo colagens de senha que o sanitizador não pegou.
Ele fica no único nó com IP público.

- Manter fora: NANAO e manuscritos (já fora), `~/.iron-rail/secrets`, o vault. Usar `[capture] ignore_paths` no marcador.
- Projetos sensíveis em modo `restricted` (`ai-memory project access --mode restricted`) e `new_projects_restricted = true`.
- Consolidação e embeddings **só com modelos locais** pelo Kong (`iron-fast`, `iron-embed`).
  Nunca `/cloud/v1`, ou o conteúdo das sessões sai de casa. A confirmar: o Kong aceita o header
  `Authorization: Bearer` que o ai-memory envia, ou só `x-iron-key`.
- Não enviar o wiki a um remoto de git sem criptografia (documentação de backup do projeto).
- Backup restic append-only já existe (BKP-07); falta **testar a restauração**.

### R8. Cada harness precisa estar ligado
| Harness | Estado no ai-memory | O que falta |
| :-- | :-- | :-- |
| Claude Code (Macs, WSL, VPS) | Suportado: MCP + hooks; `install-mcp --session-aware` para sessões paralelas | Instalar em cada nó e ligar o briefing |
| Hermes | Suportado via plugin + hooks de ferramenta | R3 e R4 |
| Windows nativo | **Experimental** | Usar o WSL (já é o runtime do PC) |
| Sessão do Claude na nuvem (esta) | Só MCP, sem hooks | Ver seção 3 |

`ai-memory run claude` (e `run codex`...) é o jeito preferido de abrir uma sessão: liga hooks e MCP
sozinho e mantém a mesma sessão lógica entre harnesses.

### R9. Rede e acesso
O nome `memory.mesh.w3ss.sh` já resolve para a tailnet e o Caddy derruba quem vem de fora. Ao aplicar a
política v2.2 (NET-04), dar às tags de todos os nós acesso à porta 443 da VPS para o ai-memory. Sem isso,
a memória some dos nós que ficarem sem a regra.

### R10. Testes que faltam no Caderno
Hoje só existem MEM-01 e BKP-07. Propostas para o `caderno.yaml`:

| ID | Teste | Gravidade |
| :-- | :-- | :-- |
| MEM-02 | Handoff criado no nó A é visível e aceito no nó B (mesmo usuário) | Alta |
| MEM-03 | Todo repositório do `mesh.yaml` tem `.ai-memory.toml` versionado com workspace, project e briefing | Alta |
| MEM-04 | Cada perfil Hermes de código tem plugin e MCP, e `/admin` ou `/api/v1` responde com a credencial dele | Alta |
| MEM-05 | Nenhum projeto sensível está `open`; nenhum caminho de `secrets` ou do vault é capturado | Crítica |
| MEM-06 | Restauração do backup do ai-memory num diretório temporário e `reindex` funcionam | Média |
| MEM-07 | Nenhum consolidador ou embedder do ai-memory aponta para `/cloud/v1` | Crítica |

## 3. Esta sessão (Claude Code na nuvem)

Medido agora: `memory.mesh.w3ss.sh` não responde daqui (HTTP 000) e `controlplane.tailscale.com`,
`login.tailscale.com` e `pkgs.tailscale.com` também são bloqueados pela política de rede do ambiente.
Esta sessão não alcança a tailnet nem consegue entrar nela.

Evidência do problema: nesta conversa precisei reler as sessões de agosto transcrevendo eventos de
arquivos para descobrir o que já existia. Um ai-memory acessível teria entregue isso em segundos.

| Opção | Custo | Risco | Recomendação |
| :-- | :-- | :-- | :-- |
| **A.** Usar sessões `remote-control` no Mac Mini e no MacBook (com hooks e MCP) como "o Claude do celular" para trabalho que precisa de memória | Nenhum além do kit `mesh/` | Baixo | **Recomendada** |
| **B.** Pôr o contêiner na tailnet: liberar `controlplane.tailscale.com`, `login.tailscale.com`, `pkgs.tailscale.com` e a rede DERP no ambiente, com chave efêmera de tag própria (`tag:cloud`) e ACL só para 443 da VPS | Média | Média: chave guardada no ambiente e conteúdo capturado vindo de rede de terceiros | Só depois da política v2.2 e de R7 |
| **C.** Ponte por repositório: o que importa fica em `mesh/` (RUNBOOK, AI-MEMORY, notas), e toda sessão nova começa lendo isso | Nenhum | Nenhum | Já funciona, é manual |
| **D.** Abrir o ai-memory para a internet | — | Alto: o conteúdo é sensível e o servidor está no nó público | **Não** |

Em qualquer caso, esta sessão só tem MCP: ela precisaria chamar `memory_handoff_begin` ao terminar,
porque não há hook de fim de sessão.

## 4. O que da arquitetura atual aproveitar

| Já existe | Uso |
| :-- | :-- |
| VPS 24/7 com Caddy, TLS curinga e DNS `*.mesh.w3ss.sh` | Hospedar o servidor (já feito) |
| Tailscale e a política v2.2 por tags | Controlar quem fala com o ai-memory |
| Kong + `iron-embed` (bge-m3) + `iron-fast` | Embeddings e consolidação local, sem custo e sem sair de casa |
| restic append-only e BKP-07 | Backup do wiki e do índice; falta o teste de restauração |
| Caderno de Auditoria e GRIMJOW (segunda 04:30) | Rodar MEM-02 a MEM-07 toda semana |
| AIZEN (ciclo semanal) e `memory_auto_improve` / lint de `rule_suggestion` | Promover regras do ai-memory para propostas no vault |
| cron-to-vault e `00-INBOX/agents/<agente>/` | Caminho de promoção com revisão humana |
| Telegram HITL | Aprovar promoções e bastões importantes |
| A2A do Hermes (9900) | Canal síncrono; o ai-memory cobre o assíncrono |
| `mesh.yaml` | Registro de `workspace/project` por repositório |
| Kit `mesh/` (`doctor.sh`, `ai-memory-check.sh`, `meshctl.sh`) | Verificação e rollout |

## 5. Plano de execução

1. **Hoje (você, Mac Mini):** `./ai-memory-check.sh` com o token do nó. Cola a saída para eu ajustar.
2. **Decidir R3:** corrigir o plugin do Hermes no fork antes de criar usuários.
3. **Marcadores:** commitar `.ai-memory.toml` nos repositórios ativos (`gilgamesh`, `iron-rail-gateway` e os de jogos).
4. **Usuário e chaves:** `wendel` + uma chave por nó; revogar o que for token compartilhado.
5. **Ligar cada nó:** Claude Code (`ai-memory run claude` ou `install-mcp` + `install-hooks`), Hermes (plugin + MCP) nos perfis de código.
6. **Prova:** abrir uma sessão no MacBook, deixar um handoff, aceitar no Mac Mini (teste MEM-02). Repetir para WSL e VPS.
7. **Auditoria:** acrescentar MEM-02 a MEM-07 ao caderno.
8. **Promoção para o vault** com AIZEN, depois de duas semanas de uso.
9. **Esta sessão:** opção A agora, avaliar B depois.

## 6. Teste manual de ponta a ponta

No nó A (qualquer harness com o MCP do ai-memory, dentro de um repositório com marcador):
> "Chame `memory_handoff_begin` com o resumo do que fizemos e do que falta."

No nó B (mesmo repositório, mesma chave de usuário, sessão nova):
> "Liste meus handoffs pendentes e aceite o mais recente."

Esperado: o texto do nó A aparece no nó B, e o mesmo pedido no nó A depois não encontra mais nada
(consumido uma vez). Se o nó B não vê o bastão, as causas prováveis, nesta ordem, são: projeto
diferente (R1), usuário diferente (R2) ou pasta fora do caminho do bastão.
