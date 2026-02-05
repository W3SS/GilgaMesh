# PROMETHEUS MESH V2.0 - Sentinel Service

O **Sentinel** é o agente de segurança e monitoramento que roda nativamente no Windows.

## Responsabilidades

- **Monitoramento de Hardware**: CPU, RAM, Disk, GPU (via `nvidia-smi` ou `pynvml`).
- **Segurança de Processos**: Detecta processos suspeitos ou com alto consumo de recursos não autorizado.
- **Análise de Rede**: Monitora conexões abertas e portas escutando.
- **Integração OS**: Acesso a Windows Event Logs e integração com Windows Defender.

## Especificações Técnicas

### Stack

- **Linguagem**: Python 3.11+ (Native Windows Execution)
- **Libs**: `psutil`, `pywin32`, `wmi`, `GPUtil`.
- **Comunicação**: Envia métricas para Prometheus (Exporters) e alertas para Orchestrator.

### Lógica de Decisão (Threat Detection)

O Sentinel avalia processos com base em regras e heurísticas:

- **Blacklist**: Processos conhecidamente maliciosos (kill imediato).
- **Greedy**: Processos consumindo >90% CPU por >5min (alerta usuário).
- **Suspicious**: Nomes aleatórios ou executáveis fora de diretórios padrão (scan + alerta).

### Integração com Memory Service

O Sentinel consulta a `Memory` para verificar decisões passadas:

- "O usuário já autorizou este processo `mining_tool.exe` no passado?"
- Se sim `(allow)`, ignora.
- Se não `(block)`, bloqueia e notifica.

### Endpoints Principais

- `GET /system/stats`: Métricas em tempo real.
- `GET /processes`: Lista processos ativos.
- `POST /action/kill-process`: Encerra processo (requer privilégios).
- `POST /scan/full`: Inicia varredura completa do sistema.
