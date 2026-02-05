# Implementation Plan - Prometheus Mesh Scaffolding

This plan outlines the steps to generate the **Prometheus Mesh** project structure and initial code, based on the **v2.0 Architecture** proposed in `ArquiteturaPrometheusMesh.md`.

## User Review Required

> [!IMPORTANT]
> **Architecture Version**: I am proceeding with the **Improved Solution (v2.0)** described in the document, which includes the Predictive Swap, Hybrid CPU/GPU model, and Async Queue. This addresses the critical flaws (VRAM swap latency, race conditions) identified in the initial analysis.

> [!NOTE]
> **Project Location**: The project will be created at `h:\Meu Drive\codebase\tech\prometheus_mesh`.

## Proposed Changes

### Directory Structure

I will create the full directory structure as defined in the document:

```text
prometheus_mesh/
├── orchestrator/
├── sentinel/
├── memory/
├── notifications/
├── monitoring/
├── ai_services/
├── data/
├── scripts/
├── docs/
└── tests/
```

### Component Implementation

#### 1. Orchestrator Service (v2.0)

- **File**: `orchestrator/main.py`
- **Logic**: Async resource orchestrator with predictive swap, task queue, and VRAM management.
- **Infrastructure**: `Dockerfile`, `requirements.txt`.

#### 2. Sentinel Service (v2.0)

- **File**: `sentinel/sentinel_service.py`
- **Logic**: Windows native agent for monitoring specific processes (e.g., locking VRAM), security scanning, and system metrics.
- **Infrastructure**: `requirements.txt` (including `pywin32`, `wmi`), `Dockerfile` (reference only).

#### 3. Memory Service (v2.0)

- **File**: `memory/rag_memory_service.py`
- **Logic**: RAG system using Qdrant for storing decisions and long-term memory.
- **Infrastructure**: `Dockerfile`, `requirements.txt`.

#### 4. Infrastructure

- **`docker-compose.yml`**: orchestration for all containerized services (Orchestrator, Memory, Qdrant, Prometheus, Grafana, Ollama, ComfyUI).
- **Scripts**: `initial_setup.sh`, `download_models.sh`.

## Verification Plan

### Automated Verification

- **Structure Check**: Verify all directories and files are created.
- **Syntax Check**: precise check of Python files to ensure no syntax errors in the generated code.
- **Docker Config**: Run `docker-compose config` to validate the compose file.

### Manual Verification

- Review the generated structure against the `ArquiteturaPrometheusMesh.md` spec.
