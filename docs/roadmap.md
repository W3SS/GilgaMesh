# Gilgamesh — Strategic Roadmap

> **Hardware target**: Ryzen 9 7950x + RTX 4070 (12GB VRAM) | Windows 11 / Manjaro
> **Current status**: Alpha — Hexagonal architecture complete (Iterations 1-5), port-scanner feature added (Iteration 6)

---

## Architecture & Stack

### Core Stack

| Layer | Technology | Rationale |
|---|---|---|
| Orchestrator | Python 3.11 + FastAPI + asyncio | Rapid I/O, mature ecosystem, Docker SDK |
| Domain Logic | Pure Python dataclasses + typing.Protocol | No framework coupling; testable in isolation |
| System Monitoring | psutil (cross-platform) + wmi (Windows-only) | Low overhead, native access to network/process table |
| AI — Text | Ollama (llama3, mistral, phi3) | Local inference, OpenAI-compatible API |
| AI — Image | ComfyUI + SDXL/FLUX | Maximum flexibility via workflow JSON |
| AI — Audio | Faster-Whisper | 4x faster than OpenAI Whisper at same accuracy |
| Memory / RAG | Qdrant (vector DB) | Persistent embeddings, filter by metadata |
| Dashboard | React 18 + TypeScript + Vite + Tailwind + Recharts | Fast HMR, strong typing, lightweight |
| Observability | Prometheus + Grafana | Already configured; standard tooling |
| Container Runtime | Docker (WSL2 on Windows) / Docker native (Linux) | Unified service lifecycle |
| Config | pydantic-settings + `.env` | 12-factor, zero magic numbers |

### Architecture: Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────────┐
│               FastAPI Application Layer                         │
│  /tasks  /status  /api/v1/system/ports  /events  /health       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼──────────────────┐
           ▼               ▼                  ▼
     ┌──────────┐   ┌─────────────┐   ┌────────────┐
     │  Ports   │   │   Domain    │   │   Config   │
     │(Protocol)│   │(Pure Logic) │   │(pydantic)  │
     └────┬─────┘   └─────────────┘   └────────────┘
          │ inject
          ▼
     ┌──────────────────────────────────────┐
     │              Adapters                │
     │ Ollama │ ComfyUI │ Docker           │
     │ Discord │ PsutilSystem │ WMI(win)   │
     └──────────────────────────────────────┘
```

---

## Phase 1 — MVP (Current → Stable Alpha)

**Goal**: All core services working reliably; dashboard MVP; port scanner shipped.

### Iteration 6 — Port & Service Discovery (SHIPPED in this session)
- [x] `SystemMonitorPort` protocol (`orchestrator/ports/system_monitor.py`)
- [x] `PsutilSystemAdapter` with 5-second TTL cache and suspicious-port flagging
- [x] `GET /api/v1/system/ports` — open ports with suspicious annotation
- [x] `GET /api/v1/system/services` — background processes sorted by CPU
- [x] `GET /api/v1/system/ports/{port}` — single-port check
- [x] Prometheus counter `sentinel_suspicious_port_detected_total`
- [x] 14 unit tests for the new adapter (`orchestrator/tests/test_system_monitor.py`)
- [x] `spec.md`, `AGENTS.md`, `SKILLS.md`, `.mcp.json` bootstrapped

### Iteration 7 — React Dashboard MVP
- [ ] Scaffold `dashboard/` — React 18 + Vite + TypeScript + Tailwind
- [ ] `apiClient.ts` — typed HTTP wrapper for Orchestrator and Sentinel APIs
- [ ] **VRAM Gauge** panel (Recharts RadialBarChart) — live via SSE `/events`
- [ ] **Open Ports Table** — auto-refresh 5s, suspicious ports highlighted red
- [ ] **Background Services Table** — top-20 by CPU, refresh 10s
- [ ] **Container Status** panel — per-service running/stopped status chips
- [ ] **Task Queue** panel — pending / in-progress / last 5 completed
- [ ] SSE endpoint `GET /events` on Orchestrator (server-sent events for live state)
- [ ] `docker-compose.yml` — add `dashboard` service (nginx serving Vite build, port 3001)
- [ ] Bind Orchestrator to `127.0.0.1` by default (not `0.0.0.0`)

### Iteration 8 — Notification Polish & Alert Dedup
- [ ] Suspicious port alert deduplication (15-minute suppress window per port/process)
- [ ] Alert payload includes: port, process_name, PID, timestamp, severity level
- [ ] Telegram adapter parity with Discord adapter
- [ ] Prometheus AlertManager rule: `sentinel_suspicious_port_detected_total > 0`
- [ ] Grafana panel: "Suspicious Ports (last 24h)" time series

---

## Phase 2 — Alpha (Feature-Complete, Hardened)

**Goal**: Production-worthy for a personal workstation. All features stable. Proper error recovery.

### Iteration 9 — Faster-Whisper Migration
- [ ] Replace Whisper container with `faster-whisper` (4x faster, same VRAM footprint)
- [ ] Add `WhisperPort` protocol + `FasterWhisperAdapter`
- [ ] Update VRAM budgets: Whisper-Large 3000MB → 2500MB
- [ ] Streaming transcription endpoint (WebSocket)
- [ ] Task history persistence in SQLite (survive orchestrator restart)

### Iteration 10 — WMI System Adapter (Windows Enhanced Monitoring)
- [ ] `WmiSystemAdapter` implementing `SystemMonitorPort` — Windows-only
- [ ] Richer data: service display names, SCM start type, account name
- [ ] Factory function: select `WmiSystemAdapter` on Windows, `PsutilSystemAdapter` on Linux/Mac
- [ ] Add `start_type` field to `BackgroundService` domain model

### Iteration 11 — RAG Memory Integration
- [ ] Connect `memory/rag_memory_service.py` to orchestrator task pipeline
- [ ] Task completions stored as embeddings in Qdrant with metadata
- [ ] `GET /api/v1/memory/search?q=...` — semantic search over task history
- [ ] Dashboard panel: "Memory" with recent embeddings count and search box

### Iteration 12 — CI/CD & Testing Infrastructure
- [ ] GitHub Actions workflow: `pytest orchestrator/tests/ -v` + `docker compose build` on PR
- [ ] `pytest-cov` with 80% coverage gate for `orchestrator/`
- [ ] Integration test suite under `tests/` using docker-compose test profile
- [ ] Pre-commit hooks: `ruff` (lint), `mypy` (types), `black` (format)
- [ ] `Makefile` with `make dev`, `make test`, `make build`, `make lint`

---

## Phase 3 — Beta (Multi-Model, Plugin System)

**Goal**: Community-ready. Plugin API. Multiple AI backend support.

### Iteration 13 — Tauri Desktop Shell
- [ ] Wrap dashboard in a Tauri window (native Windows/Linux app)
- [ ] System tray icon with quick-status popup
- [ ] Desktop notification for suspicious port alerts
- [ ] Single `.exe` distribution for Windows 11

### Iteration 14 — Pluggable Adapter Registry
- [ ] Hot-pluggable adapter registry: register `AIProviderPort` implementations at runtime
- [ ] YAML-based adapter config (`adapters.yaml`)
- [ ] Community adapters: LocalAI, LM Studio, Kobold.cpp

### Iteration 15 — Multi-GPU Support
- [ ] VRAM budget per GPU (enumerate via GPUtil/nvidia-smi)
- [ ] Task affinity: assign tasks to specific GPU index
- [ ] Dashboard: per-GPU VRAM gauge side-by-side

### Iteration 16 — MCP Server (Gilgamesh as MCP host)
- [ ] Expose Gilgamesh itself as an MCP server
- [ ] Tools: `submit_task`, `get_open_ports`, `get_services`, `switch_mode`
- [ ] Claude Code and other MCP clients can control Gilgamesh autonomously

---

## Improvement Areas (Cross-Cutting)

### Security

| Item | Priority | Target Iteration |
|---|---|---|
| Replace default `SENTINEL_API_KEY` with generated secret on first run | High | 7 |
| Rate-limit `/tasks` endpoint to prevent VRAM-exhaustion abuse | High | 8 |
| Bind services to `127.0.0.1` by default (not `0.0.0.0`) | High | 7 |
| mTLS between internal services | Low | Beta |

### Observability

| Item | Priority | Target Iteration |
|---|---|---|
| Structured JSON logging (replace plain text format) | High | 7 |
| Grafana panel for suspicious port scan history | Medium | 8 |
| Alert: VRAM > 95% sustained for 60s | High | 8 |
| OpenTelemetry tracing for task lifecycle | Medium | 11 |

### Developer Experience

| Item | Priority | Target Iteration |
|---|---|---|
| `Makefile` with standard targets | High | 7 |
| `docker-compose.dev.yml` with hot-reload volume mounts | Medium | 7 |
| `mypy` strict mode across `orchestrator/` | Medium | 12 |
| OpenAPI spec auto-export to `docs/api.json` | Low | 11 |

### Performance

| Item | Priority | Target Iteration |
|---|---|---|
| Port scan in-process TTL cache | Done | 6 |
| Task queue persistence (SQLite) | High | 9 |
| Async Docker SDK calls in `DockerAdapter` | Medium | 10 |
| ComfyUI WebSocket streaming for live image preview | Low | 12 |

---

## Feature: Port & Service Discovery — Technical Design

### Data Flow

```
Client → GET /api/v1/system/ports
              │
              ▼
    PsutilSystemAdapter.get_open_ports()
              │  cache hit (TTL=5s) → return cached list
              │  cache miss → asyncio.to_thread(psutil.net_connections)
              ▼
    Map to NetworkConnection dataclasses
    Flag: conn.suspicious = port in SUSPICIOUS_PORTS  # O(1) set lookup
              │
              ▼
    Increment Prometheus counter for each suspicious port
              │
              ▼
    Return JSON {count, suspicious_count, ports[]}
```

### Suspicious Ports Set

```python
SUSPICIOUS_PORTS = frozenset({
    22,    # SSH (unexpected on workstation)
    23,    # Telnet
    3389,  # RDP
    4444,  # Metasploit default listener
    5900,  # VNC
    6667,  # IRC (malware C2)
    31337, # Back Orifice
})
```

### Dashboard Integration (Planned — Iteration 7)

```
React PortsTable Component
├── useEffect: poll every 5s → GET /api/v1/system/ports
├── State: NetworkConnection[]
└── Render table rows:
    └── suspicious=true → className="bg-red-50 border-l-4 border-red-500"
```

### MCP Agent Usage

```bash
# Via MCP fetch server — check if Ollama is listening
mcp fetch http://localhost:8005/api/v1/system/ports/11434

# Get all currently suspicious ports
mcp fetch http://localhost:8005/api/v1/system/ports
# Filter client-side: .ports.filter(p => p.suspicious)
```
