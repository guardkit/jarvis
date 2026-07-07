# Feature Spec Summary: Assumption Dialogue (FEAT-SPL-003, jarvis half)

**Stack**: python
**Generated**: 2026-07-07T15:21:48Z
**Scenarios**: 25 total (4 smoke, 1 regression)
**Assumptions**: 14 total (0 high / 0 medium / 14 low confidence)
**Review required**: Yes — `--auto` mode: all assumptions unconfirmed, deferred for Rich

## Scope

Jarvis's half of the Sovereign Planning Loop's assumption dialogue (SPL scope
§5 FEAT-SPL-003; canon Session 4; WS1 delta build plan §5, Session E). Two
deliverables, in order:

1. **The missing return channel (first deliverable).** A consumer for
   `jarvis.notification.slack` — forge Mode P core-publishes planning
   notifications there (`forge/src/forge/cli/_serve_planning.py`) and jarvis
   has no consumer anywhere; the JARVIS stream expires at 1h/1000 msgs, so
   with planning enabled Mode P's messages to the human evaporate unread.
   The consumer renders each `NotificationPayload` into the originating
   Slack thread (thread anchor from the payload; top-level degrade when
   absent — never dropped). This is also what makes TASK-MP-010's handoff
   notification humanly visible.

2. **Per-assumption decision prompts.** Mode P's `plan-{cid}` approval
   requests (riding the existing JNB-103 capture unchanged) render the PO's
   confidence-tagged assumptions/open_questions as per-item Block Kit
   approve/edit/defer — **forced per-item decisions, no mega-Approve**. The
   anti-rubber-stamp UX is load-bearing for WS4: the harvest found **0
   'considered' / 19 rubber_stamp / 12 partial** decisions across 31
   sessions (`~/po-dataset/MANIFEST.md`), so preference-pair training data
   cannot exist until per-assumption dispositions are captured. Dispositions
   return in the approval response (aggregate, keyed by assumption id) and
   land in the planning run's durable trace record.

Frozen constraints honoured (not re-opened): propose-never-elicit (scope
§3.3 — dialogue = harness rendering proposals; the stateless PO re-invoke
with EnrichmentBatch deltas is forge-side); ADR-ARCH-004 no session store;
identity contract v2 (`decided_by` = observed clicker member id, allowlist =
authorization only, forge `expected_approver` authoritative); cap 3 dialogue
cycles → escalate to Rich; jarvis does no reasoning — render and capture only.

## Design Decision (settled 2026-07-07 — named per WS1 §5, do not re-defer)

**DD-SPL003-1: correlation_id → Slack thread-ts mapping = Slack-ts-in-payload
round-trip. No KV bucket.**

**Decision.** The Slack thread anchor (`parent_request_id`, the originating
message ts) travels IN the payloads, both directions: jarvis stamps it into
`PlanningQueuedPayload` at intake (already shipped, FEAT-SPL-001); forge
persists it durably in SQLite (`planning_runs.parent_request_id`, already
shipped, schema_v3) and projects it back into every outbound planning
notification and checkpoint detail. Jarvis holds **zero** mapping state.

**Rationale (2026-07-07).**
1. *ADR-ARCH-004 compliance is literal, not aspirational.* The SPL scope's
   pin (scope §"pins", line 53) reads: "no session store; loop state lives in
   NATS payloads + forge SQLite rows." The round-trip is exactly that
   sentence. A KV bucket is a session store by another name — a third state
   location neither payload nor forge row.
2. *The durable mapping already exists on the sanctioned side.*
   `planning_runs.parent_request_id` (keyed by `correlation_id`) IS the
   correlation_id→thread-ts table, durable across restarts of everything.
   Payload fields are projections of that row; re-projection (forge
   re-publish, e.g. escalation's existing re-publish path) is the recovery
   path for any lost payload — which is precisely the "re-thread after
   payload loss" benefit claimed for the KV option, already available
   without new machinery.
3. *The KV option is all new surface.* nats-core has no generic KV helper
   (the sole bucket, `agent-registry`, is lookup-only and pre-provisioned by
   nats-infrastructure); a mapping bucket means new infra provisioning, a
   new nats-core convention, jarvis's first KV *write* path, and a
   two-sources-of-truth consistency problem against the SQLite row.
4. *Precedent.* `parent_request_id` was added to `PlanningQueuedPayload`
   with the docstring "lets Jarvis correlate approval requests and acks back
   to the originating conversation" — the round-trip completes the pattern
   it was created for.

**Restart-survival proof obligation (validation criterion, not
nice-to-have).** Survival is by construction — there is nothing jarvis-side
to lose — and the spec pins it behaviourally: scenario "The thread mapping
survives a Jarvis restart" (@edge-case @smoke) requires a post-restart
notification to thread correctly with the anchor taken from the payload
itself; two companion scenarios pin dialogue-state survival (pre-restart
prompts stay decidable; pre-restart partial decisions are preserved) via the
message-as-state design (ASSUM-004). The degraded path (payload without an
anchor → top-level channel post, never dropped) is pinned by a @negative
scenario.

**Costs accepted.** Threading quality depends on forge projecting the anchor
into outbound payloads (ASSUM-001/014 — Session I fields + forge detail
projection); until those land, notifications degrade to top-level channel
posts (visible, traceable, unthreaded). No re-thread is possible for a
payload that never carried an anchor AND whose run row was purged — accepted
as out of scope for v1.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 7 |
| Boundary conditions (@boundary) | 5 (one outline, 2 rows; one also @negative) |
| Negative cases (@negative) | 8 (one also @boundary; one also @regression) |
| Edge cases (@edge-case) | 6 |

Gate coverage (WS1 §5): per-assumption approve/edit/defer as distinct
dispositions in the approval payload AND the trace record (Group A:
approve/edit/defer scenarios + "dispositions land in the planning trace
record"); cap-3 → escalation to Rich (@boundary pair + @edge-case escalated
prompt); restart-survival of the thread mapping (@edge-case @smoke, plus two
dialogue-state restart scenarios); the notification consumer rendering a
real Mode P handoff message into the originating thread (@key-example @smoke,
first scenario).

## Contract Pins for nats-core Session I (WS1 §9 items 2/3 — NOT edited here)

- **NotificationPayload** (item 3): optional `parent_request_id` (Slack
  thread ts, same name/meaning as PlanningQueuedPayload's), optional
  `target_user` (member id to mention), optional `blocks` (structured Block
  Kit). ASSUM-001.
- **Approval-topic convention** (item 2): `agents.approval.forge.plan-{cid}`
  documented as normative; consumers key on checkpoint details, never on
  run-id shape. ASSUM-002.
- **Dispositions carrier**: v1 rides `ApprovalResponsePayload.notes` as JSON
  (frozen 0.5.0); a first-class structured `dispositions` field (extend or
  companion) flagged as the clean follow-up. ASSUM-003.

## Forge Half (falls out of SPL-002 where it can; delta = a task, never a feature)

Verified 2026-07-07 against forge HEAD: SPL-002's checkpoint design supplies
the approval surface (`plan-{cid}` requests, expected_approver pinning,
defer/escalation machinery) but does **not** fully cover FEAT-SPL-003's forge
half. Ready-to-file `/task-create` note for the next forge session (per WS1
§5 — no forge edits from this venue):

> **TASK (forge): Mode P assumption-dialogue support — checkpoint detail
> projection + revision assembler.** (1) Project into
> `build_planning_approval_envelope` details, per cycle: `parent_request_id`
> (from the planning_runs row), the originating channel, the dialogue
> `cycle` number, and the structured assumptions list
> `{id, text, confidence, basis}` (today: summary/rationale/attempt_count
> only). (2) Parse per-assumption dispositions from the approval response
> (v1: JSON in `notes` — schema in jarvis FEAT-SPL-003 ASSUM-003); all
> confirmed → proceed; any overridden → assemble EnrichmentBatch-shaped
> revision input → stateless PO re-invoke; any deferred → existing
> handle_defer_request. (3) Cap 3 dialogue cycles → escalate to Rich via the
> existing escalation path; record each cycle's dispositions in
> `planning_run_events.details_json` (the FEAT-SPL-005 trace spine). Also
> project `parent_request_id`/`target_user` into outbound
> `NotificationPayload`s once Session I lands the fields.

## Deferred Items

None — `--auto` accepted all four groups. Out of scope by design: any
jarvis-side reasoning or enrichment (forge assembles revisions); the PO
clarification engine (architect-only, must not leak — scope §3.3); durable
jarvis-side dedup or session state (ADR-ARCH-004); editing nats-core or
forge from this venue; Mode P dispatch/PO serving (SPL-002/DF-001).

## Open Assumptions (low confidence)

All fourteen — `--auto` mode. The load-bearing ones for Rich's review:
**ASSUM-003** (dispositions ride `notes` as JSON until Session I),
**ASSUM-004** (the Slack message IS the dialogue state — no pending map),
**ASSUM-006** (aggregate decision mapping approve/defer semantics),
**ASSUM-007** (durable consumer for notifications — deliberate departure
from the DDR-027 ephemeral pattern), **ASSUM-010** (auto-publish on final
item, no submit button), **ASSUM-014** (the forge-half delta is real:
checkpoint details lack the thread anchor and cycle number today).

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Assumption Dialogue" \
      --context features/feat-spl-003-assumption-dialogue/feat-spl-003-assumption-dialogue_summary.md

The build is a later Opus session (WS1 §5: spec [Fable, in-window], build
[Opus 4.8]). Sequencing: Session I (nats-core items 2/3) lands before or
with the build; the notification consumer (deliverable 1) can ship first and
degrade gracefully until the payload fields exist.
