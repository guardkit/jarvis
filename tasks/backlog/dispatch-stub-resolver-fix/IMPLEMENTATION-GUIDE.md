# Implementation Guide — Dispatch Stub-Resolver Fix

**Source review:** [TASK-REV-CB48](../TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md) · [report](../../../.claude/reviews/TASK-REV-CB48-review-report.md)

## Execution Strategy

### Wave 1 — Demo Insurance (today, 2026-05-08)

**Run in parallel** (different files, no shared state):

| Task | File touched | Mode | Outcome |
|---|---|---|---|
| TASK-DSR-001 (W1) | `src/jarvis/config/stub_capabilities.yaml` | direct | Adds `architect_align`, `architect_greenfield`, `architect_explore`, `architect_feasibility` to architect-agent's `capability_list`. |
| TASK-DSR-002 (Runbook) | `docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md` | direct | §0 stub↔live gate added; §6 `unresolved` row corrected. |

**Verification (Wave 1 close):** Boot Jarvis with the dual-role stack, dispatch `architect_align` once, confirm the trace lands an `agents.command.architect-agent.<corr>` envelope.

### Wave 2 — Real Fix (by 2026-05-15 dress rehearsal)

| Task | Files touched | Mode | Outcome |
|---|---|---|---|
| TASK-DSR-003 (W2) | `src/jarvis/tools/__init__.py`, `tests/test_assemble_tool_list.py` (new test cases), `tests/test_capabilities_registry.py` (parity test) | task-work | Replaces the stub-list snapshot with `list(capabilities_registry.snapshot())`; wires `subscribe_updates` for KV-driven invalidation; adds the F3 divergent-registry test and the StubCapabilitiesRegistry parity test. |

**Why task-work, not direct:** Production code change in the wiring path; test additions are the new regression contract. Full quality gates (mypy + pytest + architectural review) needed.

**Why a closure for the refresh:** The watch-driven invalidation must rebind the module attribute — not mutate a captured list — so each subsequent `dispatch_by_capability` call picks up the new snapshot via `dispatch.py:438`'s `list(_capability_registry)`. Per ASSUM-006 (already documented at `tools/__init__.py:256-262`), this rebind is atomic under the GIL and safe against in-flight dispatch tool calls.

**Why `subscribe_updates` is fire-and-forget:** It's idempotent (`capabilities_registry.py:409-413`), self-logging on watcher-open failure (lines 422-429), and a no-op for the `StubCapabilitiesRegistry` path (line 569). Wrapping the call in `asyncio.create_task(...)` keeps `assemble_tool_list` synchronous and side-effect-free for callers, matching its existing contract.

### Wave 3 — Final Polish + Verification (after Wave 2 verified)

| Task | File touched | Mode | Outcome |
|---|---|---|---|
| TASK-DSR-004 | `docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md` + end-to-end re-run | task-work | §2.5 rewrite (announce that the stub↔live divergence note is obsolete post-W2). Re-runs the runbook against the dual-role stack on the GB10 host; AC: a real `AlignmentJudgment` lands in the chat REPL. |

## Indicative W2 Diff (TASK-DSR-003)

```python
# src/jarvis/tools/__init__.py — replace the line-263 wiring step:

# BEFORE:
_dispatch._capability_registry = list(capability_registry)

# AFTER:
def _refresh_dispatch_registry() -> None:
    """Rebind the dispatch slot from the live registry's snapshot.

    Called once at wireup time, then on every KV-watch change via the
    Live registry's subscribe_updates callback. The Stub path's
    subscribe_updates is a documented no-op (the YAML cannot change at
    runtime) so this closure runs exactly once on NATS-down boots.
    Per ASSUM-006 the rebind is atomic; in-flight dispatch tool calls
    capture a local list copy at dispatch.py:438 and remain consistent.
    """
    _dispatch._capability_registry = list(capabilities_registry.snapshot())

_refresh_dispatch_registry()
asyncio.create_task(
    capabilities_registry.subscribe_updates(_refresh_dispatch_registry),
    name="dispatch_capability_kv_watch",
)
```

The `capability_registry` positional argument can stay as the second positional — the supervisor's prompt block still consumes it via `available_capabilities` at `lifecycle.py:738`. Removing it is out-of-scope for this task (would touch the supervisor prompt assembly path).

## Acceptance Criteria Mapping (from review report)

| Review AC | Subtask | Note |
|---|---|---|
| Decision recorded with go/no-go date | DSR-001 (W1 ships today) + DSR-003 (W2 by 2026-05-15) | If DSR-003 slips, DSR-001 holds the demo. |
| W2 wiring fix + watch callback + DDR-021 graceful path | DSR-003 | StubCapabilitiesRegistry's `snapshot()` returns yaml-loaded descriptors, byte-equivalent to today's NATS-down behaviour. |
| Integration test for divergent-registry resolver path | DSR-003 | The F3 test fixture passes different content to the stub list and the live kwarg; asserts `dispatch_by_capability(tool_name=<live-only>, ...)` advances past the resolver. |
| FEAT-JARVIS-004 test-corpus audit | (review report F3) | Already documented: existing test exists, did not fire because content was identical. New test in DSR-003 closes the assertion gap. |
| Runbook §2.5/§6/§0 updates | DSR-002 (§0 + §6) + DSR-004 (§2.5) | §2.5 rewrite is post-W2 because its content depends on W2's status. |
| End-to-end re-run lands real `architect_align → align` envelope and `AlignmentJudgment` | DSR-004 | Verification gate. |
| DDR/amendment for stub-yaml decision | Out-of-scope here; see review report R5 | Recommendation: keep yaml, rename role, add CI drift lint. File post-demo. |

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| W2 introduces a regression on NATS-down path | Low | High | Parity test asserts `StubCapabilitiesRegistry.snapshot()` matches `load_stub_registry(fallback_path)` directly. |
| KV-watch subscribe fails at startup | Low (existing soft-fail pattern) | Low | `subscribe_updates` already logs and continues per `capabilities_registry.py:422-429`. Dispatch still works against the warm-cache snapshot. |
| W2 slips past 2026-05-15 | Medium | High | W1 (DSR-001) is independent. Demo runs on W1 + Wave 1 runbook updates if needed. |
| Test corpus audit (R3) reveals additional gaps | Low | Medium | The F3 fixture is the smallest closure of the category. Future divergence types (e.g. risk_level mismatch) can land as follow-ups. |
