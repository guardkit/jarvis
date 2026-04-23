# API Contract — `jarvis-reasoner` AsyncSubAgent

> **Feature:** FEAT-JARVIS-003
> **Surface type:** DeepAgents `AsyncSubAgent` entry — metadata contract (name + description + graph_id + input schema)
> **Protocol:** In-process via `AsyncSubAgentMiddleware`; ASGI transport per [DDR-013](../decisions/DDR-013-langgraph-json-at-repo-root.md)
> **Consumers:** Jarvis supervisor reasoning model (invokes via `start_async_task`)
> **Generated:** 2026-04-23

---

## Overview

FEAT-JARVIS-003 exposes **one** `AsyncSubAgent` to the Jarvis supervisor per [DDR-010](../decisions/DDR-010-single-async-subagent-supersedes-four-roster.md). It backs all three routing roles defined in [DDR-011](../decisions/DDR-011-role-enum-closed-v1.md) via prompt-only differentiation of the single `gpt-oss-120b` model behind the `jarvis-reasoner` llama-swap alias.

The contract is the **description string** and the **`input` schema**. The supervisor's reasoning model reads the description at every routing decision; changes to description text change routing behaviour and require commit-message justification (scope-doc invariant preserved after the [DDR-010](../decisions/DDR-010-single-async-subagent-supersedes-four-roster.md) reframe).

---

## AsyncSubAgent Entry

Defined in `src/jarvis/agents/subagent_registry.py`:

```python
from deepagents import AsyncSubAgent
from jarvis.config.settings import JarvisConfig


def build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]:
    """Return the list of AsyncSubAgent instances wired into the supervisor.

    v1 ships exactly one — `jarvis-reasoner` — per ADR-ARCH-011 and DDR-010.
    Adding a new subagent requires a DDR of its own.
    """
    return [
        AsyncSubAgent(
            name="jarvis-reasoner",
            graph_id="jarvis_reasoner",
            description=(
                "Local reasoning subagent backed by gpt-oss-120b (MXFP4, Blackwell-optimised) "
                "via llama-swap alias `jarvis-reasoner` on GB10. Accepts a `role` input "
                "selecting one of three role modes: `critic` (adversarial evaluation), "
                "`researcher` (open-ended research with web tools), `planner` (multi-step "
                "planning). No cloud cost, no privacy risk — all inference stays on the "
                "premises. Typical latency: sub-second per turn when the model is loaded; "
                "2–4 minutes cold-swap if `qwen-coder-next` was previously loaded (the "
                "supervisor will emit a voice ack if so per ADR-ARCH-012). Prefer this for "
                "any task that requires sustained reasoning beyond a single turn. Do not "
                "use for arithmetic (use `calculate`), factual lookups (use `search_web`), "
                "file reads (use `read_file`), or frontier-tier work that Rich has "
                "explicitly asked to escalate (use `escalate_to_frontier` — attended only)."
            ),
        ),
    ]
```

### Fields

| Field | Value | Contract |
|---|---|---|
| `name` | `"jarvis-reasoner"` | Supervisor addresses subagent by this name in `start_async_task(name=...)`. **Stable** — changes break every routing call site. |
| `graph_id` | `"jarvis_reasoner"` | Key in `langgraph.json` (Python underscore to preserve JSON-key convention). Resolves to `src/jarvis/agents/subagents/jarvis_reasoner.py:graph`. **Stable.** |
| `description` | the docstring-shaped string above | **The authoring contract with the reasoning model.** Changes alter routing behaviour; require commit-message justification and a `test_routing_e2e.py` regression check. |

---

## `input` Schema

Callers invoke the subagent via `start_async_task`:

```python
start_async_task(
    name="jarvis-reasoner",
    input={
        "prompt": "<the instruction rendered from Rich's request, possibly with quoted context>",
        "role": "critic",                   # one of "critic", "researcher", "planner"
        "correlation_id": "<session.correlation_id>",
    },
)
```

| Key | Type | Required | Description |
|---|---|---|---|
| `prompt` | `str` | yes | The full instruction for the subagent to work on. The supervisor renders this from Rich's request + any tool results + any relevant context slices. |
| `role` | `str` | yes | One of the `RoleName` enum values (see [models/DM-subagent-types.md](../models/DM-subagent-types.md)): `"critic"`, `"researcher"`, `"planner"`. Selects the subagent's system prompt for this invocation. Invalid values return a structured error per ADR-ARCH-021. |
| `correlation_id` | `str` | no | UUID from the originating session. If absent, the subagent generates one for trace-richness. Flows into `jarvis_routing_history` writes in FEAT-JARVIS-004. |

The schema is enforced at the subagent graph's first node — it validates `role` against `RoleName` and returns via the `async_tasks` channel if invalid:

- Unknown role: `"ERROR: unknown_role — expected one of {critic, researcher, planner}, got=<value>"`
- Missing `prompt`: `"ERROR: missing_field — prompt is required"`

---

## Supervisor-facing tool surface (auto-injected by `AsyncSubAgentMiddleware`)

Wiring the subagent list into `create_deep_agent(async_subagents=...)` causes DeepAgents 0.5.3's `AsyncSubAgentMiddleware` to inject five tools into the supervisor graph. These are **middleware-provided** — not authored in `jarvis.tools.*` — but are part of the FEAT-JARVIS-003 contract surface because the supervisor prompt teaches the reasoning model how to call them.

| Tool | Purpose | Jarvis usage |
|---|---|---|
| `start_async_task(name, input)` | Launch subagent; returns `task_id` immediately | Every role-dispatch invocation |
| `check_async_task(task_id)` | Poll for status; returns running/complete/error + partial output | Supervisor decides "should I keep waiting?" mid-reasoning |
| `update_async_task(task_id, update)` | Mid-flight steering | Reserved for v1.5 — not used by the supervisor prompt in Phase 2 |
| `cancel_async_task(task_id)` | Terminate a running subgraph | Rich-initiated via CLI `cancel` (FEAT-JARVIS-009), not used by supervisor reasoning directly |
| `list_async_tasks()` | Enumerate all live async tasks | Reserved for Rich-facing surfaces (Dashboard FEAT-JARVIS-009) |

The supervisor's `## Subagent Routing` prompt section (see [design.md §10](../design.md)) names only `start_async_task` and `check_async_task` as reasoning-time tools. The other three are operational — they appear in the tool catalogue but aren't the reasoning model's everyday path.

---

## Output contract

The subagent graph returns output via the `async_tasks` state channel per DeepAgents 0.5.3 conventions. Shape:

```python
# Via check_async_task(task_id=...) return:
{
  "task_id": "<uuid>",
  "status": "complete" | "running" | "error",
  "result": "<string output from the subagent graph>" | None,
  "error": "<structured error string>" | None,  # ERROR: / DEGRADED: / TIMEOUT: prefix per ADR-ARCH-021
}
```

Happy-path `result` is always a string. Phase 2 does not commit to structured JSON output — role-mode differentiation is entirely in the prompt; if a role returns structured output, it's a prompt-level contract between the role prompt and the caller, not a subagent-shape contract. FEAT-JARVIS-008 (learning flywheel) may revisit if structured role output becomes useful.

---

## Error modes

Per [ADR-ARCH-021](../../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md), the subagent graph never raises; it returns structured error strings via `async_tasks`:

| Prefix | Example | Cause |
|---|---|---|
| `ERROR: unknown_role` | `ERROR: unknown_role — expected one of {critic, researcher, planner}, got=bard` | Caller passed an invalid `role` value |
| `ERROR: missing_field` | `ERROR: missing_field — prompt is required` | `input` dict lacked a required key |
| `ERROR: model_unavailable` | `ERROR: model_unavailable — llama-swap alias jarvis-reasoner not found; check llama-swap /running` | `init_chat_model` resolution or llama-swap-side error |
| `DEGRADED: swap_slow` | `DEGRADED: swap_slow — cold swap in progress, eta=240s` | llama-swap cold-load underway; result will arrive, latency is high |
| `TIMEOUT: subagent` | `TIMEOUT: subagent — task_id=<uuid> exceeded 600s` | Task-level timeout; FEAT-JARVIS-008 may adjust per-role defaults |

---

## Stability policy

- **`name` and `graph_id`** are stable across minor versions. Changing either is a breaking change for `langgraph.json`, the supervisor factory call, and every routing test.
- **`description`** may be refined for routing-quality wins but changes require (a) a commit-message justification per DDR-010 and the scope-doc invariant, (b) a `test_routing_e2e.py` run showing no regression on the seven canned prompts.
- **`input` schema** is additive: new keys may be added with safe defaults. Removing a key or changing its type requires a DDR.

---

## Traceability

- **ADR-ARCH-011** — single-subagent design
- **ADR-ARCH-031 (Forge)** — AsyncSubAgent pattern source
- **DDR-010** — supersedes four-subagent roster
- **DDR-011** — role enum
- **DDR-012** — module-import compilation
- **DDR-013** — `langgraph.json` at repo root
- **[deepagents-sdk-2026-04.md](../../../../../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md)** — 0.5.3 AsyncSubAgent preview-feature scope
