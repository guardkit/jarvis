# FEAT-SPL-001 — Slack Planning Intake

Jarvis's half of the Sovereign Planning Loop's front door (SPL scope §5;
fable-window plan ACTION 6; SPL build-plan Session 2).

**Problem**: James has no door into the factory's planning loop. Inbound Slack
is button-clicks only (JNB-104); free-text ideas have no path onto the bus.

**Solution**: A message posted by the identity-pinned originator in the
dedicated planning channel becomes a `PlanningQueuedPayload` (nats-core 0.5.0,
`stage="planning"`, required `originating_user`, explicit
`originating_adapter="slack"`) published to
`pipeline.planning-queued.{correlation_id}`, acknowledged in-thread. No
reasoning in jarvis — intake only. Forge Mode P (FEAT-SPL-002) consumes it.

**Provenance**: `/feature-spec` (18 scenarios, commit `1ef48fa`) →
TASK-REV-3240 decision review (3-lens + adversarial verify; report in
`.claude/reviews/`) → this plan.

## Subtasks

| Task | Wave | Type | Cx | Summary |
|---|---|---|---|---|
| TASK-SPL-J01 | 1 | feature | 6 | Intake handler module + settings keys + nats-core pin bump |
| TASK-SPL-J02 | 2 | feature | 5 | Shared Socket Mode routing + union no-op gate + lifecycle + `.env.example` |
| TASK-SPL-J03 | 3 | testing | 5 | Scenario + contract suite (JNB-105 pattern, 18 scenarios) |
| TASK-SPL-J04 | 4 | operator_handoff | 2 | Live-validation checklist (bundle with OPS-001) |

Operator follow-up tasks: 1 (TASK-SPL-J04).

## Load-bearing review outcomes

- One shared Socket Mode connection; routing inside the single ack-first
  listener (a second connection ack-and-drops the other feature's traffic).
- Union no-op gate: operator-id-unset must not kill intake; planning-unset must
  not kill the reply path (confirmed-HIGH finding F1).
- Bot filter keys on `bot_id`/`app_id` (modern bot posts are subtype-free).
- `originating_adapter="slack"` hard-coded; wire layer won't enforce it.
- `request_text` never appears in logs (metadata-only records).
