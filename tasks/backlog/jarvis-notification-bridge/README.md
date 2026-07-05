# Jarvis Notification Bridge (FEAT-UBS-003)

## Problem

Forge builds run unattended — overnight and away-from-desk — but every signal the pipeline emits today terminates at the jarvis CLI FIFO. A build that pauses for approval, fails, or completes while the operator is away simply waits, invisible, until the next time a terminal is open. The pause case is the sharpest edge: an approval gate can hold a build for up to its 3600s max-wait ceiling with the operator entirely unaware, and once v1.1 replies exist, a reject decided from the phone would (without further work) never confirm its own terminal outcome. The bridge puts the build lifecycle on the operator's phone via Slack, and then makes the phone a first-class approval surface.

## Solution Approach

The Slack sender is a new in-process component, `src/jarvis/infrastructure/slack_notifier.py`, living inside the jarvis supervisor — not a separate adapter process. It implements a `NotificationSink` protocol whose `notify(ForgeNotification)` enqueues onto a bounded `asyncio.Queue` drained by a single worker serialising `chat.postMessage` at roughly one message per second. Messages use Block Kit `plain_text` objects with mrkdwn disabled so rationale and failure text are inert, long rationales are chunked under Slack's ~3000-char block limit, 429 Retry-After is honoured within a bounded retry budget, and every other failure is WARNING + drop: per DDR-007 the SQLite ledger is authoritative and the notifier can never raise into the JetStream callback or `queue_build`. The sink protocol is deliberately the seam a future FEAT-JARVIS-006 JARVIS-stream publisher plugs into without touching the subscriber again.

The critical structural constraint is that the PIPELINE stream uses workqueue retention and tolerates exactly one consumer (a second binding fails with err_code 10100). The bridge therefore adds no NATS consumer for v1 at all: `ForgeNotificationsSubscriber` gains a `bind_notification_sink()` seam and calls `sink.notify()` inside its existing `_handle_message` — after envelope decode, the `source_id == 'forge'` gate, and typed payload validation, but independent of the correlation-map lookup, because the phone is per-operator rather than per-session and an LRU wipe on restart must not silence it. The queued event never touches the stream: `tools/dispatch.py queue_build` calls the sink fire-and-forget straight after its PubAck. Pause and cancelled coverage arrive as a filter extension (4 to 6 subjects) on that same single consumer, alongside a widening of the frozen `ForgeNotification` model with new optional, `None`-defaulted fields so CLI rendering is untouched.

v1 reaches a live checkpoint in three autobuildable tasks plus one operator handoff — zero forge changes, zero new consumers — and that checkpoint (TASK-JNB-004: toy feature from Open WebUI, phone shows queued -> running -> terminal exactly once each) is a hard gate on all v1.1 work. v1.1 then closes the loop in both repos: forge wires the existing-but-never-instantiated `ApprovalSubscriber` into the serve runtime as the already-typed `ApprovalGateDeps.subscriber` (`gating/wrappers.py:396`), reusing the four-step validation chain byte-for-byte (payload -> decided_by allowlist vs expected_approver -> correlation_id match -> request_id 300s dedup), and separately wires the existing `publish_build_cancelled` (`pipeline_publisher.py:272`) onto the three CANCELLED transitions, closing the accepted ASSUM-010 v1 gap. On the jarvis side a small subscriber on the AGENTS stream (limits retention — overlap is legal) captures each `ApprovalRequestPayload.request_id`, the pause message upgrades to Block Kit Approve/Reject buttons carrying `{request_id, build_id, correlation_id, approval_subject}` as value JSON, and a Socket Mode client (outbound WebSocket, no public endpoint) handles clicks: ack, gate on `user.id == JARVIS_SLACK_OPERATOR_USER_ID`, publish `ApprovalResponsePayload` with `decided_by = slack_decided_by`, then `chat.update` to disable the buttons. Window and expiry-race enforcement stay exclusively forge-side so a reply-vs-expiry race resolves in exactly one place.

All test tasks are plain pytest with classes mirroring spec scenario names — no pytest-bdd `.feature` glue anywhere (operator decision 2026-07-03, eliminating a known silent-false-green class) — with a collect-only count assertion per test task. Scenario lists are embedded in the jarvis task files because the jarvis-scoped autobuild worktree cannot read the sibling forge repo.

## Task Summary

| ID | Version | Wave | Repo | Type | Complexity | Dependencies |
|---|---|---|---|---|---|---|
| TASK-JNB-001 | v1 | 1 | jarvis | feature | 5 | — |
| TASK-JNB-002 | v1 | 1 | jarvis | feature | 5 | — |
| TASK-JNB-003 | v1 | 2 | jarvis | feature | 3 | TASK-JNB-001, TASK-JNB-002 |
| TASK-JNB-004 | v1 | 3 | jarvis | operator_handoff | 3 | TASK-JNB-003 |
| TASK-JNB-005 | v1 | 4 | jarvis | feature | 5 | TASK-JNB-003 |
| TASK-JNB-006 | v1 | 4 | jarvis | feature | 5 | TASK-JNB-003 |
| TASK-JNB-007 | v1 | 4 | jarvis | documentation | 2 | TASK-JNB-003 |
| TASK-JNB-008 | v1 | 5 | jarvis | testing | 6 | TASK-JNB-005, TASK-JNB-006 |
| TASK-JNB-009 | v1 | 6 | jarvis | operator_handoff | 3 | TASK-JNB-008 |
| TASK-JNB-101 | v1.1 | 7 | forge | feature | 7 | TASK-JNB-004 |
| TASK-JNB-103 | v1.1 | 7 | jarvis | feature | 6 | TASK-JNB-004, TASK-JNB-005 |
| TASK-JNB-102 | v1.1 | 8 | forge | feature | 5 | TASK-JNB-101 |
| TASK-JNB-104 | v1.1 | 8 | jarvis | feature | 7 | TASK-JNB-103 |
| TASK-JNB-105 | v1.1 | 9 | jarvis | testing | 5 | TASK-JNB-104 |
| TASK-JNB-106 | v1.1 | 9 | forge | testing | 5 | TASK-JNB-101, TASK-JNB-102 |
| TASK-JNB-107 | v1.1 | 10 | jarvis | operator_handoff | 3 | TASK-JNB-102, TASK-JNB-104, TASK-JNB-105, TASK-JNB-106 |

TASK-JNB-004 is the hard gate: the v1.1 feature YAMLs are deliberately not generated until it passes. Full sequencing, diagrams, and integration contracts: see `IMPLEMENTATION-GUIDE.md` in this directory.

## References (sibling repos — plain paths)

- BDD spec, assumptions, and summary: `../../../../forge/features/jarvis-notification-bridge/`
- Parent review report: `../../../../forge/.claude/reviews/TASK-REV-C951-review-report.md`
- Implementation guide (canonical, both repos): `./IMPLEMENTATION-GUIDE.md`
