# DDR-031 — `originating_adapter` resolved from `Session.adapter`, not the reasoning-model arg

- **Status:** Accepted
- **Date:** 2026-04-29
- **Feature:** FEAT-JARVIS-005 (Phase 3 / Fleet Integration)
- **Related:** [`BuildQueuedPayload._adapter_required_for_jarvis` validator](../../../../nats-core/src/nats_core/events/_pipeline.py), [ADR-ARCH-022](../../../architecture/decisions/ADR-ARCH-022-constitutional-rules-belt-braces.md), [ADR-ARCH-023](../../../architecture/decisions/ADR-ARCH-023-permissions-constitutional.md), [DDR-014](../../FEAT-JARVIS-003/decisions/DDR-014-escalate-to-frontier-in-dispatch-tool-module.md)

## Context

`BuildQueuedPayload` carries an `originating_adapter: OriginatingAdapter | None` field. The `nats-core` field validator `_adapter_required_for_jarvis` enforces that when `triggered_by == "jarvis"`, `originating_adapter` MUST be a non-None member of the closed enum `{terminal, voice-reachy, telegram, slack, dashboard, cli-wrapper}`.

The Phase 2 `queue_build` exposed `originating_adapter` as a tool argument with default `"terminal"` — meaning the reasoning model could **set** the adapter. Two failure modes follow:

1. **Spoofing.** A prompt-injected reasoning model could claim a build was queued from `dashboard` when the user is actually on the CLI, breaking adapter-routing accountability.
2. **Drift.** The reasoning model could pass an adapter value that doesn't match the active session's adapter — Forge's downstream routing-back-to-originator would target the wrong adapter.

ADR-ARCH-022 / ADR-ARCH-023 (constitutional rules, not reasoning-adjustable) implies adapter identity should be a constitutional fact, not a reasoning-model choice. The active session knows the truth: `Session.adapter` is set at `start_session(adapter, user_id)` and is immutable for the session's lifetime.

FEAT-JARVIS-004 already wired the `_current_session_hook` (Layer 2 of the DDR-014 frontier gate) — the same hook can resolve the active session here.

## Decision

1. **`originating_adapter` is resolved from the active `Session.adapter` at the `queue_build` call site.** The `_resolve_current_session()` helper (FEAT-J004 hook) returns the active `Session`; `session.adapter` is the authoritative value.
2. **The tool argument becomes a fallback.** When `_resolve_current_session()` returns `None` (tests / sessionless paths / direct unit-test invocation), the tool argument's value is used. This preserves Phase 2 unit-test paths that exercised the tool body without a session.
3. **No reasoning-model override.** When a session is active, the reasoning model's argument value is **silently overridden** (not validated, not echoed in the error path). The tool docstring's `originating_adapter:` parameter description is updated to note that the value is informational under an active session.
4. **`triggered_by="jarvis"` stays hardcoded.** Phase 2 invariant preserved.

## Rationale

- **Adapter identity is constitutional, not reasoning.** Per ADR-ARCH-022/023, anything about the security/audit-routing envelope shouldn't be reasoning-adjustable. The reasoning model can pick *what* to dispatch but not *who originated the request*.
- **Session is the authoritative source.** `Session.adapter` is set once at session start and never changes. Using it as the source eliminates the spoofing surface entirely; there's no parallel state to drift from.
- **Argument as fallback preserves test paths.** Phase 2 unit tests exercised `queue_build` without bootstrapping a `SessionManager`. Removing the arg entirely would force every test to set up a session; keeping it as a fallback (only consulted when no session is active) is the right ergonomic.
- **Silent override over loud rejection.** A loud rejection (e.g. `ERROR: adapter_mismatch`) would leak adapter detection to the reasoning model, creating side-channel inference paths. Silent override is the more secure default — the reasoning model never learns that it tried to misrepresent the adapter.
- **Validator behaviour is now load-bearing.** With this DDR, the `nats-core._adapter_required_for_jarvis` validator never trips at the wire — Jarvis always passes a non-None adapter. The validator becomes a defensive net for the rare sessionless-test path, not a runtime gate.
- **Backwards-compatible.** Phase 2 tests that passed `originating_adapter="dashboard"` directly still work (no active session in the unit-test path). Phase 3 integration tests + production paths get the secure-by-default behaviour.

## Alternatives considered

| Option | Why not |
|---|---|
| Trust the reasoning-model arg verbatim | Spoofing surface; drift between Session.adapter and emitted payload; violates ADR-ARCH-022/023 |
| Reject when arg ≠ Session.adapter (loud error) | Side-channel inference; reasoning model learns the active adapter; complicates the supervisor's DEGRADED-handling |
| Remove the arg entirely | Breaks Phase 2 unit-test paths; forces every test to bootstrap a SessionManager + Session |
| Validate arg against Session.adapter at the tool boundary | Same side-channel risk as loud reject; small step toward defence-in-depth but doesn't add real security over silent override |
| Read `Session.adapter` only inside the closure that builds `BuildQueuedPayload`, not at the tool entry | Doesn't change the security posture; just moves the resolution one frame later. Resolving at entry is clearer to read. |

## Consequences

- `tools/dispatch.py::queue_build` body resolves the adapter via `_resolve_current_session()` before constructing the payload:
  ```python
  session = _resolve_current_session()
  resolved_adapter = session.adapter if session is not None else originating_adapter
  ```
- The tool argument's docstring grows one note: `"Used as fallback only when no active session is bound (tests / sessionless paths). Under an active session, the value is replaced with Session.adapter."`
- `tests/test_dispatch_queue_build_integration.py` covers: with an active CLI session, `originating_adapter="dashboard"` arg is silently overridden to `"cli"` on the wire; without an active session, the arg passes through.
- `BuildCorrelation.adapter` (in the in-memory correlation map per DDR-028) carries the resolved adapter — same value as `BuildQueuedPayload.originating_adapter`; primarily for diagnostic logging on eviction.
- ADR-ARCH-022/023 invariants extended: the adapter identity in build provenance traces is constitutional. FEAT-J006 (Telegram) inherits the behaviour automatically — `Session.adapter == "telegram"` is the authoritative value, not whatever the reasoning model thinks.
- Future audit trail: every `BuildQueuedPayload` Jarvis publishes has `triggered_by="jarvis"` AND `originating_adapter` matching the session's actual surface. No spoofed builds in the trace.

## Status

Accepted at FEAT-JARVIS-005 `/system-design`. Future adapter additions (Telegram, Dashboard, Reachy) inherit the behaviour without per-adapter wiring.
