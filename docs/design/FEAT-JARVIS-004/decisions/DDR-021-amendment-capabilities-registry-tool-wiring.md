# DDR-021 Amendment — Capabilities registry Protocol must reach the catalogue tool slot

- **Status:** Accepted
- **Date:** 2026-04-30
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration) — follow-up bugfix wave
- **Amends:** [DDR-021 — NATS unavailable → soft-fail at startup](DDR-021-nats-unavailable-soft-fail.md)
- **Implementing task:** TASK-J004-FIX-001 (`tasks/in_progress/TASK-J004-FIX-001-wire-capabilities-registry-through-assemble-tool-list.md`)
- **Triggering review:** [TASK-REV-FFE4 — feat-j004 capabilities-registry wiring inconsistency](../../../../.claude/reviews/TASK-REV-FFE4-review-report.md)

## Context — the latent defect DDR-021 implicitly assumed away

DDR-021 §3 specified that on the NATS-down branch the catalogue tools at
`jarvis.tools.capabilities._capability_registry` must speak the
`CapabilitiesRegistry` Protocol surface (`snapshot()` / `refresh()` /
`subscribe_updates(...)` / `close()`) so the Live and Stub branches are
transparent to the rest of the system. The decision was right; the
**wiring** that landed during TASK-J004-013 was wrong.

`assemble_tool_list` was writing the slot as a `list[CapabilityDescriptor]`:

```python
# src/jarvis/tools/__init__.py:219 — pre-fix
_capabilities._capability_registry = list(capability_registry)
```

But the slot's declared type and the catalogue tool bodies both speak
the Protocol surface. Every catalogue-tool invocation in production
therefore triggered an `AttributeError: 'list' object has no attribute
'snapshot'/'refresh'/'subscribe_updates'`, which the tool body's
`except Exception` branch caught and converted into either
`ERROR: registry_unavailable` or — for the dispatch surface — an
operationally indistinguishable `DEGRADED: transport_unavailable —
NATS connection failed`. The reasoning model could not tell a real
NATS outage from this latent bug.

The defect was masked in the test suite because all three test
fixtures (`bound_registry` / `empty_registry` / `configured_registry`
in `tests/test_capabilities.py` and `tests/test_tools_capabilities.py`,
and the wrap-after-assemble step in `tests/test_assemble_tool_list.py`)
explicitly post-wrapped the slot with a `_ListBackedRegistry` that
satisfied the Protocol. Production wiring had no such wrap step. See
the TASK-REV-FFE4 review report §6 sequence diagram for the full
end-to-end trace.

## Decision (the amendment)

**B1 — extend `assemble_tool_list`'s kwarg list to thread the Protocol
through.**

1. `assemble_tool_list` gains a new keyword-only parameter
   `capabilities_registry: CapabilitiesRegistry | None = None`.
2. The body writes the catalogue-tool slot as the Protocol object
   directly:

   ```python
   _capabilities._capability_registry = capabilities_registry
   ```

   The `dispatch._capability_registry` slot is **unchanged** — it stays
   a `list(capability_registry)` because the dispatch tool iterates the
   list to map `tool_name → agent_id` and does not need the Protocol
   surface.
3. `lifecycle.build_app_state` passes `capabilities_registry=capabilities_registry`
   to both `assemble_tool_list` calls (attended + ambient surfaces).
4. The default ambient-tool factory in `jarvis.agents.supervisor`
   (`_default_ambient_tool_factory`) gains a matching parameter and
   plumbs it through to its inner `assemble_tool_list` call. `build_supervisor`
   gains a matching keyword-only kwarg and threads it into the default
   factory closure. `lifecycle.build_app_state` passes the kwarg.

   Without step 4 an ambient activation would re-overwrite the slot
   with `None` (the new kwarg's default) and silently re-introduce the
   defect for the rest of the session. This is review report Finding F4.

The `capabilities_registry` kwarg defaults to `None` so the catalogue
tools surface `ERROR: registry_unavailable` per ADR-ARCH-021 when no
caller wired the Protocol through — the same shape the slot has had
before any wiring runs. Silently defaulting to a list-shaped slot was
how the defect existed; we will not preserve that "convenience".

## Why not B2 — separate setter

Review report §10 / §12 recorded the alternative and the rejection:

| Option B1 (chosen) | Option B2 (rejected) |
|---|---|
| One wiring point — `assemble_tool_list` is "the ONE place that knows how to wire tool-level state" (per its own docstring and API-internal.md §1.2). The amendment preserves the invariant. | Two wiring points — `assemble_tool_list` for everything except the catalogue tool, plus a separate `capabilities.set_registry(...)` setter the lifecycle had to remember to call. Future readers (and future bugs) would need to know about both. |
| `_capabilities._capability_registry` is set once per `assemble_tool_list` call; ambient and attended re-assemblies stay symmetric. | Symmetry between attended and ambient assembly relies on the lifecycle calling the second setter twice — a strictly weaker invariant than "one call sets up everything". |
| Type system catches the bug — mypy was already flagging `tools/__init__.py:219` (the pre-fix `list(capability_registry)` write), and AC-005 closes that error. | The list-shaped slot would not have been a type error; only the missed-setter call would have been one (and only if every caller's call shape was strictly checked). |
| Backward compatible by accident — pre-existing callers that assembled tools without a registry now see catalogue tools surface the documented `ERROR: registry_unavailable`. | Same backward compatibility, but with two contracts to track. |

## Consequences

- `capabilities._capability_registry` is bound to a Protocol object on
  every `lifecycle.build_app_state` run (Live or Stub per the existing
  DDR-021 NATS branch).
- The catalogue tools (`list_available_capabilities`,
  `capabilities_refresh`, `capabilities_subscribe_updates`) work on
  both branches without the latent `AttributeError` masquerading as a
  NATS outage.
- The supervisor prompt block (`_render_available_capabilities`) is
  **unaffected** — it consumes the `available_capabilities=...` kwarg
  of `build_supervisor`, which is the `list[CapabilityDescriptor]`
  rendered once at build time. The Protocol is only used by the
  catalogue tool bodies.
- `tools/__init__.py:219` no longer triggers a mypy error
  (`Incompatible types in assignment`). AC-005 of TASK-J004-FIX-001
  confirms `uv run mypy src/jarvis/` returns zero errors.
- A new lifecycle integration test (`tests/test_lifecycle_capabilities_wiring.py`)
  asserts the Protocol shape reaches the slot on both NATS-up and
  NATS-down branches and that `list_available_capabilities` returns
  neither `ERROR:` nor `DEGRADED:` on the happy path. Pre-fix, the
  NATS-down test would have caught this in CI.
- Test suites that exercise the catalogue tool with direct slot writes
  (the `bound_registry` / `empty_registry` / `configured_registry` /
  `bound_canonical_registry` fixtures) keep their existing semantics —
  good test isolation. They already use a `_ListBackedRegistry` adapter
  that conforms to the Protocol.

## Pointers for future readers

- TASK-REV-FFE4 review report — `.claude/reviews/TASK-REV-FFE4-review-report.md`.
  §6 has the sequence diagram showing the production failure path; §10
  has the B1-vs-B2 trade-off table; §12 records the human B1/B2/C
  decision.
- TASK-J004-FIX-001 — the implementing task, with file:line-precise
  acceptance criteria covering the four production-code changes
  (`tools/__init__.py`, `lifecycle.py` ×2, `supervisor.py`), three test
  changes (migrated fixture in `test_assemble_tool_list.py`, new
  `test_lifecycle_capabilities_wiring.py`, full pytest green), and
  this DDR amendment.
- DDR-021 §3 (the original Live/Stub fallback decision) is **not
  superseded** — only the wiring path that fills the catalogue tool
  slot is amended. The Live/Stub design intent stands as written.
