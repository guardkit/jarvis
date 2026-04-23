# DDR-013: `langgraph.json` lives at the repo root; declares two graphs with ASGI transport

**Status:** Accepted
**Date:** 2026-04-23
**Deciders:** Rich + `/system-design FEAT-JARVIS-003` session
**Related context:** FEAT-JARVIS-003
**Related components:** repo-root `langgraph.json`, `jarvis.agents.supervisor`, `jarvis.agents.subagents.jarvis_reasoner`
**Depends on:** [DDR-010](DDR-010-single-async-subagent-supersedes-four-roster.md), [DDR-012](DDR-012-subagent-module-import-compilation.md), [ADR-ARCH-031 (Forge)](../../../../../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)

## Context

The Phase 2 scope document left open: *"`/system-design` pins whether this lives at the repo root (LangGraph convention) or inside `src/jarvis/`."*

LangGraph's `langgraph dev` CLI expects `langgraph.json` at the project root by default (via `--config`). The LangGraph server packages resolve graph paths relative to the JSON file's directory. Placing the manifest at `src/jarvis/` would require either `--config src/jarvis/langgraph.json` on every invocation (operational friction) or relative paths of the form `./src/jarvis/agents/supervisor.py:graph` from `src/jarvis/` — which would resolve outside the manifest directory and break the convention.

Forge's parallel decision in [ADR-ARCH-031](../../../../../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md) pinned repo-root placement:

```json
{
  "graphs": {
    "forge": "./src/forge/agent.py:graph",
    "autobuild_runner": "./src/forge/subagents/autobuild_runner.py:graph"
  }
}
```

Jarvis inherits that pattern.

## Decision

`langgraph.json` lives at the repo root (`/Users/richardwoollcott/Projects/appmilla_github/jarvis/langgraph.json`) and declares two graphs:

```json
{
  "dependencies": ["."],
  "graphs": {
    "jarvis": "./src/jarvis/agents/supervisor.py:graph",
    "jarvis_reasoner": "./src/jarvis/agents/subagents/jarvis_reasoner.py:graph"
  },
  "env": ".env",
  "python_version": "3.12"
}
```

**Transport is ASGI** (co-deployed, zero network latency). The `AsyncSubAgent(graph_id="jarvis_reasoner", ...)` entry in `build_async_subagents(config)` does *not* set a `url`; DeepAgents' `AsyncSubAgentMiddleware` resolves local `graph_id`s against the in-process LangGraph server.

The supervisor is exported as a module-level `graph` variable from `src/jarvis/agents/supervisor.py`. FEAT-JARVIS-001 shipped `build_supervisor(config)` as the factory; FEAT-JARVIS-003 adds a module-level `graph` export that invokes `build_supervisor(JarvisConfig())` once at import for `langgraph dev` resolution. The factory remains the canonical construction API for tests and programmatic use:

```python
# src/jarvis/agents/supervisor.py (FEAT-JARVIS-003 addition, sketch only)

def build_supervisor(config: JarvisConfig, *, ...) -> CompiledStateGraph: ...

# Module-level export for langgraph.json resolution.
# Reads env vars directly; operators set the environment before `langgraph dev`.
graph = build_supervisor(JarvisConfig())
```

## Rationale

- **LangGraph convention.** `langgraph dev`, the LangGraph server, and the `langgraph-cli` tooling all default to repo-root `langgraph.json`. Placing it elsewhere works against the grain of every LangGraph operator workflow and docstring example.
- **Dependency resolution.** `"dependencies": ["."]` tells LangGraph to install the current package before compiling graphs; this only works cleanly when the manifest is at the same level as `pyproject.toml`.
- **Consistency with Forge.** The fleet's two LangGraph-based agents (Jarvis, Forge) use the same layout, easing cross-repo operator cognition. A future fleet-wide `langgraph dev`-orchestration script won't need per-repo special cases.
- **Single source of truth for graph registration.** Repo-root placement means graph registration is observable in a file at `git ls-tree HEAD --name-only` depth 1. Hidden under `src/jarvis/` it would compete for attention with Python modules.

## Alternatives considered

1. **`src/jarvis/langgraph.json`.** Rejected. Every `langgraph` CLI invocation would need `--config src/jarvis/langgraph.json`; relative graph paths would need `../../src/jarvis/agents/...` resolution gymnastics; `"dependencies": ["."]` would refer to `src/jarvis/`, which is not a valid install root (no `pyproject.toml` there).

2. **`.langgraph/config.json`.** Rejected. Non-standard location; no tool support; adds a hidden directory for one file.

3. **Declare all graphs in a single `langgraph.json` at the repo root *and* add a per-subagent `*.langgraph.json` next to each subagent module.** Rejected. Two sources of truth for graph paths. The 0.5.3 SDK has no pattern for secondary manifest files.

4. **Use HTTP transport with a separate subagent container.** Rejected per [ADR-ARCH-031](../../../../../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md) (Forge's decision, adopted as the fleet default) — HTTP transport is reserved for cross-compute-profile deployments (future). v1 is single-container.

## Consequences

**Positive:**
- `langgraph dev` Just Works from the repo root with no flags.
- CI can include a `langgraph dev --no-browser --check-only` step (or equivalent) without path gymnastics.
- Matches Forge's layout; one mental model for fleet agents.

**Negative:**
- `src/jarvis/agents/supervisor.py` gains a module-level `graph = build_supervisor(JarvisConfig())` side-effect-on-import. Operators running `langgraph dev` in a misconfigured environment see a Pydantic validation error at startup — consistent with DDR-012's fail-fast posture and ADR-ARCH-015 CI, but is a new behaviour vs. Phase 1 (where the supervisor was built only inside `lifecycle.startup`). Phase 2 test fixtures set a valid `JARVIS_SUPERVISOR_MODEL` before importing `jarvis.agents.supervisor` to keep the module-level `graph` construction safe under pytest.
- Repo-root `langgraph.json` is user-visible in `git status` and PR diffs — expected, but worth noting for onboarding.

## Links

- DDR-010 — single async subagent
- DDR-012 — module-import compilation
- Forge ADR-ARCH-031 — async subagents pattern source
- LangGraph docs — `langgraph.json` schema (fetched 19 April 2026)
