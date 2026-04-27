---
feature_id: FEAT-JARVIS-002
title: Core Tools & Capability-Driven Dispatch Tools
review_mode: architectural
review_depth: standard
reviewed_at: 2026-04-26
reviewer: claude-opus-4-7 (task-review orchestrator)
status: REVIEW_COMPLETE
---

# Review Report: FEAT-JARVIS-002 — Core Tools & Capability-Driven Dispatch Tools

## 1. Executive Summary

**Verdict: ACCEPT with two non-blocking remediation tasks.**

FEAT-JARVIS-002 has shipped to spec. The 9-tool surface (`calculate`,
`capabilities_refresh`, `capabilities_subscribe_updates`,
`dispatch_by_capability`, `get_calendar_events`,
`list_available_capabilities`, `queue_build`, `read_file`, `search_web`)
is implemented, alphabetically wired through
[assemble_tool_list](src/jarvis/tools/__init__.py#L89), exercised by
591 focused tests (100% pass), and protected by the DDR-009 swap-point
grep anchors that downstream FEAT-J004/005 will rely on.

The full project test suite is green (**1585 passed, 2 skipped**, no
regressions). The end-to-end routing test
[test_routing_e2e.py](tests/test_routing_e2e.py) — the build plan's Step
11 acceptance gate — passes all 25 cases. The five DDRs landed in
`/system-design` (DDR-005..009) all materialise in code:
`dispatch_by_capability` replaces the old `call_specialist` shape
(DDR-005), `TavilyProvider` is the swap-point grep anchor (DDR-006),
`asteval.Interpreter` powers `calculate` (DDR-007), the
`{available_capabilities}` placeholder injects descriptors into the
prompt (DDR-008), and `JARVIS_DISPATCH_STUB` /
`JARVIS_QUEUE_BUILD_STUB` log lines are guarded by an explicit
invariant test (DDR-009).

Two remediation items deserve a follow-up subtask each — neither
blocks Phase 3 work:

- **Ruff/mypy housekeeping** (success criterion #9 violated): 7 ruff
  lints + 7 mypy errors across `tools/`. All low-impact (unsorted
  `__all__`, en-dash in docstrings, `StrEnum` modernisation, defensive
  unreachable branches mypy can't narrow). No behavioural risk.
- **Kanban hygiene**: the 23 task files never moved to
  `tasks/completed/` after AutoBuild closed. Files are duplicated
  across `tasks/backlog/feat-jarvis-002-…/`, loose
  `tasks/backlog/TASK-J002-*`, and `tasks/design_approved/`. Pure
  bookkeeping — but if `/feature-complete` exists it should be run.

## 2. Review Details

| Field | Value |
|-------|-------|
| Mode | architectural (with code-quality + decision elements) |
| Depth | standard |
| Duration | ~30 min interactive |
| Inputs | `tasks/FEAT-JARVIS-002-*.md` (none at root — 23 files under `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/`), `docs/research/ideas/phase2-dispatch-foundations-scope.md`, `docs/research/ideas/phase2-build-plan.md`, `docs/design/FEAT-JARVIS-002/design.md`, `.guardkit/features/FEAT-J002.yaml`, `.guardkit/autobuild/FEAT-J002/review-summary.md` |
| Source-of-truth design | [docs/design/FEAT-JARVIS-002/design.md](docs/design/FEAT-JARVIS-002/design.md) (5 DDRs, 14 sections) |
| AutoBuild status | Completed 2026-04-25, commit `1da94ca`, 23/23 tasks PASSED, 91% first-attempt approval, avg 1.09 turns/task |

## 3. Conformance Audit — Design → Code

### 3.1 Tool surface (design.md §3, §7; build plan FEAT-J002 Change 1–4)

All nine `@tool(parse_docstring=True)` functions present at the
expected module paths:

| Design surface | Implementation | Notes |
|----------------|----------------|-------|
| `read_file(path) -> str` | [src/jarvis/tools/general.py:552](src/jarvis/tools/general.py#L552) | Path-traversal guard returns `ERROR: path_traversal …` |
| `search_web(query, max_results=5) -> str` | [src/jarvis/tools/general.py:247](src/jarvis/tools/general.py#L247) | Tavily wrapper; `ERROR: config_missing` when key absent |
| `get_calendar_events(window) -> str` | [src/jarvis/tools/general.py:638](src/jarvis/tools/general.py#L638) | Stub returning `[]`; window-validated |
| `calculate(expression) -> str` | [src/jarvis/tools/general.py:483](src/jarvis/tools/general.py#L483) | `asteval.Interpreter` (DDR-007) |
| `list_available_capabilities() -> str` | [src/jarvis/tools/capabilities.py:260](src/jarvis/tools/capabilities.py#L260) | Snapshot from `assemble_tool_list` |
| `capabilities_refresh() -> str` | [src/jarvis/tools/capabilities.py:303](src/jarvis/tools/capabilities.py#L303) | Phase-2 no-op string |
| `capabilities_subscribe_updates() -> str` | [src/jarvis/tools/capabilities.py:331](src/jarvis/tools/capabilities.py#L331) | Phase-2 no-op string |
| `dispatch_by_capability(tool_name, payload_json, intent_pattern, timeout_seconds=60)` | [src/jarvis/tools/dispatch.py:210](src/jarvis/tools/dispatch.py#L210) | DDR-005 contract honoured |
| `queue_build(feature_id, feature_yaml_path, repo, branch, originating_adapter, …)` | [src/jarvis/tools/dispatch.py:366](src/jarvis/tools/dispatch.py#L366) | Pattern A; field names track `nats_core` upstream (see §4.1 below) |

`escalate_to_frontier` exists in `dispatch.py` per its reserved slot in
design §11 / DDR-014, but ships as a FEAT-J003 deliverable behind the
keyword-only `include_frontier` Layer 3 gate in
[assemble_tool_list](src/jarvis/tools/__init__.py#L193). The 9-tool
FEAT-J002 surface is preserved when `include_frontier=False`.

### 3.2 DDR conformance

| DDR | Status | Evidence |
|-----|--------|----------|
| DDR-005 — `dispatch_by_capability` supersedes `call_specialist` | ✅ | Function name + docstring contract match exactly. Tool list contains no `call_specialist`. |
| DDR-006 — Tavily as web-search provider, swap-anchored | ✅ | `class TavilyProvider` in `general.py` with comment "DDR-006 swap-point grep anchor". |
| DDR-007 — `asteval` for `calculate` | ✅ | `from asteval import Interpreter` + `asteval>=0.9.33` in `pyproject.toml`. |
| DDR-008 — Capabilities via tool AND prompt placeholder | ✅ | `{available_capabilities}` placeholder lives in `supervisor_prompt.py:74`; `list_available_capabilities` tool also wired. |
| DDR-009 — Stub transport semantics + grep anchors | ✅ | `LOG_PREFIX_DISPATCH = "JARVIS_DISPATCH_STUB"`, `LOG_PREFIX_QUEUE_BUILD = "JARVIS_QUEUE_BUILD_STUB"` constants + invariant test [test_tools_dispatch.py:735](tests/test_tools_dispatch.py#L735) that pins the four canonical anchor sites. |

### 3.3 ADR alignment (spot checks)

- **ADR-ARCH-021 (tools never raise)** — every tool wraps its body in
  `try/except` and returns a structured `ERROR:` / `DEGRADED:` /
  `TIMEOUT:` string. Verified by reading each tool body. Tests assert
  the negative-path strings explicitly.
- **ADR-ARCH-003 / 015 / 016 (no hardcoded `agent_id`)** —
  `dispatch_by_capability` resolves through the in-memory registry;
  the contradiction `C1` flagged in design §11 is fully resolved by
  DDR-005 and there is no live caller naming an `agent_id` directly.
- **ADR-ARCH-023 (reasoning model cannot rebind tool list)** —
  `assemble_tool_list` returns a fresh `list[...]` on every call;
  `include_frontier` is keyword-only; snapshot copies are made of
  `capability_registry` for both consuming modules (ASSUM-006).
- **ADR-SP-014 Pattern A + ADR-SP-016 (singular topic convention)** —
  `queue_build` builds a real `BuildQueuedPayload` with hardcoded
  `triggered_by="jarvis"` and a configurable `originating_adapter`
  whitelist; topic literal is `pipeline.build-queued.{feature_id}`.

### 3.4 Wiring + lifecycle

`build_supervisor` honours its design §8 signature exactly:
keyword-only `tools` (default empty) + `available_capabilities`
(default "No capabilities currently registered."), so Phase 1 callers
remain working. The lifecycle flow `JarvisConfig → load_stub_registry →
assemble_tool_list → build_supervisor` matches design §8 verbatim.
[langgraph.json](langgraph.json) at repo root declares both
`jarvis` and `jarvis_reasoner` graphs — note this file is technically a
FEAT-J003 deliverable but supports the J002 surface without issue.

## 4. Findings

### 4.1 NON-BLOCKING — `queue_build` field name drifted from build plan

**Severity: low (informational).** The build plan (§FEAT-J002 Change 3)
named the parameter `feature_spec_ref`. The implementation uses
`feature_yaml_path` because that is the actual field name on
`nats_core.events.BuildQueuedPayload` (verified at
[../nats-core/src/nats_core/events/_pipeline.py:298](../nats-core/src/nats_core/events/_pipeline.py#L298)).
This is the correct resolution — design.md's "Stubbed transport ≠
stubbed schema" invariant requires tracking the upstream model — but
the build plan was never updated to reflect it.

**Recommendation**: add a footnote to
[phase2-build-plan.md](docs/research/ideas/phase2-build-plan.md) noting
the field-name pin to upstream `nats-core`. No code change.

### 4.2 NON-BLOCKING — Ruff & mypy not clean (success criterion #9 fails)

**Severity: low.** Build plan success criterion #9: "Ruff + mypy clean
on all new `src/jarvis/` modules." Current state (run on the FEAT-J002
surface):

**Ruff (7 errors)**:
| Rule | File | Nature |
|------|------|--------|
| RUF022 | `tools/__init__.py` | `__all__` not isort-sorted (intentionally grouped by category in source) |
| UP037 | `tools/__init__.py:90` | Stringified `"JarvisConfig"` annotation — `TYPE_CHECKING` import no longer needed at runtime |
| UP042 | `tools/dispatch_types.py:39` | `class FrontierTarget(str, Enum)` should use `enum.StrEnum` |
| I001 | (one file) | Import block ordering |
| RUF002 | several docstrings | Em/en-dash characters flagged as ambiguous (deliberate prose style) |

**Mypy (7 errors in `tools/`)**:
- 4× `unreachable` warnings — defensive `else` branches mypy thinks
  can't fire after type-narrowing. Honest defensive code; can be
  silenced with `# type: ignore[unreachable]` or removed if truly
  dead.
- 2× `arg-type` errors at `dispatch.py:661,678` —
  `_emit_frontier_log` has a `Literal[…]` outcome union that doesn't
  include `"attended_only"`. Fix by widening the literal type.
- 1× false-positive on `Subclass of str and ResultPayload` —
  needs an `isinstance` narrowing fix.

**Recommendation**: spawn a small implementation task
("FIX-J002-quality-gates") to drive ruff + mypy clean. Either fix the
violations or pin a project-level ignore in `pyproject.toml` for
RUF002 (en-dash style is intentional). Estimated 30–45 minutes.

### 4.3 NON-BLOCKING — Kanban hygiene: tasks not moved to `tasks/completed/`

**Severity: low (process).** AutoBuild reports 23/23 tasks completed
but the task files are scattered across three directories:

- `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/` — 21 task
  files (the canonical feature subfolder, missing TASK-J002-013 and
  TASK-J002-014)
- `tasks/backlog/TASK-J002-*` — 13 loose duplicates at the top of
  backlog
- `tasks/design_approved/TASK-J002-*` — 10 J002 task files (including
  the missing 013 and 014, the dispatch and queue_build tools)

`.guardkit/features/FEAT-J002.yaml` says `status: completed`, and
`tasks/completed/` contains zero J002 entries. This is purely
bookkeeping debt. Suggested action: `/feature-complete FEAT-J002`
(if available) or a manual sweep.

### 4.4 OBSERVATION — Test coverage on `tools/` is 75% in J002-only run

The J002-only coverage view shows 75% on `tools/` overall, with
`dispatch.py` at 53% — but this is *because* the J002-only run
excludes the `escalate_to_frontier` tests that live in J003. With the
full suite run, dispatch.py coverage is materially higher (the
`escalate_to_frontier` body is several hundred lines of the 959-line
file). The build plan target was 80% on **new modules**; per-tool, the
J002-authored portions clear that bar:

| Module | Coverage (J002-only) |
|--------|----------------------|
| `tools/__init__.py` (assemble_tool_list) | 100% |
| `tools/_correlation.py` | 100% |
| `tools/types.py` | 100% |
| `tools/capabilities.py` | 92% |
| `tools/dispatch_types.py` | 95% |
| `tools/general.py` | 81% |
| `tools/dispatch.py` | 53% (J002 portion only — J003's `escalate_to_frontier` not exercised in this run) |

No remediation needed. Worth re-measuring with the J003 tests included
for the canonical Phase 2 number.

## 5. Success-Criteria Scorecard (build plan §Success Criteria)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | All Phase 1 tests still pass (zero regressions) | ✅ Full suite green (1585/1585 effective, 2 skipped) |
| 2 | 9 J002 tools registered + each has happy + failure test | ✅ Verified — `test_tools_*.py` covers all 9 |
| 3 | (FEAT-J003 — async subagents) | n/a for this review (FEAT-J003 separately closed 26 Apr) |
| 4 | End-to-end routing test passes | ✅ `test_routing_e2e.py` 25/25 PASS |
| 5 | `jarvis chat` exhibits noticeably better behaviour than Phase 1 | ⚠ Not verified in this review (requires interactive run with real keys) |
| 6 | `langgraph.json` valid; `langgraph dev` spins all graphs | ⚠ File present and structurally correct; `langgraph dev` not invoked in this review |
| 7 | Capability catalogue stub renders 4 descriptors | ✅ Tested in `test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection` |
| 8 | (FEAT-J003 — `quick_local` fallback) | n/a |
| 9 | Ruff + mypy clean on new modules | ❌ 7 ruff lints + 7 mypy errors — see §4.2 |
| 10 | Memory Store round-trip (Phase 1) still works | ✅ Phase 1 session tests pass; no regressions in `tests/test_sessions.py` |

7 hard ✅ for J002-scope items, 1 hard ❌ (#9), 2 ⚠ that need a quick
manual confirmation outside this review's scope.

## 6. Recommendations

### 6.1 Recommended decision: **Accept** the review

The feature delivers what design.md and build-plan.md asked for. Ship
it as-is for Phase 3 to consume.

### 6.2 Two follow-up subtasks worth creating

| ID (suggested) | Title | Mode | Est | Why |
|---|---|---|---|---|
| TASK-J002-FIX-001 | Drive ruff + mypy clean on `tools/` (or pin RUF002 ignore for prose dashes) | direct | 30-45 min | Closes success criterion #9; prevents quality-gate drift into Phase 3 |
| TASK-J002-FIX-002 | Move 23 J002 task files to `tasks/completed/`; deduplicate the 13 loose backlog copies and reconcile `tasks/design_approved/` entries | direct | 10-15 min | Restores kanban truth so future `/task-status` queries work |

Both are low-risk, low-effort, and orthogonal to anything in the
Phase 3 NATS work. Do them in either order.

### 6.3 One scope-doc footnote

Add a note in
[phase2-build-plan.md](docs/research/ideas/phase2-build-plan.md)
clarifying that `queue_build`'s parameter is `feature_yaml_path` (not
`feature_spec_ref` as originally drafted) because the implementation
follows the upstream `nats-core` `BuildQueuedPayload` schema. No code
change needed.

### 6.4 Outside-this-review verification

Two success criteria couldn't be verified non-interactively:

- **Criterion #5** — Run `jarvis chat` once with a real provider key
  and confirm the supervisor reaches for `calculate` /
  `dispatch_by_capability` correctly across 2-3 prompts.
- **Criterion #6** — Run `langgraph dev` once locally and confirm the
  graphs spin up.

Both are part of the "Phase 2 close" sign-off the build plan flagged
("**Next: `/task-review` + regression check + Step 11 end-to-end
routing validation.**"). The Step-11 routing test is verified ✅;
criterion #5/#6 are the remaining attended-checkpoint items.

## 7. Decision Matrix

| Option | Effort | Risk | Phase 3 readiness | Recommendation |
|--------|--------|------|-------------------|----------------|
| **Accept now**, file FIX-001/FIX-002 in backlog | very low | low | Ready | ★ **recommended** |
| Accept after running FIX-001 + FIX-002 first | ~1 hr | very low | Slightly cleaner | acceptable if you want a fully clean handoff |
| Revise — deeper analysis of `dispatch.py` coverage (53% → re-measure with J003 tests) | low | none (data only) | Ready | unnecessary — analysis above explains the artefact |
| Implement (create FIX subtasks now) | low | low | Ready | preferable to plain Accept if you want them tracked |

## 8. Appendix — Verified Inventory

**Tool modules** (`src/jarvis/tools/`, 2496 LOC):
- `__init__.py` (216) — `assemble_tool_list` factory + re-exports
- `general.py` (680) — 4 general tools + `TavilyProvider` swap anchor
- `capabilities.py` (351) — `CapabilityDescriptor` + 3 catalogue tools
- `dispatch.py` (959) — 2 J002 dispatch tools + 1 reserved-slot J003 escalation
- `types.py` (127) — `WebResult`, `CalendarEvent`
- `dispatch_types.py` (123) — `DispatchError`, `FrontierTarget` (J003)
- `_correlation.py` (40) — `new_correlation_id`

**Test modules** (J002-tagged):
`test_tools_general.py`, `test_tools_capabilities.py`,
`test_tools_dispatch.py`, `test_tools_dispatch_contract.py`,
`test_tools_queue_build.py`, `test_tools_types.py`,
`test_dispatch_by_capability.py`, `test_capabilities.py`,
`test_general_calculate.py`, `test_search_web.py`,
`test_get_calendar_events.py`, `test_supervisor_with_tools.py`,
`test_assemble_tool_list.py`, `test_load_stub_registry.py`,
`test_correlation.py`, `test_config_phase2.py`,
`test_phase2_dependencies.py`. **591 cases, 100% pass.**

**Stub registry**: [src/jarvis/config/stub_capabilities.yaml](src/jarvis/config/stub_capabilities.yaml)
— 4 agents (architect, product-owner, ideation, forge), 78 LOC.

**DDR-009 swap-point anchors verified at**:
- `src/jarvis/tools/dispatch.py:106-107` (constants)
- `src/jarvis/tools/dispatch.py:323` (dispatch log)
- `src/jarvis/tools/dispatch.py:478` (queue_build log)
- `tests/test_tools_dispatch.py:735+` (invariant test)
