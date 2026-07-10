---
id: TASK-J006-011
title: "Wire reconnect callbacks so jarvis survives steady-state broker bounces"
task_type: bug
feature_id: FEAT-JARVIS-006
status: completed
completed: 2026-07-10
completed_location: tasks/completed/feat-jarvis-006-nats-chat-gateway/
priority: critical
complexity: 3
wave: 6
implementation_mode: task-work
dependencies:
  - TASK-J006-010
parent_review: null
tags:
  - nats
  - infrastructure
  - bug
  - demo-blocker
  - reconnect
  - hard-dependency-posture
implementation_reference:
  template: study-tutor TASK-NATS-FIX-006 (commit 34d4a16 in study-tutor)
  files:
    - study-tutor/src/study_tutor/adapters/nats_adapter.py (_on_reconnect, _on_disconnect, _on_closed, _terminal_close_event)
    - study-tutor/src/study_tutor/cli/main.py (_serve_adapter, asyncio.wait FIRST_COMPLETED race)
  nats_core_api: nats-core TASK-NC10 — reconnected_cb / disconnected_cb / closed_cb on NATSClient.__init__
created: 2026-05-12
---

> **✅ COMPLETED 2026-07-10 (WS3-S7) — code + hermetic tests landed and green
> (AC-01..AC-06); AC-07/AC-08 GB10 live probes deferred to the next jarvis
> operator session (bundle with GB10). Task tests re-run at completion:
> `tests/test_j006_011_reconnect_callbacks.py` + `tests/test_serve_nats_cli.py`
> = 34 passed.**
>
> **🟡 IN REVIEW 2026-07-09 (WS3-S7) — code + hermetic tests landed; AC-07/AC-08
> GB10 live probes remain operator follow-up.** Ported the study-tutor
> TASK-NATS-FIX-006 pattern, adapted to jarvis's three-module lifecycle split:
> - `src/jarvis/infrastructure/nats_client.py` — `ReconnectContext` +
>   `build_lifecycle_callbacks(ctx)` factory (bound re-register + heartbeat
>   respawn + `terminal_close_event`); `NATSClient.connect` gains an optional
>   `lifecycle_callbacks` key-wise override (log-only stubs stay the default →
>   AC-01, test-path stability preserved).
> - `src/jarvis/infrastructure/lifecycle.py` — `build_app_state` builds the
>   context + bound callbacks BEFORE connect, late-binds the wrapper, tracks the
>   current heartbeat task in a mutable holder; new `AppState.reconnect_context`
>   + `AppState.terminal_close_event` + `active_heartbeat_task()`; shutdown
>   cancels the *current* (possibly respawned) heartbeat.
> - `src/jarvis/cli/main.py` — `_serve_adapter` races `shutdown_event` vs
>   `terminal_close_event` (FIRST_COMPLETED); a terminal close runs the graceful
>   teardown then `raise SystemExit(1)` (AC-05) so an external supervisor
>   recovers with a fresh registration.
>
> Hermetic broker-bounce coverage (no live broker from this session):
> `tests/test_j006_011_reconnect_callbacks.py` (AC-01/02/03/04/06) +
> `tests/test_serve_nats_cli.py::TestTerminalCloseExit` (AC-05). Full jarvis
> suite green (2787 passed / 2 skipped / 0 failed), ruff + format clean, mypy on
> the three touched modules clean bar one pre-existing `notifier` type finding.
> **Remaining (operator, GB10): AC-J006-011-07** (transient bounce →
> `nats_reconnect` → `fleet_reregister_published` → `fleet_heartbeat_restarted`,
> KV revision increments, chat still replies, no restart) and **AC-J006-011-08**
> (prolonged outage → `nats_terminally_closed` → `jarvis_serve_nats_terminal_close_exit`,
> exit code 1). Bundle those with the next GB10 jarvis operator session.

# Task: Wire reconnect callbacks so jarvis survives steady-state broker bounces

## Severity / impact

**P0 — demo-resilience demo-blocker for 2026-05-16 DDD Southwest.**

TASK-J006-010 bounded the **initial** connect attempt at boot. It did **not** add any reconnect-callback behaviour for steady-state broker bounces during a serve-nats run. Today (2026-05-12 GB10 verification rerun) the broker was bounced mid-session by an external actor; jarvis entered a `fleet_heartbeat_failed (nats: connection closed)` loop, the KV registration went stale, and the gateway silently stopped serving chat traffic. OpenWebUI then timed out at 120 s with no usable error path back to the operator.

By contrast, study-tutor's `gcse-tutor` — which landed TASK-NATS-FIX-006 / consumed nats-core TASK-NC10's `reconnected_cb` API — survived the same bounce:
- **Transient bounce (≤30 s):** disconnect → `_on_reconnect` callback re-published the manifest to `agent-registry` KV; no container restart needed.
- **Prolonged outage (>30 s, nats-py `max_reconnect_attempts` exhausted):** `_on_closed` set a `terminal_close_event` → CLI raced `shutdown_event` vs `terminal_close_event` and raised `SystemExit(1)` → Docker's restart policy recovered the container → fresh registration.

Jarvis needs both paths. **If the broker hiccups for any reason in the 24 h before demo or during the demo itself, jarvis will silently drop off the fleet** — exactly the failure mode TASK-NATS-FIX-006 fixed for study-tutor.

## Evidence (real-world bounce captured during TASK-J006-005 run-5, 2026-05-12)

Jarvis serve-nats log `/tmp/jarvis-serve-nats-smoke-run5-prebounce.log` (PID 1746120, boot at 18:59:25):

```
19:05:11.210  nats_error TimeoutError "nats: timeout"
19:05:11.359  nats_error ConnectionRefusedError "[Errno 111] Connect call failed ('127.0.0.1', 4222)"
... 11 more ConnectionRefusedError every 2s ...
19:05:33.377  nats_disconnect      ← _on_disconnect fired (log only)
19:05:33.377  nats_closed          ← _on_closed fired (log only)
19:05:36.215  nats_error ConnectionClosedError "nats: connection closed"
19:05:41.192  fleet_heartbeat_failed "nats: connection closed"  ← every 30s
19:05:11.223  fleet_heartbeat_failed ...
...                                                             ← repeats indefinitely
```

Comparable gcse-tutor log entries from the same bounce window (`docker logs study-tutor-gcse-tutor-1`):

```
19:02:40.149  WARNING nats_disconnected
19:02:56.176  INFO    nats_reconnected — re-registering agent 'gcse-tutor'  ← _on_reconnect re-published manifest
19:03:33.270  WARNING nats_disconnected
19:05:33.475  WARNING nats_disconnected
19:05:33.475  ERROR   nats_terminally_closed                                ← _on_closed set terminal_close_event
19:06:39.518  INFO    Registered agent 'gcse-tutor' to fleet.register       ← Docker restart policy → fresh register
```

Both gcse-tutor paths (transient + terminal) functioned. Jarvis exercised neither.

## Root cause

`src/jarvis/infrastructure/nats_client.py` wires the three callbacks in `connect()` at lines 175-177:

```python
kwargs: dict[str, Any] = {
    "servers": config.nats_url,
    "error_cb": _on_error,
    "disconnected_cb": _on_disconnect,
    "reconnected_cb": _on_reconnect,
    "closed_cb": _on_closed,
}
```

But the three callbacks at lines 547-579 are **log-only stubs**:

```python
async def _on_reconnect() -> None:
    logger.info("nats_reconnect")  # ← no manifest re-publish

async def _on_disconnect() -> None:
    logger.warning("nats_disconnect")

async def _on_closed() -> None:
    logger.info("nats_closed")  # ← no terminal_close_event; CLI never knows
```

There is no path from these module-level callbacks to the live runtime state (heartbeat task, registry client, app state), so they cannot re-register on reconnect or signal the CLI on close.

## Fix scope

Port study-tutor's TASK-NATS-FIX-006 pattern, adapted to jarvis's structure. Jarvis's lifecycle is split across three modules (vs. study-tutor's single `NATSAdapter`), so the wiring is more invasive than a drop-in:

### 1. `src/jarvis/infrastructure/nats_client.py` — bound-callback factory

Convert the module-level callbacks into a factory that closes over the live `AppState` (or a minimal `ReconnectContext` struct carrying the registry, manifest, heartbeat-task slot, and `terminal_close_event`):

```python
@dataclass
class ReconnectContext:
    manifest: AgentManifest
    nats_client: NATSClient
    heartbeat_interval_seconds: float
    heartbeat_task_holder: list[asyncio.Task | None]  # mutable slot
    terminal_close_event: asyncio.Event

def build_lifecycle_callbacks(ctx: ReconnectContext) -> dict[str, Callable]:
    async def _on_reconnect() -> None:
        logger.info("nats_reconnect", agent_id=ctx.manifest.agent_id)
        try:
            await register_on_fleet(ctx.nats_client, ctx.manifest)
            logger.info("fleet_reregister_published", agent_id=ctx.manifest.agent_id)
        except NATSConnectionError as exc:
            logger.warning("fleet_reregister_failed", agent_id=ctx.manifest.agent_id, error=str(exc))
        # Restart heartbeat task if it died during the disconnect
        old_task = ctx.heartbeat_task_holder[0]
        if old_task is None or old_task.done():
            ctx.heartbeat_task_holder[0] = asyncio.create_task(
                heartbeat_loop(ctx.nats_client, ctx.manifest, ctx.heartbeat_interval_seconds)
            )
            logger.info("fleet_heartbeat_restarted", agent_id=ctx.manifest.agent_id)

    async def _on_disconnect() -> None:
        logger.warning("nats_disconnect", agent_id=ctx.manifest.agent_id)

    async def _on_closed() -> None:
        logger.error("nats_terminally_closed", agent_id=ctx.manifest.agent_id)
        ctx.terminal_close_event.set()

    return {"reconnected_cb": _on_reconnect, "disconnected_cb": _on_disconnect, "closed_cb": _on_closed, "error_cb": _on_error}
```

The existing module-level callbacks at 547-579 stay as the *default* for tests / boot-path use; `NATSClient.connect()` accepts an optional `lifecycle_callbacks: dict` override that, when present, takes precedence.

### 2. `src/jarvis/infrastructure/lifecycle.py` — construct the context

In `build_app_state()` (or wherever the heartbeat task gets spawned today), construct the `ReconnectContext` after manifest + registry are ready, build the callbacks, and re-wire them onto the connected client (or pass them through to `connect()` before the connect call). Store `terminal_close_event` on the `AppState` so the CLI can `await` it.

### 3. `src/jarvis/cli/main.py:_serve_adapter` — race shutdown vs terminal close

Mirror study-tutor's `cli/main.py:_serve_adapter` pattern:

```python
done, pending = await asyncio.wait(
    [asyncio.create_task(shutdown_event.wait()),
     asyncio.create_task(app_state.terminal_close_event.wait())],
    return_when=asyncio.FIRST_COMPLETED,
)
for task in pending:
    task.cancel()
if app_state.terminal_close_event.is_set():
    logger.error("jarvis_serve_nats_terminal_close_exit")
    await _graceful_shutdown(app_state)
    raise SystemExit(1)  # ← Docker restart policy can recover
```

Without `raise SystemExit(1)`, the CLI would treat a terminal close as a "graceful" exit and the container would not auto-restart.

## Acceptance criteria

| AC | Description |
|---|---|
| AC-J006-011-01 | `nats_client.connect()` accepts an optional `lifecycle_callbacks` dict that overrides the module-level stub callbacks. Existing default behaviour (log-only) preserved when no override is passed (test-path stability). |
| AC-J006-011-02 | Unit test: when the bound `_on_reconnect` fires, the manifest is re-published to `agent-registry` KV via `register_on_fleet(...)`. Mock the registry; assert one call to `register(manifest)`. |
| AC-J006-011-03 | Unit test: when `_on_reconnect` fires AND the heartbeat task has died (`task.done() is True`), a new heartbeat task is spawned. Use `heartbeat_task_holder[0]` to assert the replacement. |
| AC-J006-011-04 | Unit test: when `_on_closed` fires, `app_state.terminal_close_event` is set. |
| AC-J006-011-05 | Unit test: `_serve_adapter` races `shutdown_event` vs `terminal_close_event`; the terminal-close branch raises `SystemExit(1)` after invoking graceful shutdown. |
| AC-J006-011-06 | Regression test: existing TASK-J006-010 behaviour (boot-path hard-fail at `startup_connect_timeout_seconds=10`) still passes — the new callbacks must not fire during a *boot* connect failure (they only matter post-`jarvis_startup_complete`). |
| AC-J006-011-07 | GB10 manual probe — same recipe as runbook §3.8 but a different shape: with serve-nats already running + healthy, bounce the broker briefly (`docker restart ships-computer-nats`). Within ~30 s of broker healthy: (a) jarvis log shows `nats_reconnect` → `fleet_reregister_published` → `fleet_heartbeat_restarted`; (b) `agent-registry` KV `revision` increments; (c) a subsequent `nats request agents.command.jarvis` returns a chat reply within normal latency. No process restart needed. |
| AC-J006-011-08 | GB10 manual probe — terminal-close path: stop the broker for >60 s (long enough for nats-py's `max_reconnect_attempts` to exhaust on the post-boot client). Jarvis log shows `nats_terminally_closed` then `jarvis_serve_nats_terminal_close_exit`; process exits with code 1. (No container yet for jarvis — this AC documents the exit; deferring "Docker restart policy" to whenever jarvis is containerised.) |

## Out of scope

- Changing the steady-state `max_reconnect_attempts` setting on `nats-py` itself — TASK-J006-010 explicitly preserves the default; only the post-`_on_closed` exit path is new.
- Changing the boot-path hard-fail (TASK-J006-010 stays as-is).
- Containerising jarvis (separate concern; AC-J006-011-08 documents the exit-1 path which is the precondition for Docker restart policy to be useful).
- Backporting to non-FEAT-JARVIS-006 code paths (CLI `chat` command, etc.).

## Demo-day note (2026-05-16)

If this task does NOT land before demo day, the operational mitigation is:
1. Pre-demo: confirm `nats kv get agent-registry jarvis` returns the **post-bounce** revision (i.e. test the path once during dry-run).
2. If the broker bounces during demo prep: **restart jarvis serve-nats manually** (it's not currently containerised). The bounded boot connect in TASK-J006-010 means it will fail-fast if the broker is still down, surfacing the problem; once the broker is healthy, restart succeeds.
3. During demo: if a chat times out, in a side terminal run `nats kv get agent-registry jarvis --raw 2>&1 | head -1` and inspect the `revision` field — a stale revision (no recent increment) means jarvis is dead in the water; restart it.

## Related work

- **Implementation template:** `study-tutor/commit 34d4a16` (TASK-NATS-FIX-006) — same fix, smaller scaffolding. The diff there is the implementation reference.
- **API surface:** `nats-core/TASK-NC10` — reconnected_cb / disconnected_cb / closed_cb on `NATSClient.__init__`. Already imported by jarvis (just not used to its full potential).
- **Sibling task:** `specialist-agent/tasks/backlog/TASK-NATS-009-bound-startup-reconnect-broker-hard-fail.md` — the *startup* analog of this task for the specialist-agent fleet. AC-NATS-009 covers boot-path; this task (TASK-J006-011) covers steady-state. Both should land for the fleet to be demo-resilient.
- **Predecessor:** `tasks/completed/feat-jarvis-006-nats-chat-gateway/TASK-J006-010-bound-startup-reconnect-broker-hard-fail.md` — bounded the boot-path; this task closes the steady-state gap it explicitly deferred.
