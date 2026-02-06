# Plano de Ação Iterativo: Migração para Arquitetura Hexagonal

> **Estratégia**: "Strangler Fig Pattern" (Estrangulamento)
> **Objetivo**: Migrar o legado (`PrometheusOrchestrator`) para uma arquitetura limpa sem interromper o desenvolvimento de features.
> **Duração Estimada**: 8-10 semanas (5 Iterações)
> **Status Atual**: ✅ **TODAS AS ITERAÇÕES COMPLETAS**

## 🏗 Estratégia Geral & Regras de Ouro

1.  **Zero Regressão**: Nenhuma iteração pode quebrar a build.
2.  **Parallel Run**: O código novo convive com o velho até ser chaveado.
3.  **Deployability**: "Commit de sexta-feira" deve ser seguro. O sistema deve estar sempre em estado deployável.

---

## ✅ Iteração 1: Fundação & Configuração - **COMPLETO**

**Objetivo**: Remover "números mágicos" e configurações hardcoded.

*   ✅ Introduzir `pydantic-settings`.
*   ✅ Criar `config/settings.py`.
*   ✅ Substituir constantes globais por `settings.*`.
*   **Resultado**: Configurações extraídas. Sistema deployável.

---

## ✅ Iteração 2: Observabilidade & I/O Básico - **COMPLETO**

**Objetivo**: Isolar efeitos colaterais (Logging, Notificações).

*   ✅ `NotificationPort` + `DiscordAdapter` + `NullNotificationAdapter`.
*   ✅ Injeção de dependência no `__init__`.
*   **Resultado**: Padrão de Ports & Adapters estabelecido.

---

## ✅ Iteração 3: Abstração de Infraestrutura Pesada - **COMPLETO**

**Objetivo**: Isolar Docker SDK.

*   ✅ `ContainerRuntimePort` + `DockerAdapter`.
*   ✅ Injeção no `__init__`.
*   **Resultado**: Infraestrutura pronta para migração incremental.

---

## ✅ Iteração 4: Portas de IA & Isolamento do Domínio - **COMPLETO**

**Objetivo**: Desacoplar lógica de negócio da lógica de driver.

*   ✅ `AIProviderPort` + `OllamaAdapter` + `ComfyUIAdapter`.
*   ✅ Extrair modelos: `domain/models.py`.
*   **Resultado**: Geração de texto/imagem delegada aos adapters.

---

## ✅ Iteração 5: Pureza do Domínio & Injeção Final - **COMPLETO**

**Objetivo**: Limpeza final. Orchestrator como coordenador puro.

*   ✅ `ContextDomainService` com lógica de VRAM e swap.
*   ✅ `ServiceHealth` movido para domain.
*   ✅ 19 testes unitários (100% pass rate).
*   ✅ Container names atualizados para `gilgamesh-*`.
*   **Resultado**: Domain isolado e testável.

---

## 🚦 Status Final

| Critério | Status |
|----------|--------|
| Testes passando | ✅ 19/19 (0.50s) |
| Acoplamento reduzido | ✅ Ports isolam Docker, AI, Notifications |
| Domain puro | ✅ Sem I/O em `domain/` |
| Deployability | ✅ Sistema funcional |

## Arquitetura Final

```
orchestrator/
├── config/              # Settings (pydantic-settings)
├── domain/              # Pure business logic
│   ├── models.py        # Task, TaskType, Priority, ContextMode
│   ├── service_health.py
│   └── context_service.py  # VRAM logic, mode decisions
├── ports/               # Interfaces
│   ├── ai_provider.py
│   ├── container_runtime.py
│   └── notification.py
├── adapters/            # Implementations
│   ├── ollama_adapter.py
│   ├── comfyui_adapter.py
│   ├── docker_adapter.py
│   └── discord_adapter.py
├── tests/               # Unit tests
│   ├── test_domain_models.py
│   └── test_context_service.py
└── main.py              # Application service
```
