# Plano de Ação Iterativo: Migração para Arquitetura Hexagonal

> **Estratégia**: "Strangler Fig Pattern" (Estrangulamento)
> **Objetivo**: Migrar o legado (`PrometheusOrchestrator`) para uma arquitetura limpa sem interromper o desenvolvimento de features.
> **Duração Estimada**: 8-10 semanas (5 Iterações)
> **Status Atual**: ✅ Iterações 1-3 Completas | 🚧 Iterações 4-5 Pendentes

## 🏗 Estratégia Geral & Regras de Ouro

1.  **Zero Regressão**: Nenhuma iteração pode quebrar a build.
2.  **Parallel Run**: O código novo convive com o velho até ser chaveado.
3.  **Deployability**: "Commit de sexta-feira" deve ser seguro. O sistema deve estar sempre em estado deployável.

---

## ✅ Iteração 1: Fundação & Configuração (Semana 1-2) - **COMPLETO**

**Objetivo**: Remover "números mágicos" e configurações hardcoded, preparando o terreno para injeção de dependência.

*   **Componentes**: `orchestrator/main.py` (VRAM_LIMITS, URLs).
*   **Ação Tática**:
    1.  ✅ Introduzir `pydantic-settings`.
    2.  ✅ Criar `config/settings.py` que lê `.env` ou defaults.
    3.  ✅ Substituir todas as constantes globais em `main.py` por chamadas a `settings`.
*   **Contratos/Portas**: N/A (Refatoração interna).
*   **Critérios de Aceitação**:
    *   [x] É possível mudar a URL do Ollama via `.env` sem tocar no código.
    *   [x] `main.py` não contém mais dicionários de configuração hardcoded.
    *   [x] Testes passam (regressão).
*   **Risco**: Baixo.
*   **Resultado**: Configurações extraídas com sucesso. Sistema deployável.

---

## ✅ Iteração 2: Observabilidade & I/O Básico (Semana 3-4) - **COMPLETO**

**Objetivo**: Isolar os efeitos colaterais mais simples (Logging e Notificações) para estabelecer o padrão de Ports & Adapters.

*   **Componentes**: `logging`, `notify()` em `PrometheusOrchestrator`.
*   **Ação Tática**:
    1.  ✅ Definir protocolo `NotificationPort` (Interface).
    2.  ✅ Implementar `DiscordAdapter` e `NullNotificationAdapter`.
    3.  ✅ Injetar o Adapter no `__init__` do Orchestrator.
    4.  ⚠️ Logging estruturado (JSON) - Planejado para próxima iteração.
*   **Contratos/Portas**:
    *   ✅ `ports/notification.py`: `send(title, message, priority)`
*   **Critérios de Aceitação**:
    *   [x] Orchestrator aceita `notification_service` no construtor.
    *   [ ] Logs saem em JSON estruturado (PENDENTE).
*   **Risco**: Baixo/Médio (alteração de assinatura de métodos).
*   **Resultado**: NotificationPort estabelecido. Padrão de adapters funcionando.

---

## ✅ Iteração 3: Abstração de Infraestrutura Pesada (Semana 5-6) - **COMPLETO**

**Objetivo**: Isolar a maior fonte de acoplamento: o Docker SDK.

*   **Componentes**: Chamadas a `self.docker_client` e `containers.get()`.
*   **Ação Tática**:
    1.  ✅ Definir protocolo `ContainerRuntimePort`.
    2.  ✅ Implementar `DockerAdapter` com operações async.
    3.  ✅ Injetar ContainerRuntime no `__init__`.
    4.  ⚠️ Refatorar todas as chamadas diretas ao Docker (uso parcial - compatibilidade mantida).
*   **Contratos/Portas**:
    *   ✅ `ports/container_runtime.py`: `start()`, `stop()`, `get_stats()`.
*   **Critérios de Aceitação**:
    *   [~] `import docker` ainda presente em `main.py` (referência de compatibilidade).
    *   [x] É possível injetar mock de `ContainerRuntimePort` para testes.
*   **Risco**: Alto (lógica core de gerenciamento).
*   **Mitigação**: DockerAdapter mantém comportamento original.
*   **Resultado**: ContainerRuntimePort criado. Infraestrutura pronta para migração incremental dos métodos de gerenciamento de containers.

---

## 🚧 Iteração 4: Portas de IA & Isolamento do Domínio (Semana 7-8) - **PENDENTE**

**Objetivo**: Decopular a lógica de "Negócio" (qual modelo carregar?) da lógica de "Driver" (como chamar a API?).

*   **Componentes**: `_execute_text_generation`, `_execute_image_generation`.
*   **Ação Tática**:
    1.  Definir protocolo `AIProviderPort` com métodos genéricos (`generate_text`, `generate_image`).
    2.  Implementar `OllamaAdapter` e `ComfyUIAdapter`.
    3.  Extrair modelos de Domínio: `Task`, `ContextRequest`.
*   **Contratos/Portas**:
    *   `ports/ai_provider.py`.
*   **Critérios de Aceitação**:
    *   [ ] Lógica de *construção* do payload JSON movida para os Adapters.
    *   [ ] Orchestrator apenas "pede" a geração, não sabe se é Ollama ou OpenAI.
*   **Risco**: Alto (impacta a funcionalidade principal).

---

## 🚧 Iteração 5: Pureza do Domínio & Injeção Final (Semana 9-10) - **PENDENTE**

**Objetivo**: Limpeza final. O Orchestrator vira um coordenador puro.

*   **Componentes**: Lógica residual em `main.py` (cálculos de VRAM, fila de prioridade).
*   **Ação Tática**:
    1.  Mover lógica de decisão (Swap) para `ContextDomainService` (Puro Python, sem I/O).
    2.  Configurar Container de Injeção de Dependência na inicialização da API (FastAPI `Depends`).
    3.  Renomear arquivo `orchestrator/main.py` para `orchestrator/service.py` (simbólico).
*   **Critérios de Aceitação**:
    *   [ ] Cobertura de testes unitários do Domain Service > 90%.
    *   [ ] Nenhuma dependência de `docker` ou `httpx` no pacote `domain`.

---

## 🚦 Checklist de Saúde & Decisão (Pós-Iteração)

Ao fim de cada iteração, aplicar:

1.  **Testes**: A suite de testes antiga passa 100%?
2.  **Acoplamento**: O número de imports de bibliotecas externas diminuiu no módulo alvo?
3.  **Bloqueio**: Alguma feature nova foi impedida por mais de 2 dias?
    *   *Sim* -> **Pausar e Estabilizar**. Não avançar para próxima iteração.
    *   *Não* -> Continuar.

### Status Atual (Iterações 1-3)
- ✅ **Testes**: Sistema permanece deployável após cada iteração
- ✅ **Acoplamento**: Reduzido via introdução de Ports & Adapters
- ✅ **Bloqueio**: Nenhuma feature bloqueada

## ⚔️ Estratégia de Desenvolvimento Paralelo

Como continuar shipando features durante a migração?

*   **Regra do Escoteiro**: Vai mexer numa função para adicionar feature? Se ela toca num componente da iteração atual, refatore-a *agora*.
*   **Adapters Novos**: Features novas devem ser implementadas já como Adapters novos (ex: adicionar suporte a "Claude API" implementando `AIProviderPort`), sem sujar o código legado.
*   **Feature Flags**: Se a refatoração for arriscada, use uma flag `USE_NEW_DOCKER_ADAPTER=true` para testar em dev antes de virar default.
