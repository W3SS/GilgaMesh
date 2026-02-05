# PROMETHEUS MESH V2.0 - Guia de Setup e Deployment

Este guia cobre a instalação, configuração e execução de todo o ecossistema Prometheus Mesh.

## Pré-requisitos

- **OS**: Windows 10/11 (com WSL2 ativado para Docker) ou Linux.
- **GPU**: NVIDIA RTX 3060 ou superior (recomendado 8GB+ VRAM).
- **RAM**: 16GB+ (recomendado 32GB).
- **Software**:
  - Docker Desktop & Docker Compose.
  - Python 3.11+.
  - Git.
  - NVIDIA Drivers atualizados.

## Passo a Passo

### 1. Clonar e Preparar

```bash
git clone https://github.com/seu-repo/prometheus-mesh.git
cd prometheus-mesh
cp .env.example .env
# Edite o arquivo .env com suas chaves de API e configurações de caminho
```

### 2. Configurar Serviços de IA

O sistema precisa baixar os modelos pesados (Llama3, SDXL). Use o script facilitador:

```bash
# Git Bash ou Linux
bash scripts/setup/download_models.sh
```

*Isso baixará alguns GBs de dados. Certifique-se de ter espaço em disco.*

### 3. Build e Start (Docker)

Inicie a infraestrutura básica (Orchestrator, Memory, AI Services, Monitoring):

```bash
docker-compose up -d --build
```

Aguarde até que os serviços `ollama` e `qdrant` estejam saudáveis.

### 4. Iniciar Sentinel (Nativo Windows)

O Sentinel deve rodar fora do Docker para ter acesso irrestrito ao sistema.
Abra um **PowerShell como Administrador**:

```powershell
cd sentinel
pip install -r requirements.txt
python sentinel_service.py
```

### 5. Configurar Notificações (Opcional)

Se desejar alertas no Discord/Telegram:

1. Crie os bots nas respectivas plataformas e obtenha os Tokens.
2. Adicione ao `.env` na pasta `notifications/`.
3. Inicie o serviço de notificações:

   ```bash
   docker-compose up -d notifications
   ```

## Dashboards e Acesso

- **Grafana (Monitoramento)**: [http://localhost:3000](http://localhost:3000)
  - Login padrão: `admin` / `prometheus_admin`
- **Orchestrator API (Docs)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Notification Dashboard**: [http://localhost:9002/client/](http://localhost:9002/client/)

## Troubleshooting

- **Erro de VRAM**: Se o `ollama` ou `comfyui` cair por falta de memória, verifique os logs do Orchestrator. Ele deve estar matando um serviço antes de iniciar outro. Ajuste os limites no `.env`.
- **Sentinel Access Denied**: Certifique-se de rodar o PowerShell como Administrador. O acesso a processos de sistema e Event Logs requer elevação.
- **Docker GPU não detectada**: Verifique se o Docker Desktop está configurado para usar a engine WSL2 e se os drivers NVIDIA Container Toolkit estão instalados (no Linux) ou se o suporte a GPU está ativado no Windows.
