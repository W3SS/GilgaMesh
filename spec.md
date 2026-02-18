# spec.md — Gilgamesh System Specification

> **Version**: 0.3.0-alpha
> **Status**: Active
> **Owner**: @Architect
> **Last updated**: 2026-02-18

---

## Problem Statement

Modern AI development on consumer hardware requires juggling multiple local models (LLMs, image generators, audio transcribers) that compete for limited VRAM. There is no existing tool that:

1. Intelligently orchestrates local AI services based on real-time VRAM availability.
2. Monitors system security (open ports, suspicious processes, anomalous network connections) from a single API surface.
3. Provides a unified dashboard that makes the internal state of the "AI workstation" visible to the user.
4. Exposes all capabilities via a clean MCP-compatible API so AI agents (Claude Code, etc.) can introspect and control the system autonomously.

Gilgamesh solves this for single-machine, high-end consumer setups (RTX 4070-class GPUs, Windows 11 / Manjaro Linux).

---

## Goals

- **G1**: Orchestrate Docker-based AI services (Ollama, ComfyUI, Whisper) with automatic VRAM-aware context switching.
- **G2**: Monitor and expose open TCP/UDP ports and running background services via a structured REST API.
- **G3**: Detect and alert on suspicious network activity (unexpected open ports, process anomalies) in real time.
- **G4**: Provide a real-time web dashboard showing VRAM usage, service states, port table, and task queue.
- **G5**: Expose all system state through MCP-compatible endpoints so AI agents can read and act on it.
- **G6**: Run entirely locally — no cloud dependencies for core functionality.

## Non-Goals

- **NG1**: Remote / multi-machine orchestration. This is a single-host tool.
- **NG2**: Network scanning of external hosts. Port discovery is local-only.
- **NG3**: Antivirus or malware removal. Detection and alerting only.
- **NG4**: Managing non-Docker AI services (e.g., Conda environments, bare-metal processes managed externally).
- **NG5**: Mobile or cloud-hosted dashboard.

---

## User Stories

### US-01: VRAM-Aware Task Routing
**As a** developer running multiple local AI models,
**I want** the orchestrator to automatically stop lower-priority services when VRAM is insufficient for a new task,
**so that** I can submit tasks without manually managing model swapping.

**Acceptance Criteria**:
- [ ] When a TEXT_GENERATION task is submitted and VRAM is insufficient, image/audio services stop automatically.
- [ ] Context switch completes in < 30 seconds on RTX 4070 hardware.
- [ ] A Prometheus metric `prometheus_swap_seconds` records each context switch.
- [ ] Notification is sent via Discord/Telegram when a swap occurs.

---

### US-02: Open Port & Service Discovery
**As a** system administrator running Gilgamesh,
**I want** to query a REST endpoint that lists all open TCP/UDP ports and the processes owning them,
**so that** I can detect unexpected services or potential intrusion vectors.

**Acceptance Criteria**:
- [ ] `GET /api/v1/system/ports` returns a JSON list of `{port, protocol, state, pid, process_name}`.
- [ ] `GET /api/v1/system/services` returns running background services with CPU/RAM usage.
- [ ] Ports in the suspicious set `{22, 23, 3389, 4444, 5900, 6667, 31337}` are flagged with `"suspicious": true`.
- [ ] Response time < 2 seconds (psutil scan with cache TTL of 5 seconds).
- [ ] Prometheus counter `sentinel_suspicious_port_detected_total` increments on each detection.

---

### US-03: Real-Time Dashboard
**As a** user,
**I want** a web dashboard that shows current VRAM usage, open ports, running containers, and the task queue,
**so that** I can understand my system state at a glance without using CLI tools.

**Acceptance Criteria**:
- [ ] Dashboard loads at `http://localhost:3001` (Vite dev server) or as a static build.
- [ ] VRAM gauge updates in real time via SSE (< 1-second lag from state change).
- [ ] Port table refreshes every 5 seconds and highlights suspicious ports in red.
- [ ] Container status panel shows running/stopped state per service.
- [ ] Task queue panel shows pending, in-progress, and last 5 completed tasks.

---

### US-04: MCP Agent Integration
**As an** AI agent (e.g., Claude Code) working on this codebase,
**I want** to query the Orchestrator and Sentinel APIs via MCP servers,
**so that** I can introspect system state, trigger tasks, and validate that services are healthy without leaving the agent context.

**Acceptance Criteria**:
- [ ] MCP `fetch` server is configured to reach `localhost:8005` (Orchestrator) and `localhost:8001` (Sentinel).
- [ ] MCP `filesystem` server can read all project source files.
- [ ] MCP `git` server supports read-only repository inspection.
- [ ] Agent can call `GET /health` and receive service health in < 1 second.

---

### US-05: Suspicious Activity Alerting
**As a** security-conscious user,
**I want** to receive a Discord or Telegram notification when a suspicious port or process is detected,
**so that** I am informed of potential threats without actively monitoring the dashboard.

**Acceptance Criteria**:
- [ ] Sentinel checks for suspicious ports every 60 seconds (configurable via `SENTINEL_SCAN_INTERVAL`).
- [ ] On detection, notification is sent within 10 seconds via the configured channel (Discord/Telegram).
- [ ] Notification body includes: port number, owning process name, PID, and detection timestamp.
- [ ] Duplicate alerts for the same port/process are suppressed for 15 minutes (dedup window).

---

## Technical Constraints

### Hardware
| Resource | Spec | Implication |
|---|---|---|
| GPU | RTX 4070 — 12GB VRAM | Maximum 11GB usable (1GB safety margin) |
| CPU | Ryzen 9 7950x — 16 cores / 32 threads | Async task workers can scale to 8 concurrent |
| RAM | 32GB DDR5 | Qdrant vector DB can hold large embedding sets |
| Storage | NVMe SSD | Container image pulls and model downloads are fast |

### OS
| Platform | Notes |
|---|---|
| Windows 11 (primary) | Docker via WSL2; Sentinel uses `win32evtlog`, `wmi`, `psutil` |
| Manjaro Linux (secondary) | Full Docker native; Sentinel uses `psutil` only |

### Latency Targets
| Operation | Target |
|---|---|
| Task submission → queue acknowledgement | < 100ms |
| Context switch (VRAM swap) | < 30s |
| Port scan API response | < 2s |
| Dashboard SSE update lag | < 1s |
| Notification delivery | < 10s |

### Service Port Map
| Service | Port | Protocol |
|---|---|---|
| Orchestrator API | 8005 | HTTP/REST + SSE |
| Sentinel API | 8001 | HTTP/REST |
| Dashboard | 3001 | HTTP (dev) / static |
| Ollama | 11434 | HTTP |
| ComfyUI | 8188 | HTTP + WebSocket |
| Whisper | 9000 | HTTP |
| Qdrant HTTP | 6333 | HTTP |
| Qdrant gRPC | 6334 | gRPC |
| Prometheus | 9093 | HTTP |
| Grafana | 3000 | HTTP |
| Memory Service | 9001 | HTTP |
| Notification Service | 9003 | HTTP |

---

## Architecture Decision Records

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Hexagonal Architecture (Ports & Adapters) via Strangler Fig | Implemented |
| ADR-002 | Python `typing.Protocol` for Port interfaces (no ABCs) | Implemented |
| ADR-003 | `pydantic-settings` for all configuration | Implemented |
| ADR-004 | `psutil` + platform-specific adapters for system monitoring | Proposed |
| ADR-005 | React + Vite + SSE for real-time dashboard | Proposed |
| ADR-006 | MCP `fetch` + `filesystem` + `git` server configuration | Proposed |
