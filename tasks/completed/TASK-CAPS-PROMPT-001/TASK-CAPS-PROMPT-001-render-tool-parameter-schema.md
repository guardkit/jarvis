---
id: TASK-CAPS-PROMPT-001
title: "Render tool parameter schema in supervisor capability prompt block (R2 — Typed Args)"
task_type: bugfix
status: completed
created: 2026-05-08T19:35:00Z
updated: 2026-05-08T20:45:00Z
completed: 2026-05-08T20:45:00Z
completed_location: tasks/completed/TASK-CAPS-PROMPT-001/
previous_state: in_review
state_transition_reason: "All in-PR ACs (AC-001..AC-006, AC-008) complete; AC-007 deferred per Decision D4 (P0 follow-up ≤2 days post-merge); AC-009 is a manual smoke gate before merge to main, not a task-completion gate."
organized_files:
  - TASK-CAPS-PROMPT-001-render-tool-parameter-schema.md  # this file
priority: critical
complexity: 4
implementation_mode: task-work
estimated_minutes: 180
parent_review: TASK-REV-9939
feature_id: FEAT-CAPS-PROMPT
demo_blocker_for: 2026-05-16
go_no_go_date: 2026-05-13  # T-2 from dress rehearsal 2026-05-15
related_tasks:
  - TASK-CAPS-PROMPT-002  # Sibling — runbook docs follow-ups
  - TASK-REV-CB48          # Sibling review — closed dispatch-resolver wiring gap
  - TASK-DSR-003           # Closed the dispatch-resolver wiring gap (W2)
tags: [jarvis, capabilities-registry, prompt-engineering, supervisor-prompt, dispatch, ddr-021, dddsw-2026-05-16]
context_files:
  - src/jarvis/tools/capabilities.py                       # CapabilityToolSummary (line 85), as_prompt_block() (line 135)
  - src/jarvis/infrastructure/capabilities_registry.py     # _manifest_to_descriptor() (line 136)
  - src/jarvis/config/stub_capabilities.yaml               # Stub registry (DDR-021 NATS-down soft-fail path)
  - src/jarvis/prompts/supervisor_prompt.py                # {available_capabilities} placeholder (line 69-74)
  - src/jarvis/tools/dispatch.py                           # dispatch_by_capability docstring references parameters schema (line 381)
  - .claude/reviews/TASK-REV-9939-review-report.md         # Review decisions and surface plan
  - /home/richardwoollcott/Projects/appmilla_github/specialist-agent/src/specialist_agent/adapters/manifest.py  # ToolCapability schema source
test_results:
  status: passing
  coverage: null  # Coverage measured against full suite — 2205 passed, 1 skipped (1 pre-existing graphiti pin failure unrelated to this task)
  last_run: 2026-05-08T20:30:00Z
  new_test_files:
    - tests/test_capability_descriptor_prompt_block.py  # AC-006 snapshot suite (7 tests)
    - tests/test_stub_capabilities_parity.py            # AC-004 stub parity assertion (3 tests)
acceptance_criteria_status:
  AC-001: complete  # CapabilityToolSummary.parameters added — capabilities.py
  AC-002: complete  # _manifest_to_descriptor pipes tool.parameters — capabilities_registry.py
  AC-003: complete  # as_prompt_block() emits Args (required) block via _render_required_args
  AC-004: complete  # stub_capabilities.yaml + DM-stub-registry.md canonical block carry parameters; parity test passes
  AC-005: complete  # supervisor_prompt.py prose reframed (D3); test_prompts.py PRE_J003_HEAD updated to lock the new wording
  AC-006: complete  # tests/test_capability_descriptor_prompt_block.py — 7 tests passing; pre-fix red verified by stash+rerun (manual)
  AC-007: deferred  # Integration test — P0 follow-up per Decision D4. File as sibling task TASK-CAPS-PROMPT-003 on merge. (Snapshot + parity tests cover the bytes-side contract; integration test verifies model-fake harness reads the new shape correctly.)
  AC-008: complete  # DDR-021 amendment paragraph added (2026-05-13 entry)
  AC-009: pending   # Manual smoke (runbook end-to-end on GB10 host) — gate before merge to main, requires natural-prompt operator interaction. Cannot be executed headless.
---

# Task: Render tool parameter schema in supervisor capability prompt block (R2)

## Description

Canonical close of the CAPS-PROMPT-SCHEMA gap surfaced by
[`TASK-REV-9939`](../in_review/TASK-REV-9939-capabilities-prompt-block-missing-parameter-schema.md).
The review identified a **two-layer drop** of the tool parameter schema between the
live KV registry and the supervisor's `{available_capabilities}` prompt block: the
projection at
[`_manifest_to_descriptor`](../../src/jarvis/infrastructure/capabilities_registry.py#L151-L158)
silently discards `tool.parameters`, and `CapabilityToolSummary`
([`capabilities.py:85-99`](../../src/jarvis/tools/capabilities.py#L85-L99)) has no
`parameters` field to carry it even if the projection wanted to. As a result the
supervisor (`qwen36-workhorse`) invents argument names when constructing
`payload_json` for `dispatch_by_capability`, and the architect rejects the dispatch
in 6ms with *"Missing required arguments for 'align'"* (3× evidence on 2026-05-08
in [`RESULTS-...-postfix.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md)).

Ship **R2 (Typed Args block)** per the review's Decision D2 — render `Args (required):`
with type and per-arg description, matching the `Args:` block convention every
other tool's `@tool(parse_docstring=True)` docstring already uses elsewhere in the
prompt. R1 (required-keys-only) lives in a feature branch as a same-day fallback;
the operator's explicit-args prompt template stays in the on-stage script as the
break-glass.

This is the structural twin of [`TASK-DSR-003`](../completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)
(closed the dispatch-resolver wiring gap from `TASK-REV-CB48`). Together
`TASK-DSR-003` + this task close the wire-side and prompt-side fidelity gaps that
together blocked end-to-end natural-prompt dispatch.

## Implementation Plan

Edit order matters — model first so the projection has somewhere to write, then
projection so the renderer has data to read, then renderer.

### Step 1 — Extend `CapabilityToolSummary` ([`capabilities.py:85-99`](../../src/jarvis/tools/capabilities.py#L85-L99))

Add an optional `parameters` field carrying the JSON-Schema-shaped dict from
`nats_core.ToolCapability.parameters`:

```python
class CapabilityToolSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["read_only", "mutating", "destructive"] = "read_only"
    parameters: dict[str, Any] | None = Field(
        default=None,
        description=(
            "JSON-Schema-shaped parameter dict from "
            "nats_core.ToolCapability.parameters. None when the upstream "
            "manifest carries no schema (older specialists, stub yaml "
            "without the parameters block)."
        ),
    )
```

`None` is the pre-wired sentinel — older manifests and bare stub entries land
on `None`, and `as_prompt_block()` simply omits the `Args:` block in that case.
This matches the existing tolerance pattern (`last_heartbeat_at: None`,
`cost_signal: "unknown"`).

### Step 2 — Pipe `parameters` through the projection ([`capabilities_registry.py:151-158`](../../src/jarvis/infrastructure/capabilities_registry.py#L151-L158))

```python
capability_list = [
    CapabilityToolSummary(
        tool_name=tool.name,
        description=tool.description or tool.name,
        risk_level=tool.risk_level,
        parameters=tool.parameters,  # NEW — carry the schema through
    )
    for tool in manifest.tools
]
```

`tool.parameters` is already a `dict[str, Any]` on `nats_core.ToolCapability`, so
no transformation is needed — it's a verbatim pass-through.

### Step 3 — Render `Args (required):` block ([`capabilities.py:135-164`](../../src/jarvis/tools/capabilities.py#L135-L164))

Extend `as_prompt_block()` so that when `cap.parameters` is non-`None` it appends
a `Args (required):` block with one indented line per **required** key, in
manifest-declared order, with type and description:

```
  - architect_align (read_only) — Align an existing design against the ADR set; emit an AlignmentJudgment.
    Args (required):
      - context (string): Background: existing architecture, constraints
      - proposal (string): The proposal or design to evaluate
      - question (string): Specific question to answer
```

Render rules (DM-tool-types §"Prompt-block shape" amendment):

- Iterate `parameters.required` (preserves manifest order); for each name look up
  `parameters.properties[name]` for `type` and `description`.
- If a `required` key is absent from `properties`, emit `(unknown): <name>` —
  defensive but should not happen in practice (validates upstream manifest hygiene).
- If `parameters` is a non-`None` dict but `required` is empty/missing, omit the
  block entirely — no spurious empty headers.
- Optional (non-required) parameters are deliberately **not rendered** in R2 —
  the supervisor needs the must-have args; nice-to-haves bloat the prompt and
  invite hallucinated optional fields. R3 (full schema) is the path if optional
  args ever become load-bearing for a tool.
- 4-space indent for the `Args (required):` header (matches the existing
  `  - tool_name` indent on its parent line); 6-space indent for each arg
  bullet.

### Step 4 — Stub yaml schema parity (Decision D6)

Extend [`stub_capabilities.yaml`](../../src/jarvis/config/stub_capabilities.yaml)
so each tool entry carries a `parameters:` block mirroring the upstream manifest's
shape. Concretely, add `parameters:` blocks to every `architect_*`, `review_*`,
`refine_*`, etc. tool currently listed.

Source of truth for shapes: `specialist-agent/src/specialist_agent/adapters/manifest.py`
(architect manifest at lines 81-211; product-owner / ideation lower in the file).
Copy-paste verbatim — `nats_core.ToolCapability` parses the YAML's `parameters`
through the same Pydantic model the live registry uses, so byte-identical input
yields byte-identical output.

This closes the DDR-021 NATS-down soft-fail regression: under degraded operation
the stub fallback now renders the same `Args:` block as the live registry, so the
prompt is shape-stable across the live↔stub swap.

### Step 5 — DDR-021 amendment

Add a paragraph to
[`docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md`](../../docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md):

> **Amendment (2026-05-13, TASK-CAPS-PROMPT-001):** The stub registry must mirror
> the live KV's tool-parameter schema (`ToolCapability.parameters`) so the
> supervisor's `{available_capabilities}` prompt block is shape-stable across the
> live↔stub swap. A stub registry entry that omits `parameters:` regresses the
> supervisor to schema-guessing under degraded operation — the failure mode that
> originally surfaced in `TASK-REV-9939`. CI assertion: every tool in
> `stub_capabilities.yaml` parses with non-`None` `parameters`.

### Step 6 — Supervisor prose reframe (Decision D3)

Adjust the prose around `list_available_capabilities` in
[`supervisor_prompt.py`](../../src/jarvis/prompts/supervisor_prompt.py#L81-L83):

**Before:**
> Call `list_available_capabilities` at most once per session — the catalogue
> injected above is authoritative for the rest of the conversation.

**After:**
> Call `list_available_capabilities` at most once per session — the catalogue
> injected above is authoritative for the rest of the conversation, **including
> the `Args (required):` block under each tool**. Construct `payload_json` for
> `dispatch_by_capability` from those declared keys; do not invent argument names.

The wording stays a single sentence so the bullet shape matches the surrounding
list. Keep the budget-conscious framing ("at most once per session") — it's
correct now *because* the catalogue is authoritative, not despite it.

### Step 7 — Tests

**7a. Snapshot test** (required, in PR) at
`tests/test_capability_descriptor_prompt_block.py`:

- Build a `CapabilityDescriptor` using the architect-agent shape with the three
  required arg keys (`context`, `proposal`, `question`).
- Assert `as_prompt_block()` output contains the literal substring
  `"Args (required):"` and the three keys in manifest-declared order with
  type/description.
- Negative test: a descriptor with `parameters=None` emits no `Args:` block
  (back-compat for older manifests and skinny stubs).
- Negative test: a descriptor with `parameters` present but `required: []`
  emits no `Args:` header.
- Pin against architect-agent only (1 manifest), not the full fleet — fleet
  tests stay shape-only so manifest description tweaks don't churn snapshots.

**7b. Integration test** (required, P0 follow-up ≤2 days post-merge) at
`tests/test_supervisor_payload_construction_integration.py`:

- Drive the supervisor with a deterministic model fake (`qwen36-workhorse`-shaped
  responses) and a naturally phrased prompt naming the architect by capability.
- Assert the resulting `dispatch_by_capability` call's `payload_json` parses
  to `{context, proposal, question}` exactly (order-independent set match).
- Use `tests/fixtures/caps_prompt_schema/architect_align_misshape.json` as the
  pre-fix replay fixture (capture from the existing 2026-05-08 traces
  `31a2e8de` / `232ec2e0` / `368f9149` — D1 of the review).

**7c. Stub-yaml CI assertion** (required, in PR) at
`tests/test_stub_capabilities_parity.py`:

- Loop every tool in every descriptor returned by
  `load_stub_registry(Path("src/jarvis/config/stub_capabilities.yaml"))`.
- Assert `tool.parameters is not None` for each.
- Failure message names the offending `agent_id.tool_name` so the operator
  knows where to add the missing block.

### Step 8 — Manual smoke (gate before merge to `main`)

Re-run [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
end-to-end on the GB10 host against the dual-role stack with a **naturally
phrased prompt** (no explicit-args enumeration). Phase 4 must land an
`agents.command.architect-agent.<corr>` envelope with a payload whose keys
exactly match the manifest's `required` list, and a real `AlignmentJudgment`
must land in the chat REPL on the **first attempt**.

Capture the FRR-003 trace as evidence (`trace-architect_align-<corr>-r2-success.json`).

## Acceptance Criteria

- [ ] **AC-001** — `CapabilityToolSummary.parameters: dict[str, Any] | None`
      added; `None` is the pre-wired default.
- [ ] **AC-002** — `_manifest_to_descriptor` projection pipes
      `tool.parameters` into `CapabilityToolSummary`.
- [ ] **AC-003** — `as_prompt_block()` emits the `Args (required):` block per
      Step 3 render rules; back-compat preserved when `parameters is None`.
- [ ] **AC-004** — Every tool in `stub_capabilities.yaml` carries a
      `parameters:` block byte-equivalent to the upstream manifest's shape.
      `tests/test_stub_capabilities_parity.py` passes.
- [ ] **AC-005** — Supervisor prompt prose reframed per Step 6.
- [ ] **AC-006** — `tests/test_capability_descriptor_prompt_block.py` passes
      after the fix and **fails on a clean checkout of `main`** prior to the
      fix (verify by stashing the change and re-running).
- [ ] **AC-007** — `tests/test_supervisor_payload_construction_integration.py`
      passes; the constructed `payload_json` parses to `{context, proposal,
      question}` for `architect_align`. (P0 follow-up if not in PR — file as
      a sibling task on merge.)
- [ ] **AC-008** — DDR-021 amendment paragraph added per Step 5.
- [ ] **AC-009** — Manual smoke per Step 8: runbook end-to-end success on
      first attempt against a natural prompt. FRR-003 trace captured as
      evidence and committed under
      `docs/runbooks/evidence/dddsw-demo/`.

## Risks & Mitigations

- **Snapshot-test churn** — pin against architect-agent only (1 manifest), not
  the full fleet.
- **Stub yaml drift** — Step 7c CI assertion catches missing `parameters:`
  blocks at PR time.
- **Token-budget creep** — current fleet adds ~360 tokens; revisit only if
  fleet grows past 30+ specialists (review F3).
- **R2 still misshapes** under `qwen36-workhorse` — Step 7b integration test
  catches before merge; operator's explicit-args break-glass is the stage
  fallback.

## Out of Scope

- Runbook §0.1/§0.5/§4.2-§4.4/§4.3/§5.2/§6 docs updates — owned by sibling
  task [`TASK-CAPS-PROMPT-002`](TASK-CAPS-PROMPT-002-runbook-followups-ddsw-demo.md).
- Re-litigating Bugs #1/#2/#3 (specialist-agent — closed by `1979aa8` /
  `08a95fe` / `4d80bd3`).
- The `nats-core/pyproject.toml` v0.4.0 bump (committed separately in
  `nats-core` repo).
- Forge dispatch path (FEAT-JARVIS-INTERNAL-001) — `queue_build` does not
  use `dispatch_by_capability`.
- R3 (JSON-Schema verbatim) and full optional-parameter rendering — review
  rejected R3 and deferred optional-arg rendering until a tool surfaces a
  load-bearing optional.

## Phase Alignment

This is the prompt-side close of the catalogue-render fidelity story:

- `TASK-DSR-003` (W2) closed the wire-side resolver wiring gap (live registry
  → dispatch resolver).
- This task closes the prompt-side fidelity gap (live registry parameters →
  supervisor prompt block).

Together they make capability-name dispatch end-to-end usable from a naturally
phrased operator prompt, on time for 2026-05-16.

## See Also

- [`TASK-REV-9939`](../in_review/TASK-REV-9939-capabilities-prompt-block-missing-parameter-schema.md)
  — parent review, decision rationale.
- [`.claude/reviews/TASK-REV-9939-review-report.md`](../../.claude/reviews/TASK-REV-9939-review-report.md)
  — full report with two-layer-drop finding (F1) and surface plan.
- [`TASK-CAPS-PROMPT-002`](TASK-CAPS-PROMPT-002-runbook-followups-ddsw-demo.md)
  — sibling docs PR (runbook follow-ups).
- [`TASK-DSR-003`](../completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)
  — structural twin (wire-side resolver wiring).
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md)
  — surfacing context, evidence index.

## Implementation Summary

Closed the CAPS-PROMPT-SCHEMA two-layer drop surfaced by `TASK-REV-9939`: the
supervisor's `{available_capabilities}` prompt block now renders an
`Args (required):` subblock under each tool, with `(type)` and per-arg
description, in manifest-declared order. This lets the supervisor
(`qwen36-workhorse`) construct `payload_json` for `dispatch_by_capability`
from declared keys rather than guessing them — closes the demo blocker for
2026-05-16 (FRR-003 misshape rejections in 6ms with "Missing required
arguments for 'align'").

R2 (Typed Args) shipped per Decision D2. Three coordinated edits across the
model layer (`CapabilityToolSummary.parameters`), projection layer
(`_manifest_to_descriptor`), and render layer (`as_prompt_block`), plus
DDR-021 schema-parity for the stub yaml so the prompt is shape-stable across
the live↔stub swap. Supervisor prose reframed (D3) so the catalogue's
authority extends to the new `Args (required):` block.

**Approach:** Source-edit order — model → projection → renderer → stub yaml
→ DDR amendment → supervisor prose → tests. Snapshot test pinned against the
single architect-agent manifest (not fleet-wide) to avoid manifest-description
churn. Stub-yaml parity test enforces `parameters is not None` per tool with
agent_id.tool_name in failure messages so operators know where to add missing
blocks.

**Lessons learned:**
- The original task body identified the gap as a single-layer render fix; the
  parent review (TASK-REV-9939) correctly identified it as a two-layer drop
  (model + projection + render). Fix order matters: model first so the
  projection has somewhere to write, then projection so the renderer has data
  to read, then renderer.
- Byte-for-byte canonical pin tests (DM-stub-registry.md ↔ stub_capabilities.yaml,
  PRE_J003_HEAD ↔ supervisor_prompt.py) caught two intentional changes that
  needed lock-step updates. The canonical references aren't tests of "do not
  change" — they're tests of "change in lock-step." Update the canonical
  alongside the file it pins, with an inline comment explaining the
  intentional drift.
- For stub-only tools (no upstream specialist-agent manifest entry), authoring
  plausible JSON schemas from the description is sufficient for stub parity —
  the CI assertion is `parameters is not None`, not "matches upstream
  byte-for-byte". The DDR-021 amendment language acknowledges this
  ("byte-equivalent for tools with upstream parity, authored for stub-only
  tools").

## Implementation Notes (2026-05-08)

Implemented per the plan in source-edit order: model → projection → renderer → stub
yaml → DDR amendment → supervisor prose → tests.

**Render rule for `Args (required):`** is implemented by a leaf helper
`_render_required_args` next to `CapabilityDescriptor` (capabilities.py). The helper
returns an empty list when no block should be emitted (no `parameters`, or
`required` empty/missing) so the parent `as_prompt_block()` decides whether to
emit the header. The defensive `(unknown):` fallback fires when a `required` key
has no entry under `properties` — should not happen in practice, surfaces hygiene
gaps visibly when it does.

**Stub-yaml schema parity (Step 4):** the stub catalogue contains 7 tools that
exist only in the stub (no upstream specialist-agent manifest entry):
`run_architecture_session`, `draft_adr`, `review_specification`,
`refine_acceptance_criteria`, `generate_alternatives`, `steelman`, `build_feature`.
For these the `parameters:` block was authored from each tool's description with
inline `# NOTE: stub-only tool ...` comments. The 4 tools that mirror upstream
(`architect_greenfield`, `architect_align`, `architect_explore`,
`architect_feasibility`) carry byte-equivalent parameters from
`specialist-agent/.../adapters/manifest.py:_architect_manifest_factory`.
**Critically, `architect_align`'s required keys (`context/proposal/question`)
match the upstream manifest exactly** — that's the demo path for 2026-05-16.

**Canonical DM-stub-registry.md updated:** the YAML block under `## Canonical
Phase 2 content` was kept in lock-step with `src/jarvis/config/stub_capabilities.yaml`
because `tests/test_stub_capabilities.py::TestAC002CanonicalByteForByteMatch`
asserts byte-for-byte equality between the two. An amendment paragraph was added
to that section explaining the schema-parity work.

**`test_prompts.py::TestJ003014AdditiveAboveInsertionPoint::PRE_J003_HEAD`
amended:** the constant locking "everything above the Subagent Routing insertion
point" was updated to reflect the intentional D3 prose change. A code comment
in the constant explains why the line changed — future drift-detection still
catches accidental edits everywhere else in the head.

**Files touched:**
- `src/jarvis/tools/capabilities.py` (Step 1+3, +47 LOC)
- `src/jarvis/infrastructure/capabilities_registry.py` (Step 2, +6 LOC)
- `src/jarvis/config/stub_capabilities.yaml` (Step 4, +175 LOC of `parameters:` blocks + comments)
- `docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md` (canonical YAML lock-step + amendment paragraph)
- `docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md` (Step 5, +1 amendment paragraph)
- `src/jarvis/prompts/supervisor_prompt.py` (Step 6, prose reframe)
- `tests/test_prompts.py` (PRE_J003_HEAD lock updated for D3 prose change)
- `tests/test_capability_descriptor_prompt_block.py` (NEW — 7 tests, AC-006)
- `tests/test_stub_capabilities_parity.py` (NEW — 3 tests, AC-004)

**Test status:** Full suite **2205 passed, 1 skipped, 0 caused-by-this-task
failures** (1 pre-existing failure in
`test_phase4_dependencies.py::test_graphiti_core_lower_bound_present` is
unrelated — graphiti-core uses a `git+` pin instead of `>=`, verified pre-existing
by stash+rerun on a clean main).

**Open follow-ups:**
- **AC-007 (integration test)** is **deferred per Decision D4** — file as sibling
  task `TASK-CAPS-PROMPT-003` on merge. The model-fake harness for `qwen36-workhorse`
  is non-trivial; D4 explicitly says do not block R2 merge on it but land it ≤2
  days post-merge.
- **AC-009 (manual smoke gate)** still required before merge to `main`. Re-run
  `RUNBOOK-jarvis-architect-align-dddsw-demo.md` end-to-end on the GB10 host with
  a naturally phrased prompt; capture the FRR-003 trace as
  `docs/runbooks/evidence/dddsw-demo/trace-architect_align-<corr>-r2-success.json`.
