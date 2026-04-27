# API-tools — Tool surface deltas (FEAT-JARVIS-004)

> **Owner:** [FEAT-JARVIS-004 design §3](../design.md)
> **Predecessor:** [../FEAT-JARVIS-002/contracts/API-tools.md](../../FEAT-JARVIS-002/contracts/API-tools.md), [../FEAT-JARVIS-003/contracts/API-tools.md](../../FEAT-JARVIS-003/contracts/API-tools.md)

This document captures the tool-surface **deltas** introduced by FEAT-JARVIS-004. Every tool listed here exists today (Phase 2 / FEAT-J003); FEAT-J004 swaps the body, not the contract. Per scope-doc §"Do-Not-Change", the reasoning model's view of the world is identical.

---

## 1. `dispatch_by_capability` — body swap, contract unchanged

**Signature** — unchanged:

```python
@tool(parse_docstring=True)
def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str | None = None,
    timeout_seconds: int = 60,                    # DDR-016: default still 60
) -> str: ...
```

**Docstring deltas** (only):

- The Phase 2 paragraph `"In Phase 2 the transport is stubbed: ... FEAT-JARVIS-004 replaces the stub with real NATS round-trips without changing this docstring."` is **deleted**. The transport swap has happened.
- Two new **return-shape lines** in the structured-error documentation:
  - `DEGRADED: dispatch_overloaded — wait and retry` (DDR-020 — semaphore overflow)
  - `DEGRADED: transport_unavailable — NATS connection failed` (DDR-021 — NATS soft-fail)
- The existing `DEGRADED: transport_stub — (Phase 2 stub, …)` line is **removed** (no longer reachable).

**Behavioural contract** — see [design §8 — runtime sequence](../design.md). Key invariants preserved:

1. Never raises — every error path returns a structured string per ADR-ARCH-021.
2. `correlation_id` generated per call (ASSUM-001).
3. `timeout_seconds` validation (5..600) preserved.
4. `payload_json` JSON-object literal validation preserved.
5. Resolution order preserved (`_resolve_agent_id`: exact match, then intent fallback, lexicographic ties).
6. Visited-set guards loops on retry-with-redirect (DDR-017).
7. Trace write at every dispatch outcome — fire-and-forget (DDR-019).

**New behavioural contract additions:**

- **Concurrency cap** — `dispatch_semaphore.try_acquire()` first; overflow → `DEGRADED: dispatch_overloaded` synchronously (no block).
- **Real round-trip** — `await nats.request("agents.command.{agent_id}", envelope)` with `asyncio.wait_for(..., timeout=timeout_seconds)`.
- **Retry-with-redirect** — max 1 redirect per DDR-017; visited-set on `agent_id`.

---

## 2. `queue_build` — unchanged in FEAT-JARVIS-004

Body still stubbed (Phase 2). FEAT-JARVIS-005 swaps the JetStream publish. Documented here so the diagram + module map reflect the post-FEAT-004 state including the not-yet-swapped tool. **Trace writes also remain stubbed** for `queue_build` — FEAT-J005 lights up `routing_history_writer.write_build_queue_dispatch(...)`.

---

## 3. `list_available_capabilities` — body swap, contract unchanged

**Signature** — unchanged:

```python
@tool(parse_docstring=True)
def list_available_capabilities() -> str: ...
```

**Docstring deltas:**

- The Phase 2 paragraph `"In Phase 2 this reads from an in-memory stub registry; in FEAT-JARVIS-004 (Phase 3) it will read from the live NATS KV manifest registry. The signature and response shape are identical across phases."` is **deleted**.
- The latency-signal line `"<5ms (stub) / <30ms (cached live registry)"` simplifies to `"<30ms (cached live registry; <5ms when serving the stub fallback)"`.

**Behavioural contract** — body now reads from `CapabilitiesRegistry.snapshot()` (Protocol from API-internal.md). The Protocol unifies live + stub-fallback paths so the JSON return shape is identical regardless of NATS availability.

---

## 4. `capabilities_refresh` — real KV re-read

**Signature** — unchanged.

**Docstring deltas:**

- `STUB in Phase 2: no-op...` paragraph **deleted**.
- New behavioural line: `Forces an immediate re-read of NATSKVManifestRegistry; returns "OK: refresh queued" on success, or "DEGRADED: transport_unavailable" if NATS is down (registry continues serving the stub fallback).`

**New return strings:**

- `OK: refresh queued — registry resynchronised` (success)
- `DEGRADED: transport_unavailable — NATS connection failed` (NATS soft-fail; registry continues serving stub)

The old `_REFRESH_OK_MESSAGE` constant is removed. (No grep invariant breaks — the FEAT-J002 grep check was on `LOG_PREFIX_DISPATCH`, not on these strings.)

---

## 5. `capabilities_subscribe_updates` — real watcher

**Signature** — unchanged.

**Docstring deltas:**

- `STUB in Phase 2: no-op...` paragraph **deleted**.
- New behavioural line: `Attaches a NATS KV watcher; when fleet membership changes, the cached registry invalidates and the next list_available_capabilities call returns fresh data. Idempotent — calling more than once per session is a no-op.`

---

## 6. `escalate_to_frontier` — F5 + F6 plumbing

**Signature** — unchanged.

**Body changes:**

1. **F5 — real `session_id` plumbing.** `_FRONTIER_SESSION_PLACEHOLDER = "frontier-call"` is **deleted**. `_check_attended_only` now passes the resolved `Session.session_id` into `_emit_frontier_log` so `FrontierEscalationContext.session_id` carries a real value. When the session resolver returns `None` (Layer-1 unit-test path), the placeholder `"unknown"` is used (a sentinel that can be filtered out at trace-analysis time).
2. **F6 — `frontier_default_target` config field becomes load-bearing.** The tool's literal default `target=FrontierTarget.GEMINI_3_1_PRO` becomes a **fallback only** — the resolution order at call time is:
   1. Explicit `target=` argument (reasoning-model controlled).
   2. `_default_target_hook()` returning `config.frontier_default_target` (lifecycle-wired closure).
   3. Hard fallback `FrontierTarget.GEMINI_3_1_PRO` (unchanged).
   This lets FEAT-JARVIS-008's budget-policy levers per-budget-window switch the default target via config without restarting Jarvis.

Both fixes preserve every Phase 3 acceptance test — F5 / F6 are additive plumbing.

**Outcome Literal extension** (FEAT-J003 review F3 follow-up — already landed in `_emit_frontier_log` via the FEAT-J003-FIX-002 wave):

```python
outcome: Literal[
    "success",
    "config_missing",
    "attended_only",
    "provider_unavailable",
    "degraded_empty",
]
```

— unchanged in FEAT-J004.

---

## 7. Tools NOT changed in FEAT-JARVIS-004

Listed here for completeness of the audit-trail:

- All FEAT-JARVIS-002 deterministic tools: `calculate`, `read_file`, `search_web`, `list_directory`.
- All FEAT-JARVIS-003 AsyncSubAgent middleware tools: `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks`.

Their docstrings, signatures, and bodies are byte-identical between FEAT-J003 and FEAT-J004.

---

*"The reasoning model has been routing against this surface since Phase 2; it does not need to learn anything new."* — [design §10](../design.md)
