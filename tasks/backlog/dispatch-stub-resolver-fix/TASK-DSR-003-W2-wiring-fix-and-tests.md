---
id: TASK-DSR-003
title: "W2 — Wire live CapabilitiesRegistry into dispatch resolver + watch callback + tests"
task_type: bugfix
status: backlog
created: 2026-05-08T00:00:00Z
updated: 2026-05-08T00:00:00Z
priority: critical
complexity: 4
wave: 2
implementation_mode: task-work
estimated_minutes: 240
parent_review: TASK-REV-CB48
feature_id: FEAT-DSR
demo_blocker_for: 2026-05-16
depends_on:
  - TASK-DSR-001  # W1 stays in place as the safety net while W2 lands
tags: [jarvis, dispatch, capabilities-registry, feat-j004-followup, ddr-021, watch-callback, integration-test]
context_files:
  - src/jarvis/tools/__init__.py
  - src/jarvis/tools/dispatch.py
  - src/jarvis/infrastructure/lifecycle.py
  - src/jarvis/infrastructure/capabilities_registry.py
  - tests/test_assemble_tool_list.py
  - tests/test_dispatch_by_capability_integration.py
  - tests/test_lifecycle_feat_j004_wiring.py
  - .claude/reviews/TASK-REV-CB48-review-report.md
  - tasks/completed/TASK-J004-FIX-001/TASK-J004-FIX-001.md  # structural twin precedent
  - docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md
test_results:
  status: pending
  coverage: null
  last_run: null
acceptance_criteria_status:
  AC-001: pending  # _dispatch._capability_registry sourced from capabilities_registry.snapshot()
  AC-002: pending  # subscribe_updates callback rebinds the dispatch slot on KV change
  AC-003: pending  # NATS-down (StubCapabilitiesRegistry) path remains byte-equivalent to today
  AC-004: pending  # Divergent-registry integration test (F3 fixture) lands and passes
  AC-005: pending  # StubCapabilitiesRegistry parity test lands and passes
  AC-006: pending  # mypy clean
  AC-007: pending  # Full pytest green
---

# Task: W2 — Wire live CapabilitiesRegistry into dispatch resolver

## Description

Canonical close of the DISPATCH-STUB-RESOLVER gap surfaced by TASK-REV-CB48.
Replaces the stub-list snapshot at `tools/__init__.py:263` with a snapshot
sourced from the Protocol-shaped `capabilities_registry`, and wires a
KV-watch-driven callback that rebinds the dispatch slot whenever the live
registry refreshes.

This is the structural twin of [TASK-J004-FIX-001](../../completed/TASK-J004-FIX-001/TASK-J004-FIX-001.md)
(B1 — closed the catalogue-tool side of the same wiring inconsistency). The
review's F2 finding confirmed the Protocol shape is identical between
`LiveCapabilitiesRegistry.snapshot()` and `StubCapabilitiesRegistry.snapshot()`
(both return `list[CapabilityDescriptor]`), so this is a drop-in replacement
with no shape mismatch.

## Implementation

### Step 1 — `src/jarvis/tools/__init__.py` line 263

Replace:

```python
_dispatch._capability_registry = list(capability_registry)
```

With:

```python
def _refresh_dispatch_registry() -> None:
    """Rebind the dispatch slot from the live registry's snapshot.

    Called once at wireup, then on every KV-watch change via the Live
    registry's subscribe_updates callback. The Stub path's
    subscribe_updates is a documented no-op (DDR-021 NATS-down) so this
    closure runs exactly once on NATS-down boots. ASSUM-006: rebinding
    the module attribute is atomic; in-flight dispatch tool calls
    capture a local list copy at dispatch.py:438 and remain consistent.
    """
    _dispatch._capability_registry = list(capabilities_registry.snapshot())

_refresh_dispatch_registry()
asyncio.create_task(
    capabilities_registry.subscribe_updates(_refresh_dispatch_registry),
    name="dispatch_capability_kv_watch",
)
```

Add `import asyncio` if not already imported in the module.

The `capability_registry` positional argument stays — the supervisor's prompt
block consumes it via `available_capabilities` at `lifecycle.py:738`. Removing
the redundant arg is out-of-scope (would touch the supervisor prompt assembly).

### Step 2 — Update the line-263 docstring block (lines 254-262)

The existing comment block at lines 254-262 references the stub-list source.
Update it to reflect the new live-source semantics:

```python
# 3. Snapshot-bind the dispatch slot to the live capabilities registry.
#
# The Protocol-shaped ``capabilities_registry`` is the source of truth
# for both catalogue tools (slot 2 above) and the dispatch resolver
# (this slot). The stub-list ``capability_registry`` argument now
# feeds only the supervisor prompt block (via
# ``available_capabilities=`` at the build_supervisor call site).
#
# A subscribe_updates callback rebinds this slot whenever the Live
# registry's KV watch fires; the Stub registry's subscribe_updates is
# a documented no-op so DDR-021 NATS-down boots run the wireup once
# and stay there. ASSUM-006: rebinding the attribute is atomic; the
# dispatch tool's per-call ``list(_capability_registry)`` snapshot at
# dispatch.py:438 means in-flight calls remain consistent.
```

### Step 3 — Integration test (the F3 fixture from review)

Add a new test to `tests/test_assemble_tool_list.py`:

```python
def test_dispatch_resolver_observes_live_registry_for_divergent_content(
    self,
    test_config: JarvisConfig,
    descriptor_alpha: CapabilityDescriptor,
    descriptor_beta: CapabilityDescriptor,  # build via fixture or factory
    reset_tool_state: None,
) -> None:
    """Regression: dispatch resolver MUST find tools published by the live
    registry even when they are absent from the stub list (the W2 / TASK-DSR-003
    closure of the DISPATCH-STUB-RESOLVER gap surfaced by TASK-REV-CB48)."""

    class _ListBackedRegistry:
        # Same shape as the existing helper at line 358 of this file.
        def __init__(self, descriptors): self._descriptors = descriptors
        def snapshot(self): return list(self._descriptors)
        async def refresh(self): return None
        async def subscribe_updates(self, callback): return None
        async def close(self): return None

    # Stub list contains alpha only; live registry contains beta only.
    assemble_tool_list(
        test_config,
        [descriptor_alpha],
        capabilities_registry=_ListBackedRegistry([descriptor_beta]),
    )

    from jarvis.tools import dispatch as _dispatch_module
    snapshot = list(_dispatch_module._capability_registry)
    agent_ids = {d.agent_id for d in snapshot}
    # The dispatch slot reflects the LIVE registry, not the stub list.
    assert "beta" in agent_ids
    assert "alpha" not in agent_ids
```

`descriptor_beta` may need a new fixture or local factory (mirror the existing
`descriptor_alpha` shape with `agent_id="beta"` and a single `CapabilityToolSummary`
whose `tool_name` is e.g. `"beta_tool"`).

### Step 4 — StubCapabilitiesRegistry parity test

Add to `tests/test_capabilities_registry.py` (or wherever the existing
StubCapabilitiesRegistry tests live):

```python
def test_stub_registry_snapshot_matches_load_stub_registry_directly(
    tmp_path,
) -> None:
    """DDR-021 graceful degradation guarantee: StubCapabilitiesRegistry.snapshot()
    must return content equivalent to load_stub_registry(fallback_path) so that
    the W2 dispatch wiring (TASK-DSR-003) keeps NATS-down behaviour byte-equivalent
    to the pre-W2 stub-list source."""
    yaml_path = tmp_path / "stub_capabilities.yaml"
    yaml_path.write_text(_MINIMAL_VALID_YAML)  # use existing test fixture

    direct = load_stub_registry(yaml_path)
    via_registry = StubCapabilitiesRegistry(yaml_path).snapshot()

    assert direct == via_registry
```

### Step 5 — KV-watch invalidation rebind test (optional but recommended)

If `tests/test_lifecycle_feat_j004_wiring.py` or a similar test already
exercises the Live registry's KV-watch path with a fake watcher, add an
assertion that the dispatch slot rebinds when the watch fires:

```python
async def test_dispatch_slot_rebinds_when_kv_watch_fires(...):
    """W2 watch-callback regression: a KV update must rebind
    _dispatch._capability_registry to reflect the new snapshot."""
    # Use the existing fake watcher pattern from test_capabilities_registry.py
    # to drive a single update event, then assert the dispatch slot's
    # contents changed.
```

This is best-effort — if the existing test infrastructure for fake watchers
is not in place, file as a follow-up. The integration test in Step 3 covers
the wireup path; the watch-callback rebind is the harder edge to assert.

## Acceptance Criteria

- [ ] **AC-001:** `tools/__init__.py:263` no longer reads
      `capability_registry` for the dispatch slot; the slot is sourced from
      `capabilities_registry.snapshot()` at boot via the new closure.
- [ ] **AC-002:** A `subscribe_updates(_refresh_dispatch_registry)` callback
      is registered on the `capabilities_registry` (fire-and-forget via
      `asyncio.create_task`); rebinds the dispatch slot when the Live KV
      watch fires.
- [ ] **AC-003:** NATS-down path remains byte-equivalent — when
      `capabilities_registry` is a `StubCapabilitiesRegistry`,
      `_dispatch._capability_registry` after wireup contains the same
      descriptors `list(capability_registry)` would have produced under the
      old wiring. Asserted by the parity test (Step 4) and by re-running the
      DDR-021 NATS-down test cases in `test_lifecycle_feat_j004_wiring.py`.
- [ ] **AC-004:** Divergent-registry integration test (Step 3) lands and
      passes — the dispatch slot reflects the live registry's content, not
      the stub list's, when the two diverge.
- [ ] **AC-005:** StubCapabilitiesRegistry parity test (Step 4) lands and
      passes.
- [ ] **AC-006:** `mypy` is clean (`mypy src/jarvis tests`).
- [ ] **AC-007:** Full pytest green (`pytest tests/`); no existing test
      regresses.
- [ ] **AC-008:** Manual smoke — boot Jarvis with the dual-role stack against
      the GB10 host, dispatch `architect_align`, observe an
      `agents.command.architect-agent.<corr>` envelope land on JetStream.
      (TASK-DSR-004 owns the full end-to-end runbook re-run; this AC is the
      narrowest happy-path smoke for W2 alone.)

## Notes

- ASSUM-006 (`tools/__init__.py:256-262` original comment) already covers the
  rebind-not-mutate concurrency guarantee. No additional locking required —
  the GIL makes the attribute rebind atomic, and the dispatch tool's
  `list(_capability_registry)` snapshot at the start of each invocation
  isolates in-flight calls from rebind events.
- W1 (TASK-DSR-001) stays in place. W2 makes the W1 yaml entries redundant
  for the dispatch path, but the yaml is still the DDR-021 NATS-down source
  of truth so the entries remain useful as a known-good fleet baseline.
- See review report R5 — stub-yaml deprecation question is deferred to a
  post-demo task. Do not delete or rename the yaml in this task.

## Out of Scope

- Removing the redundant `capability_registry` positional argument from
  `assemble_tool_list` (still consumed by the supervisor prompt block).
- Stub-yaml deprecation / rename / CI drift lint (review report R5).
- Runbook §2.5 rewrite — TASK-DSR-004.
- End-to-end runbook re-run — TASK-DSR-004.

## See Also

- [Review report](../../../.claude/reviews/TASK-REV-CB48-review-report.md) — R2 + R3.
- [`tools/__init__.py:263`](../../../src/jarvis/tools/__init__.py#L263) — line to change.
- [`capabilities_registry.py`](../../../src/jarvis/infrastructure/capabilities_registry.py) — Protocol surface and Live/Stub impls.
- [TASK-J004-FIX-001](../../completed/TASK-J004-FIX-001/TASK-J004-FIX-001.md) — structural twin precedent.
- [TASK-DSR-001](./TASK-DSR-001-W1-stub-yaml-patch.md) — W1 insurance, stays in place.
- [TASK-DSR-004](./TASK-DSR-004-runbook-final-rewrite-and-verification.md) — runbook §2.5 + end-to-end verification, runs after this task.
