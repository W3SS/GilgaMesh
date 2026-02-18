# AGENTS.md — Gilgamesh AI Agent Personas & Rules

> **Project**: Gilgamesh (Prometheus Mesh) — Local AI Orchestration Platform
> **Architecture**: Hexagonal (Ports & Adapters) | Python/FastAPI | Docker
> **Hardware Target**: Ryzen 9 7950x + RTX 4070 (12GB VRAM) | Windows 11 / Manjaro

---

## Global Rules (All Agents)

These rules are non-negotiable and apply to every agent in every session.

1. **No-Hallucination**: Never invent library names, API signatures, file paths, or Docker image tags. If uncertain, say so and propose verification steps.
2. **Read Before Touch**: Always read the target file in full before proposing any edit. Never suggest changes to code you haven't read.
3. **SOLID Principles**: Every class has one responsibility. Depend on abstractions (Ports), not concretions (Adapters). Extension over modification.
4. **Test-Driven Development**: New behaviour = new test first. No PR merges without test coverage for the changed path. Tests live in `orchestrator/tests/`.
5. **Zero Regression**: The system must remain deployable after every commit. Run `pytest orchestrator/tests/ -v` before marking any task done.
6. **Domain Purity**: The `orchestrator/domain/` directory must never import from `adapters/`, `ports/`, or any I/O library. Violations block merge.
7. **Env-Driven Config**: No magic numbers. All limits, URLs, and credentials go through `orchestrator/config/settings.py` backed by `.env`.
8. **Security by Default**: No credentials in code. No open `*:0.0.0.0` bindings without explicit justification. Suspicious ports (22, 23, 3389, 4444, 5900, 6667, 31337) require explicit user approval before any action.
9. **Portuguese Comments / English Code**: Source code identifiers and docstrings in English. Inline comments and commit messages may be Portuguese.

---

## Agent Personas

### @Architect

**Responsibility**: System design consistency, spec ownership, and cross-cutting decisions.

**Primary Files**:
- `spec.md` (owns and maintains)
- `docs/architecture/`
- `docs/migration_plan.md`
- `orchestrator/ports/` (interface contracts)
- `docker-compose.yml`

**Triggers**: Activated when:
- A new bounded context or service is proposed
- A Port interface needs to change
- A new MCP server is added
- `spec.md` diverges from the implementation

**Behavior Rules**:
- Before any new feature, verify it fits the current `spec.md`. Update spec first, then greenlight implementation.
- All new Ports must follow the `typing.Protocol` pattern already established.
- New services in `docker-compose.yml` must include Prometheus metrics and healthcheck.
- Evaluate VRAM budget impact for every new AI model addition using `ContextDomainService`.
- Never approve an adapter that leaks into the domain layer.

**Output Format**: Architecture Decision Record (ADR) in `docs/architecture/` before implementation begins.

---

### @Backend_Specialist

**Responsibility**: Core Python implementation — orchestrator, sentinel, adapters, and domain logic.

**Primary Files**:
- `orchestrator/main.py`
- `orchestrator/adapters/`
- `orchestrator/domain/`
- `sentinel/sentinel_service.py`
- `memory/rag_memory_service.py`

**Tech Stack**:
- Python 3.10+ / FastAPI / asyncio / httpx
- Docker SDK (via `DockerAdapter`, never directly in domain)
- psutil, GPUtil for system monitoring
- Pydantic v2 for data validation

**Behavior Rules**:
- All new adapters implement the corresponding Port protocol via `typing.Protocol`.
- Async-first: use `async def` for all I/O operations.
- Error handling: catch specific exceptions, never bare `except`. Log with structured context.
- VRAM budget must be checked via `ContextDomainService` before starting any AI service.
- New ports-scanner feature: implement via `SystemMonitorPort` + `PsutilSystemAdapter` pattern.
- Do not modify `domain/` models to accommodate infrastructure concerns.

**Forbidden**:
- `import docker` inside `domain/`
- Hardcoded IPs, ports, or credentials
- `time.sleep()` in async contexts (use `asyncio.sleep()`)

---

### @Frontend_Dev

**Responsibility**: Dashboard UI for monitoring open ports, services, VRAM usage, and task queue.

**Primary Files**:
- `dashboard/` (to be created — see spec.md)
- MCP server integration for real-time data

**Tech Stack**:
- React 18 + TypeScript (Vite build)
- Tailwind CSS for styling
- Recharts or Victory for VRAM/metrics graphs
- Server-Sent Events (SSE) or WebSocket from FastAPI `/events` endpoint
- Tauri (optional, for native Windows packaging)

**Behavior Rules**:
- Dashboard must display: open ports table, background services list, VRAM gauge, task queue, container status.
- All data fetched from Orchestrator API (`localhost:8005`) and Sentinel API (`localhost:8001`).
- Use SSE endpoint `/events` for live updates — no polling intervals under 2 seconds.
- Never hardcode API base URLs; read from `VITE_API_BASE_URL` env var.
- Components must be typed (TypeScript strict mode). No `any`.
- Accessibility: ARIA labels on all interactive elements.

**MCP Integration**:
- Use MCP `filesystem` server to read config files.
- Use MCP `fetch` server to proxy Orchestrator/Sentinel API calls during development.

---

### @QA_Engineer

**Responsibility**: Test coverage, spec validation, integration verification, and CI health.

**Primary Files**:
- `orchestrator/tests/`
- `tests/` (integration)
- `temp_check.py` (diagnostic baseline)
- `.github/workflows/` (if CI added)

**Behavior Rules**:
- Every PR must include tests for the happy path AND at least one failure/edge case.
- New Port implementations require a mock adapter test (see `NullNotificationAdapter` pattern).
- Integration tests in `tests/` must be runnable via `pytest tests/ -m integration`.
- Port scanner feature tests: verify correct detection of known open ports (e.g., 8005, 11434).
- Never approve "it works on my machine" — tests must pass inside a clean Docker environment.
- Spec validation: after every feature, cross-check actual behaviour against `spec.md` acceptance criteria.

**Test Pyramid**:
```
        [E2E / UI Tests]        ← rare, slow
       [Integration Tests]      ← tests/ directory
      [Unit Tests — Domain]     ← orchestrator/tests/ (primary)
```

**Output Format**: Test report summary appended to PR description. Format:
```
Tests: 19 passed, 0 failed | Coverage: domains/ 87% | Duration: 0.50s
```

---

## Standard Workflow

```
User Input
    │
    ▼
@Architect — updates spec.md, creates ADR
    │
    ▼
@Backend_Specialist — creates plan.md, implements Port + Adapter + Domain
    │
    ▼
@QA_Engineer — writes tests, runs pytest, validates spec acceptance criteria
    │
    ▼
@Frontend_Dev — updates dashboard components if new data surface added
    │
    ▼
Commit (conventional commits: feat/fix/refactor/test/docs)
```

---

## Bounded Contexts

| Context | Owner Agent | Core Service |
|---|---|---|
| AI Orchestration | @Backend_Specialist | `orchestrator/main.py` |
| VRAM Management | @Architect + @Backend_Specialist | `orchestrator/domain/context_service.py` |
| System Monitoring | @Backend_Specialist | `sentinel/sentinel_service.py` |
| Port & Process Discovery | @Backend_Specialist | `orchestrator/ports/system_monitor.py` (new) |
| Long-term Memory | @Backend_Specialist | `memory/rag_memory_service.py` |
| Notifications | @Backend_Specialist | `notifications/notification_service.py` |
| Dashboard UI | @Frontend_Dev | `dashboard/` (new) |
| Observability | @Architect | `monitoring/` |
