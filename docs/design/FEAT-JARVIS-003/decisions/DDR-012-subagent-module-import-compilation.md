# DDR-012: Subagent graphs compile at module-import time

**Status:** Accepted
**Date:** 2026-04-23
**Deciders:** Rich + `/system-design FEAT-JARVIS-003` session
**Related context:** FEAT-JARVIS-003
**Related components:** `jarvis.agents.subagents.jarvis_reasoner`, `langgraph.json`
**Depends on:** [DDR-010](DDR-010-single-async-subagent-supersedes-four-roster.md), [DDR-013](DDR-013-langgraph-json-at-repo-root.md), [ADR-ARCH-015](../../../architecture/decisions/ADR-ARCH-015-ci-ruff-mypy-pytest.md)

## Context

The Phase 2 scope document left open: *"Each graph has a `graph_id` matching the subagent name. The graphs are compiled at module import time (or lazily at first use — the ADR from `/system-design` pins which)."*

Two options:

- **Module-import compilation.** `graph = create_deep_agent(...)` runs at `import jarvis.agents.subagents.jarvis_reasoner`. `langgraph.json` resolves `./src/jarvis/agents/subagents/jarvis_reasoner.py:graph` at startup; missing provider keys fail immediately.
- **Lazy-at-first-use compilation.** `graph = None` at import; a `get_graph()` function compiles on first call. Startup is faster; errors surface at first dispatch.

LangGraph's server convention (per the 19 April 2026 SDK review) is that `langgraph.json` entries resolve to module-level graph variables. Lazy compilation requires a wrapper that still exposes a graph-shaped attribute at import, which adds indirection without removing the need to resolve the underlying module.

## Decision

Subagent graphs — currently only `jarvis_reasoner` per DDR-010 — compile at **module-import time**. Concretely, `src/jarvis/agents/subagents/jarvis_reasoner.py` exposes:

```python
from __future__ import annotations

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from jarvis.agents.subagents.prompts import ROLE_PROMPTS, RoleName

# Module-import-time compile. Errors raised here fail startup cleanly
# and are caught by `langgraph dev` validation + ADR-ARCH-015's CI gates.
_model = init_chat_model("openai:jarvis-reasoner")

# The graph reads `input["role"]` at its first node, resolves the system
# prompt from ROLE_PROMPTS[RoleName(role)], and runs the DeepAgents loop
# with that prompt. Implementation detail of create_deep_agent wiring is
# out of scope for this DDR; the contract is that `graph` is a compiled
# CompiledStateGraph ready for ASGI invocation.
graph = create_deep_agent(
    model=_model,
    tools=[],                              # leaf subagent; no further dispatch
    system_prompt=ROLE_PROMPTS[RoleName.PLANNER],  # default — overridden per invocation
    subagents=[],
)
```

Role resolution happens at the graph's first node (not at module import), but the graph itself — the `CompiledStateGraph` object that `langgraph.json` references — is a module-import-time artefact.

`langgraph.json` at the repo root (per [DDR-013](DDR-013-langgraph-json-at-repo-root.md)) references this attribute directly:

```json
{
  "graphs": {
    "jarvis": "./src/jarvis/agents/supervisor.py:graph",
    "jarvis_reasoner": "./src/jarvis/agents/subagents/jarvis_reasoner.py:graph"
  }
}
```

## Rationale

- **Fail-fast validation matches ADR-ARCH-015 CI posture.** Missing provider keys, malformed `init_chat_model` aliases, or misconfigured `OPENAI_BASE_URL` surface at startup, not on the first Rich-typed prompt. Lazy compilation would push the failure mode to user-facing latency, worsening the attended-conversation UX.
- **`langgraph dev` validation is deterministic.** The server loads each graph at startup and asserts it's a `CompiledStateGraph`. Lazy compilation would require `langgraph dev` to either call the resolver or accept a sentinel — extra moving parts.
- **Preview-feature exposure window widens the CI net.** DeepAgents 0.5.3's `AsyncSubAgent` is a preview; compile-time exercise of the subagent graph means CI catches 0.6-preview-divergence on every PR, not only on routing-e2e-test runs.
- **Startup cost is negligible for Phase 2.** `init_chat_model` does no network I/O; `create_deep_agent` builds a `CompiledStateGraph` via LangGraph internals (microseconds). With one subagent, the entire subagents import graph adds sub-millisecond startup; lazy would be a premature optimisation.

## Alternatives considered

1. **Lazy-at-first-use.** Rejected. Pushes config errors from startup to interactive latency; complicates `langgraph.json` resolution; no measurable startup-time win at the current subagent cardinality.

2. **Hybrid — module-import for `langgraph.json`-referenced graphs, lazy for internal-only graphs.** Not applicable in v1 (no internal-only subagent graphs). Revisit if Jarvis grows non-LangGraph-registered subagent patterns.

3. **Compile in `build_async_subagents(config)` (runtime factory).** Rejected. `build_async_subagents` returns `AsyncSubAgent` TypedDicts (metadata), not graphs — the graphs are resolved separately by `langgraph.json` at deployment time. Coupling graph compilation to a runtime factory would require both paths to agree on a model-aliasing mechanism, doubling the failure surface.

## Consequences

**Positive:**
- Single source of truth for graph compilation: the subagent module itself.
- `import jarvis` (or any transitive import) surfaces subagent-graph errors immediately — valuable for the supervisor factory's unit tests in `test_supervisor_with_subagents.py`.
- FEAT-JARVIS-008's learning flywheel can `import jarvis.agents.subagents.jarvis_reasoner` to introspect the graph without the lazy-compilation side-effect ordering problem.

**Negative:**
- Importing `jarvis.agents.subagents.jarvis_reasoner` requires `OPENAI_BASE_URL` (or equivalent) to be set, even in test contexts. Test fixtures use a `test_config` with `JARVIS_SUPERVISOR_MODEL=openai:jarvis-reasoner` pointed at an unreachable-but-syntactically-valid URL; `init_chat_model` instantiation does not issue a network request (verified in Phase 1 scaffolding — [FEAT-JARVIS-001 `test_supervisor.py`](../../../../src/jarvis/agents/supervisor.py)). Documented in `tests/conftest.py` fixtures.
- Adding a new subagent in a future feature is slightly more work than the lazy case (create module + ensure import-safe). Acceptable — new subagents are rare and should carry a DDR of their own anyway (DDR-010's commit-message-justification principle).

## Links

- DDR-010 — single async subagent
- DDR-013 — `langgraph.json` at repo root
- ADR-ARCH-015 — CI = ruff + mypy + pytest
- Phase 2 scope doc — open question "module import vs lazy-at-first-use"
