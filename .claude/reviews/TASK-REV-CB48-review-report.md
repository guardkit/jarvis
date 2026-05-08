# Review Report: TASK-REV-CB48 — DISPATCH-STUB-RESOLVER wiring gap

**Status:** REVIEW_COMPLETE — awaiting decision checkpoint
**Mode:** decision · **Depth:** standard · **Date:** 2026-05-08
**Demo blocker for:** DDD South West 2026-05-16 (dress rehearsal 2026-05-15)

---

## Executive Summary

The task author's root-cause hypothesis is **fully validated** against the live source tree. `tools/__init__.py:263` wires `list(capability_registry)` (the stub list) into `_dispatch._capability_registry`, while `tools/__init__.py:252` correctly wires the Protocol-shaped `capabilities_registry` (Live or Stub) into the catalogue-tool slot. The dispatch resolver iterates the stub list at `dispatch.py:438`, so any tool name published in the live KV but absent from `stub_capabilities.yaml` returns `ERROR: unresolved` — exactly the failure captured in the three 2026-05-08 traces.

Both `LiveCapabilitiesRegistry.snapshot()` and `StubCapabilitiesRegistry.snapshot()` return `list[CapabilityDescriptor]` — the exact shape `_dispatch._capability_registry` consumes. **W2 is mechanically a drop-in replacement** with no shape mismatch and no concurrency hazard new to ASSUM-006.

This is the structural twin of TASK-REV-FFE4 (catalogue-side wiring gap, completed via TASK-J004-FIX-001 / option B1 "refactor"). The same machinery is shipped, the same `assemble_tool_list` signature already accepts both registries, and exactly one wiring step is plumbed wrong on the dispatch side. **The precedent strongly favours W2 over W1.**

**Recommendation: Hybrid plan.** Land W1 immediately (one yaml edit, ≤15 minutes including verification) as an unconditional safety net for the demo. Land W2 in parallel for the 2026-05-15 dress rehearsal; if W2 slips, W1 holds the demo. After W2 ships and is verified end-to-end, defer the stub-yaml deprecation question (decision 5) to a separate task — it is cleanly out-of-band of the demo window.

**Architectural Score:** 78/100 (one wiring miss in otherwise well-designed dual-registry topology — same-shape gap as FFE4, both halves now ready to close)

**Findings:** 6 · **Recommendations:** 5

---

## Review Details

- **Mode:** decision
- **Depth:** standard
- **Reviewer:** task-review (LLM-driven, no Graphiti context available — reviewing from codebase analysis only)
- **Scope:** Wiring correctness, runtime fix selection, demo-unblock path
- **Trade-off priority (from task):** Time-critical correctness — real fix preferred over workaround if it fits the window
- **Validation method:** Direct read of all five context files + cross-check against TASK-REV-FFE4 + test-corpus audit

---

## Findings

### F1. Root-cause hypothesis validated end-to-end (Severity: critical)

**Evidence:**
- `src/jarvis/tools/dispatch.py:438` — `registry_snapshot = list(_capability_registry)` reads from the **stub** module attribute set at line 263 of `tools/__init__.py`.
- `src/jarvis/tools/dispatch.py:486-489` — emits the literal string `"ERROR: unresolved — no capability matches tool_name=… intent_pattern=…"` on resolver miss; matches verbatim with the chat-log evidence file.
- `src/jarvis/tools/__init__.py:252-263` — split wiring confirmed:
  - Line 252 (catalogue slot): `_capabilities._capability_registry = capabilities_registry` ← Protocol-shaped (Live or Stub)
  - Line 263 (dispatch slot): `_dispatch._capability_registry = list(capability_registry)` ← stub list snapshot
- `src/jarvis/config/stub_capabilities.yaml` — architect-agent's `capability_list` contains `run_architecture_session` + `draft_adr` only. No `architect_align`, `architect_greenfield`, `architect_explore`, `architect_feasibility`.
- `src/jarvis/infrastructure/lifecycle.py:628` — Live registry constructed via `LiveCapabilitiesRegistry.create(nats_client)`; lines 637/639 fall back to `_build_stub_capabilities_registry` when NATS-down (DDR-021).

**Conclusion:** Production boots with two registries that diverge whenever the live fleet publishes tool names absent from the stub yaml. The dispatch resolver iterates only the stub list. `architect_align` is exactly such a tool. Behaviour matches the three captured traces (`outcome_type: "unresolved"`, empty `attempts` and `visited`, zero envelopes on `agents.command.architect-agent.>`).

### F2. Wireup machinery is fully shipped — fix is one line plus a callback (Severity: high — positive)

**Evidence:**
- `src/jarvis/infrastructure/capabilities_registry.py:88-118` — `CapabilitiesRegistry` Protocol exposes `snapshot()`, `refresh()`, `subscribe_updates(callback)`, `close()`.
- Both implementations return `list[CapabilityDescriptor]` from `snapshot()` (lines 342-349 Live, 557-559 Stub) — **identical shape to what the dispatch slot already expects**.
- `LiveCapabilitiesRegistry.subscribe_updates` (line 394) is idempotent; the watch loop at line 432 fires the supplied callback after every cache invalidation.
- `StubCapabilitiesRegistry.subscribe_updates` (line 569) is a documented no-op — correct because the yaml cannot change at runtime — so the W2 callback wires up safely on the NATS-down path too.
- `assemble_tool_list` already accepts `capabilities_registry` as a kwarg (signature confirmed at `tools/__init__.py:208-221` of the docstring; called at `lifecycle.py:703/722`).

**Conclusion:** No new contracts, no new code paths, no signature changes. The fix is a 3-4 line edit plus a new local closure. This is the same shape as TASK-REV-FFE4: the machinery shipped, the wiring step missed.

### F3. Test corpus does not exercise divergent registry content (Severity: high)

**Evidence:**
- `tests/test_assemble_tool_list.py:376-380` (the `test_list_available_capabilities_observes_snapshot` test added by TASK-J004-FIX-001):
  ```python
  assemble_tool_list(
      test_config,
      [descriptor_alpha],                                          # stub list (positional)
      capabilities_registry=_ListBackedRegistry([descriptor_alpha]) # live kwarg
  )
  ```
  **Both arguments carry the same `descriptor_alpha`.** When the two registries' contents are identical, the wiring gap is invisible — the dispatch resolver finds the tool because the stub snapshot accidentally matches the live view.

**Why the gap shipped through:** The FFE4 review correctly closed the catalogue-tool side (the slot at line 252) and added a test that exercises the catalogue path. That test does not — and was not designed to — exercise the dispatch resolver's view of a Live-only tool. The latent divergence between the two slots was inert in test fixtures and only fired in production where the Live KV publishes tools the stub yaml does not list.

**Conclusion:** AC #4 has a concrete answer: **yes, an existing test exercises `assemble_tool_list` end-to-end, but no, it did not fire the gap because the test fixture passes identical content to both inputs.** The FEAT-JARVIS-004 corpus was honest about what it asserts (catalogue path); it just did not assert the dispatch path against divergent registry content. The W2 regression test is therefore the *new* assertion the corpus needs, not a fix to an existing test.

### F4. W3 (intent_pattern fallback) is verifiably unreliable (Severity: medium)

**Evidence:**
- `RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md` records attempt 3 explicitly testing the fallback: the supervisor `qwen36-workhorse` was instructed to call `dispatch_by_capability(tool_name="architect_align", intent_pattern="Architect", …)` and dropped the `intent_pattern` arg from the tool call payload (`chat-attempt3-intent-pattern-arg-dropped.log`).
- `tools/dispatch.py:249-254` confirms the resolver does have a role-based fallback that *would* have rescued the call — but the resolver never sees the arg the supervisor never sends.

**Conclusion:** W3 is a model-behaviour bet, not an architectural fix. Even if a larger supervisor model preserves the arg reliably, depending on prompt-following at a critical demo moment is a risk class the runbook explicitly cannot tolerate. **Reject W3 as primary path. Document as informational ("works if supervisor honours the explicit arg") but do not select.**

### F5. W2 has no concurrency hazard new to ASSUM-006 (Severity: low — positive)

**Evidence:**
- `dispatch.py:438` snapshots once per invocation: `registry_snapshot = list(_capability_registry)`. The dispatch tool body reads its own local `registry_snapshot` for the entire call.
- `tools/__init__.py:263` already states ASSUM-006: *"a concurrent rebinding of the attribute (e.g. by a future Phase 3 `capabilities_refresh` follow-up) replaces the list rather than mutating it in place; the in-flight tool calls capture a local reference at the start of each invocation so they remain consistent."*
- W2's refresh callback (`_dispatch._capability_registry = list(capabilities_registry.snapshot())`) is a single attribute rebind. The Python GIL makes the rebind atomic; in-flight dispatches see either the old or new list, never a half-written one.

**Conclusion:** No locking is required. The KV-watch callback firing during an in-flight dispatch is exactly the case ASSUM-006 was written for. W2 fits the existing concurrency model.

### F6. Runbook §2.5 misleads operators in a load-bearing way (Severity: high)

**Evidence:** Task description quotes §2.5: *"live KV watch replaces the stub entries"*. This is half-correct:
- True for the prompt-block injection (catalogue tools read `capabilities_registry` per F1 evidence).
- False for the dispatch resolver (still reads the stub-yaml snapshot per F1 evidence).

An operator who trusted §2.5 would expect Phase 4 to work the moment the live KV warmed; that expectation cost three independent dispatch attempts on 2026-05-08. The note is the most consequential of the three runbook follow-ups: it sets the operator's mental model. §6 (failure-modes table fix) and §0 (pre-flight gate) are smaller corrections downstream of getting §2.5 right.

---

## Decision Matrix

| Option | Demo-safe by 05-16 | Closes the gap | Test cost | Blast radius | Recommendation |
|---|---|---|---|---|---|
| **W1** — patch yaml | ✅ Yes (one edit, reversible) | ❌ Masks; future divergence reopens it | Trivial (`load_stub_registry` test) | Single config file | **Land first. Insurance for the demo.** |
| **W2** — fix wiring | ✅ Likely (small, well-scoped diff) | ✅ Yes — closes the structural gap | One integration test (the F3 fixture) + StubCapabilitiesRegistry parity test | `tools/__init__.py` (~5 lines + closure) | **Land in parallel. Canonical close.** |
| **W3** — intent_pattern | ❌ Unreliable (F4 evidence) | ❌ Doesn't touch the resolver | n/a | Supervisor prompt only | **Reject as primary path.** |

**Recommended decision: Hybrid (W1 + W2).** W1 is the failsafe; W2 is the durable close. The two are independent — landing W1 first has zero impact on W2's diff (W2 simply makes the W1 yaml edit redundant for the dispatch path; the yaml is still load-bearing for DDR-021 NATS-down soft-fail).

---

## Recommendations

### R1. Land W1 today (`stub_capabilities.yaml` patch) — 15 minutes

**What:** Add `architect_align`, `architect_greenfield`, `architect_explore`, `architect_feasibility` to architect-agent's `capability_list` in `src/jarvis/config/stub_capabilities.yaml`, mirroring the live KV's published surface.

**Why this first:** Reversible, single-file change, demo-safe. Even if W2 lands and is reverted, W1 keeps the dispatch resolver finding the tool in the worst case. Pure insurance — the cost is one PR, the upside is the demo holds regardless of W2 status.

**Verification:** Re-boot Jarvis with the dual-role stack and dispatch `architect_align` once. The trace should land an `agents.command.architect-agent.<corr>` envelope on JetStream.

**Caveat:** W1 alone leaves the structural gap open. Any future architect-agent tool added to the live KV without a corresponding yaml edit re-fires the same bug. Treat W1 as a tourniquet, not a fix.

### R2. Land W2 (real wiring fix) for 2026-05-15 dress rehearsal

**What (`tools/__init__.py` around line 263):**
```python
# Replace:
_dispatch._capability_registry = list(capability_registry)

# With:
def _refresh_dispatch_registry() -> None:
    _dispatch._capability_registry = list(capabilities_registry.snapshot())

_refresh_dispatch_registry()
# Best-effort wireup; the Live impl opens a KV watch, the Stub impl is a no-op.
asyncio.create_task(capabilities_registry.subscribe_updates(_refresh_dispatch_registry))
```

**Why the closure:** The watch-driven invalidation must rebind the module attribute (not mutate a captured list), so each future dispatch picks up the rebind via `dispatch.py:438`'s `list(_capability_registry)`. The closure captures `capabilities_registry` from the enclosing scope; that scope is `assemble_tool_list`, which is called once per startup.

**Why `subscribe_updates` is fire-and-forget:** It's idempotent (line 409-413) and self-logging on failure (lines 422-429). A KV-watch open failure is operator-relevant but not startup-blocking — same DDR-021 soft-fail philosophy as the rest of the boot path.

**Why this preserves DDR-021 NATS-down behaviour:** When `capabilities_registry` is a `StubCapabilitiesRegistry` (NATS-down path, lifecycle.py:637/639), `snapshot()` returns `load_stub_registry(fallback_path)` — i.e. the same content `list(capability_registry)` returns today. NATS-down dispatch behaviour is byte-equivalent.

**Concurrency note:** No lock needed (F5). ASSUM-006 already documents the rebind-not-mutate contract; W2 honours it.

### R3. Add the F3 integration test as part of W2

**What:** A test that drives `assemble_tool_list` with **divergent** content:
```python
stub_descriptors = [descriptor_alpha]   # alpha-only
live_descriptors = [descriptor_beta]    # beta-only
assemble_tool_list(
    test_config,
    stub_descriptors,                                # positional → stub slot
    capabilities_registry=_ListBackedRegistry(live_descriptors),
)
# Assert: dispatch_by_capability(tool_name=<beta-tool>, ...) does NOT return
# ERROR: unresolved (it should at minimum advance past the resolver into
# the wire/timeout path; the exact downstream outcome can be mocked).
```

**Why this matters more than scope:** This is the assertion the FFE4 corpus did not make. Land it as part of W2 and it permanently closes the *category* of bug, not just this instance — any future divergence between Live and Stub regression-tests this same gap.

**Also add:** A parity test asserting `StubCapabilitiesRegistry.snapshot()` returns content equivalent to `load_stub_registry(fallback_path)` directly. This is the DDR-021 graceful-degradation guarantee the W2 path now relies on; a future StubCapabilitiesRegistry refactor that breaks it would silently break NATS-down dispatch.

### R4. Runbook updates (decision 4 — three sections)

Order them by load-bearing-ness, fix in this order:

1. **§2.5 "Catalogue-vs-stub note"** — rewrite. Suggested text:
   > *Until DISPATCH-STUB-RESOLVER closes (TASK-REV-CB48), the live KV watch only replaces the stub entries the **prompt block** sees. The dispatch resolver iterates the static stub yaml regardless of what the live KV publishes. Operators must keep `stub_capabilities.yaml` aligned with the live fleet for any tool name they intend to dispatch by `dispatch_by_capability(tool_name=…)`. Once W2 ships, this note is obsolete and should be deleted.*

2. **§6 "failure modes" — `unresolved` row.** Replace the "restart jarvis chat" advice with: *"Confirm `stub_capabilities.yaml` lists the tool name. If absent, add it (W1) or land DISPATCH-STUB-RESOLVER fix (W2). Restarting jarvis without editing the yaml does not change the resolver's view."*

3. **§0 pre-flight — new gate.** Add: *"Stub↔Live alignment: confirm every `tool_name` the supervisor will dispatch in this run is present in `stub_capabilities.yaml` for the matching `agent_id`. Until W2 lands, this is the single guard that saves the demo."*

When W2 ships and is verified, §2.5 can be deleted entirely, the §6 row reverts to a generic resolver-failure entry, and §0's gate is downgraded to advisory (still useful, no longer load-bearing).

### R5. Defer stub-yaml deprecation (decision 5)

**Position:** **Keep the stub yaml after W2.** Rationale:
- It still serves DDR-021 (NATS-down soft-fail) — the StubCapabilitiesRegistry path at lifecycle.py:637/639 reads it.
- A known-good baseline of fleet capabilities is operationally useful as a NATS-down safety net independent of the dispatch question.
- Deprecation is reversible work that does not block the demo and benefits from being scoped after W2 settles.

**Action:** File a follow-up task post-demo to:
- Rename the file's documented purpose ("dispatch resolver source of truth + DDR-021 fallback" → "DDR-021 NATS-down fallback only") in its YAML header comment and in any docs that reference it.
- Add a CI lint that warns when the stub yaml's tool list and a snapshot of the live KV diverge at startup. Lint, not a build break — divergence is allowed by design once W2 ships, but a warning surfaces drift to operators.

This avoids a contentious "delete the stub" debate while properly scoping its remaining role.

---

## Acceptance-Criteria Mapping

| AC from task | Met by | Status |
|---|---|---|
| Decision recorded with go/no-go date | Hybrid plan (W1+W2). Go date: W1 today, W2 by 2026-05-15 dress rehearsal; W1 alone is acceptable for demo if W2 slips | ✅ Recorded above |
| W2 implementation lands wiring fix + watch callback + DDR-021 graceful path | R2 specifies the diff; F5 confirms no lock needed; StubCapabilitiesRegistry parity covered | ✅ Specified |
| Integration test for divergent-registry resolver path | R3 specifies the fixture and the parity test | ✅ Specified |
| FEAT-JARVIS-004 test-corpus audit | F3 + R3 — explicit finding: existing test exists, did not fire because content was identical; the new assertion is what the corpus is missing | ✅ Documented |
| Runbook §2.5/§6/§0 updates | R4 with suggested replacement text in load-bearing order | ✅ Specified |
| End-to-end re-run lands a real `architect_align → align` envelope and `AlignmentJudgment` | Verification gate after W2 ships — outside this review's scope | ⏳ Pending W2 |
| DDR (or amendment) for stub-yaml decision | R5 defers; recommendation is keep, rename, lint | ✅ Recommendation recorded; DDR amendment optional |

---

## Out of Scope (acknowledged)

Confirmed unaffected by this review per task §"Out of Scope":
- Forge dispatch path (FEAT-JARVIS-INTERNAL-001) — `queue_build` uses a separate registry-free path; verified at `tools/__init__.py:280` (`_dispatch._forge_subscriber = forge_subscriber`).
- Supervisor's hallucinated "no heartbeat" prose — model behaviour, not wiring.
- Supervisor's failure to honour explicit `intent_pattern` — F4 confirms it's a model-behaviour question, separate from the resolver fix.
- FEAT-JARVIS-005 tool surface — separate registry-free path.

---

## Context Used

No Graphiti knowledge graph context was loaded for this review (the MCP tools were not available in this session and no `.guardkit/graphiti.yaml` was present). The review was conducted from direct codebase analysis only:

- `src/jarvis/tools/__init__.py` lines 120-289 (assemble_tool_list signature, slot wiring, ASSUM-006)
- `src/jarvis/tools/dispatch.py` lines 420-500 (resolver loop, error string)
- `src/jarvis/infrastructure/lifecycle.py` lines 540-740 (registry construction, DDR-021 fallback, assemble_tool_list call sites)
- `src/jarvis/infrastructure/capabilities_registry.py` (Protocol + Live + Stub implementations, lock semantics)
- `src/jarvis/config/stub_capabilities.yaml` (architect-agent capability_list — confirms the missing tool names)
- `tests/test_assemble_tool_list.py` lines 340-390 (the FFE4-added catalogue test — confirms the test-corpus gap)
- `tasks/completed/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md` (precedent: structurally identical, B1 chosen, TASK-J004-FIX-001 shipped)

---

## Decision Checkpoint

```
=========================================================================
REVIEW COMPLETE: TASK-REV-CB48
=========================================================================

Architecture Score: 78/100 (one wiring miss in otherwise sound dual-registry topology)
Findings: 6 · Recommendations: 5 · Severity: critical (demo blocker)

Key Recommendations:
  R1. Land W1 (yaml patch) today — demo insurance
  R2. Land W2 (real wiring fix + watch callback) for 2026-05-15
  R3. Add F3 integration test (divergent-registry resolver assertion) with W2
  R4. Runbook §2.5 / §6 / §0 updates per load-bearing order
  R5. Keep stub yaml post-W2; rename role to "DDR-021 fallback only"; add CI drift lint

Decision Options:
  [A]ccept   — Approve hybrid plan, archive review, await implementation tasks
  [R]evise   — Request deeper analysis (e.g. cache_ttl semantics, watcher restart, …)
  [I]mplement — Create implementation subtasks (W1 + W2 + tests + runbook)
  [C]ancel   — Discard review

Recommended choice: [I]mplement (hybrid: W1 immediate, W2 by 2026-05-15)
=========================================================================
```
