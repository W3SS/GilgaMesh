# Prometheus Mesh Scaffolding Walkthrough

The project structure and initial code for **Prometheus Mesh v2.0** have been successfully generated at `h:\Meu Drive\codebase\tech\prometheus_mesh`.

## Generated Components

### 1. Orchestrator Service (`/orchestrator`)

- **`main.py`**: Implements the v2.0 logic with:
  - **Resource Orchestration**: Async management of Docker containers.
  - **Predictive Swap**: `_predictive_warmup_loop` analyzes prompt history to pre-warm ComfyUI.
  - **Context Modes**: `TEXT_HEAVY`, `CREATIVE`, `AUDIO_PROCESSING`.
  - **VRAM Management**: Intelligent tracking and allocation logic.
- **Infrastructure**: `Dockerfile` and `requirements.txt` included.

## Phase 3.1: Sentinel Native Enhancements

**Date**: 2026-02-05

### Changes

1. **Dynamic Configuration**: Replaced static `SentinelConfig` with a singleton that loads/saves `sentinel_config.json`.
    - Exposed endpoints `/config/whitelist` and `/config/blacklist` for runtime management.
2. **Active Monitoring Loop**: Implemented `_monitoring_loop` in `SentinelCore` that runs every 10 seconds.
    - Analyzes process threats (CPU/Memory/Suspicious Names).
    - Checks system resource anomalies.
    - Checks network connections (every 60s).
3. **Dependency Fixes**: Updated `requirements.txt` to support Python 3.14 (removed pinned versions) and installed `GPUtil`, `pydantic`, `fastapi`, etc.

### Verification

- **Script**: `tests/verify_sentinel_native.py`
- **Result**: Passed. Verified config persistence and core threat logic.
- **Docker**: Skipped Docker-based verification (Qdrant integration) due to unavailable engine.

### 2. Sentinel Service (`/sentinel`)

- **`sentinel_service.py`**: Native Windows agent implementing:
  - **Process Monitoring**: `analyze_process_threats` with whitelist/blacklist support.
  - **Security**: Windows Defender integration and event log monitoring.
  - **Hardware Monitoring**: Real-time stats for CPU, RAM, VRAM (NVIDIA).
- **Run Mode**: Designed to run natively on Windows (no Docker), but a reference `Dockerfile` is provided.

### 3. Memory Service (`/memory`)

- **`rag_memory_service.py`**: Qdrant-based RAG system.
  - **Collections**: Decisions, Conversations, Knowledge.
  - **Learning**: `store_decision` and `process_learning_feedback` for incremental improvement.
  - **Context**: Retrieval of relevant history for the Orchestrator.

### 4. Infrastructure

- **`docker-compose.yml`**: Orchestrates all services including:
  - **Core**: Orchestrator, Memory, Qdrant.
  - **AI**: Ollama (GPU), ComfyUI (GPU), Whisper.
  - **Monitoring**: Prometheus, Grafana.
- **Configuration**:
  - `monitoring/prometheus/prometheus.yml`
  - `monitoring/grafana/dashboards/prometheus_mesh.json`
- **Scripts**:
  - `scripts/setup/initial_setup.sh`: Automated setup (Linux/WSL friendly).
  - `scripts/setup/download_models.sh`: Fetches Llama3 and SDXL models.

## How to Start

1. **Environment Setup**:

    ```bash
    cp .env.example .env
    # Edit .env with your API keys
    ```

2. **Run Setup Script** (Git Bash or WSL):

    ```bash
    bash scripts/setup/initial_setup.sh
    ```

3. **Manual Start**:
    If not using the script, ensure Docker is running and execute:

    ```bash
    bash scripts/setup/download_models.sh
    docker-compose up -d --build
    ```

4. **Run Sentinel (Windows Native)**:
    Open a separate PowerShell terminal as Administrator:

    ```powershell
    cd sentinel
    pip install -r requirements.txt
    python sentinel_service.py
    ```

5. **Access Dashboards**:
    - **Grafana**: <http://localhost:3000> (admin/prometheus_admin)
    - **Orchestrator API**: <http://localhost:8000/docs>
    - **Sentinel API**: <http://localhost:9000/docs>
