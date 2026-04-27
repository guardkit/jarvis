# Review Report: FEAT-JARVIS-003 — Async Subagent + Attended Frontier Escape

**Mode:** architectural · **Depth:** standard · **Date:** 2026-04-26
**Subject:** Post-merge review of FEAT-JARVIS-003 (merge commit `49dcbd0`).
**Anchors:** [phase2-dispatch-foundations-scope.md](../../docs/research/ideas/phase2-dispatch-foundations-scope.md) (partially superseded), [phase2-build-plan.md](../../docs/research/ideas/phase2-build-plan.md), [design.md](../../docs/design/FEAT-JARVIS-003/design.md), DDR-010..015, ADR-ARCH-001/011/012/027.
**Reviewer:** Claude Code `/task-review` (architectural mode).

---

## Executive Summary

FEAT-JARVIS-003 successfully reconciles the original four-cloud-subagent scope with the four superseding ADRs (ARCH-001/011/012/027) and ships the canonical shape: one local `jarvis-reasoner` AsyncSubAgent with a closed `RoleName` enum (critic/researcher/planner), a `LlamaSwapAdapter` slot for swap-aware voice latency, a constitutional `escalate_to_frontier` cloud escape, and a 2-graph `langgraph.json` ASGI deployment. The 24 subtasks landed across 8 AutoBuild waves with zero failures; 1585 tests pass; the routing E2E (TASK-J003-023), role propagation (TASK-J003-022), and roster regression (TASK-J003-020) all hold.

**Score: 80 / 100.** Strong structural correctness and excellent docstring/contract discipline, but **two substantive defects** open material risk:

1. **Layer 2 of the belt+braces gate on `escalate_to_frontier` is dormant in production** — the resolver hooks DDR-014 designates for `lifecycle.startup` wiring are never assigned in `src/`. The constitutional gate runs as Layer-1+Layer-3 in production (Layer 1 = prompt/docstring; Layer 3 = registration-absence) instead of the documented three-layer guarantee.
2. **Phase 2 close criterion #9 ("ruff + mypy clean on `src/jarvis/`") is not met** — 9 mypy errors and 8 ruff errors remain in `src/jarvis/`, including a `Literal["attended_only"]` arg-type mismatch in the Layer-2 helper that flags exactly the production gap above.

Recommend **[I]mplement** with a small follow-up wave (3 tasks) to wire Layer 2, fix the mypy contract, and pre-seed `OPENAI_API_KEY` for fresh-env test collection. Findings F4–F7 are forward-compat polish, not blockers.

---

## Review Details

| | |
|---|---|
| **Mode** | Architectural |
| **Depth** | Standard |
| **Trade-off priority** | Balanced (defaulted; no clarification questions asked — context already heavily anchored by 3 `--context` paths) |
| **Subject** | Already-merged feature (no decision-to-build; review is post-mortem + follow-up scoping) |
| **Reviewer** | architectural-reviewer pattern, executed inline |

### Method

1. Loaded scope (phase2-dispatch-foundations-scope.md), build plan (phase2-build-plan.md), design (design/FEAT-JARVIS-003/design.md), 6 DDRs (DDR-010..015), 4 superseding ADRs (ARCH-001/011/012/027).
2. Read load-bearing modules: `subagent_registry.py`, `tools/dispatch.py` (full), `agents/subagents/{jarvis_reasoner,prompts,types}.py`, `infrastructure/lifecycle.py`, `agents/supervisor.py`, `adapters/llamaswap.py`, `langgraph.json`.
3. Ran ruff, mypy, pytest (1585 passed / 2 skipped with `OPENAI_API_KEY=stub`), focused test suites for routing E2E (37/37), regression (12/12), langgraph.json (26/26), escalate (78/78 across two modules).
4. Compared landed surface against original scope's "files that will change" + "success criteria" tables, accounting for the 2026-04-23 supersession.

### Graphiti

Knowledge-graph context unavailable in this session (`mcp__graphiti__*` tools deferred-only and not loaded). No prior FEAT-J002 review findings or ADR rationale was injected — review is sourced entirely from on-disk context.

---

## Findings

### F1 — Layer 2 of `escalate_to_frontier` belt+braces gate is **dormant in production** ⚠️ HIGH

**Evidence**

- `src/jarvis/tools/dispatch.py:559-560`:
  ```python
  _current_session_hook: Callable[[], Session | None] | None = None
  _async_subagent_frame_hook: Callable[[], bool | None] | None = None
  ```
- `src/jarvis/tools/dispatch.py:642-645` (`_check_attended_only`):
  ```python
  if _current_session_hook is None and _async_subagent_frame_hook is None:
      # Layer 2 is dormant — production startup wires the hooks; tests
      # for Layer 1 exercise the body directly.
      return None
  ```
- DDR-014 §"Layer 2": *"Production wiring lands in `jarvis.infrastructure.lifecycle.startup` — the lifecycle module assigns these hooks to a SessionManager-backed resolver and (when DeepAgents 0.5.3 exposes the metadata) the middleware probe."*
- `grep -rn "_current_session_hook\|_async_subagent_frame_hook" src/`: only the *definitions* in dispatch.py — **no assignment site** in any startup or wiring module.
- `lifecycle.py` does not import or touch the dispatch hooks.

**Impact**

In production today, the belt+braces gate has two layers, not three:

| Layer | Source | Status |
|---|---|---|
| 1 — Prompt + docstring | supervisor_prompt.py + tool docstring | ✅ Active |
| 2 — Executor assertion | dispatch.py `_check_attended_only` | ❌ **Dormant** (no rejection) |
| 3 — Registration absence | `assemble_tool_list(include_frontier=False)` | ✅ Active for ambient consumers — **but no ambient consumer exists yet** (see F4) |

ADR-ARCH-022 requires *at least* two layers; FEAT-J003 design promised three because cloud spend is irreversible (DDR-014 §Rationale). The shipped surface has effectively *one* hard layer (Layer 3 / registration absence) plus a social rule (Layer 1 / prompt). A spoofed-ambient call from an attended session running an async-subagent frame — exactly the case Layer 2 was designed to catch — will not be blocked.

The gap is not exposed by the test suite because every Layer-2 test (`test_escalate_to_frontier.py`) explicitly assigns the hooks per-test and tears them down on cleanup. Production has no equivalent assignment, so all observability-tests pass while the production binary lacks the gate.

**Severity rationale**

ADR-ARCH-027 ("attended-only cloud escape hatch") is the *whole reason* `escalate_to_frontier` exists as a constitutional tool rather than a free function. The supervisor reasoning model is configured to follow Layer 1 (prompt rule); Layer 3 protects against a future ambient consumer registering its own tool list. Layer 2 is the ONLY layer that protects against an in-process spoofed-ambient call from an attended session — exactly the runtime-rather-than-design-time risk the ADR cares about.

**Fix (small)**

Add to `lifecycle.build_app_state` after the `SessionManager` is built:

```python
from jarvis.tools import dispatch as _dispatch

_dispatch._current_session_hook = lambda: session_manager.current_session()
# AsyncSubAgentMiddleware metadata probe (preferred):
_dispatch._async_subagent_frame_hook = lambda: _middleware_in_subagent_flag()
# Fallback: leave None — _is_async_subagent_frame() falls back to
# session.metadata['currently_in_subagent'].
```

If `SessionManager.current_session()` doesn't exist yet, the session-state fallback path (`session.metadata["currently_in_subagent"]`) on its own is acceptable Phase 2 wiring per ASSUM-FRONTIER-CALLER-FRAME — the design explicitly allows either resolver alone.

---

### F2 — Module-import compilation requires `OPENAI_API_KEY`; conftest doesn't pre-seed ⚠️ MEDIUM

**Evidence**

- DDR-012 mandates that the `jarvis_reasoner` graph compile at module import: `src/jarvis/agents/subagents/jarvis_reasoner.py:393` calls `_build_graph()` at module scope, which calls `init_chat_model("openai:jarvis-reasoner")` at line 347.
- `init_chat_model` constructs `ChatOpenAI(...)`, which raises `OpenAIError("api_key client option must be set...")` if `OPENAI_API_KEY` is not in `os.environ` (regardless of `OPENAI_BASE_URL`).
- `tests/conftest.py` autouse fixture clears the cwd via `monkeypatch.chdir(tmp_path)` but does **not** monkeypatch `os.environ["OPENAI_API_KEY"]`.
- `pytest tests/` in a clean shell: collection fails with `ERROR collecting tests/test_async_task_input.py` because `from jarvis.agents.subagents.types import AsyncTaskInput` triggers the `__init__.py` re-export of `graph`, which triggers the OpenAI key check.
- With `OPENAI_API_KEY=stub` set: `1585 passed, 2 skipped`.

**Impact**

- Fresh-env test collection breaks (CI on a runner without the env var; new contributors after `git clone`).
- The DDR-012 promise — *"langgraph dev gives deterministic startup validation and fails fast on missing provider keys"* — is realised, but the test suite shouldn't be paying that cost. Tests should compile the graph against a synthetic provider, not the real OpenAI client.
- The README quickstart (`.claude/CLAUDE.md`) doesn't mention this.

**Fix (small)**

Either:

(a) `tests/conftest.py` — autouse: `monkeypatch.setenv("OPENAI_API_KEY", "stub-for-tests")` (clearest, smallest diff); OR
(b) `jarvis_reasoner.py` — defer the `init_chat_model` call into `_build_graph` body but compile lazily on first dispatch (relax DDR-012 to "compile at first use"); OR
(c) Document the requirement in `pyproject.toml`'s test entry-point and `.env.example`.

Path (a) is least disruptive; document the choice in `tests/conftest.py` next to the existing `_isolate_dotenv` fixture.

---

### F3 — Phase 2 success criterion #9 not met: 9 mypy + 8 ruff errors in `src/jarvis/` ⚠️ MEDIUM

Phase-2 close criterion #9 (build-plan.md): *"Ruff + mypy clean on new `src/jarvis/` modules."*

**Mypy** (9 errors, all in `src/jarvis/`):

| File | Lines | Error |
|---|---|---|
| `tools/dispatch.py` | 661, 678 | `_emit_frontier_log` `outcome` Literal omits `"attended_only"`; Layer-2 callers pass `"attended_only"` literally — **type checker flags exactly the documented design contract 4 outcome list** (`success / config_missing / attended_only / provider_unavailable / degraded_empty`). |
| `tools/dispatch.py` | 349, 356, 359 | Unreachable-branch noise from the tagged-tuple match. Cosmetic. |
| `tools/dispatch.py` | 944 | Defensive fallthrough is unreachable per Pydantic coercion. Cosmetic. |
| `tools/general.py` | 187 | Statement is unreachable. Cosmetic. |
| `agents/subagents/jarvis_reasoner.py` | 254 | `_make_role_runner` missing return annotation (`-> Callable[[_ReasonerState], Awaitable[dict[str, Any]]]`). |
| `agents/subagents/jarvis_reasoner.py` | 374 | `add_conditional_edges` mapping arg type. Probably a langgraph stub gap. |

The two **substantive** errors are at lines 661 and 678: they expose F1's gap structurally — Layer 2 was added (TASK-J003-011) but `_emit_frontier_log`'s `outcome` Literal (TASK-J003-010 / Contract 4) was not extended to include the new outcome. This is the kind of coupled-update miss that mypy is supposed to catch — and it did, but the gate didn't block the merge.

**Ruff** (8 errors in `src/jarvis/`):

- `UP042` (×2) — `RoleName(str, Enum)` and `FrontierTarget(str, Enum)` should migrate to `enum.StrEnum` (Python 3.11+; project pins 3.12). One-line fix per class but check `RoleName("")` / `RoleName("CRITIC")` ValueError shape stays identical (it does — `StrEnum` raises `ValueError` the same way; ASSUM-004 holds).
- `RUF022` (×2) — `__all__` not sorted in `tools/__init__.py` and one other module.
- `UP037` (×2) — `from __future__ import annotations` lets you drop quotes on type annotations.
- `RUF002` — Ambiguous EN DASH `–` in a docstring.
- `I001` — Import block sort/format.

All ruff errors are autofixable with `ruff check --fix`. None affect runtime.

**Impact**

Build hygiene drift; Phase-2 close criterion #9 unsatisfied — should either be fixed or the criterion explicitly relaxed in the build-plan status log.

**Fix (trivial)**

1. `tools/dispatch.py`: extend `_emit_frontier_log`'s `outcome` Literal to add `"attended_only"`. Single line change. Removes 2 mypy errors and ratifies design contract 4.
2. `ruff check src/jarvis/ --fix` for the 4 autofixable; manually fix UP042 (StrEnum migration) and RUF002.
3. Add unreachable-branch suppressions or restructure the tagged-tuple match if the noise is to be retired vs. tolerated.

---

### F4 — Layer 3 ambient_tool_factory has no production consumer ⚠️ LOW (forward-compat)

The `_jarvis_ambient_tool_factory` graph attribute is set in `build_supervisor` but only read by tests. No `src/jarvis/watchers/`, `src/jarvis/learning/`, or Pattern-C entry point consumes it (those packages are reserved-empty per FEAT-JARVIS-001 TASK-J001-010).

This is **not a defect** — Pattern B watchers land in FEAT-J004+ and the ADR-ARCH-027 ambient gate is forward-compatible. Recording it here so the FEAT-J004 design recovers the constraint: any module that builds its own tool list must call `getattr(graph, AMBIENT_TOOL_FACTORY_ATTR)()` rather than re-deriving from lifecycle state. A test could be added now to assert that the `watchers/` and `learning/` packages do not import `escalate_to_frontier` directly — preserving Layer 3 as a packaging invariant.

---

### F5 — `FrontierEscalationContext.session_id` is hard-coded to placeholder ⚠️ LOW

`dispatch.py:516`: `_FRONTIER_SESSION_PLACEHOLDER: str = "frontier-call"` — used at line 709 in every `_emit_frontier_log` call regardless of whether `_resolve_current_session()` returned a real session.

When FEAT-J004 lights up Graphiti writes to `jarvis_routing_history`, every cloud escalation will be tagged with the same `session_id` value, breaking per-session correlation.

The author's note at line 514 explicitly defers real session id plumbing ("the placeholder remains the value used in the structured log records so the FrontierEscalationContext.session_id constraint stays satisfied without leaking caller state into telemetry"). The "leaking caller state" framing reads as ADR-ARCH-029 caution — but session ids are not PII; the redaction posture is about *instruction body*, not metadata. This deserves a re-read at FEAT-J004 design time.

**Fix (small, deferred)**

Plumb `session.session_id` through `_check_attended_only` → `_emit_frontier_log` once F1 is wired. Add a test that `session_id` in the log record matches the active session.

---

### F6 — `frontier_default_target` config field is declared but not read ⚠️ LOW

`design.md §8` "Frontier escalation contract": *"Default target is `google_genai:gemini-3.1-pro`; `target=FrontierTarget.OPUS_4_7` switches…"*
`@tool` signature: `escalate_to_frontier(instruction: str, target: FrontierTarget = FrontierTarget.GEMINI_3_1_PRO)` — literal default, not config-driven.
`config.settings.frontier_default_target` field exists per integration contract 8 (IMPLEMENTATION-GUIDE.md line 346) but `dispatch.py` does not read it.

If the field is kept for FEAT-J004 budget-policy levers (per-budget-window default switching), document it explicitly. Otherwise YAGNI it.

---

### F7 — Adapter label in log = provider, not session ⚠️ LOW (semantic shift)

`FrontierEscalationContext.adapter` carries `"google-genai"` / `"anthropic"` (provider tag) rather than the session adapter (`"cli"`, `"telegram"`, `"reachy"`, `"dashboard"`). This is a deliberate post-design choice — fine for budget bucketing per ADR-ARCH-030 — but it creates a naming collision with `Session.adapter` (the user-channel id). Consider renaming the field to `provider` or `cloud_adapter` when FEAT-J004 lands the schema.

---

## Strengths

The strengths catalogue is unusually long for a single feature, which is why the score holds at 80 even with F1+F3 outstanding.

1. **Faithful supersession.** Every line of phase2-dispatch-foundations-scope.md's FEAT-J003 section is reconciled in the design doc and DDRs. The four-roster is gone from `src/`, `tests/`, and supervisor prompt; TASK-J003-020's grep regression locks this in.
2. **Excellent contract documentation.** Module docstrings cite ADR/DDR/AC by number for every load-bearing decision. A reviewer six months from now will be able to reason about *why* the code looks the way it does without spelunking commit history.
3. **DDR-010 routing description is exactly the contract IMPLEMENTATION-GUIDE.md §4 Contract 6 specifies.** All 6 mandatory substrings present (`gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`); 0 forbidden substrings (verified by TASK-J003-020).
4. **ADR-ARCH-029 redaction holds.** Instruction body never appears in error returns or log records; only `instruction_length`. Provider-side error messages are normalised to `type(exc).__name__` to prevent SDK-message leakage of caller input.
5. **Snapshot-isolation contract intact.** `assemble_tool_list` returns fresh lists; `build_async_subagents` constructs a new dict + list per call; ASSUM-006 honoured throughout.
6. **`langgraph.json` minimal and correct.** Two graphs, ASGI transport, env file, python_version. Per DDR-013 / ADR-ARCH-031 default. `python -c "import json; …"` validates it.
7. **Routing E2E coverage is faithful to design.md §9.** All 7 prompts parametrized; assertions are tool-call-sequence (structural), not natural-language (behavioural) — exactly the Player-Coach test pattern the scope doc nominated.
8. **Quality bar in tests is high.** 78 tests across the three frontier/escalate modules; 16 voice-ack scenarios; 12 role-propagation tests; 12 regression tests; 26 langgraph.json validation tests. Tests assert real invariants (description substrings, log-field set, registration-list shape) rather than pass-through structure.
9. **AutoBuild discipline.** 24/24 across 8 waves, zero failures, every wave router reported `task_failures: 0`. Preview-feature risk (DeepAgents 0.5.3 `AsyncSubAgentMiddleware` + ASGI multi-graph) cleared on first attempt.
10. **Voice-ack policy correctly implements ADR-ARCH-012 boundary table.** Strict-greater threshold at 30 seconds; default voice-reactive set is `{reachy}`; helper signature lets a future adapter opt in via the `voice_reactive_adapters=` kwarg without touching the module global.

---

## Decision Matrix

| Option | Score | Effort | Risk | Recommendation |
|---|---|---|---|---|
| **[A]ccept** — close FEAT-J003 as-is, file F1/F2/F3 as separate tasks | 6/10 | none | Layer 2 dormant in production for unknown duration; `OPENAI_API_KEY` requirement undocumented for new contributors | not recommended |
| **[R]evise** — re-run review against FEAT-J002 to triangulate | 4/10 | 1 day | The supersession (DDR-010..015) is already adjudicated; deeper analysis won't surface different blockers | not recommended |
| **[I]mplement** — small follow-up wave fixing F1 + F2 + F3 (3 tasks) | **9/10** | ~half day | Low — all three are scoped, well-understood, and have clear acceptance criteria | **recommended** |
| **[C]ancel** — discard review | 0/10 | none | Findings unrecorded | not recommended |

---

## Recommended Follow-Up (if [I]mplement)

**Wave: FEAT-J003-FIX — close Phase 2 close criteria, restore Layer 2 gate**

| # | Title | Complexity | Mode | Notes |
|---|---|---|---|---|
| FIX-001 | Wire `_current_session_hook` + `_async_subagent_frame_hook` in `lifecycle.build_app_state` | 4 | task-work (TDD) | Add an integration test that asserts a spoofed-ambient call (attended adapter + `currently_in_subagent=True`) is rejected through the lifecycle-built supervisor, not just the unit-tested dispatch tool. |
| FIX-002 | Extend `_emit_frontier_log`'s `outcome` Literal to include `"attended_only"`; clear remaining ruff drift in `src/` (StrEnum migration, `__all__` sort) | 2 | direct | Re-runs Phase-2 close criterion #9 to green. |
| FIX-003 | Pre-set `OPENAI_API_KEY` stub in `tests/conftest.py` autouse fixture; document in `.env.example` | 1 | direct | Restores fresh-env `pytest tests/` collection. |

Optional follow-ups (defer to FEAT-J004 design):
- F5 — plumb real `session_id` into `FrontierEscalationContext` (post-FIX-001, free).
- F6 — wire or remove `frontier_default_target` config field.
- F7 — rename `adapter` → `provider` in `FrontierEscalationContext` if appropriate.

Estimated wall-clock: half a day at AutoBuild's FEAT-J002/J003 cadence (1 wave, 3 tasks, 2 of which are direct).

---

## Appendix A — Quality-gate evidence

| Gate | Outcome |
|---|---|
| `uv run pytest tests/` (no env) | ❌ Collection error — `OpenAIError: api_key client option must be set` |
| `OPENAI_API_KEY=stub uv run pytest tests/` | ✅ 1585 passed, 2 skipped, 197 warnings, 6.73s |
| `uv run ruff check src/jarvis/` | ❌ 8 errors |
| `uv run ruff check tests/` | ❌ 28 errors (out of scope for Phase 2 #9, but worth tracking) |
| `uv run mypy src/jarvis/` | ❌ 9 errors in 3 files (39 source files checked) |
| `tests/test_no_retired_roster_strings.py` (regression) | ✅ 12/12 |
| `tests/test_langgraph_json.py` (smoke) | ✅ 26/26 |
| `tests/test_routing_e2e.py` (acceptance) | ✅ 25/25 |
| `tests/test_role_propagation_e2e.py` (integration) | ✅ 12/12 |
| `tests/test_escalate_to_frontier.py` + `test_tools_escalate_to_frontier_layer2.py` | ✅ 50+/50+ |
| `langgraph.json` validity | ✅ JSON parses; 2 graphs (`jarvis`, `jarvis_reasoner`); ASGI transport |

## Appendix B — Phase-2 close criteria status (build-plan.md §"Success Criteria")

| # | Criterion | Status |
|---|---|---|
| 1 | All Phase 1 tests still pass (zero regressions) | ✅ via 1585-pass run |
| 2 | 10 Phase 2 tools registered + tested (FEAT-J002 baseline) | ✅ (FEAT-J002 scope) |
| 3 | 4 `AsyncSubAgent` instances built — **superseded → 1 `jarvis-reasoner`** | ✅ per DDR-010 |
| 4 | Routing E2E passes 7 canned prompts | ✅ |
| 5 | `jarvis chat` exhibits expected behaviour | ⏸ Manual — unchecked in IMPLEMENTATION-GUIDE |
| 6 | `langgraph dev` spins both graphs | ⏸ Manual — unchecked in IMPLEMENTATION-GUIDE |
| 7 | Capability catalogue stub renders | ✅ (FEAT-J002 scope) |
| 8 | `quick_local` fallback covered — **superseded → swap-aware voice-ack** | ✅ per DDR-015 / ADR-ARCH-012 |
| 9 | Ruff + mypy clean on new src/jarvis/ | ❌ 8 ruff + 9 mypy errors (F3) |
| 10 | Memory Store round-trip from Phase 1 still works | ✅ via session tests |

Three checkboxes (#5, #6, plus the ambient-rejection criterion) are manual validations the AutoBuild cycle can't verify. Recommend a one-liner shell session before closing the phase: `OPENAI_API_KEY=… GOOGLE_API_KEY=… uv run python -m langgraph dev` plus a manual `jarvis chat` round.

---

*Generated 2026-04-26 — `/task-review FEAT-JARVIS-003 --mode=architectural --depth=standard`*
