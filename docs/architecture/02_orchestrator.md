# PROMETHEUS MESH V2.0 - Orchestrator Service

O **Orchestrator** é o componente central responsável por gerenciar recursos, tarefas e o ciclo de vida dos serviços de IA.

## Responsabilidades

- **Gerenciamento de VRAM**: Monitora e aloca memória de vídeo para evitar OOM.
- **Task Queue**: Fila de prioridade para requisições (User > System > Background).
- **Service Lifecycle**: Inicia/Para containers (Ollama, ComfyUI, Whisper) sob demanda.
- **Predictive Swap**: Analisa o histórico recente para pré-carregar modelos (ex: se usuário está conversando sobre "imagem", já aquece o ComfyUI).

## Especificações Técnicas

### Stack

- **Linguagem**: Python 3.11+
- **Framework**: FastAPI (Async)
- **Container**: Docker
- **Comunicação**: HTTP/REST + WebSocket

### Lógica de Controle de VRAM

O Orchestrator mantém uma tabela de estado da VRAM:

- `TOTAL_VRAM`: 12GB (exemplo)
- `RESERVED_SYSTEM`: 2GB (Windows)
- `AVAILABLE`: 10GB

Quando uma tarefa chega:

1. Verifica requisitos do modelo (ex: Llama3 = 6GB).
2. Se `AVAILABLE < REQUIRED`:
   - Identifica serviço ocioso (ex: ComfyUI).
   - Envia sinal `STOP` ou `HIBERNATE` para o serviço.
   - Aguarda liberação de recursos.
3. Aloca recurso e inicia tarefa.

### Context Modes

O Orchestrator opera em modos de contexto para otimizar o swap:

1. **TEXT_HEAVY**: Prioriza LLM na VRAM. ComfyUI descarregado.
2. **CREATIVE**: Prioriza ComfyUI. LLM descarregado ou usando modelo menor (quantizado).
3. **AUDIO_PROCESSING**: Prioriza Whisper.

### Endpoints Principais

- `POST /tasks`: Submete nova tarefa.
- `GET /tasks/{id}`: Status da tarefa.
- `GET /status`: Estado atual do sistema (VRAM, Queue, Modes).
- `POST /control/mode`: Força troca de modo de contexto.
