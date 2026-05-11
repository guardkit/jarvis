---
task_id: TASK-REV-9939
review_mode: decision
review_depth: standard
score: 78
findings_count: 6
recommendations_count: 6
decision: refactor
generated_at: 2026-05-08
demo_blocker_for: 2026-05-16
---

# Review Report: TASK-REV-9939 — CAPS-PROMPT-SCHEMA

**Decision:** Render parameter schema in `as_prompt_block()` per **R2 (Typed Args)**. Ship to `main` by **2026-05-13** (T-2 from dress rehearsal). Hold **R1 in a feature branch** as a same-day fallback if R2 slips. Keep the explicit-args operator script as the **break-glass** for stage.

---

## Executive Summary

The runbook trace evidence (3× FRR-003 misshape traces + 1× workaround success) is consistent with the code-level root cause. The supervisor cannot construct the correct payload because **the parameter schema never reaches the prompt** — and the projection drops it one layer earlier than the task body identified.

**Two-layer gap (not one):**

1. **Model layer** — `CapabilityToolSummary` ([`capabilities.py:85-99`](../../src/jarvis/tools/capabilities.py#L85-L99)) has **no `parameters` field**. Even if `as_prompt_block()` wanted to render the schema, the data isn't on the model.
2. **Render layer** — `as_prompt_block()` ([`capabilities.py:135-164`](../../src/jarvis/tools/capabilities.py#L135-L164)) emits only `tool_name (risk) — description` per tool.

The projection at [`_manifest_to_descriptor`](../../src/jarvis/infrastructure/capabilities_registry.py#L151-L158) reads `tool.parameters` from `nats_core.AgentManifest`, then **silently discards it** when constructing `CapabilityToolSummary`. The stub-loader path (`load_stub_registry`) inherits the same gap and will too — even after R2 — because the stub YAML schema doesn't carry `parameters` per tool.

This means the fix is **3 coordinated edits** (model + projection + render), not just 1 (render). It's still small (~30 LOC across three files) but the task body's "~10 LOC change in `as_prompt_block()`" understates the surface by a factor of 3.

**Decision recommendation:** Ship R2. Effort is small, evidence is conclusive, fallbacks are cheap, and the demo narrative depends on it.

---

## Findings

### F1 — Two-layer drop, not one *(High, validated against code)*

The task body's root-cause is correct in direction but understates the surface. The schema is dropped at projection time, before render time. Fix order matters: extend the model first, then the projection, then the renderer; otherwise the renderer reads `None` and silently emits the current shape.

**Evidence:**
- [`capabilities.py:85-99`](../../src/jarvis/tools/capabilities.py#L85-L99) — `CapabilityToolSummary` carries `tool_name`, `description`, `risk_level` only.
- [`capabilities_registry.py:151-158`](../../src/jarvis/infrastructure/capabilities_registry.py#L151-L158) — comprehension reads `tool.name`, `tool.description`, `tool.risk_level` and ignores `tool.parameters`.
- Upstream: [`specialist-agent/manifest.py:118-137`](../../../specialist-agent/src/specialist_agent/adapters/manifest.py#L118-L137) — `parameters` is present and well-formed at the source.

### F2 — Stub registry parity will silently regress under DDR-021 *(Medium, design-debt)*

If R2 ships only against the live KV path, the NATS-down soft-fail (DDR-021) renders tools with no `Args:` block — recreating the supervisor-guessing failure mode under degraded operation, when stress is highest. Stub YAML ([`config/stub_capabilities.yaml`](../../src/jarvis/config/stub_capabilities.yaml)) currently has no `parameters` field on any tool.

This argues for solving F1 and F2 in the same change so the stub yaml schema mirrors the live KV's shape and the prompt is shape-stable across the live↔stub swap. The runtime types (`CapabilityToolSummary` with optional `parameters`) tolerate stub absence, but the operator-visible failure mode regresses. Decision 6 in the task body should land **yes**.

### F3 — Token-cost projection is comfortable *(Low, sanity-confirmed)*

Per-tool cost estimate for R2 typed render (manifest-author-controlled descriptions, kept tight):

| Tool size | Args lines | ~Tokens added |
|-----------|-----------|--------------|
| 3-arg flat strings (architect_align) | 4 | ~60 |
| 6-arg with optional fields | 8 | ~150 |

Current fleet (1 specialist × 6 tools avg): **~360 tokens** added to the supervisor prompt — negligible against any 32k+ context. Hypothetical 10× fleet: **~3.6k tokens** — still comfortable. No need to gate the renderer on context-budget heuristics; if the fleet ever grows past 30+ specialists we revisit (and at that point the catalogue should be tool-fetched rather than fully injected).

### F4 — The "at most once per session" prose is now a *cost* nudge, not a *correctness* nudge *(Low, prompt hygiene)*

[`supervisor_prompt.py:81-83`](../../src/jarvis/prompts/supervisor_prompt.py#L81-L83):

> Call `list_available_capabilities` at most once per session — the catalogue injected above is authoritative for the rest of the conversation.

Pre-R2, this prose nudged the supervisor away from its only escape hatch when the schema was missing. Post-R2, the nudge is correct *because* the catalogue is authoritative. Keep the line; reframe the rationale in the surrounding prose so the model reads "the catalogue is authoritative — including the `Args:` block under each tool" rather than "don't re-query." This is the decision-3 ask.

### F5 — `dispatch_by_capability` docstring already names the right artefact *(Low, no change needed)*

[`dispatch.py:381-385`](../../src/jarvis/tools/dispatch.py#L381):

> `payload_json: JSON string matching the tool's parameters schema as declared in its ToolCapability.parameters.`

This docstring is honest about where the schema *should* be available — the prompt block is what's failing it, not the dispatcher. Tightening the docstring further is unnecessary; do **not** add a "consult the catalogue" reminder here, because the catalogue is now the load-bearing surface and doubled prose dilutes both copies. Reject the optional refinement in concern (e) of the task body.

### F6 — Test honesty: the gap shipped uncaught *(Medium, regression hygiene)*

There is no snapshot test on `as_prompt_block()` that asserts `Args:` fidelity, so the failure mode is invisible to CI. The new tests must (a) fail today against `main` so the regression bar is real, then (b) pass after the fix. Two tests, both required:

- **Snapshot test** on `as_prompt_block()` against an `architect_align`-shaped descriptor — golden-output assertion that the new `Args (required):` block is present, with the three keys in manifest-declared order. Fast, deterministic, no model harness.
- **Integration test** using the existing `qwen36-workhorse`-equivalent stub harness (or a deterministic LangGraph fake) that drives the supervisor against the catalogue render and asserts `dispatch_by_capability`'s constructed `payload_json` contains exactly `{context, proposal, question}`. This is the *user-visible* behaviour change; unit-only coverage is insufficient because the hypothesis is "the model reads the new shape correctly", not "the renderer emits the new shape."

The integration test's value is highest if it runs against a model fake that reproduces `qwen36-workhorse`'s observed behaviour. If that's expensive to assemble, ship the snapshot now and file the integration test as same-week follow-up; do **not** ship without the snapshot.

---

## Decision Matrix — Render Shape

| Option | Effort | Token cost | Demo-narrative fit | Risk | Recommendation |
|--------|--------|-----------|-------------------|------|----------------|
| **R1** Required-keys-only | ~30 LOC (3 files) | Lowest | Adequate | Model may still guess types on non-string args | **Fallback** (feature branch) |
| **R2** Typed Args block | ~40 LOC (3 files) | +~360 tok / fleet | Best — mirrors `@tool` docstring convention | Low | **Primary** ✅ |
| R3 JSON-Schema verbatim | ~25 LOC | Highest | Reads as "infrastructure" not "intent" | Hardest for the model to skim under load | Reject |

**Why R2 over R1:** The marginal effort delta (R1 → R2) is one extra loop in the renderer — ~10 LOC. The narrative-fit delta is large: R2 matches the `Args:` block convention `qwen36-workhorse` already sees in every `@tool(parse_docstring=True)` docstring across the rest of the prompt (the catalogue tools, dispatch tool, calculate tool — all rendered with `Args:` sections). Anchoring on the same convention is a free reliability win.

**Why R2 over R3:** R3 leaks JSON Schema artefacts (`type: object`, `additionalProperties`) into prose-shaped surface. The model reads the catalogue as instructions, not as a contract, and JSON-Schema reads as a contract. R2 keeps the prose register consistent.

**Why not punt to R1:** The post-talk follow-up theory ("ship R1 for demo, file R2") burns engineering attention twice on the same surface for a one-off. R2 is small enough that doing it once is cheaper than scheduling the second pass.

---

## Required Decisions (per task body)

### D1 — Confirm runtime symptom in dev *(deferred to implementation task)*

Already confirmed 3× in production-equivalent run on 2026-05-08 (traces `31a2e8de`, `232ec2e0`, `368f9149`). The lab repro exists to **freeze a fixture**, not to re-prove the symptom. Capture one trace + one envelope as `tests/fixtures/caps_prompt_schema/architect_align_misshape.json` so the integration test can replay it against `main` (failing) and the patched branch (passing).

### D2 — Render shape: **R2 (Typed Args)**

Ship R2 to `main` by **2026-05-13** (T-2 from dress rehearsal). R1 in a feature branch as a same-day fallback. Operator's explicit-args prompt template stays in the on-stage script as the **break-glass** for the live talk. (Three layers of defence is generous but the demo cost-of-failure asymmetry argues for it.)

### D3 — `list_available_capabilities` "at most once per session" guidance: **Keep, reframe**

Keep the line; revise the surrounding rationale so the prose lands on **"the catalogue is authoritative — including the `Args:` block under each tool"** rather than **"don't re-query."** Prose-only change in [`supervisor_prompt.py`](../../src/jarvis/prompts/supervisor_prompt.py#L69-L74) — bundle with the R2 patch so the prompt reads coherently.

### D4 — Test plumbing: **Snapshot now, integration same-week**

- **Snapshot test** on `as_prompt_block()` — required; ships in the same PR as R2.
- **Integration test** — required; can land within 2 days post-merge if the model-fake harness is non-trivial. Do **not** block R2 merge on the integration test, but treat it as a P0 follow-up.

### D5 — Runbook follow-ups: **All five, batched in a single docs PR**

The five updates (§0.5, §4.3, §5.2, §0.1, §4.2/§4.4/§6) are independent of the R2 fix and the runbook is a docs artefact — fold them into one docs PR that lands **before 2026-05-15 dress-rehearsal** so the on-stage operator works against an accurate guide. §5.2 (wire-tap inbox-routing note) is the load-bearing one for the on-stage script — prioritise that edit.

§4.2/§4.4/§6 (drop the explicit-args workaround language) is conditional on R2 landing first; if R2 slips and we ship R1, leave the explicit-args language in but add a footnote that the natural-routing claim is degraded for R1.

### D6 — Stub-yaml schema parity: **Yes — extend the stub YAML**

Adopt the live KV schema shape in [`stub_capabilities.yaml`](../../src/jarvis/config/stub_capabilities.yaml) so DDR-021 NATS-down soft-fail renders the same `Args:` block. Effort is small (~one `parameters:` block per tool, copy-pasted from the upstream manifest) and prevents the prompt from regressing under degraded operation.

Record as a **DDR amendment** to DDR-021 — "Stub registry must mirror the live KV's tool-parameter schema so the prompt block is shape-stable across the swap." The amendment is a paragraph; the implementation is a YAML edit.

---

## Implementation Surface Summary

The follow-up implementation task should touch **exactly** these surfaces (in this order):

1. **`src/jarvis/tools/capabilities.py`** — Extend `CapabilityToolSummary` with `parameters: dict[str, Any] | None = None`. Extend `as_prompt_block()` to emit the `Args (required):` block when `parameters` is non-`None`.
2. **`src/jarvis/infrastructure/capabilities_registry.py`** — Pipe `tool.parameters` through `_manifest_to_descriptor`'s comprehension.
3. **`src/jarvis/config/stub_capabilities.yaml`** — Add `parameters:` blocks to every tool, mirroring the upstream manifest shapes (DDR amendment).
4. **`src/jarvis/prompts/supervisor_prompt.py`** — Reframe the prose around `list_available_capabilities` to land on "catalogue authoritative" rather than "don't re-query."
5. **Tests** — Snapshot test on `as_prompt_block()` (in PR); integration test against a model fake (P0 follow-up, ≤2 days post-merge).
6. **Runbook docs PR** — §0.5, §4.3, §5.2, §0.1, §4.2/§4.4/§6. Bundle separate from the R2 PR (different review surfaces).

Total: ~40 LOC of source, ~30 LOC of tests, 1 YAML edit, 1 docs PR. Two PRs (code + docs) for clean review.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| R2 lands but `qwen36-workhorse` *still* misshapes args | Low | Demo-blocker | Integration test catches before merge; operator's explicit-args script is the break-glass |
| Snapshot test churns on every manifest description tweak | Medium | Annoying, not blocking | Pin against architect-agent only (1 manifest), not the full fleet — fleet tests stay shape-only |
| Stub YAML drifts from live KV | Medium | DDR-021 path regresses | Add a CI check that `stub_capabilities.yaml` parses as `CapabilityToolSummary` with non-`None` `parameters` (one assertion, no upstream coupling) |
| Token budget creep on a hypothetical large fleet | Low (current fleet) | Future cost | F3 projection covers it; revisit at fleet >30 specialists |

---

## Acceptance Criteria — Crosswalk

| Task body AC | Status | Notes |
|--------------|--------|-------|
| Decision recorded (R1/R2/R3 + go/no-go) | ✅ | R2 by 2026-05-13; R1 fallback branch; explicit-args break-glass |
| `as_prompt_block()` extended; snapshot test | ✅ planned | Implementation task: `TASK-CAPS-PROMPT-001` |
| Integration / E2E test on supervisor payload | ✅ planned | P0 follow-up, ≤2 days post-merge |
| FRR-003 trace audit (post-fix run) | ✅ planned | Re-run runbook end-to-end T-2/T-1 from demo |
| Runbook §0.1/§0.5/§4.2-§4.4/§4.3/§5.2/§6 updated | ✅ planned | Single docs PR; §5.2 prioritised |
| DDR amendment (stub-yaml parity) | ✅ planned | DDR-021 amendment paragraph |
| Naturally phrased prompt → first-attempt success | ✅ planned | Verification gate before the docs PR merges |

---

## Out of Scope (acknowledged)

Bugs #1/#2/#3 closure (`1979aa8`/`08a95fe`/`4d80bd3`), `nats-core` v0.4.0 commit, Forge `queue_build` path, supervisor model-engineering questions, and `qwen36-workhorse` replacement decisions are all explicitly excluded per the task body. R2 is designed to be supervisor-model-agnostic — any reasonably capable supervisor reading the `Args:` block should construct the right payload.

---

## Context Used

- **Code paths walked:** [`capabilities.py:85-164`](../../src/jarvis/tools/capabilities.py#L85-L164), [`capabilities_registry.py:136-168`](../../src/jarvis/infrastructure/capabilities_registry.py#L136-L168), [`supervisor_prompt.py:69-90`](../../src/jarvis/prompts/supervisor_prompt.py#L69-L90), [`dispatch.py:351-405`](../../src/jarvis/tools/dispatch.py#L351-L405), [`stub_capabilities.yaml`](../../src/jarvis/config/stub_capabilities.yaml), upstream [`manifest.py:112-141`](../../../specialist-agent/src/specialist_agent/adapters/manifest.py#L112-L141).
- **Knowledge graph context:** Graphiti enabled in `.guardkit/graphiti.yaml` but MCP tools not loaded in this session — review proceeded from codebase analysis only. ADR-ARCH-002 (leaf-import discipline) and DDR-021 (NATS-down soft-fail) referenced from in-tree docstrings.
- **Sibling task:** `TASK-REV-CB48` closed the dispatch-resolver wiring gap; this task closes the catalogue-render fidelity gap. Together they make capability-name dispatch end-to-end usable from a naturally phrased operator prompt.
- **Evidence corroborated:** Three FRR-003 misshape traces and one workaround-success trace on 2026-05-08 are consistent with the code-level finding F1.
