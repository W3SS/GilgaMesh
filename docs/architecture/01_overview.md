#  GILGAMESH V1.0 - Arquitetura e Visão Global

> **STATUS**: EM DESENVOLVIMENTO  
> **DATA**: 04/02/2026  
> **VERSÃO**: 1.0 (Refined Architecture)

---

## 1. VISÃO GERAL

O **Prometheus Mesh** é um ecossistema de inteligência artificial orquestrado, projetado para operar como um "Sistema Operacional Vivo" sobre o Windows. Ele não é apenas um chatbot, mas uma malha de serviços interconectados que monitoram, analisam, decidem e agem sobre o ambiente computacional e o fluxo de trabalho do usuário.

### Objetivos Principais

1. **Onipresença Invisível**: O sistema roda em background, sem interferir na UX, a menos que solicitado ou necessário (Sentinel).
2. **Eficiência Extrema**: Uso inteligente de recursos (CPU/GPU/RAM) para rodar LLMs locais (Ollama) e modelos de imagem (ComfyUI) em hardware consumer (ex: RTX 3060/4060).
3. **Memória Persistente (RAG)**: O sistema "lembra" de decisões passadas, contextos de conversas e aprende com o feedback do usuário.
4. **Segurança Ativa**: Monitoramento de processos maliciosos e anomalias de rede em tempo real.

---

## 2. AMEAÇAS E PROBLEMAS

A análise da arquitetura inicial revelou os seguintes pontos críticos:

1. **VRAM Thrashing**: Trocar entre LLM (Ollama) e Image Gen (ComfyUI) causava latência de 10s-30s.
2. **Context Loss**: O Orchestrator não tinha persistência de estado robusta entre reinícios.
3. **Security Blindspots**: O Sentinel original não tinha integração profunda com o Windows Event Log.
4. **Race Conditions**: Múltiplos serviços competindo pela GPU causavam OOM (Out of Memory).
5. **Sync Blocking**: A API era síncrona, bloqueando o processamento enquanto aguardava inferência.

---

## 3. SOLUÇÃO PROPOSTA

### 3.1. Arquitetura de Componentes

O sistema é dividido em 4 pilares principais:

1. **ORCHESTRATOR (O Cérebro)**:
    * Gerencia o ciclo de vida dos containers Docker.
    * Controla a alocação de VRAM.
    * Possui fila de tarefas assíncrona (Task Queue).
    * Implementa "Predictive Swap" (prevê qual modelo será necessário).

2. **SENTINEL (O Guarda-Costas)**:
    * Agente nativo Windows (não-Docker para acesso direto ao Kernel/API).
    * Monitora Processos, Rede e Hardware.
    * Executa ações de segurança (Kill Process, Block IP).

3. **MEMORY (O Hipocampo)**:
    * Banco de dados vetorial (Qdrant) para RAG.
    * Armazena: Logs, Conversas, Decisões, Conhecimento Técnico.
    * Interface de busca semântica para o Orchestrator.

4. **NETWORK (O Sistema Nervoso)**:
    * Comunicação via WebSocket bidirecional.
    * Notificações multi-canal (Discord, Telegram, Desktop).
