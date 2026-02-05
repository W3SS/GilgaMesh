# Architecture Critique: Gilgamesh Implementation Plan

## Executive Summary
This document evaluates `implementation_plan.md.resolved` against the project's long-term goals. While the diagnosis of the "God Class" problem and the choice of Hexagonal Architecture are **correct**, the implicit suggestion of a "Big Bang" rewrite poses a severe risk to project momentum.

## Critical Analysis

### 1. Diagnosis Accuracy (Verdict: ✅ Accurate)
-   **God Class Identified**: The critique correctly identifies `PrometheusOrchestrator` as an anti-pattern. Mixing Docker SDK calls (infrastructure) with context-switching logic (business rules) makes the system fragile and untestable.
-   **Architecture Choice**: Hexagonal Architecture is the appropriate remedy, allowing the "Active OS" core to remain stable while AI backends (Ollama, ComfyUI) evolve.

### 2. Migration Strategy (Verdict: ⚠️ Risk Alert)
-   **The "Big Bang" Trap**: The plan outlines the destination well but implies a massive, simultaneous refactor of all components. For an Alpha-stage project, pausing feature development to rewrite the entire core is a recipe for abandonment.
-   **Recommendation**: A **Strangler Fig Pattern** (Iterative Migration) is strictly better here. We should peel off layers one by one while keeping the system runnable.

### 3. Missing Elements
-   **Memory Integration**: The plan under-emphasizes the role of Qdrant. In an "Active OS", vector memory is not just a plugin; it's a core dependency for the "Brain".
-   **Windows Abstraction**: Sentinel needs a `SystemMonitor` interface to decouple the business logic from `win32` API calls, facilitating testing on non-Windows dev environments.

## Recommendations for Implementation

### 🚫 What NOT to Do (Big Bang)
1.  Do NOT delete `PrometheusOrchestrator` and try to write `OrchestratorService`, `DockerAdapter`, and `AiAdapter` all at once.
2.  Do NOT stop shipping features for 2 months to "fix architecture".

### ✅ Practical Iterative Roadmap
1.  **Phase 1: Configuration Extraction (Low Risk)**
    *   Move hardcoded `VRAM_LIMITS` and URLs to `pydantic-settings`.
    *   *Result*: No logic change, but immediate deployment flexibility.
2.  **Phase 2: The "ContainerRuntime" Port (Medium Risk)**
    *   Define the interface.
    *   Move Docker calls from `main.py` to `DockerAdapter`.
    *   *Result*: `main.py` becomes cleaner, logic is easier to read.
3.  **Phase 3: Domain Extraction (High Value)**
    *   Create `Context` and `Task` domain models.
    *   Refactor `main.py` to use these models instead of raw dicts.

## Final Verdict
The `implementation_plan.md.resolved` is **APPROVED as a North Star vision**, subject to the strict condition that it is executed **Iteratively** according to the roadmap above.
