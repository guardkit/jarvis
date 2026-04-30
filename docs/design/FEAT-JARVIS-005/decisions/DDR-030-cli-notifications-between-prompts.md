# DDR-030 — CLI notifications render between prompts only; per-session queue capped at 100

- **Status:** Accepted
- **Date:** 2026-04-29
- **Feature:** FEAT-JARVIS-005 (Phase 3 / Fleet Integration)
- **Related:** ASSUM-003 (single-concurrent-invoke per session), [ASSUM-004](../../../research/ideas/jarvis-vision.md) (sequential REPL turns), [DDR-026](DDR-026-forge-notifications-module-location.md), [DDR-027](DDR-027-stage-complete-ephemeral-deliver-new.md), [DDR-028](DDR-028-correlation-map-in-memory-bounded.md)

## Context

Forge's stage-complete events arrive asynchronously as a build progresses — one event per gate-evaluated dispatch. The CLI REPL is sequential (ASSUM-004): one user-input → one supervisor-invoke → one rendered reply. Two interleaving questions arise:

1. **When to render notifications.** Mid-supervisor-turn (interrupt the LLM's streaming output)? Mid-`stdin.readline` (cut into the user's typed line)? Between prompts only? Push to a separate channel (e.g. tmux pane)?
2. **What's the queue depth.** A long-running Forge build with many stages could emit 50+ events; a runaway loop could emit hundreds. The render path can't blow up under load.

ASSUM-003 (single-concurrent-invoke per session) already pins the in-memory queue's safety story: there's never a race between `enqueue_notification` (subscriber callback) and `pending_notifications` (REPL drain) at the in-flight-supervisor boundary because they're on the same event loop with cooperative scheduling, and the REPL drain happens *before* `stdin.readline` (which is itself awaited via `run_in_executor`).

## Decision

1. **Notifications render between prompts only.** The CLI REPL drains `pending_notifications` at the **top of each loop iteration**, before reading the next stdin line. Mid-turn (during `await session_manager.invoke`) and mid-stdin-typing notifications are buffered in the queue; they surface on the *next* iteration.
2. **Per-session queue cap = 100 entries.** Configurable via `JarvisConfig.forge_notifications_queue_cap` (`Field(ge=1, le=10_000)`).
3. **Overflow eviction = oldest first.** Implemented via `collections.deque(maxlen=cap)`; the standard library evicts on append. A wrapper observes the discard and emits `WARN forge_notification_queue_overflow session_id=<x> dropped_correlation=<y>`.
4. **Cleared on `end_session`.** When a session ends (REPL `/exit`, SIGINT, EOF), the per-session queue is freed and a structured log records the count cleared.
5. **Idempotent on dropped sessions.** `enqueue_notification(session_id, ...)` for an already-ended `session_id` drops the notification with `DEBUG forge_notification_dropped reason=session_ended` and does not re-enqueue.

## Rationale

- **Between-prompts is the only safe render boundary in a stdin REPL.** Mid-`readline` rendering would require terminal escape sequences to redraw the user's in-progress line — a UX minefield + cross-terminal compatibility nightmare. Mid-supervisor-turn rendering would interleave Forge progress with the LLM's response stream, making both unreadable. Push to a separate channel would require a second terminal or a tmux pane — out of scope for v1's "minimum useful CLI".
- **The trade-off is buffering latency.** A stage-complete event that arrives mid-turn waits up to `next_user_input_time` to render. In typical use that's seconds; in worst case (Rich types nothing for 10 minutes), the notification surfaces on the next prompt. Acceptable — the alternative is broken UI.
- **100 is a defensive ceiling, not an expected operating point.** Typical Forge builds emit 5–15 stage-complete events; even multiple concurrent builds (queued from one Jarvis session) shouldn't exceed dozens. 100 absorbs spike + provides headroom; 1000+ would be wasteful and a slow burn for any real saturation case.
- **Oldest-first eviction matches the operator's mental model.** "Show me what's happened recently" is more useful than "show me what happened first". Operator can re-query Forge directly for full history.
- **`end_session` clearing prevents queue leaks** — the deque hangs off `SessionManager._notification_queues[sid]`; without explicit removal a long-lived process accumulates dead-session deques.
- **WARN on overflow is observable but not load-bearing.** Same severity choice as DDR-019: trace continuity matters; runtime correctness is unaffected.

## Alternatives considered

| Option | Why not |
|---|---|
| Mid-turn rendering (interleave with LLM stream) | Unreadable; corrupts the LLM-stream UX; clashes with click.echo flush semantics |
| Mid-readline rendering (push line above user's typing) | Requires terminal escape sequences; fragile cross-terminal; bad UX for slow typists |
| Pop-up to a separate tmux/terminal pane | Out of scope for v1; adds shell environment assumptions |
| No cap (unbounded deque) | Memory leak vector; one runaway build could grow the queue indefinitely |
| Cap at 10 (very small) | Drops normal-build notifications under multi-build load; saturation should be a *signal*, not a *common case* |
| Cap at 1000 (very large) | Waste; user value of seeing 1000 stale stage events is near-zero |
| Render only on `/notifications` command (opt-in) | Breaks ambient-feedback UX — Rich wouldn't see Forge progress without polling |
| Discard newest on overflow (drop incoming) | Loses *recent* progress signal; oldest-first eviction preserves the most-useful tail |

## Consequences

- `cli/main.py::_chat_loop` grows three lines at the top of the loop:
  ```python
  for n in session_manager.pending_notifications(session.session_id):
      click.echo(n.format_one_line())
  ```
- `SessionManager.enqueue_notification(session_id, notification, *, cap=100)` is the public surface; the cap is also forwarded from `ForgeNotificationsSubscriber` (which reads it from `JarvisConfig`).
- `tests/test_forge_notifications_unit.py` covers: 100 enqueues drain in FIFO; 101st evicts oldest with WARN; `end_session` clears the queue; enqueue on ended session drops with DEBUG.
- `tests/test_cli_renders_notifications.py` (new) covers: between-prompt render shape; SIGINT clears the queue; renderer is idempotent if drained twice (second drain is empty).
- ASSUM-NOTIFICATION-RUNAWAY-CAP (carried forward) — if `WARN forge_notification_queue_overflow` fires in real-world operation, an append-only DDR raises the cap or introduces a stage-rollup (e.g. coalesce N consecutive same-stage events into one rendered line).
- FEAT-J006 (Telegram) reuses the same queue + cap; format_one_line is the canonical body. FEAT-J009 (Dashboard) renders the live trace viewport from the same queue without going through the deque (it tails the underlying notification stream directly).

## Status

Accepted at FEAT-JARVIS-005 `/system-design`. Cap and rendering policy are operator-tunable via env; if real-world load saturates 100 entries, append-only DDR can raise it.
