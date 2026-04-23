# API Contract — FEAT-JARVIS-003 Tool Surface

> **Feature:** FEAT-JARVIS-003
> **Surface type:** DeepAgents `@tool(parse_docstring=True)` function (1 new) + 5 middleware-provided tools
> **Protocol:** In-process — tool docstrings are the contract with the reasoning model
> **Consumers:** Jarvis supervisor reasoning model
> **Generated:** 2026-04-23

---

## 1. `escalate_to_frontier` (NEW)

Located in `src/jarvis/tools/dispatch.py` (fills the slot reserved by [FEAT-JARVIS-002 DDR-005](../../FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md) C2).

### Signature

```python
from enum import Enum
from typing import Annotated
from langchain_core.tools import tool


class FrontierTarget(str, Enum):
    GEMINI_3_1_PRO = "google_genai:gemini-3.1-pro"
    OPUS_4_7 = "anthropic:claude-opus-4-7"


@tool(parse_docstring=True)
def escalate_to_frontier(
    instruction: str,
    target: FrontierTarget = FrontierTarget.GEMINI_3_1_PRO,
) -> str:
    """Escalate to a cloud frontier model (Gemini 3.1 Pro or Claude Opus 4.7).

    ATTENDED USE ONLY. This tool is only available when Rich has explicitly
    asked for a frontier opinion ("ask Gemini", "frontier view", "cloud model").
    It is not a default escalation path — local reasoning via `jarvis-reasoner`
    is preferred. Calls from ambient watchers, learning loops, or Pattern-C
    volitional contexts are rejected with a structured error, and the tool is
    absent from ambient tool sets entirely (belt+braces per ADR-ARCH-022).

    Budget is shared £20–£50/month fleet-wide (ADR-ARCH-030); use sparingly.
    Each invocation is trace-tagged `model_alias=cloud-frontier` in logs and
    will flow into `jarvis_routing_history` once FEAT-JARVIS-004 writes go live.

    Args:
        instruction: The full prompt to send to the frontier model. Include all
            necessary context; the frontier model does not have access to the
            supervisor's tools, subagents, or session state.
        target: Which frontier to use. Default Gemini 3.1 Pro (best breadth and
            context window). Use OPUS_4_7 for adversarial critique specifically —
            Opus tends to find subtler flaws but costs more per token.

    Returns:
        The frontier model's response as a plain string. On error, returns a
        structured error string per ADR-ARCH-021:
          - "ERROR: attended_only — escalate_to_frontier rejected (<reason>)"
          - "ERROR: config_missing — <provider> key not set"
          - "DEGRADED: provider_unavailable — <detail>"
    """
```

### Behaviour

Per [DDR-014](../decisions/DDR-014-escalate-to-frontier-in-dispatch-tool-module.md), the tool enforces constitutional gating at **three layers**:

1. **Docstring (reasoning layer).** The text above is the reasoning model's instruction. The supervisor system prompt's `## Frontier Escalation` section repeats the rule.
2. **Executor assertion (tool-boundary layer).** The tool body checks:
   ```python
   session = _current_session()
   if session.adapter not in ATTENDED_ADAPTERS:           # {TELEGRAM, CLI, DASHBOARD, REACHY}
       return "ERROR: attended_only — escalate_to_frontier rejected (adapter=%s)" % session.adapter
   if _caller_is_async_subagent():                         # fail-closed on unknown
       return "ERROR: attended_only — escalate_to_frontier rejected (async-subagent frame)"
   ```
3. **Registration absence (tool-set layer).** `assemble_tool_list(..., include_frontier=False)` omits this tool from the ambient tool list entirely, so reasoning in ambient/learning contexts cannot see it to invoke.

Happy path reaches the frontier via `init_chat_model(target.value).invoke(instruction)` — direct, no llama-swap (llama-swap only fronts local models).

### Logging

Every invocation logs at INFO with prefix `JARVIS_FRONTIER_ESCALATION`:

```
JARVIS_FRONTIER_ESCALATION target=google_genai:gemini-3.1-pro session_id=<uuid> correlation_id=<uuid> adapter=cli
```

Logging structure mirrors FEAT-JARVIS-002's `JARVIS_DISPATCH_STUB` / `JARVIS_QUEUE_BUILD_STUB` prefixes so `jarvis_routing_history` ingestion (FEAT-JARVIS-004) can grep for all three dispatch categories uniformly.

### Error modes

| Return value | Cause |
|---|---|
| `ERROR: attended_only — … (adapter=<x>)` | Session is on an ambient/unknown adapter |
| `ERROR: attended_only — … (async-subagent frame)` | Called from a Pattern B watcher or `jarvis-reasoner` subagent |
| `ERROR: config_missing — GOOGLE_API_KEY not set` | `FrontierTarget.GEMINI_3_1_PRO` without key configured |
| `ERROR: config_missing — ANTHROPIC_API_KEY not set` | `FrontierTarget.OPUS_4_7` without key configured |
| `DEGRADED: provider_unavailable — <detail>` | Provider returned 429 / 5xx / timeout; reasoning model handles per ADR-ARCH-021 |

---

## 2. Middleware-provided tools (5)

Wiring `async_subagents=[...]` into `create_deep_agent(...)` causes `AsyncSubAgentMiddleware` to inject the following five tools into the supervisor's tool catalogue. Jarvis does not author or own these; the contract is that the supervisor prompt teaches the reasoning model when to use them.

| Tool | Signature | Supervisor-prompt guidance |
|---|---|---|
| `start_async_task` | `(name: str, input: dict) -> str` returning `task_id` | "Launch a sustained reasoning task via `name='jarvis-reasoner'` with `input={'role': ..., 'prompt': ...}`" |
| `check_async_task` | `(task_id: str) -> dict` returning `{status, result, error}` | "Poll if your next step depends on the subagent's result; otherwise continue the reasoning loop and poll later" |
| `update_async_task` | `(task_id: str, update: str) -> None` | *Not named in the Phase 2 supervisor prompt; reserved for v1.5.* |
| `cancel_async_task` | `(task_id: str) -> None` | *Not named in the Phase 2 supervisor prompt; driven by CLI in later features.* |
| `list_async_tasks` | `() -> list[dict]` | *Not named in the Phase 2 supervisor prompt; driven by Dashboard in later features.* |

The middleware's exact tool signatures follow DeepAgents 0.5.3 — see the [DeepAgents SDK review](../../../../../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md) for the version-pinned shape.

---

## 3. Integration with FEAT-JARVIS-002 tools

FEAT-JARVIS-003 changes no FEAT-JARVIS-002 tool surfaces. The full supervisor tool list becomes:

| Tool | Source feature | Attended | Ambient |
|---|---|---|---|
| `read_file` | FEAT-JARVIS-002 | ✅ | ✅ |
| `search_web` | FEAT-JARVIS-002 | ✅ | ✅ |
| `get_calendar_events` | FEAT-JARVIS-002 | ✅ | ✅ |
| `calculate` | FEAT-JARVIS-002 | ✅ | ✅ |
| `list_available_capabilities` | FEAT-JARVIS-002 | ✅ | ✅ |
| `capabilities_refresh` | FEAT-JARVIS-002 | ✅ | ✅ |
| `capabilities_subscribe_updates` | FEAT-JARVIS-002 | ✅ | ✅ |
| `dispatch_by_capability` | FEAT-JARVIS-002 | ✅ | ✅ |
| `queue_build` | FEAT-JARVIS-002 | ✅ | ✅ |
| **`escalate_to_frontier`** | **FEAT-JARVIS-003** | **✅** | **❌** *(absent from ambient tool list — DDR-014 Layer 3)* |
| `start_async_task` (× 5 middleware tools) | FEAT-JARVIS-003 (middleware-injected) | ✅ | ✅ |

10 tools on attended sessions; 9 on ambient. The ambient factory is hooked in this feature for the constitutional absence property; no ambient paths consume it until FEAT-JARVIS-003's Pattern B watchers are built (deferred).

---

## 4. Traceability

- **ADR-ARCH-021** — tools return structured errors, never raise
- **ADR-ARCH-022** — belt+braces constitutional rules
- **ADR-ARCH-023** — permissions constitutional, not reasoning-adjustable
- **ADR-ARCH-027** — attended-only cloud escape hatch
- **ADR-ARCH-030** — budget envelope for cloud spend
- **DDR-014** — `escalate_to_frontier` placement + gating
- **[FEAT-JARVIS-002 DDR-005](../../FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md)** — slot reservation
