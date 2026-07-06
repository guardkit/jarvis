# Feature Spec Summary: Slack Planning Intake (FEAT-SPL-001)

**Stack**: python
**Generated**: 2026-07-06T09:55:25Z
**Scenarios**: 18 total (5 smoke, 0 regression)
**Assumptions**: 10 total (0 high / 0 medium / 10 low confidence)
**Review required**: Yes — `--auto` mode: all assumptions unconfirmed, deferred for Rich

## Scope

Jarvis's half of the Sovereign Planning Loop's front door (Phase SPL, scope §5
FEAT-SPL-001): a free-text message posted by the identity-pinned originator
(James) in the dedicated planning channel becomes a `PlanningQueuedPayload`
(nats-core ≥0.5.0, `stage="planning"`, required `originating_user`, explicit
`originating_adapter="slack"` — the wire layer does NOT enforce it when
omitted) published to JetStream on `pipeline.planning-queued.{correlation_id}`,
acknowledged in-thread. Jarvis does no reasoning — intake only; Mode P (forge,
FEAT-SPL-002) consumes the payload. Rides the JNB-104 Socket Mode connection
as an additional `events_api` listener beside the existing `interactive`
approval listener.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 5 |
| Boundary conditions (@boundary) | 2 (one outline, 3 rows) |
| Negative cases (@negative) | 7 (one also @boundary) |
| Edge cases (@edge-case) | 5 |

## Deferred Items

None — no groups were deferred (`--auto` accepted all four groups). Out of
scope by design (scope §6): thread dialogue (FEAT-SPL-003), any reasoning or
enrichment in jarvis, target-repo parsing from message text, durable
cross-restart dedup, auto-approval of anything.

## Open Assumptions (low confidence)

All ten — `--auto` mode. The load-bearing ones for Rich's review:

- **ASSUM-001** — single authorized originator id vs allow-list (affects
  pre-exemplar testing where Rich, not James, will post).
- **ASSUM-002** — unauthorized posts are silently ignored (logged), no
  ephemeral refusal.
- **ASSUM-005** — process-local bounded dedup keyed by Slack event id;
  restart inside the redelivery window may duplicate one planning run.
- **ASSUM-006** — top-level, subtype-free user messages only.
- **ASSUM-007** — shared Socket Mode connection (one per process);
  Slack app manifest needs the `message.channels` bot event subscription
  (operator step, alongside OPS-001).

## Integration with /feature-plan

    /feature-plan "Slack Planning Intake" \
      --context features/feat-spl-001-slack-planning-intake/feat-spl-001-slack-planning-intake_summary.md

Implementation surface expected by the SPL build plan ("Files that will
change"): new Socket Mode inbound message handler (new module beside
`slack_reply.py`); `config/settings.py` gains the two planning keys;
lifecycle wiring in `build_app_state`; `.env.example` documents the new keys.
Publish path follows `queue_build`'s envelope + `Topics.Pipeline.PLANNING_QUEUED`
+ DDR-025 bounded-timeout pattern in `tools/dispatch.py`.
