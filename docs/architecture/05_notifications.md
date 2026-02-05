# PROMETHEUS MESH V2.0 - Notification & Network Service

O **Notification Service** atua como o sistema nervoso, gerenciando a comunicação bidirecional entre o Prometheus e o Usuário através de múltiplos canais.

## Responsabilidades

- **Notificações Multi-Canal**: Entrega alertas via Discord, Telegram, Email e WebSocket.
- **Two-Way Binding**: Permite que o usuário responda às notificações (ex: Aprovar/Rejeitar ação) diretamente do chat do Telegram/Discord.
- **Web Interface**: Fornece um painel de controle em tempo real via WebSocket.

## Especificações Técnicas

### Stack

- **Protocolos**: HTTP (REST), WebSocket.
- **Integrações**:
  - **Discord**: `discord.py` (Bot API).
  - **Telegram**: `python-telegram-bot`.
  - **Email**: SMTP (Gmail/Outlook).
- **Frontend**: HTML/JS puro (Client WebSocket).

### Arquitetura de Canais

#### 1. Discord Bot

- **Comandos**: `!status`, `!generate`, `!kill <pid>`.
- **Alertas**: Envia Embeds coloridos baseados na severidade (Info=Azul, Critical=Vermelho).
- **Interatividade**: Botões (se suportado) ou reply commands para aprovação.

#### 2. Telegram Bot

- **Comandos**: `/status`, `/generate`, `/scan`.
- **Alertas**: Mensagens formatadas com Markdown.
- **Praticidade**: Ideal para controle mobile rápido.

#### 3. WebSocket (Desktop/Web Dashboard)

- **Real-time**: Atualizações de métricas (VRAM, CPU) 10x por segundo.
- **Task Progress**: Barras de progresso para geração de imagens/texto.
- **System Control**: Controle total do Orchestrator via painel web.

### Fluxo de Notificação

1. **Trigger**: Sentinel detecta anomalia.
2. **Request**: Sentinel POST `/notify` para Notification Service.
3. **Routing**: Notification Service verifica configurações de canais (ex: Critical -> Todos os canais, Info -> Apenas WebSocket).
4. **Delivery**: Executa envio paralelo para canais selecionados.
5. **Response**: Se usuário responder (ex: `/approve`), o Bot chama o Orchestrator para executar a ação.

### Endpoints Principais

- `POST /notify`: Envia notificação.
- `WS /ws/{client_id}`: Conexão WebSocket persistente.
- `GET /clients`: Lista clientes conectados.
