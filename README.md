# Gilgamesh: Neural Audio Workstation

> **Status**: 🚧 Alpha (Refactoring in Progress)
> **Architecture**: Hybrid (Python/Rust/Docker)

Gilgamesh is an "Active Operating System" overlay designed to orchestrate local AI models (LLMs, Image Gen, Audio) with intelligent resource management. It aims to act as a seamless bridge between raw hardware performance and high-level AI orchestration.

## 🏗 Architecture Overview

The system operates as a distributed mesh of services, currently orchestrated by a central Python service.

### Components

| Service | Technology | Role |
| :--- | :--- | :--- |
| **Orchestrator** | Python (FastAPI) | Resource manager, task router, context switcher. |
| **Sentinel** | Python (Windows Native) | Security agent, hardware monitor, "Bodyguard". |
| **Memory** | Qdrant | Vector database for RAG and long-term memory. |
| **ComfyUI** | Python/PyTorch | Image/Video generation engine. |
| **Ollama** | Go/GGML | Local LLM inference. |
| **Whisper** | Python/PyTorch | Audio transcription. |

### The "Active OS" Concept
Unlike passive tools, Gilgamesh actively manages system resources:
*   **Predictive Swap**: Analyzes user intent to pre-warm GPU models (e.g., swapping out an LLM for Stable Diffusion when "imagine" is typed).
*   **VRAM Management**: Strictly tracks VRAM usage to prevent OOM errors on consumer cards (target: RTX 4070 Super, 12GB).
*   **Sentinel**: A native Windows agent that monitors for threats and anomalies that isolated Docker containers cannot see.

## 🚀 Getting Started

### Prerequisites
*   Windows 10/11
*   NVIDIA GPU (8GB+ VRAM recommended)
*   Docker Desktop (with WSL2 backend)
*   Python 3.10+

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/W3SS/GilgaMesh.git
    cd GilgaMesh
    ```

2.  **Environment Setup:**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys (Discord/Telegram) and paths
    ```

3.  **Start the Mesh:**
    ```bash
    docker-compose up -d
    ```

4.  **Start Sentinel (Native):**
    ```bash
    cd sentinel
    pip install -r requirements.txt
    python sentinel_service.py
    ```

## ⚠️ Critical Analysis & Roadmap (v2.0 Refactor)

The current implementation is in a **transition phase**. While functional, the architecture is being refactored from a monolithic script approach to a clean Hexagonal Architecture.

### Current Issues (v1.0)
*   **Monolithic Orchestrator**: `main.py` contains too much logic (hardware math + business rules + HTTP handling).
*   **Hardcoded Configuration**: VRAM limits and model names are embedded in code.
*   **Tight Coupling**: High dependency on specific Docker container names and internal implementation details.

### Roadmap to v2.0
- [ ] **Hexagonal Architecture**: Extract business logic (Domain) from infrastructure code (Adapters).
- [ ] **Config Separation**: Move all hardcoded limits to `config.yaml`.
- [ ] **Typed Interfaces**: Define strict Protocols for `AIProvider`, `ContainerRuntime`, etc.
- [ ] **Enhanced Sentinel**: Decouple Windows-specific API calls to allow for easier testing.

## 🤝 Contributing

We welcome contributions! Please check the `implementation_plan.md` (if available in artifacts) or the Roadmap above before starting major refactors.

---
*Powered by the Antigravity Kit*
