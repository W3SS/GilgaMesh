# SKILLS.md — Gilgamesh Skill Configuration

> Skill registry for Claude Code agents working on the Gilgamesh project.
> These skills extend agent capabilities with project-specific context and workflows.

---

## Core Skills (Standard)

These skills should be active in every session on this project:

| Skill | Purpose |
|---|---|
| `@security-audit` | Review code for injection, open bindings, credential leaks, suspicious port exposure |
| `@docker-expert` | docker-compose orchestration, healthcheck design, volume and network configuration |
| `@git-workflow` | Conventional commits, branch strategy, PR descriptions, changelog generation |
| `@python-async` | asyncio patterns, httpx best practices, FastAPI lifecycle management |
| `@pytest-tdd` | Test-first development, fixture design, mock/stub patterns for Ports |
| `@prometheus-observability` | Metrics naming conventions, Grafana dashboard JSON, alert rule design |
| `@hexagonal-architecture` | Ports & Adapters review, domain purity checks, dependency direction audits |

---

## Custom Skills (Project-Specific)

### `@gilgamesh-vram-manager`

**Purpose**: Reason about VRAM budget decisions for RTX 4070 (12GB) hardware target.

**Context provided to agent**:
- Total VRAM: 12,000 MB with 1,000 MB safety margin (usable: 11,000 MB)
- Model budgets: Llama3-8B=6000MB, SDXL=8500MB, FLUX=10000MB, Whisper-Large=3000MB
- `ContextDomainService` logic in `orchestrator/domain/context_service.py`
- Context modes: TEXT_HEAVY, CREATIVE, AUDIO_PROCESSING, HYBRID

**Activation trigger**: Any task involving adding a new AI model, changing VRAM limits, or modifying `context_service.py`.

**Rules**:
- Always calculate total VRAM consumption before approving a new model.
- Propose which services must be stopped to accommodate the new model.
- Check against `settings.VRAM_TOTAL - settings.VRAM_SAFETY_MARGIN`.

---

### `@gilgamesh-system-monitor`

**Purpose**: Implement and reason about the system monitoring feature — open ports, background services, process discovery.

**Context provided to agent**:
- New Port interface: `orchestrator/ports/system_monitor.py` (`SystemMonitorPort`)
- New Adapter: `orchestrator/adapters/psutil_system_adapter.py` (`PsutilSystemAdapter`)
- Sentinel service already uses `psutil` and `wmi` for process/network monitoring
- Data model: `NetworkConnection(pid, local_port, remote_addr, state, process_name)`
- Suspicious ports list: `{22, 23, 3389, 4444, 5900, 6667, 31337}`
- FastAPI endpoint: `GET /api/v1/system/ports` and `GET /api/v1/system/services`

**Activation trigger**: Any task touching network monitoring, port scanning, service discovery, or the `system_monitor` port.

**Rules**:
- Port scanning is LOCAL ONLY (localhost/127.0.0.1). Never scan remote hosts.
- All network data must be aggregated, not raw PIDs, to avoid privilege escalation concerns.
- Suspicious port detections must trigger a Prometheus counter (`sentinel_suspicious_port_detected_total`).

---

### `@gilgamesh-dashboard`

**Purpose**: Build and maintain the React dashboard that visualises system state.

**Context provided to agent**:
- API base: `http://localhost:8005` (Orchestrator), `http://localhost:8001` (Sentinel)
- SSE endpoint: `GET /events` on Orchestrator (real-time task/service updates)
- Dashboard panels: VRAM Gauge, Open Ports Table, Background Services, Task Queue, Container Status
- Tech stack: React 18 + TypeScript + Vite + Tailwind + Recharts
- Dashboard source: `dashboard/` directory (React app)

**Activation trigger**: Any task touching `dashboard/`, the `/events` SSE endpoint, or UI data shapes.

**Rules**:
- All API calls through a typed `apiClient.ts` module — never raw `fetch()` inline.
- Port table must highlight suspicious ports in red (ports from `SUSPICIOUS_PORTS` set).
- VRAM gauge must show per-service breakdown, not just total.
- Live update interval: SSE preferred; fallback polling at 5-second intervals maximum.

---

## Installation Command

```bash
# Standard skills
npx @anthropic/claude-code skill install \
  @security-audit \
  @docker-expert \
  @git-workflow \
  @python-async \
  @pytest-tdd \
  @prometheus-observability \
  @hexagonal-architecture

# Custom skills are loaded automatically from SKILLS.md in the project root
# No installation needed — Claude Code reads this file as project context
```

---

## Skill Activation Matrix

| Task Type | Active Skills |
|---|---|
| Adding a new AI model | `@gilgamesh-vram-manager`, `@hexagonal-architecture`, `@pytest-tdd` |
| Port/service monitoring feature | `@gilgamesh-system-monitor`, `@security-audit`, `@pytest-tdd` |
| Dashboard UI changes | `@gilgamesh-dashboard`, `@security-audit` |
| Docker/infra changes | `@docker-expert`, `@prometheus-observability`, `@git-workflow` |
| Security review | `@security-audit`, `@gilgamesh-system-monitor` |
| Refactoring / migration | `@hexagonal-architecture`, `@pytest-tdd`, `@git-workflow` |
| Commit / PR creation | `@git-workflow` |
