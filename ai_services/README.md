# Prometheus Mesh - AI Services

This directory contains the configurations, models, and scripts for the AI services managed by the Orchestrator.

## Structure

### 🦙 Ollama (`/ollama`)

Local LLM inference engine.

- `models/`: Docker volume mount for LLM weights (e.g., Llama 3).
- `scripts/`:
  - `setup.sh`: Pulls required Docker images and models.

### 🎨 ComfyUI (`/comfyui`)

Node-based Stable Diffusion interface.

- `models/`: Volume mount for Checkpoints, Loras, VAEs.
- `output/`: Volume mount for generated images.
- `workflows/`: JSON templates for Orchestrator integration.
  - `default.json`: Standard text-to-image workflow.
- `scripts/`:
  - `setup.sh`: Downloads SDXL checkpoints from HuggingFace.

### 🗣️ Whisper (`/whisper`)

Speech-to-text service (OpenAI Whisper).

- `cache/`: Volume mount for model weights to persist between restarts.
- `scripts/`: (Planned) Custom model download logic if needed.

## Setup

To initialize all models, run the global setup script:

```bash
bash scripts/setup/download_models.sh
```

This script delegates execution to the individual `setup.sh` files in each service directory.
