
/feature-spec "Build Queue Dispatch to Forge: queue_build publishes BuildQueuedPayload to pipeline.build-queued.{feature_id} per ADR-SP-014 Pattern A; Jarvis subscribes to pipeline.stage-complete.> via ephemeral push consumer (deliver_policy=NEW); ForgeNotificationsSubscriber routes correlation-matched events to per-session CLI rendering between prompts; routing-history writer emits append-only stage_complete edges on the originating JarvisRoutingHistoryEntry" \
  --context docs/design/FEAT-JARVIS-005/design.md \
  --context docs/design/FEAT-JARVIS-005/contracts/API-tools.md \
  --context docs/design/FEAT-JARVIS-005/contracts/API-internal.md \
  --context docs/design/FEAT-JARVIS-005/contracts/API-events.md \
  --context docs/design/FEAT-JARVIS-005/models/DM-forge-notification.md \
  --context docs/design/FEAT-JARVIS-005/diagrams/forge-feedback-l3.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-025-queue-build-real-transport.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-026-forge-notifications-module-location.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-028-correlation-map-in-memory-bounded.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-029-stage-complete-as-append-only-edges.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-030-cli-notifications-between-prompts.md \
  --context docs/design/FEAT-JARVIS-005/decisions/DDR-031-originating-adapter-from-session.md \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/design/FEAT-JARVIS-004/contracts/API-internal.md \
  --context docs/design/FEAT-JARVIS-004/contracts/API-events.md \
  --context docs/design/FEAT-JARVIS-004/models/DM-routing-history.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-018-routing-history-schema-authoritative.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-020-concurrent-dispatch-cap-8.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context ../forge/docs/design/contracts/API-nats-pipeline-events.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../nats-core/src/nats_core/events/_pipeline.py \
  --context ../nats-core/src/nats_core/events/__init__.py \
  --context ../nats-core/src/nats_core/topics.py \
  --context src/jarvis/tools/dispatch.py \
  --context src/jarvis/infrastructure/nats_client.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context src/jarvis/infrastructure/lifecycle.py \
  --context src/jarvis/sessions/manager.py \
  --context src/jarvis/cli/main.py \
  --context .guardkit/context-manifest.yaml

Phase 1 complete — context loaded: stack=python, 4 existing .feature files, all 7 FEAT-J005 DDRs (025-031), nats_core payload schemas, current stub body. Here is the Phase 2 proposal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: Build Queue Dispatch to Forge (FEAT-JARVIS-005)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@feat-jarvis-005 @forge-feedback @fleet-dispatch
Feature: Build Queue Dispatch to Forge
  As Jarvis
  I want to publish build-queue requests to Forge as a real JetStream
  message, listen for the matching stage-complete events, and surface
  them back to the originating session between prompts
  So that Rich can hand off a planned feature to Forge from the chat
  loop and watch its progress arrive on the next prompt cycle, with a
  trace-rich history of what was queued and what happened to it,
  without ever blocking the supervisor's next turn

  Background:
    Given Jarvis is running with a connected NATS transport
    And Jarvis has subscribed to Forge's pipeline stage-complete events
    And Rich is in an active terminal chat session
━━ GROUP A: Key Examples (6 scenarios) ━━


  # Why: Phase 3 close criterion #5 — the real publish replaces the Phase 2 stub
  @key-example @smoke
  Scenario: Queueing a build publishes the request to Forge and returns a queued acknowledgement
    Given a planned feature with a valid feature identifier, repository, and feature-yaml path
    When Rich asks Jarvis to queue the build
    Then Forge should receive the build-queued request on the singular per-feature subject
    And the published request should identify Jarvis as the trigger
    And the published request should record the originating adapter as the active session's adapter
    And the supervisor should be told the build was queued
    And the acknowledgement should carry the correlation identifier, the feature identifier, the queued timestamp, and the publish target

  # Why: Phase 3 close criterion #6 — stage-complete events route back to the originating session
  @key-example @smoke
  Scenario: A stage-complete event for a queued build surfaces on the originating session
    Given Rich has queued a build from this session
    And Forge is processing that build
    When Forge announces that a stage of the build has completed
    Then a notification should be queued for delivery on Rich's session
    And no notification should be queued for any other session

  # Why: DDR-029 — append-only edges preserve the audit trail
  @key-example @smoke
  Scenario: A stage-complete event is recorded as an append-only edge on the originating routing history entry
    Given Rich has queued a build from this session
    And the build's queue-time routing history entry has been written
    When Forge announces that a stage of the build has completed
    Then a stage-complete edge should be appended to that routing history entry
    And the originating routing history entry should remain unchanged

  # Why: DDR-029 — multiple stages do not collide; each one becomes a distinct edge
  @key-example
  Scenario: Multiple stage-complete events for one build produce multiple distinct stage-complete edges
    Given Rich has queued a build from this session
    When Forge announces that three stages of the build have completed in sequence
    Then three distinct stage-complete edges should be recorded against the originating routing history entry
    And no earlier stage-complete record should be overwritten by a later one

  # Why: DDR-030 — notifications render between prompts only, in the canonical cross-adapter shape
  @key-example @smoke
  Scenario: Pending notifications are rendered to the CLI before the next prompt is read
    Given a stage-complete notification for Rich's session is pending delivery
    When the chat loop is ready to read Rich's next input
    Then Rich should see one line for that notification before the next prompt
    And the line should show the local time, the feature identifier, the stage label, and the stage status
    And the pending notification queue should be empty after the line is rendered

  # Why: First live forge_build_queue trace — feeds the v1.5 learning substrate
  @key-example
  Scenario: Queueing a build writes a forge_build_queue routing history entry without blocking the supervisor
    Given a planned feature ready to be queued
    When Rich asks Jarvis to queue the build
    Then a routing history entry should be written for that build
    And the entry should be tagged as a forge build-queue dispatch
    And the entry should carry the correlation identifier as its subagent task identifier
    And the entry should record the originating session, the originating adapter, and the publish target
    And the supervisor should not have waited for the routing history write to land
━━ GROUP B: Boundary Conditions (6 scenarios, 1 outline) ━━


  # Why: Just-inside boundary — the per-session queue absorbs a full burst without loss
  # [ASSUMPTION: confidence=high] DDR-030 — default per-session cap is 100 entries
  @boundary
  Scenario: The per-session notification queue holds the full configured number of pending notifications
    Given the per-session notification cap is one hundred
    When one hundred stage-complete notifications are enqueued for Rich's session
    Then all one hundred notifications should be available on the next prompt cycle
    And they should be rendered in the order Forge published them

  # Why: Just-outside boundary — the (cap + 1)th eviction is observable
  @boundary @negative
  Scenario: Enqueueing one notification beyond the per-session cap evicts the oldest entry
    Given the per-session notification queue is full at the configured cap
    When one more stage-complete notification is enqueued for that session
    Then the oldest pending notification should be discarded
    And the queue length should remain at the configured cap
    And an overflow warning should be recorded for the discarded notification

  # Why: Just-inside boundary — the correlation map absorbs the full configured number of in-flight builds
  # [ASSUMPTION: confidence=high] DDR-028 — default correlation map cap is 1000 entries
  @boundary
  Scenario: The correlation map holds the full configured number of in-flight build correlations
    Given the correlation map cap is the configured value
    When that many builds have been queued without their correlations being evicted
    Then every queued correlation should still be resolvable for incoming stage-complete events

  # Why: Just-outside boundary — the (cap + 1)th correlation evicts the oldest
  @boundary @negative
  Scenario: Registering one correlation beyond the configured cap evicts the oldest correlation
    Given the correlation map is full at the configured cap
    When one more build is queued and its correlation is registered
    Then the oldest correlation should be removed from the map
    And an eviction warning should be recorded for the removed correlation
    And a stage-complete event arriving for the evicted correlation should be silently dropped

  # Why: Just-inside boundary — a publish that lands under the timeout returns "queued"
  # [ASSUMPTION: confidence=high] DDR-025 — default publish timeout is 5 seconds
  @boundary
  Scenario: A publish acknowledgement received within the configured timeout returns a queued acknowledgement
    Given the publish timeout is set to its configured default
    When the broker acknowledges the publish before the timeout elapses
    Then the supervisor should be told the build was queued
    And the queued acknowledgement should reference the message stored in the pipeline stream

  # Why: Just-outside boundary — a publish that misses the timeout reports transport unavailable
  @boundary @negative
  Scenario: A publish that does not acknowledge within the configured timeout reports the transport as unavailable
    Given the publish timeout is set to its configured default
    When the broker fails to acknowledge the publish before the timeout elapses
    Then the supervisor should receive a degraded response indicating the JetStream publish failed
    And a routing history entry should still be written recording the transport-unavailable outcome
    And no correlation should be registered for the un-published build
━━ GROUP C: Negative Cases (5 scenarios + 1 outline with 3 examples) ━━


  # Why: Audit-trail invariant — only Forge may publish stage-complete events Jarvis acts on
  @negative
  Scenario: A stage-complete event from an unrecognised source is dropped without surfacing
    Given Rich has queued a build from this session
    When a stage-complete event arrives for that build but it claims a non-Forge source
    Then no notification should be queued for any session
    And no stage-complete edge should be recorded against the originating routing history entry
    And the unexpected source should be reported in the operator log

  # Why: Without a registered correlation there is no session to surface the event to
  @negative
  Scenario: A stage-complete event for an unknown correlation is silently dropped
    Given the correlation map has no entry for an incoming event's correlation identifier
    When that stage-complete event is delivered to the subscriber
    Then no notification should be queued for any session
    And no stage-complete edge should be recorded
    And no error should be raised on the subscriber

  # Why: DDR-021 inheritance — NATS-down must soft-fail visibly to the reasoning model
  @negative
  Scenario: Queueing a build when the NATS transport is unavailable returns a degraded response
    Given Jarvis is running without a connected NATS transport
    When Rich asks Jarvis to queue a build
    Then the supervisor should receive a degraded response indicating the NATS connection failed
    And a routing history entry should still be written recording the transport-unavailable outcome
    And the chat session should remain usable

  # Why: DDR-020 — the dispatch concurrency cap also covers queue_build
  @negative
  Scenario: Queueing a build when the dispatch concurrency cap is saturated returns a degraded response
    Given the supervisor's concurrent dispatch slots are all held by other in-flight work
    When Rich asks Jarvis to queue a build
    Then the supervisor should receive a degraded response indicating dispatch is overloaded
    And no build-queued request should be published to Forge
    And no correlation should be registered

  # Why: ADR-ARCH-021 — every error path must be a structured string, never an exception
  @negative
  Scenario Outline: Queueing a build with invalid arguments returns a structured validation error
    When Rich asks Jarvis to queue a build with an <invalid_field>
    Then the supervisor should receive a structured validation error naming the offending field
    And no build-queued request should be published to Forge
    And no correlation should be registered

    Examples:
      | invalid_field                                                |
      | feature identifier that does not match the FEAT-XXX pattern  |
      | repository value that is not in org/name format              |
      | originating adapter that is not in the allowed adapter set   |

  # Why: DDR-031 — adapter identity is constitutional, not reasoning-adjustable
  @negative @security
  Scenario: A reasoning-model attempt to override the originating adapter is silently overridden by the session adapter
    Given Rich's session uses the terminal adapter
    When the reasoning model invokes the queue tool claiming a different originating adapter
    Then the published build-queued request should record the session's terminal adapter
    And the reasoning model should not be told that its argument was overridden
    And no error path should be taken
━━ GROUP D: Edge Cases (6 scenarios) ━━


  # Why: Per-session isolation — notifications must not leak across concurrent sessions
  @edge-case
  Scenario: A stage-complete event for a build queued from one session does not surface on a different session
    Given two terminal sessions are active for the same operator
    And Rich queued a build from the first session
    When Forge announces a stage of that build has completed
    Then only the first session's pending notifications should contain the new event
    And the second session's pending notifications should remain empty

  # Why: DDR-030 — notifications never interleave with the LLM stream or the user's typing
  @edge-case
  Scenario: A notification arriving during a supervisor turn is buffered until the next prompt cycle
    Given Rich has just submitted a prompt and the supervisor is producing a reply
    When Forge announces a stage of an earlier build has completed
    Then the notification should not be rendered while the reply is being produced
    And the notification should be rendered before Rich is asked for the next prompt

  # Why: DDR-030 — end_session leaves no stranded notifications
  @edge-case
  Scenario: Ending a session clears that session's pending notifications and discards future ones
    Given Rich's session has pending stage-complete notifications
    When Rich ends the session
    Then the session's pending notification queue should be cleared
    And the cleared count should be recorded in the operator log
    And any subsequent stage-complete event for a build queued from that session should be discarded without raising

  # Why: DDR-031 — the tool argument remains a fallback for sessionless test/scripted paths
  @edge-case
  Scenario: Queueing a build without an active session uses the originating-adapter argument as a fallback
    Given there is no active session bound to the queue tool
    When the queue tool is invoked with an explicit originating adapter
    Then the published build-queued request should use the supplied originating adapter
    And the routing history entry should record the same adapter
    And no notification should be queued anywhere

  # Why: DDR-019 inheritance — Graphiti unavailability must not block the user-visible feedback loop
  @edge-case
  Scenario: A failed stage-complete edge write is logged as a warning but does not affect notification delivery
    Given Rich has queued a build from this session
    And the routing history substrate is unavailable
    When Forge announces that a stage of the build has completed
    Then the stage-complete notification should still be queued for Rich's session
    And the failed edge write should be recorded in the operator log as a warning
    And the chat session should continue without error

  # Why: DDR-027 — deliver_policy=NEW means stage events from before subscription are intentionally not replayed
  @edge-case
  Scenario: Stage-complete events that fired before the subscriber started are not delivered to the session
    Given Forge published stage-complete events while Jarvis was not running
    When Jarvis starts and creates its stage-complete subscription
    Then those earlier events should not be delivered to any session
    And only events Forge publishes after the subscription was created should be considered for delivery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 24 scenarios across 4 groups (28 example rows including the validation Scenario Outline)
Inferred assumptions: 11 (will be resolved in Phase 5; all anchored in DDR-025/027/028/029/030/031, so confidence is high)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Per group: [A] accept · [R] reject · [M] modify (provide change inline) · [+] add (describe extra scenario) · [?] defer

Fast path: reply A A A A to accept all four groups.

GROUP A — Key Examples (6 scenarios): _
GROUP B — Boundary Conditions (6 scenarios + 1 outline): _
GROUP C — Negative Cases (5 scenarios + 1 outline): _
GROUP D — Edge Cases (6 scenarios): _
After curation I'll offer Phase 4 (additional security/concurrency/integration edge cases — malformed envelopes, duplicate correlation replays, Forge-side schema drift, subscriber stop during a wedged broker) and then Phase 5 assumption confirmation.

A A A A
All four groups accepted as-is. Proceeding to Phase 4.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've identified 8 additional scenarios covering security, concurrency, data integrity, and integration boundaries. Two samples below; the rest follow the same shape.

Security (2):


  # Why: Defence against payload tampering — malformed JSON must not crash the subscriber
  @edge-case @security
  Scenario: A stage-complete delivery whose body is not a valid envelope is dropped without raising
    Given Rich has queued a build from this session
    When a stage-complete delivery arrives whose body cannot be parsed as a message envelope
    Then no notification should be queued for any session
    And the malformed delivery should be reported in the operator log
    And the subscriber should remain healthy and continue processing later events

  # Why: Defence against payload schema drift — extra Forge-side fields must not break consumption
  @edge-case @security
  Scenario: A stage-complete event carrying additional unknown fields is consumed without rejection
    Given Rich has queued a build from this session
    When Forge announces a stage of the build has completed with additional unknown fields in the payload
    Then a notification should still be queued for Rich's session
    And a stage-complete edge should still be recorded against the originating routing history entry
Concurrency (2):


  # Why: Two operators (or two test fixtures) racing on the same correlation must each get their own routing
  @edge-case @concurrency
  Scenario: Two stage-complete events for two different correlations arriving in the same instant each route to their own session
    Given two builds have been queued from two different sessions
    When stage-complete events for both builds are delivered concurrently
    Then each session should see only the notification for its own build
    And both originating routing history entries should each receive one new stage-complete edge

  # Why: Forge's contract emits multiple stages per build — bursts must preserve order on a single session
  @edge-case @concurrency
  Scenario: A burst of stage-complete events for one build is rendered in publication order on the next prompt cycle
    Given Rich has queued a build from this session
    When Forge publishes five stage-complete events for that build in rapid succession
    Then the next prompt cycle should render the five notifications in publication order
    And five distinct stage-complete edges should be recorded against the originating routing history entry
Data integrity (2):


  # Why: Forge dedupes by (feature_id, correlation_id); Jarvis must not register the same correlation twice
  @edge-case
  Scenario: Re-using an explicit correlation identifier across two queue requests does not corrupt the correlation map
    Given Rich queued a build with an explicit correlation identifier
    When Rich queues a second build supplying the same correlation identifier
    Then the correlation map should hold a single entry for that correlation identifier
    And subsequent stage-complete events for that correlation should route to the most-recent originating session

  # Why: A stage event whose correlation was just evicted must not silently overwrite a different entry
  @edge-case
  Scenario: A stage-complete event arriving after its correlation has been evicted is dropped without affecting any other correlation
    Given a build's correlation has been evicted from the correlation map due to overflow
    When a stage-complete event for that evicted correlation arrives
    Then no notification should be queued for any session
    And no other correlation's stage-complete edges should be modified
Integration boundaries (2):


  # Why: Shutdown must not hang on a wedged broker
  @edge-case @integration
  Scenario: Stopping the subscriber during shutdown completes within the bounded timeout even when the broker is unresponsive
    Given Jarvis is shutting down
    And the broker is unresponsive to drain requests
    When the subscriber is asked to stop with the configured shutdown timeout
    Then the subscriber should report stopped within the timeout
    And the timeout escalation should be recorded in the operator log
    And shutdown should proceed to the remaining steps

  # Why: queue_build is published via JetStream; specialist dispatch is core-NATS request/reply — they must not interfere
  @edge-case @integration
  Scenario: A build queue and a specialist dispatch issued in parallel each consume one slot from the shared concurrency cap
    Given two of the supervisor's concurrent dispatch slots are free
    When Rich asks Jarvis to queue a build and dispatch a specialist at the same time
    Then both requests should proceed
    And two slots should be observed as in-flight while both are running
    And both slots should be released once each request completes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Include these 8 additional scenarios?

[Y] Yes — include all 8 (added to their respective groups in the output)
[S] Sample — show only these 4 samples; ask group-by-group
[N] No — skip and proceed to Phase 5 with the 24 already accepted
Your choice [Y/S/N]:

Y
Adding all 8 edge cases. Total: 32 scenarios across the 4 groups (28 base + 8 expansion). Now Phase 5.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (11 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Every value is anchored in a DDR or contract document — all proposed at confidence=high. Press Enter (or accept-all) to confirm; type a replacement to override.

#	Assumption	Proposed	Confidence	Basis
1	Per-session notification queue cap	100	high	DDR-030 §"Decision" + JarvisConfig.forge_notifications_queue_cap default
2	Correlation map cap	1000	high	DDR-028 §"Decision" + JarvisConfig.forge_correlation_map_cap default
3	Publish timeout (PubAck)	5 seconds	high	DDR-025 + JarvisConfig.pipeline_publish_timeout_seconds default
4	Subscriber stop timeout on shutdown	5 seconds	high	API-internal §1 ForgeNotificationsSubscriber.stop(timeout=5.0)
5	Per-session queue eviction policy	oldest-first FIFO (deque.maxlen)	high	DDR-030 §"Decision" §3
6	Correlation map eviction policy	LRU oldest	high	DDR-028 §"Decision" §3
7	Subscriber source-id rule	drop + WARN unless source_id == "forge"	high	API-events §3 + design §8 step 2
8	Shared concurrent-dispatch cap (queue_build + dispatch_by_capability)	8	high	DDR-020 (FEAT-J004) — explicitly names both tools as cap-bound
9	Duplicate correlation_id on register	update existing entry's LRU position	high	DDR-028 §"Consequences"
10	Subscriber ack semantics	auto-ack (no manual_ack); failures upstream of correlation lookup drop silently; failures downstream caught by writer's WARN-only path	high	DDR-027 §"Decision" §4 + design §8
11	CLI line format	[HH:MM] Forge {feature_id}: stage {stage_label} ({status})	high	DM-forge-notification §1.format_one_line
Reply with one of:

accept all — proceed with all 11 proposed values as-is
A list of overrides like 3=10s, 8=12 — accept the rest, change only the listed numbers
Specific questions about any item before deciding
Your response:

accept all
All 11 assumptions confirmed at high confidence. Writing output files now.

Bash Create output directory for feature spec
IN
mkdir -p /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-005-build-queue-dispatch-to-forge

OUT
(Bash completed with no output)
Write feat-jarvis-005-build-queue-dispatch-to-forge.feature
328 lines
# Generated by /feature-spec
# Feature: Build Queue Dispatch to Forge (FEAT-JARVIS-005)
# Stack: python
# Assumptions: 11 (see feat-jarvis-005-build-queue-dispatch-to-forge_assumptions.yaml)
# Generated: 2026-04-29T15:00:00Z

@feat-jarvis-005 @forge-feedback @fleet-dispatch
Feature: Build Queue Dispatch to Forge
  As Jarvis
  I want to publish build-queue requests to Forge as a real JetStream
  message, listen for the matching stage-complete events, and surface
  them back to the originating session between prompts
  So that Rich can hand off a planned feature to Forge from the chat
  loop and watch its progress arrive on the next prompt cycle, with a
  trace-rich history of what was queued and what happened to it,
  without ever blocking the supervisor's next turn

  Background:
    Given Jarvis is running with a connected NATS transport
    And Jarvis has subscribed to Forge's pipeline stage-complete events
    And Rich is in an active terminal chat session

  # ─── GROUP A: Key Examples ──────────────────────────────────────────────

  # Why: Phase 3 close criterion #5 — the real publish replaces the Phase 2 stub
  @key-example @smoke
  Scenario: Queueing a build publishes the request to Forge and returns a queued acknowledgement
    Given a planned feature with a valid feature identifier, repository, and feature-yaml path
    When Rich asks Jarvis to queue the build
    Then Forge should receive the build-queued request on the singular per-feature subject
    And the published request should identify Jarvis as the trigger
    And the published request should record the originating adapter as the active session's adapter
    And the supervisor should be told the build was queued
    And the acknowledgement should carry the correlation identifier, the feature identifier, the queued timestamp, and the publish target

  # Why: Phase 3 close criterion #6 — stage-complete events route back to the originating session
  @key-example @smoke
  Scenario: A stage-complete event for a queued build surfaces on the originating session
    Given Rich has queued a build from this session
    And Forge is processing that build
    When Forge announces that a stage of the build has completed
    Then a notification should be queued for delivery on Rich's session
    And no notification should be queued for any other session

  # Why: DDR-029 — append-only edges preserve the audit trail
  @key-example @smoke
  Scenario: A stage-complete event is recorded as an append-only edge on the originating routing history entry
    Given Rich has queued a build from this session
    And the build's queue-time routing history entry has been written
    When Forge announces that a stage of the build has completed
    Then a stage-complete edge should be appended to that routing history entry
    And the originating routing history entry should remain unchanged

  # Why: DDR-029 — multiple stages do not collide; each one becomes a distinct edge
  @key-example
  Scenario: Multiple stage-complete events for one build produce multiple distinct stage-complete edges
    Given Rich has queued a build from this session
    When Forge announces that three stages of the build have completed in sequence
    Then three distinct stage-complete edges should be recorded against the originating routing history entry
    And no earlier stage-complete record should be overwritten by a later one

  # Why: DDR-030 — notifications render between prompts only, in the canonical cross-adapter shape
  # [ASSUMPTION: confidence=high] CLI line format is "[HH:MM] Forge {feature_id}: stage {stage_label} ({status})" per DM-forge-notification §1
  @key-example @smoke
  Scenario: Pending notifications are rendered to the CLI before the next prompt is read
    Given a stage-complete notification for Rich's session is pending delivery
    When the chat loop is ready to read Rich's next input
    Then Rich should see one line for that notification before the next prompt
    And the line should show the local time, the feature identifier, the stage label, and the stage status
    And the pending notification queue should be empty after the line is rendered

  # Why: First live forge_build_queue trace — feeds the v1.5 learning substrate
  @key-example
  Scenario: Queueing a build writes a forge_build_queue routing history entry without blocking the supervisor
    Given a planned feature ready to be queued
    When Rich asks Jarvis to queue the build
    Then a routing history entry should be written for that build
    And the entry should be tagged as a forge build-queue dispatch
    And the entry should carry the correlation identifier as its subagent task identifier
    And the entry should record the originating session, the originating adapter, and the publish target
    And the supervisor should not have waited for the routing history write to land

  # ─── GROUP B: Boundary Conditions ───────────────────────────────────────

  # Why: Just-inside boundary — the per-session queue absorbs a full burst without loss
  # [ASSUMPTION: confidence=high] DDR-030 — default per-session cap is 100 entries
  @boundary
  Scenario: The per-session notification queue holds the full configured number of pending notifications
    Given the per-session notification cap is one hundred
    When one hundred stage-complete notifications are enqueued for Rich's session
    Then all one hundred notifications should be available on the next prompt cycle
    And they should be rendered in the order Forge published them

  # Why: Just-outside boundary — the (cap + 1)th eviction is observable
  # [ASSUMPTION: confidence=high] DDR-030 — eviction policy is oldest-first FIFO
  @boundary @negative
  Scenario: Enqueueing one notification beyond the per-session cap evicts the oldest entry
    Given the per-session notification queue is full at the configured cap
    When one more stage-complete notification is enqueued for that session
    Then the oldest pending notification should be discarded
    And the queue length should remain at the configured cap
    And an overflow warning should be recorded for the discarded notification

  # Why: Just-inside boundary — the correlation map absorbs the full configured number of in-flight builds
  # [ASSUMPTION: confidence=high] DDR-028 — default correlation map cap is 1000 entries
  @boundary
  Scenario: The correlation map holds the full configured number of in-flight build correlations
    Given the correlation map cap is the configured value
    When that many builds have been queued without their correlations being evicted
    Then every queued correlation should still be resolvable for incoming stage-complete events

  # Why: Just-outside boundary — the (cap + 1)th correlation evicts the oldest
  # [ASSUMPTION: confidence=high] DDR-028 — eviction policy is LRU oldest
  @boundary @negative
  Scenario: Registering one correlation beyond the configured cap evicts the oldest correlation
    Given the correlation map is full at the configured cap
    When one more build is queued and its correlation is registered
    Then the oldest correlation should be removed from the map
    And an eviction warning should be recorded for the removed correlation
    And a stage-complete event arriving for the evicted correlation should be silently dropped

  # Why: Just-inside boundary — a publish that lands under the timeout returns "queued"
  # [ASSUMPTION: confidence=high] DDR-025 — default publish timeout is 5 seconds
  @boundary
  Scenario: A publish acknowledgement received within the configured timeout returns a queued acknowledgement
    Given the publish timeout is set to its configured default
    When the broker acknowledges the publish before the timeout elapses
    Then the supervisor should be told the build was queued
    And the queued acknowledgement should reference the message stored in the pipeline stream

  # Why: Just-outside boundary — a publish that misses the timeout reports transport unavailable
  @boundary @negative
  Scenario: A publish that does not acknowledge within the configured timeout reports the transport as unavailable
    Given the publish timeout is set to its configured default
    When the broker fails to acknowledge the publish before the timeout elapses
    Then the supervisor should receive a degraded response indicating the JetStream publish failed
    And a routing history entry should still be written recording the transport-unavailable outcome
    And no correlation should be registered for the un-published build

  # ─── GROUP C: Negative Cases ────────────────────────────────────────────

  # Why: Audit-trail invariant — only Forge may publish stage-complete events Jarvis acts on
  # [ASSUMPTION: confidence=high] Subscriber drops with WARN unless envelope source_id == "forge" per API-events §3
  @negative
  Scenario: A stage-complete event from an unrecognised source is dropped without surfacing
    Given Rich has queued a build from this session
    When a stage-complete event arrives for that build but it claims a non-Forge source
    Then no notification should be queued for any session
    And no stage-complete edge should be recorded against the originating routing history entry
    And the unexpected source should be reported in the operator log

  # Why: Without a registered correlation there is no session to surface the event to
  # [ASSUMPTION: confidence=high] Subscriber auto-acks and drops silently on unknown correlation per DDR-027 + design §8
  @negative
  Scenario: A stage-complete event for an unknown correlation is silently dropped
    Given the correlation map has no entry for an incoming event's correlation identifier
    When that stage-complete event is delivered to the subscriber
    Then no notification should be queued for any session
    And no stage-complete edge should be recorded
    And no error should be raised on the subscriber

  # Why: DDR-021 inheritance — NATS-down must soft-fail visibly to the reasoning model
  @negative
  Scenario: Queueing a build when the NATS transport is unavailable returns a degraded response
    Given Jarvis is running without a connected NATS transport
    When Rich asks Jarvis to queue a build
    Then the supervisor should receive a degraded response indicating the NATS connection failed
    And a routing history entry should still be written recording the transport-unavailable outcome
    And the chat session should remain usable

  # Why: DDR-020 — the dispatch concurrency cap also covers queue_build
  # [ASSUMPTION: confidence=high] Shared dispatch cap = 8, covers both queue_build and dispatch_by_capability per DDR-020
  @negative
  Scenario: Queueing a build when the dispatch concurrency cap is saturated returns a degraded response
    Given the supervisor's concurrent dispatch slots are all held by other in-flight work
    When Rich asks Jarvis to queue a build
    Then the supervisor should receive a degraded response indicating dispatch is overloaded
    And no build-queued request should be published to Forge
    And no correlation should be registered

  # Why: ADR-ARCH-021 — every error path must be a structured string, never an exception
  @negative
  Scenario Outline: Queueing a build with invalid arguments returns a structured validation error
    When Rich asks Jarvis to queue a build with an <invalid_field>
    Then the supervisor should receive a structured validation error naming the offending field
    And no build-queued request should be published to Forge
    And no correlation should be registered

    Examples:
      | invalid_field                                                |
      | feature identifier that does not match the FEAT-XXX pattern  |
      | repository value that is not in org/name format              |
      | originating adapter that is not in the allowed adapter set   |

  # Why: DDR-031 — adapter identity is constitutional, not reasoning-adjustable
  @negative @security
  Scenario: A reasoning-model attempt to override the originating adapter is silently overridden by the session adapter
    Given Rich's session uses the terminal adapter
    When the reasoning model invokes the queue tool claiming a different originating adapter
    Then the published build-queued request should record the session's terminal adapter
    And the reasoning model should not be told that its argument was overridden
    And no error path should be taken

  # ─── GROUP D: Edge Cases ────────────────────────────────────────────────

  # Why: Per-session isolation — notifications must not leak across concurrent sessions
  @edge-case
  Scenario: A stage-complete event for a build queued from one session does not surface on a different session
    Given two terminal sessions are active for the same operator
    And Rich queued a build from the first session
    When Forge announces a stage of that build has completed
    Then only the first session's pending notifications should contain the new event
    And the second session's pending notifications should remain empty

  # Why: DDR-030 — notifications never interleave with the LLM stream or the user's typing
  @edge-case
  Scenario: A notification arriving during a supervisor turn is buffered until the next prompt cycle
    Given Rich has just submitted a prompt and the supervisor is producing a reply
    When Forge announces a stage of an earlier build has completed
    Then the notification should not be rendered while the reply is being produced
    And the notification should be rendered before Rich is asked for the next prompt

  # Why: DDR-030 — end_session leaves no stranded notifications
  @edge-case
  Scenario: Ending a session clears that session's pending notifications and discards future ones
    Given Rich's session has pending stage-complete notifications
    When Rich ends the session
    Then the session's pending notification queue should be cleared
    And the cleared count should be recorded in the operator log
    And any subsequent stage-complete event for a build queued from that session should be discarded without raising

  # Why: DDR-031 — the tool argument remains a fallback for sessionless test/scripted paths
  @edge-case
  Scenario: Queueing a build without an active session uses the originating-adapter argument as a fallback
    Given there is no active session bound to the queue tool
    When the queue tool is invoked with an explicit originating adapter
    Then the published build-queued request should use the supplied originating adapter
    And the routing history entry should record the same adapter
    And no notification should be queued anywhere

  # Why: DDR-019 inheritance — Graphiti unavailability must not block the user-visible feedback loop
  @edge-case
  Scenario: A failed stage-complete edge write is logged as a warning but does not affect notification delivery
    Given Rich has queued a build from this session
    And the routing history substrate is unavailable
    When Forge announces that a stage of the build has completed
    Then the stage-complete notification should still be queued for Rich's session
    And the failed edge write should be recorded in the operator log as a warning
    And the chat session should continue without error

  # Why: DDR-027 — deliver_policy=NEW means stage events from before subscription are intentionally not replayed
  @edge-case
  Scenario: Stage-complete events that fired before the subscriber started are not delivered to the session
    Given Forge published stage-complete events while Jarvis was not running
    When Jarvis starts and creates its stage-complete subscription
    Then those earlier events should not be delivered to any session
    And only events Forge publishes after the subscription was created should be considered for delivery

  # Why: Defence against payload tampering — malformed JSON must not crash the subscriber
  @edge-case @security
  Scenario: A stage-complete delivery whose body is not a valid envelope is dropped without raising
    Given Rich has queued a build from this session
    When a stage-complete delivery arrives whose body cannot be parsed as a message envelope
    Then no notification should be queued for any session
    And the malformed delivery should be reported in the operator log
    And the subscriber should remain healthy and continue processing later events

  # Why: Defence against payload schema drift — extra Forge-side fields must not break consumption
  @edge-case @security
  Scenario: A stage-complete event carrying additional unknown fields is consumed without rejection
    Given Rich has queued a build from this session
    When Forge announces a stage of the build has completed with additional unknown fields in the payload
    Then a notification should still be queued for Rich's session
    And a stage-complete edge should still be recorded against the originating routing history entry

  # Why: Two operators (or two test fixtures) racing on the same correlation must each get their own routing
  @edge-case @concurrency
  Scenario: Two stage-complete events for two different correlations arriving in the same instant each route to their own session
    Given two builds have been queued from two different sessions
    When stage-complete events for both builds are delivered concurrently
    Then each session should see only the notification for its own build
    And both originating routing history entries should each receive one new stage-complete edge

  # Why: Forge's contract emits multiple stages per build — bursts must preserve order on a single session
  @edge-case @concurrency
  Scenario: A burst of stage-complete events for one build is rendered in publication order on the next prompt cycle
    Given Rich has queued a build from this session
    When Forge publishes five stage-complete events for that build in rapid succession
    Then the next prompt cycle should render the five notifications in publication order
    And five distinct stage-complete edges should be recorded against the originating routing history entry

  # Why: Forge dedupes by (feature_id, correlation_id); Jarvis must not register the same correlation twice
  # [ASSUMPTION: confidence=high] DDR-028 — duplicate correlation_id register updates the existing entry's LRU position
  @edge-case
  Scenario: Re-using an explicit correlation identifier across two queue requests does not corrupt the correlation map
    Given Rich queued a build with an explicit correlation identifier
    When Rich queues a second build supplying the same correlation identifier
    Then the correlation map should hold a single entry for that correlation identifier
    And subsequent stage-complete events for that correlation should route to the most-recent originating session

  # Why: A stage event whose correlation was just evicted must not silently overwrite a different entry
  @edge-case
  Scenario: A stage-complete event arriving after its correlation has been evicted is dropped without affecting any other correlation
    Given a build's correlation has been evicted from the correlation map due to overflow
    When a stage-complete event for that evicted correlation arrives
    Then no notification should be queued for any session
    And no other correlation's stage-complete edges should be modified

  # Why: Shutdown must not hang on a wedged broker
  # [ASSUMPTION: confidence=high] Subscriber stop timeout is 5 seconds per API-internal §1
  @edge-case @integration
  Scenario: Stopping the subscriber during shutdown completes within the bounded timeout even when the broker is unresponsive
    Given Jarvis is shutting down
    And the broker is unresponsive to drain requests
    When the subscriber is asked to stop with the configured shutdown timeout
    Then the subscriber should report stopped within the timeout
    And the timeout escalation should be recorded in the operator log
    And shutdown should proceed to the remaining steps

  # Why: queue_build is published via JetStream; specialist dispatch is core-NATS request/reply — they must not interfere
  @edge-case @integration
  Scenario: A build queue and a specialist dispatch issued in parallel each consume one slot from the shared concurrency cap
    Given two of the supervisor's concurrent dispatch slots are free
    When Rich asks Jarvis to queue a build and dispatch a specialist at the same time
    Then both requests should proceed
    And two slots should be observed as in-flight while both are running
    And both slots should be released once each request completes
Write feat-jarvis-005-build-queue-dispatch-to-forge_assumptions.yaml
86 lines
# Assumptions manifest for feat-jarvis-005-build-queue-dispatch-to-forge.feature
# Generated by /feature-spec

feature: "Build Queue Dispatch to Forge (FEAT-JARVIS-005)"
generated: "2026-04-29T15:00:00Z"
stack: "python"
review_required: false

assumptions:
  - id: "ASSUM-001"
    scenario: "The per-session notification queue holds the full configured number of pending notifications"
    assumption: "Per-session notification queue cap defaults to 100 entries (configurable via JarvisConfig.forge_notifications_queue_cap, ge=1, le=10_000)"
    confidence: high
    basis: "DDR-030 §Decision §2 + API-internal §7 JarvisConfig.forge_notifications_queue_cap default"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Enqueueing one notification beyond the per-session cap evicts the oldest entry"
    assumption: "Per-session queue eviction policy is oldest-first FIFO, implemented via collections.deque(maxlen=cap); overflow emits WARN forge_notification_queue_overflow"
    confidence: high
    basis: "DDR-030 §Decision §3"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "The correlation map holds the full configured number of in-flight build correlations"
    assumption: "Correlation map cap defaults to 1000 entries (configurable via JarvisConfig.forge_correlation_map_cap, ge=10, le=100_000)"
    confidence: high
    basis: "DDR-028 §Decision §2 + API-internal §7 JarvisConfig.forge_correlation_map_cap default"
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "Registering one correlation beyond the configured cap evicts the oldest correlation"
    assumption: "Correlation map eviction policy is LRU oldest, implemented via OrderedDict; eviction emits WARN forge_correlation_evicted"
    confidence: high
    basis: "DDR-028 §Decision §3"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "A publish acknowledgement received within the configured timeout returns a queued acknowledgement"
    assumption: "Pipeline publish timeout (PubAck) defaults to 5 seconds (configurable via JarvisConfig.pipeline_publish_timeout_seconds, ge=1, le=60)"
    confidence: high
    basis: "DDR-025 §Decision §3 + API-internal §7 JarvisConfig.pipeline_publish_timeout_seconds default"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "A stage-complete event from an unrecognised source is dropped without surfacing"
    assumption: "Subscriber drops the message with WARN forge_notifications_unexpected_source unless envelope.source_id == 'forge'; the message is still auto-acked"
    confidence: high
    basis: "API-events §3 + design §8 step 2"
    human_response: "confirmed"

  - id: "ASSUM-007"
    scenario: "A stage-complete event for an unknown correlation is silently dropped"
    assumption: "Subscriber uses ephemeral push consumer with deliver_policy=NEW and auto-ack (no manual_ack); failures upstream of the correlation lookup drop silently with DEBUG; failures downstream are caught by the writer's WARN-only path"
    confidence: high
    basis: "DDR-027 §Decision §4 + design §8"
    human_response: "confirmed"

  - id: "ASSUM-008"
    scenario: "Queueing a build when the dispatch concurrency cap is saturated returns a degraded response"
    assumption: "Concurrent-dispatch cap = 8 and is shared between queue_build and dispatch_by_capability"
    confidence: high
    basis: "DDR-020 (FEAT-J004) — explicitly names both tools as cap-bound; reused by DDR-025"
    human_response: "confirmed"

  - id: "ASSUM-009"
    scenario: "Re-using an explicit correlation identifier across two queue requests does not corrupt the correlation map"
    assumption: "Inserting a duplicate correlation_id updates the existing entry's LRU position (re-inserts at the head) without growing the map"
    confidence: high
    basis: "DDR-028 §Consequences"
    human_response: "confirmed"

  - id: "ASSUM-010"
    scenario: "Pending notifications are rendered to the CLI before the next prompt is read"
    assumption: "CLI line format is '[HH:MM] Forge {feature_id}: stage {stage_label} ({status})' where time is the local-time portion of completed_at; this is the canonical cross-adapter rendering shape"
    confidence: high
    basis: "DM-forge-notification §1 ForgeNotification.format_one_line"
    human_response: "confirmed"

  - id: "ASSUM-011"
    scenario: "Stopping the subscriber during shutdown completes within the bounded timeout even when the broker is unresponsive"
    assumption: "Subscriber stop timeout is 5 seconds; on timeout the subscriber logs WARN and abandons; safe to call from shutdown(state) even when start() never succeeded"
    confidence: high
    basis: "API-internal §1 ForgeNotificationsSubscriber.stop(timeout=5.0)"
    human_response: "confirmed"
Write feat-jarvis-005-build-queue-dispatch-to-forge_summary.md
81 lines
# Feature Spec Summary: Build Queue Dispatch to Forge (FEAT-JARVIS-005)

**Stack**: python
**Generated**: 2026-04-29T15:00:00Z
**Scenarios**: 32 total (1 of which is a Scenario Outline with 3 example rows = 34 effective example rows)
**Smoke**: 4 · **Regression**: 0
**Assumptions**: 11 total (11 high / 0 medium / 0 low)
**Review required**: No

## Scope

Closes the Jarvis → Forge loop. `queue_build` swaps from a Phase 2 stub log line to a real `js.publish(...)` on `pipeline.build-queued.{feature_id}` with PubAck-as-receipt and a 5-second timeout (per ADR-SP-014 Pattern A + DDR-025). Jarvis subscribes to `pipeline.stage-complete.>` via an ephemeral push consumer with `deliver_policy=NEW` (DDR-027), routes correlation-matched events through an in-process `ForgeNotificationsSubscriber` to the originating session's per-session pending-notification queue (DDR-026, DDR-030), and renders one CLI line per notification between prompts in the canonical `[HH:MM] Forge {feature_id}: stage {stage_label} ({status})` shape. Every build-queue dispatch writes a `subagent_type="forge_build_queue"` `JarvisRoutingHistoryEntry` and every matched stage-complete event lands as an append-only Graphiti edge on that entry (DDR-029). Adapter identity is constitutional — resolved from `Session.adapter`, not the reasoning-model arg (DDR-031). The reasoning model's tool surface is unchanged from Phase 2.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (`@key-example`) | 6 |
| Boundary conditions (`@boundary`) | 6 |
| Negative cases (`@negative`) | 9 (incl. 3 boundary-overlap rows + 3 outline rows) |
| Edge cases (`@edge-case`) | 14 |
| Smoke (`@smoke`) | 4 |
| Security (`@security`) | 3 |
| Concurrency (`@concurrency`) | 2 |
| Integration (`@integration`) | 2 |
| Regression (`@regression`) | 0 |

Note: tags overlap (e.g. several boundary scenarios are also `@negative`); the Scenario Outline in Group C contributes 3 distinct example rows.

## Deferred Items

None. All four proposed groups were accepted in full and the Phase 4 expansion (8 additional scenarios across security, concurrency, data integrity, and integration boundaries) was included in full.

## Open Assumptions (low confidence)

None. All 11 assumptions were resolved at `confidence=high` with explicit DDR or contract-document anchors:

| ID | Anchor |
|---|---|
| ASSUM-001 / 002 (per-session queue cap + eviction) | DDR-030 |
| ASSUM-003 / 004 (correlation map cap + eviction) | DDR-028 |
| ASSUM-005 (publish timeout) | DDR-025 |
| ASSUM-006 (subscriber source-id rule) | API-events §3 |
| ASSUM-007 (subscriber ack semantics + delivery policy) | DDR-027 |
| ASSUM-008 (shared concurrent-dispatch cap = 8) | DDR-020 |
| ASSUM-009 (duplicate correlation_id register) | DDR-028 §Consequences |
| ASSUM-010 (CLI line format) | DM-forge-notification §1 |
| ASSUM-011 (subscriber stop timeout) | API-internal §1 |

## Cross-Reference: Design Decisions Exercised

| DDR | Scenarios that exercise it |
|---|---|
| DDR-025 (real JetStream publish + 5s PubAck timeout) | Group A #1, Group B #5–6 |
| DDR-026 (subscriber lives in `infrastructure/forge_notifications.py`) | Implicit in all subscriber-side scenarios |
| DDR-027 (ephemeral push, `deliver_policy=NEW`, auto-ack) | Group D #6, Group C #1–2, Group D #7 |
| DDR-028 (in-memory LRU correlation map cap=1000) | Group B #3–4, Group D #11–12 |
| DDR-029 (append-only Graphiti edges) | Group A #3–4, Group D #5, Group D #10 |
| DDR-030 (between-prompts render, per-session cap=100) | Group A #5, Group B #1–2, Group D #2–3 |
| DDR-031 (originating_adapter from Session.adapter) | Group A #1, Group C #6, Group D #4 |
| DDR-020 inherited (shared dispatch cap = 8) | Group C #4, Group D #14 |
| DDR-021 inherited (NATS-down soft-fail) | Group C #3 |
| DDR-019 inherited (Graphiti fire-and-forget WARN-only) | Group A #6, Group D #5 |
| DDR-018 inherited (frozen routing-history entry) | Group A #3 |
| ADR-ARCH-021 (structured-error tools, never raise) | Group C #5 outline |

## Forge Cross-Repo Contract

The 32 scenarios consume `nats_core.events.BuildQueuedPayload` (publish) and `nats_core.events.StageCompletePayload` (subscribe) verbatim — no Jarvis-specific wire extensions. Subjects are produced by `nats_core.Topics.Pipeline.BUILD_QUEUED.format(...)` / `.STAGE_COMPLETE.format(...)`; hard-coded subject strings remain forbidden. Forge ADR-SP-014 Pattern A (Jarvis publishes; Forge consumes; no synchronous round-trip) is honoured: Jarvis returns "queued" on PubAck, never blocks on Forge consumption.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

```bash
/feature-plan "FEAT-JARVIS-005 — Build Queue Dispatch to Forge" \
  --context features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md
```

`/feature-plan`'s Step 11 (BDD-linker) will tag each scenario with `@task:TASK-J005-NNN` against the wave-organised task breakdown from `phase3-build-plan.md` §13 Suggested wave structure (Wave 1: config + DDRs; Wave 2: subscriber module + routing-history extensions; Wave 3: queue_build swap + integration tests; Wave 4: SessionManager queue + CLI rendering; Wave 5: lifecycle wiring + soft-fail tests; Wave 6: contract tests + grep-invariant retire; Wave 7: end-to-end Forge round-trip).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Build Queue Dispatch to Forge (FEAT-JARVIS-005)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:

features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge.feature
features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_assumptions.yaml
features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md
Scenarios: 32 total (1 Outline → 34 effective example rows)

@key-example: 6 · @boundary: 6 · @negative: 9 · @edge-case: 14
@smoke: 4 · @security: 3 · @concurrency: 2 · @integration: 2 · @regression: 0
Assumptions: 11 total — all confidence=high, anchored in DDR-025/027/028/029/030/031, DDR-019/020/021 inherited, plus API-events §3, API-internal §1/§7, and DM-forge-notification §1.

Review required: No — no low-confidence assumptions.

Deferred: None — all four groups accepted in full; Phase 4 expansion (8 scenarios) included in full.

Next steps:

Review: features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge.feature
Pass to feature-plan:

/feature-plan "FEAT-JARVIS-005 — Build Queue Dispatch to Forge" \
  --context features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md


