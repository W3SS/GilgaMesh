# PROMETHEUS MESH V2.0 - ROADMAP DE IMPLEMENTAÇÃO

Este documento define a ordem sequencial recomendada para a implementação e evolução do sistema.

## FASE 1: FUNDAÇÃO (Concluída ✅)

O objetivo desta fase é estabelecer a infraestrutura básica e os serviços core.

- [x] **Estrutura de Diretórios**: Criação da árvore de pastas.
- [x] **Orchestrator V1 (Scaffold)**: Implementação básica do gerenciamento de VRAM e filas.
- [x] **Sentinel V1 (Scaffold)**: Monitoramento básico de hardware e processos.
- [x] **Memory V1 (Scaffold)**: Conexão com Qdrant e lógica de embeddings.
- [x] **Docker Compose**: Orquestração de todos os containers.
- [x] **Scripts de Setup**: Automação de ambiente e download de modelos.

---

## FASE 2: INTELIGÊNCIA E MEMÓRIA (Atual 🚧)

Foco em tornar o sistema "inteligente" e capaz de aprender.

### 2.1. Refinamento da Memória (Prioridade Alta)

- [x] Implementar sistema de **Feedback Loop** no `rag_memory_service.py`.
- [x] Criar "seed data" (memórias iniciais) para a collection `knowledge`.
- [ ] Testar busca semântica com casos reais.

### 2.2. Integração AI Services

- [ ] Testar integração real Orchestrator -> Ollama (verificar latência).
- [ ] Testar integração real Orchestrator -> ComfyUI (verificar geração de imagens).
- [ ] Ajustar timeouts e limites de VRAM baseados em testes de carga.

---

## FASE 3: SEGURANÇA E MONITORAMENTO

Foco em proteger o sistema e dar visibilidade.

### 3.1. Sentinel Avançado (Windows Native)

- [x] Implementar detecção de anomalias de rede (conexões suspeitas).
- [x] Integrar com Windows Defender API para scans reais.
- [x] Criar whitelist/blacklist de processos editável via API.

### 3.2. Dashboard Unificados

- [ ] Refinar Dashboard do Grafana com métricas reais coletadas.
- [ ] Criar alertas no Prometheus (ex: VRAM > 95% por 5 min).

---

## FASE 4: INTERFACE E COMUNICAÇÃO

Foco na experiência do usuário e controle.

### 4.1. Notification Service

- [ ] Implementar `notifications/notification_service.py` (código já arquitetado).
- [ ] Configurar Bots (Discord/Telegram).
- [ ] Implementar WebSocket Server para comunicação Real-Time.

### 4.2. Web Dashboard (Frontend)

- [ ] Criar interface Web simples (HTML/JS) para visualizar logs e controlar tarefas.
- [ ] Integrar com WebSocket do Notification Service.

---

## FASE 5: EVOLUÇÃO E APRENDIZADO CONTÍNUO

Foco na autonomia do sistema.

- [ ] **Predictive Warming**: Melhorar algoritmo de previsão de uso de modelos.
- [ ] **Auto-Healing**: Permitir que o Orchestrator reinicie serviços travados automaticamente.
- [ ] **Voice Interface**: Integrar Whisper (STT) e TTS para controle por voz.
