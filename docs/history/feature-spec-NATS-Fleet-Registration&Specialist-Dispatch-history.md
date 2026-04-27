/feature-spec "NATS Fleet Registration & Specialist Dispatch: Jarvis registers on fleet.register, discovers specialists via NATSKVManifestRegistry, dispatches via agents.command.{agent_id}/agents.result.{agent_id} with timeout + retry-with-redirect; first live jarvis_routing_history trace-rich writes per ADR-FLEET-001" \
  --from docs/design/FEAT-JARVIS-004/ \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context .claude/reviews/FEAT-JARVIS-003-review-report.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-017-live-fleet-watching.md \
  --context ../nats-core/src/nats_core/manifest.py \
  --context ../nats-core/src/nats_core/events/_agent.py \
  --context ../nats-core/src/nats_core/topics.py \
  --context src/jarvis/tools/dispatch.py \
  --context src/jarvis/tools/capabilities.py \
  --context src/jarvis/infrastructure/lifecycle.py \
  --context src/jarvis/config/settings.py \
  --context .guardkit/context-manifest.yaml

I'll execute the six-phase Propose-Review methodology. Starting with Phase 1: silent context gathering.

Bash Inspect feature design dir, existing features, stack signals
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/ 2>&1; echo "---"; ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/ 2>&1; echo "---"; ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/pyproject.toml 2>&1

OUT
total 88
drwxr-xr-x  7 richardwoollcott  staff    224 Apr 27 13:26 .
drwxr-xr-x  6 richardwoollcott  staff    192 Apr 27 13:20 ..
drwxr-xr-x  5 richardwoollcott  staff    160 Apr 27 13:25 contracts
drwxr-xr-x  9 richardwoollcott  staff    288 Apr 27 13:30 decisions
-rw-r--r--  1 richardwoollcott  staff  43340 Apr 27 13:20 design.md
drwxr-xr-x  3 richardwoollcott  staff     96 Apr 27 13:23 diagrams
drwxr-xr-x  3 richardwoollcott  staff     96 Apr 27 13:22 models
---
__pycache__
conftest.py
feat-jarvis-002-core-tools-and-dispatch
feat-jarvis-003-async-subagent-and-frontier-escape
project-scaffolding-supervisor-sessions
---
/Users/richardwoollcott/Projects/appmilla_github/jarvis/pyproject.toml
Bash List FEAT-JARVIS-004 sub-directory contents
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/contracts/ /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/decisions/ /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/models/ /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/diagrams/ 2>&1

OUT
/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/contracts/:
total 64
drwxr-xr-x  5 richardwoollcott  staff    160 Apr 27 13:25 .
drwxr-xr-x  7 richardwoollcott  staff    224 Apr 27 13:26 ..
-rw-r--r--  1 richardwoollcott  staff   7018 Apr 27 13:25 API-events.md
-rw-r--r--  1 richardwoollcott  staff  13204 Apr 27 13:24 API-internal.md
-rw-r--r--  1 richardwoollcott  staff   7056 Apr 27 13:25 API-tools.md

/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/decisions/:
total 112
drwxr-xr-x  9 richardwoollcott  staff   288 Apr 27 13:30 .
drwxr-xr-x  7 richardwoollcott  staff   224 Apr 27 13:26 ..
-rw-r--r--  1 richardwoollcott  staff  4585 Apr 27 13:26 DDR-016-dispatch-timeout-default-60s.md
-rw-r--r--  1 richardwoollcott  staff  5786 Apr 27 13:26 DDR-017-retry-with-redirect-policy.md
-rw-r--r--  1 richardwoollcott  staff  7245 Apr 27 13:27 DDR-018-routing-history-schema-authoritative.md
-rw-r--r--  1 richardwoollcott  staff  5827 Apr 27 13:28 DDR-019-graphiti-fire-and-forget-writes.md
-rw-r--r--  1 richardwoollcott  staff  5943 Apr 27 13:28 DDR-020-concurrent-dispatch-cap-8.md
-rw-r--r--  1 richardwoollcott  staff  6632 Apr 27 13:29 DDR-021-nats-unavailable-soft-fail.md
-rw-r--r--  1 richardwoollcott  staff  5812 Apr 27 13:30 DDR-022-defer-llamaswap-live-reads-to-v15.md

/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/diagrams/:
total 24
drwxr-xr-x  3 richardwoollcott  staff    96 Apr 27 13:23 .
drwxr-xr-x  7 richardwoollcott  staff   224 Apr 27 13:26 ..
-rw-r--r--  1 richardwoollcott  staff  9137 Apr 27 13:23 fleet-dispatch-l3.md

/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-004/models/:
total 40
drwxr-xr-x  3 richardwoollcott  staff     96 Apr 27 13:22 .
drwxr-xr-x  7 richardwoollcott  staff    224 Apr 27 13:26 ..
-rw-r--r--  1 richardwoollcott  staff  16634 Apr 27 13:22 DM-routing-history.md
Read design.md
Read API-tools.md
Read API-events.md
Read API-internal.md
Read DM-routing-history.md
Read DDR-016-dispatch-timeout-default-60s.md
Read DDR-017-retry-with-redirect-policy.md
Update Todos

Phase 1: Gather context (read all DDRs, ADRs, code)

Phase 2: Generate grouped scenario proposal

Phase 3: Wait for human curation A/R/M/+/?

Phase 4: Offer edge case expansion

Phase 5: Resolve assumptions

Phase 6: Write feature/assumptions/summary files
Read DDR-018-routing-history-schema-authoritative.md
Read DDR-019-graphiti-fire-and-forget-writes.md
Read DDR-020-concurrent-dispatch-cap-8.md
Read DDR-021-nats-unavailable-soft-fail.md
Read DDR-022-defer-llamaswap-live-reads-to-v15.md
Read phase3-fleet-integration-scope.md
Read dispatch.py
Read capabilities.py
Read settings.py
Bash List infra dir and check nats-core structure
IN
ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/src/jarvis/infrastructure/ 2>&1; echo ---; head -50 /Users/richardwoollcott/Projects/appmilla_github/jarvis/src/jarvis/infrastructure/lifecycle.py 2>&1; echo ---; ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/ 2>&1

OUT
__init__.py
__pycache__
lifecycle.py
logging.py
---
"""Application lifecycle management — startup and shutdown.

Provides :func:`build_app_state` and :func:`shutdown` for bootstrapping and
tearing down the Jarvis runtime, plus the frozen :class:`AppState`
dataclass that holds all runtime dependencies.

``build_app_state()`` configures structured logging **before** any validation
so that configuration errors are emitted as structured events.  It returns a
fully populated ``AppState`` — supervisor, session manager, capability
registry and (since FEAT-JARVIS-003) the ``LlamaSwapAdapter`` are always
wired.

TASK-J002-017 extended ``build_app_state`` with two additional steps that
sit between store creation and supervisor build:

1. ``capability_registry = load_stub_registry(config.stub_capabilities_path)``
   — startup-fatal if the YAML is missing (FEAT-JARVIS-002 design §7).
2. ``tool_list = assemble_tool_list(config, capability_registry)`` — wires
   the 9 Phase 2 tools and snapshots the registry into the capability +
   dispatch tool modules (ASSUM-006 snapshot isolation).

TASK-J003-015 (FEAT-JARVIS-003 design §8 "← NEW") layers four further
additions on top:

3. ``LlamaSwapAdapter`` is constructed from
   ``config.llama_swap_base_url`` and stored on :class:`AppState` so the
   supervisor's swap-aware voice-latency policy (ADR-ARCH-012) can probe
   the GB10 builders-group state at request time.
4. ``OPENAI_BASE_URL`` is exported into ``os.environ`` as
   ``<config.llama_swap_base_url>/v1`` *before* the
   ``jarvis-reasoner`` AsyncSubAgent's leaf graph compiles — that
   compilation runs through ``init_chat_model`` which reads the env
   var to route OpenAI-shaped requests at the local llama-swap proxy.
5. ``async_subagents = build_async_subagents(config)`` is built and
   threaded into ``build_supervisor`` so DeepAgents'
   ``AsyncSubAgentMiddleware`` injects its five operational tools
   (``start_async_task`` / ``check_async_task`` / ``update_async_task``
   / ``cancel_async_task`` / ``list_async_tasks``).
6. ``assemble_tool_list`` is called twice — once with
   ``include_frontier=True`` (the *attended* 10-tool surface) and once
   with ``include_frontier=False`` (the *ambient* 9-tool surface that
   excludes ``escalate_to_frontier`` per DDR-014's registration-layer
   gate).  The ambient list is exposed via
   ``ambient_tool_factory=lambda: tool_list_ambient`` so ambient /
   learning consumers can pull the canonical list without re-running
   the lifecycle wiring.

All seams are imported at module top so tests can patch them via the
canonical ``jarvis.infrastructure.lifecycle`` namespace.

---
__init__.py
__pycache__
_routing.py
agent_config.py
client.py
config.py
envelope.py
events
manifest.py
py.typed
topics.py
Read manifest.py
I have enough context to generate the proposal. Stack is python (pyproject.toml + setup), 4 existing .feature directories under features/, and the design pins almost every behavioural detail in DDR-016..022 plus the contracts + DM-routing-history. Moving to Phase 2.

Update Todos

Phase 1: Gather context (read all DDRs, ADRs, code)

Phase 2: Generate grouped scenario proposal

Phase 3: Wait for human curation A/R/M/+/?

Phase 4: Offer edge case expansion

Phase 5: Resolve assumptions

Phase 6: Write feature/assumptions/summary files
Context loaded: stack=python, 7 modules under src/jarvis/ scanned, 3 existing .feature directories, 7 DDRs (016–022), 1 ADR-FLEET-001, 3 forge ADRs (ARCH-015/016/017), full design + 3 contract docs + DM-routing-history.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: NATS Fleet Registration & Specialist Dispatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@feat-jarvis-004 @fleet-dispatch
Feature: NATS Fleet Registration and Specialist Dispatch
  As Jarvis
  I want to register myself on the fleet, discover specialists from the
  live catalogue, and round-trip work to them over NATS
  So that Rich can ask Jarvis to delegate to the architect, product owner,
  or any other specialist agent — with timeout, retry-with-redirect,
  trace-rich learning records, and visible degradation when the
  transport or learning substrate is unavailable

  Background:
    Given Jarvis is starting up with a configured NATS endpoint
    And the configured Graphiti endpoint
    And the configured stub capability catalogue as a fallback
━━ GROUP A: Key Examples (6 scenarios) ━━


  # Why: Symmetric fleet contract — the architectural "should" becomes runtime "does"
  @key-example @smoke
  Scenario: Jarvis publishes its own manifest on fleet.register at startup
    Given the NATS transport is available
    When Jarvis completes startup
    Then Jarvis's manifest should be discoverable on the fleet registry
    And the manifest should identify Jarvis as a core fleet member
    And the manifest should advertise Jarvis's general-purpose-agent role
    And the manifest should advertise Jarvis's intent capabilities for
      conversational dispatch, capability dispatch, meta-dispatch, and memory recall

  # Why: Jarvis's continued liveness must be visible to peers
  @key-example
  Scenario: Jarvis republishes its manifest periodically as a heartbeat
    Given Jarvis has registered on the fleet
    When the configured heartbeat interval elapses
    Then Jarvis's manifest should be republished to the fleet
    And the manifest's trust tier and version should remain stable across republications

  # Why: Live discovery — Phase 2's stub becomes the live catalogue
  @key-example @smoke
  Scenario: Jarvis discovers registered specialists from the live fleet catalogue
    Given two specialist agents have registered their manifests on the fleet
    When the supervisor lists available capabilities
    Then both specialists should appear in the catalogue
    And each entry should expose the specialist's role, capabilities, and trust tier

  # Why: Phase 3 close criterion #4 — the real round-trip
  @key-example @smoke
  Scenario: dispatch_by_capability round-trips successfully with a registered specialist
    Given a specialist is registered on the fleet that exposes a capability
    And the specialist is ready to reply to commands
    When the supervisor dispatches that capability with a valid payload
    Then the specialist should receive the command
    And the supervisor should receive the specialist's successful reply
    And the result should be returned to the reasoning model

  # Why: Live KV watch — fleet membership changes propagate without restart
  @key-example
  Scenario: A new specialist registering mid-session becomes visible to the supervisor
    Given Jarvis has been running for some time
    And the supervisor has previously listed the fleet catalogue
    When a new specialist registers its manifest on the fleet
    Then the supervisor should see the new specialist on its next catalogue listing
    And the new specialist should be eligible for dispatch immediately

  # Why: First live ADR-FLEET-001 writes — the learning substrate lights up
  @key-example @smoke
  Scenario: A successful dispatch writes a trace-rich record to the routing history
    Given the routing history substrate is available
    When the supervisor dispatches a capability and the specialist replies successfully
    Then a routing history record should be written for that decision
    And the record should identify the chosen specialist
    And the record should record the outcome as a first-attempt success
    And the record should include the supervisor's reasoning context, resource cost, and environmental context
    And the record should be associated with the originating session
━━ GROUP B: Boundary Conditions (6 scenarios) ━━


  # Why: Just-inside boundary — minimum and maximum dispatch timeout values
  @boundary
  Scenario Outline: Dispatch accepts timeouts within the supported range
    Given a specialist is registered for the requested capability
    When the supervisor dispatches with timeout of <timeout_seconds> seconds
    Then the dispatch should be accepted as a valid request
    Examples:
      | timeout_seconds |
      | 5               |
      | 60              |
      | 600             |

  # Why: Just-outside boundary — values below 5 or above 600 are rejected at the tool boundary
  @boundary @negative
  Scenario Outline: Dispatch rejects timeouts outside the supported range
    Given a specialist is registered for the requested capability
    When the supervisor dispatches with timeout of <timeout_seconds> seconds
    Then the dispatch should be rejected as having an invalid timeout
    And no command should be sent to the specialist
    Examples:
      | timeout_seconds |
      | 0               |
      | 4               |
      | 601             |
      | 3600            |

  # Why: Just-inside boundary — concurrent dispatches up to the cap succeed
  # [ASSUMPTION: confidence=high] Concurrent dispatch cap default is 8 per DDR-020
  @boundary
  Scenario: Concurrent dispatches at the cap all proceed
    Given specialists are registered and ready to reply slowly
    When the supervisor launches 8 concurrent dispatches
    Then all 8 dispatches should be accepted into flight
    And each should eventually receive its specialist's reply

  # Why: Just-outside boundary — 9th in-flight dispatch is rejected immediately as overloaded
  @boundary @negative
  Scenario: A dispatch above the concurrent cap is rejected as overloaded
    Given 8 dispatches are already in flight
    When the supervisor attempts a 9th concurrent dispatch
    Then the supervisor should be told the dispatch system is overloaded and to retry later
    And the rejection should arrive without waiting for any in-flight dispatch to complete

  # Why: Trace records small enough to inline stay inline; nothing is offloaded unnecessarily
  # [ASSUMPTION: confidence=high] 16KB filesystem-offload threshold per DDR-018
  @boundary
  Scenario: A trace record below the offload threshold is stored inline
    Given a dispatch produces a tool-call sequence well under the offload threshold
    When the routing history record is written
    Then the tool-call sequence should be stored inline in the record
    And no trace file should be written to the local filesystem

  # Why: Trace records above the offload threshold offload to the local trace directory
  @boundary
  Scenario: A trace record above the offload threshold is offloaded to the filesystem
    Given a dispatch produces a tool-call sequence above the offload threshold
    When the routing history record is written
    Then the tool-call sequence should be offloaded to a per-decision trace file
      under the local Jarvis traces directory
    And the record should reference that file by path and content hash
    And the file's content hash should match the offloaded payload
━━ GROUP C: Negative Cases (7 scenarios) ━━


  # Why: Tool-boundary input contract preserved from Phase 2
  @negative
  Scenario: Dispatch rejects a payload that is not a JSON object
    Given a specialist is registered for the requested capability
    When the supervisor dispatches with a payload that is not a JSON object literal
    Then the dispatch should be rejected as having an invalid payload
    And no command should be sent to any specialist

  # Why: Resolution failure — no descriptor matches tool_name nor intent_pattern
  @negative
  Scenario: Dispatch returns an unresolved error when no capability matches
    Given the catalogue contains no specialist exposing the requested capability
    And no specialist matches the optional intent pattern
    When the supervisor dispatches that capability
    Then the dispatch should be reported as unresolved
    And a routing history record should be written with an unresolved outcome

  # Why: Specialist explicitly errors and no other candidate exists → specialist_error / exhausted
  @negative
  Scenario: A single specialist replying with an error and no alternative exhausts the dispatch
    Given exactly one specialist is registered for the requested capability
    And that specialist replies with an explicit error
    When the supervisor dispatches that capability
    Then the dispatch should be reported as exhausted
    And the routing history record should capture the specialist's error reason

  # Why: Timeout with no alternative — exhausted after the bounded retry budget
  @negative
  Scenario: A timeout with no alternative specialist exhausts the dispatch
    Given exactly one specialist is registered for the requested capability
    And that specialist does not reply within the configured timeout
    When the supervisor dispatches that capability
    Then the dispatch should be reported as a timeout that exhausted the retry budget
    And the routing history record should list the failed attempt

  # Why: NATS soft-fail at startup — chat survives, dispatch surfaces a visible degraded state
  @negative
  Scenario: Jarvis still starts when NATS is unreachable and dispatch surfaces a degraded transport
    Given the configured NATS endpoint is unreachable
    When Jarvis completes startup
    Then Jarvis should still be available for chat
    And the supervisor should not register on the fleet
    And every dispatch attempt should be reported as transport-unavailable
    And the catalogue should fall back to the stub capability list so the
      reasoning model still sees a non-empty catalogue
    And the frontier escape route should remain available on attended sessions

  # Why: capabilities_refresh on the soft-fail path returns a degraded transport string
  @negative
  Scenario: Refreshing the catalogue while NATS is unavailable reports a degraded transport
    Given Jarvis has started in NATS-unavailable mode
    When the supervisor requests a catalogue refresh
    Then the refresh should be reported as transport-unavailable
    And the catalogue should continue to serve the stub capability list

  # Why: Hard-coded plural subjects must never be emitted — singular topic convention is law
  @negative
  Scenario: The supervisor never emits a non-canonical subject name
    Given a specialist is registered for the requested capability
    When the supervisor dispatches that capability
    Then every NATS subject the supervisor publishes to should come from the
      canonical singular-topic formatters
    And no plural-form subject should ever appear on the wire
━━ GROUP D: Edge Cases (10 scenarios) ━━


  # Why: The retry-with-redirect resilience case (DDR-017)
  @edge-case @smoke
  Scenario: A timeout falls back to a second specialist that succeeds
    Given two specialists are registered for the requested capability
    And the first specialist (in lexicographic order) does not reply within the timeout
    And the second specialist replies successfully
    When the supervisor dispatches that capability
    Then the supervisor should receive the second specialist's reply
    And the routing history record should record the outcome as a successful redirect
    And the record should list one prior attempt against the first specialist
    And the chosen specialist should be the second one

  # Why: Visited-set loop guard — even if both candidates time out, no third attempt is made
  @edge-case
  Scenario: Two timeouts in a row exhaust the dispatch and never revisit the same specialist
    Given two specialists are registered for the requested capability
    And neither specialist replies within the timeout
    When the supervisor dispatches that capability
    Then the dispatch should be reported as exhausted after exactly two attempts
    And the routing history record should list both attempts in order
    And no specialist should appear more than once in the attempts list

  # Why: Specialist error also triggers retry-with-redirect
  @edge-case
  Scenario: A specialist error falls back to a second specialist that succeeds
    Given two specialists are registered for the requested capability
    And the first specialist replies with an explicit error
    And the second specialist replies successfully
    When the supervisor dispatches that capability
    Then the supervisor should receive the second specialist's reply
    And the routing history record should capture the first specialist's error reason
    And the record's outcome should be a successful redirect

  # Why: Retry-with-redirect must NOT trigger on transport failure mid-flight
  @edge-case
  Scenario: A NATS connection failure mid-dispatch surfaces transport-unavailable without a redirect
    Given two specialists are registered for the requested capability
    And the NATS transport fails after the first command is sent
    When the supervisor dispatches that capability
    Then the dispatch should be reported as transport-unavailable
    And the supervisor should not attempt to redirect to the second specialist
    And the routing history record should record the transport-unavailable outcome

  # Why: Graphiti soft-fail — dispatch keeps working when the learning substrate is down
  @edge-case
  Scenario: Dispatches still succeed when the routing history substrate is unreachable
    Given the configured Graphiti endpoint is unreachable at startup
    When the supervisor dispatches a capability and the specialist replies successfully
    Then the dispatch should still succeed for the reasoning model
    And the routing history write should be observed to fail as a warning, not as an error
    And no routing history record should reach the substrate for that dispatch

  # Why: Trace writes are fire-and-forget — the supervisor must not pay Graphiti latency
  @edge-case
  Scenario: A successful dispatch returns to the supervisor before its trace write completes
    Given the routing history substrate is slow to accept new records
    When the supervisor dispatches a capability and the specialist replies successfully
    Then the dispatch result should be returned to the reasoning model promptly
    And the routing history record should be written asynchronously after the dispatch returns

  # Why: Combined NATS-down + Graphiti-down — only the local-only surface remains
  @edge-case
  Scenario: Both transport and learning substrate unavailable — Jarvis still starts
    Given the configured NATS endpoint is unreachable
    And the configured Graphiti endpoint is unreachable
    When Jarvis completes startup
    Then Jarvis should still be available for chat
    And every fleet dispatch should be reported as transport-unavailable
    And no routing history record should reach the substrate
    And local subagent dispatch and frontier escape should still work on attended sessions

  # Why: Late replies after timeout are discarded; reasoning never sees stale results
  @edge-case
  Scenario: A specialist replying after the timeout is discarded
    Given a specialist is registered for the requested capability
    And that specialist replies after the configured timeout has elapsed
    When the supervisor dispatches that capability
    Then the supervisor should not surface the late reply to the reasoning model
    And the dispatch outcome should be a timeout, not a success

  # Why: Clean shutdown drains in-flight work and deregisters from the fleet
  @edge-case
  Scenario: Shutdown drains in-flight dispatches and deregisters from the fleet
    Given Jarvis has been running with at least one in-flight dispatch
    When Jarvis is asked to shut down
    Then the in-flight dispatch should be allowed to complete or be drained within the bounded shutdown window
    And Jarvis should deregister itself from the fleet
    And any in-flight routing history writes should be drained within the bounded flush window

  # Why: Privacy posture — sensitive content never reaches the persisted trace
  @edge-case @regression
  Scenario: Sensitive content in a trace record is redacted before persistence
    Given a dispatch's reasoning context contains a sensitive value such as a credential or API key
    When the routing history record is persisted
    Then the sensitive value should not appear in the persisted record
    And the redacted value should be replaced with a redaction marker

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 29 scenarios across 4 groups (with 3 boundary outlines covering 7 example rows)
Inferred assumptions: 9 (will be resolved in Phase 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each group you may:

[A] Accept — include all scenarios in this group as-is
[R] Reject — exclude all scenarios in this group
[M] Modify — accept but specify changes (provide inline)
[+] Add — accept and add additional scenarios you describe
[?] Defer — mark group for future specification; excluded from output
Fast path: type A A A A to accept all four groups at once.


GROUP A — Key Examples (6 scenarios): _
GROUP B — Boundary Conditions (6 scenarios): _
GROUP C — Negative Cases (7 scenarios): _
GROUP D — Edge Cases (10 scenarios): _
Reply with your decision per group (e.g. A A M A plus modifications), and I'll move to Phase 4 (edge case expansion offer) and Phase 5 (assumption resolution) afterwards.

feature-spec-NATS-Fleet-Registration&Specialist-Dispatch-history.md
A A A A
All four groups accepted. Moving to Phase 4.

Update Todos

Phase 1: Gather context (read all DDRs, ADRs, code)

Phase 2: Generate grouped scenario proposal

Phase 3: Wait for human curation A/R/M/+/?

Phase 4: Offer edge case expansion

Phase 5: Resolve assumptions

Phase 6: Write feature/assumptions/summary files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've identified 7 additional scenarios covering security, concurrency,
contract integrity, and integration boundaries. They sit beyond the core
behaviour and are optional.

Security (2)

Specialist's reply contains a malformed payload that violates the wire contract — surfaced as a specialist error, no redirect ping-pong
Manifest republished by a specialist with the same agent_id mid-dispatch must not corrupt an in-flight resolution (snapshot isolation)
Concurrency (2)

A specialist deregistering mid-dispatch — the in-flight call still completes against the resolved agent_id; the catalogue updates for the next call
The dispatch semaphore releases on every exit path (success / timeout / specialist error / transport failure / unresolved) so it never leaks slots
Contract / data integrity (2)

Every emitted command envelope carries source_id="jarvis" (audit-trail invariant)
A trace record exceeding the offload threshold is unique on disk per decision — overwriting an existing decision file is treated as a write failure
Integration boundaries (1)

A deferred specialist (registered but status="degraded") is still visible in the catalogue and remains eligible for dispatch attempts in v1; the trace record carries the specialist's reported status at decision time

[Y] Yes     — show and curate them with the same A/R/M/+/? actions
[S] Sample  — show 2 examples in full Gherkin then decide
[N] No      — skip and proceed to Phase 5 (assumption resolution)

Your choice [Y/S/N]: _
Y
Here are all 7 expansion scenarios in full Gherkin.

━━ EDGE-CASE EXPANSION GROUP (7 scenarios) ━━


  # Why: Contract violation on the reply path is treated as a specialist error
  # and does NOT trigger redirect (the next specialist would likely violate the
  # same contract — DDR-017 explicit exclusion)
  @edge-case @negative
  Scenario: A malformed specialist reply is treated as a specialist error without redirect
    Given two specialists are registered for the requested capability
    And the first specialist replies with content that does not match the wire contract
    When the supervisor dispatches that capability
    Then the dispatch should be reported as a specialist error
    And the supervisor should not attempt to redirect to the second specialist
    And the routing history record should record the contract-violation reason

  # Why: Snapshot isolation (ASSUM-006) — concurrent registry rebinding
  # must not corrupt an in-flight resolution
  @edge-case
  Scenario: A specialist republishing its manifest mid-dispatch does not change the in-flight resolution
    Given a specialist is registered for the requested capability
    And the supervisor has begun resolving a dispatch against that specialist
    When the same specialist republishes a modified manifest before the reply arrives
    Then the in-flight dispatch should still target the originally resolved specialist
    And subsequent catalogue listings should reflect the new manifest

  # Why: Catalogue invalidation on deregistration must not break an in-flight call
  @edge-case
  Scenario: A specialist deregistering mid-dispatch lets the in-flight call finish against its original target
    Given a specialist is registered for the requested capability
    And a dispatch against that specialist is in flight
    When the specialist deregisters from the fleet before its reply arrives
    Then the in-flight dispatch should still complete against the original target
    And the deregistered specialist should disappear from the next catalogue listing

  # Why: Semaphore must release on every exit path or the cap leaks
  @edge-case @regression
  Scenario Outline: The concurrent dispatch slot is released on every dispatch outcome
    Given the dispatch system is fully saturated with one slot held by an in-flight dispatch
    When that in-flight dispatch finishes with outcome <outcome>
    Then a slot should be returned to the dispatch system
    And a subsequent dispatch should be accepted into flight
    Examples:
      | outcome                |
      | success                |
      | timeout                |
      | specialist error       |
      | transport unavailable  |
      | unresolved             |

  # Why: Audit-trail invariant — every command envelope identifies its source
  @edge-case @regression
  Scenario: Every command envelope the supervisor emits identifies Jarvis as the source
    Given a specialist is registered for the requested capability
    When the supervisor dispatches that capability
    Then the emitted command envelope should identify Jarvis as the source agent

  # Why: Filesystem offload uniqueness — overwriting a decision file is a bug
  @edge-case @negative
  Scenario: Writing a trace file that already exists for the same decision is treated as a write failure
    Given the routing history substrate is available
    And a trace file already exists at the path for a given decision id
    When the routing history writer attempts to offload another large trace at that same path
    Then the second write should be reported as a routing history write failure
    And the original trace file should remain unchanged

  # Why: Degraded specialists stay dispatch-eligible in v1; the trace records their status
  @edge-case
  Scenario: A specialist reporting degraded status is still eligible for dispatch and the trace records the status
    Given a specialist is registered for the requested capability with degraded status
    When the supervisor dispatches that capability and the specialist replies successfully
    Then the supervisor should receive the specialist's reply
    And the routing history record should capture the specialist's reported status at decision time
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE-CASE GROUP CURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Same A/R/M/+/? actions as before. You can also accept/reject scenarios individually by listing numbers (e.g. accept 1,3,5; reject 2,4,6,7).


1. Malformed reply → specialist_error, no redirect
2. Manifest republish during in-flight resolution
3. Deregistration during in-flight dispatch
4. Slot release on every outcome (5-row outline)
5. Envelope source_id == jarvis (audit invariant)
6. Trace file already exists at path → write failure
7. Degraded-status specialist still dispatchable; status captured

Your decision: _
accept all
All 7 expansion scenarios accepted. 36 scenarios total (29 + 7). Moving to Phase 5.

Update Todos

Phase 1: Gather context (read all DDRs, ADRs, code)

Phase 2: Generate grouped scenario proposal

Phase 3: Wait for human curation A/R/M/+/?

Phase 4: Offer edge case expansion

Phase 5: Resolve assumptions

Phase 6: Write feature/assumptions/summary files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (12 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each assumption has a proposed default, confidence, and basis. Press
Enter to accept all, or list overrides as [N] = value. Most are
already pinned by your DDRs and contracts — surfaced for transparency.


[1] Heartbeat interval default
    Proposed:   30 seconds
    Confidence: high
    Basis:      API-internal §8: heartbeat_interval_seconds = Field(default=30, ge=5, le=300)
    Accept or override: _

[2] Default dispatch timeout
    Proposed:   60 seconds (range 5..600)
    Confidence: high
    Basis:      DDR-016 — pinned default; range preserved from Phase 2
    Accept or override: _

[3] Concurrent dispatch cap
    Proposed:   8 in-flight dispatches per supervisor process
    Confidence: high
    Basis:      DDR-020 — asyncio.Semaphore(8); operator-tunable 1..64
    Accept or override: _

[4] Max redirect count
    Proposed:   1 redirect (2 total attempts per dispatch)
    Confidence: high
    Basis:      DDR-017 — caps wall-clock at 2 × timeout; visited-set guard
    Accept or override: _

[5] Trace inline/offload threshold
    Proposed:   16 KB JSON-encoded (per-decision filesystem offload)
    Confidence: high
    Basis:      DDR-018 — aligns with Graphiti entity-size guidance; ADR-FLEET-001 §"Large traces"
    Accept or override: _

[6] NATS drain timeout on shutdown
    Proposed:   5 seconds
    Confidence: high
    Basis:      API-internal §1 — NATSClient.drain(timeout=5.0); idempotent
    Accept or override: _

[7] Routing history flush timeout on shutdown
    Proposed:   5 seconds
    Confidence: high
    Basis:      DDR-019 — bounded drain then WARN routing_history_flush_timeout
    Accept or override: _

[8] Degraded specialist dispatch eligibility
    Proposed:   Specialists with status="degraded" remain dispatch-eligible in v1; the trace records their reported status at decision time
    Confidence: medium
    Basis:      Manifest enum permits "degraded" but no DDR forbids dispatching to one. v1 lets the supervisor + redirect policy handle it; learning module (FEAT-J008) can suppress later
    Accept or override: _

[9] Existing-trace-file overwrite semantics
    Proposed:   Treated as a routing history write failure (logged WARN; original file preserved)
    Confidence: low
    Basis:      DDR-018 endorses 1:1 decision-id→file mapping; collision implies a UUID re-use which is itself an error condition. Not explicitly stated in design — operator-decidable
    Accept or override: _

[10] Redaction set at the write boundary
    Proposed:   API keys, JWTs, NATS credentials, email addresses
    Confidence: high
    Basis:      ADR-ARCH-029 + design §11 redaction-posture compatibility note
    Accept or override: _

[11] Resolution determinism
    Proposed:   Lexicographic agent_id ordering for both first-attempt and redirect candidates
    Confidence: high
    Basis:      DDR-017 — testable, reproducible, trace-replayable
    Accept or override: _

[12] Late-reply handling after timeout
    Proposed:   Discarded at the NATS request/reply layer (per-call inbox is gone)
    Confidence: high
    Basis:      API-events §3 — supersedes the Phase 2 docstring's speculative "late replies may appear"
    Accept or override: _
Gating note: [9] is the single low-confidence item. If you accept it as-is, the output will carry a REVIEW REQUIRED flag against ASSUM-009 only.

Reply with accept all, or list overrides like 9 = no-op (overwrite ok); 8 = exclude degraded specialists from resolution.

accept all
All 12 assumptions accepted. Writing Phase 6 outputs.

Update Todos

Phase 1: Gather context (read all DDRs, ADRs, code)

Phase 2: Generate grouped scenario proposal

Phase 3: Wait for human curation A/R/M/+/?

Phase 4: Offer edge case expansion

Phase 5: Resolve assumptions

Phase 6: Write feature/assumptions/summary files
Bash Create output directory
IN
mkdir -p /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-004-fleet-registration-and-specialist-dispatch && ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-004-fleet-registration-and-specialist-dispatch

OUT
(Bash completed with no output)
Write feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature
394 lines
# Generated by /feature-spec
# Feature: NATS Fleet Registration and Specialist Dispatch (FEAT-JARVIS-004)
# Stack: python
# Assumptions: 12 (see feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml)
# Generated: 2026-04-27T12:00:00Z

@feat-jarvis-004 @fleet-dispatch
Feature: NATS Fleet Registration and Specialist Dispatch
  As Jarvis
  I want to register myself on the fleet, discover specialists from the
  live catalogue, and round-trip work to them over NATS
  So that Rich can ask Jarvis to delegate to the architect, product owner,
  or any other specialist agent — with timeout, retry-with-redirect,
  trace-rich learning records, and visible degradation when the
  transport or learning substrate is unavailable

  Background:
    Given Jarvis is starting up with a configured NATS endpoint
    And the configured Graphiti endpoint
    And the configured stub capability catalogue as a fallback

  # ─── GROUP A: Key Examples ──────────────────────────────────────────────

  # Why: Symmetric fleet contract — the architectural "should" becomes runtime "does"
  @key-example @smoke
  Scenario: Jarvis publishes its own manifest on fleet.register at startup
    Given the NATS transport is available
    When Jarvis completes startup
    Then Jarvis's manifest should be discoverable on the fleet registry
    And the manifest should identify Jarvis as a core fleet member
    And the manifest should advertise Jarvis's general-purpose-agent role
    And the manifest should advertise Jarvis's intent capabilities for
      conversational dispatch, capability dispatch, meta-dispatch, and memory recall

  # Why: Jarvis's continued liveness must be visible to peers
  # [ASSUMPTION: confidence=high] Heartbeat interval default 30s per API-internal §8
  @key-example
  Scenario: Jarvis republishes its manifest periodically as a heartbeat
    Given Jarvis has registered on the fleet
    When the configured heartbeat interval elapses
    Then Jarvis's manifest should be republished to the fleet
    And the manifest's trust tier and version should remain stable across republications

  # Why: Live discovery — Phase 2's stub becomes the live catalogue
  @key-example @smoke
  Scenario: Jarvis discovers registered specialists from the live fleet catalogue
    Given two specialist agents have registered their manifests on the fleet
    When the supervisor lists available capabilities
    Then both specialists should appear in the catalogue
    And each entry should expose the specialist's role, capabilities, and trust tier

  # Why: Phase 3 close criterion #4 — the real round-trip
  @key-example @smoke
  Scenario: dispatch_by_capability round-trips successfully with a registered specialist
    Given a specialist is registered on the fleet that exposes a capability
    And the specialist is ready to reply to commands
    When the supervisor dispatches that capability with a valid payload
    Then the specialist should receive the command
    And the supervisor should receive the specialist's successful reply
    And the result should be returned to the reasoning model

  # Why: Live KV watch — fleet membership changes propagate without restart
  @key-example
  Scenario: A new specialist registering mid-session becomes visible to the supervisor
    Given Jarvis has been running for some time
    And the supervisor has previously listed the fleet catalogue
    When a new specialist registers its manifest on the fleet
    Then the supervisor should see the new specialist on its next catalogue listing
    And the new specialist should be eligible for dispatch immediately

  # Why: First live ADR-FLEET-001 writes — the learning substrate lights up
  @key-example @smoke
  Scenario: A successful dispatch writes a trace-rich record to the routing history
    Given the routing history substrate is available
    When the supervisor dispatches a capability and the specialist replies successfully
    Then a routing history record should be written for that decision
    And the record should identify the chosen specialist
    And the record should record the outcome as a first-attempt success
    And the record should include the supervisor's reasoning context, resource cost, and environmental context
    And the record should be associated with the originating session

  # ─── GROUP B: Boundary Conditions ───────────────────────────────────────

  # Why: Just-inside boundary — minimum and maximum dispatch timeout values
  # [ASSUMPTION: confidence=high] Default 60s, range 5..600 per DDR-016
  @boundary
  Scenario Outline: Dispatch accepts timeouts within the supported range
    Given a specialist is registered for the requested capability
    When the supervisor dispatches with timeout of <timeout_seconds> seconds
    Then the dispatch should be accepted as a valid request

    Examples:
      | timeout_seconds |
      | 5               |
      | 60              |
      | 600             |

  # Why: Just-outside boundary — values below 5 or above 600 are rejected at the tool boundary
  @boundary @negative
  Scenario Outline: Dispatch rejects timeouts outside the supported range
    Given a specialist is registered for the requested capability
    When the supervisor dispatches with timeout of <timeout_seconds> seconds
    Then the dispatch should be rejected as having an invalid timeout
    And no command should be sent to the specialist

    Examples:
      | timeout_seconds |
      | 0               |
      | 4               |
      | 601             |
      | 3600            |

  # Why: Just-inside boundary — concurrent dispatches up to the cap succeed
  # [ASSUMPTION: confidence=high] Concurrent dispatch cap default is 8 per DDR-020
  @boundary
  Scenario: Concurrent dispatches at the cap all proceed
    Given specialists are registered and ready to reply slowly
    When the supervisor launches 8 concurrent dispatches
    Then all 8 dispatches should be accepted into flight
    And each should eventually receive its specialist's reply

  # Why: Just-outside boundary — 9th in-flight dispatch is rejected immediately as overloaded
  @boundary @negative
  Scenario: A dispatch above the concurrent cap is rejected as overloaded
    Given 8 dispatches are already in flight
    When the supervisor attempts a 9th concurrent dispatch
    Then the supervisor should be told the dispatch system is overloaded and to retry later
    And the rejection should arrive without waiting for any in-flight dispatch to complete

  # Why: Trace records small enough to inline stay inline; nothing is offloaded unnecessarily
  # [ASSUMPTION: confidence=high] 16KB JSON-encoded filesystem-offload threshold per DDR-018
  @boundary
  Scenario: A trace record below the offload threshold is stored inline
    Given a dispatch produces a tool-call sequence well under the offload threshold
    When the routing history record is written
    Then the tool-call sequence should be stored inline in the record
    And no trace file should be written to the local filesystem

  # Why: Trace records above the offload threshold offload to the local trace directory
  @boundary
  Scenario: A trace record above the offload threshold is offloaded to the filesystem
    Given a dispatch produces a tool-call sequence above the offload threshold
    When the routing history record is written
    Then the tool-call sequence should be offloaded to a per-decision trace file
      under the local Jarvis traces directory
    And the record should reference that file by path and content hash
    And the file's content hash should match the offloaded payload

  # ─── GROUP C: Negative Cases ────────────────────────────────────────────

  # Why: Tool-boundary input contract preserved from Phase 2
  @negative
  Scenario: Dispatch rejects a payload that is not a JSON object
    Given a specialist is registered for the requested capability
    When the supervisor dispatches with a payload that is not a JSON object literal
    Then the dispatch should be rejected as having an invalid payload
    And no command should be sent to any specialist

  # Why: Resolution failure — no descriptor matches tool_name nor intent_pattern
  @negative
  Scenario: Dispatch returns an unresolved error when no capability matches
    Given the catalogue contains no specialist exposing the requested capability
    And no specialist matches the optional intent pattern
    When the supervisor dispatches that capability
    Then the dispatch should be reported as unresolved
    And a routing history record should be written with an unresolved outcome

  # Why: Specialist explicitly errors and no other candidate exists → specialist_error / exhausted
  @negative
  Scenario: A single specialist replying with an error and no alternative exhausts the dispatch
    Given exactly one specialist is registered for the requested capability
    And that specialist replies with an explicit error
    When the supervisor dispatches that capability
    Then the dispatch should be reported as exhausted
    And the routing history record should capture the specialist's error reason

  # Why: Timeout with no alternative — exhausted after the bounded retry budget
  @negative
  Scenario: A timeout with no alternative specialist exhausts the dispatch
    Given exactly one specialist is registered for the requested capability
    And that specialist does not reply within the configured timeout
    When the supervisor dispatches that capability
    Then the dispatch should be reported as a timeout that exhausted the retry budget
    And the routing history record should list the failed attempt

  # Why: NATS soft-fail at startup — chat survives, dispatch surfaces a visible degraded state
  @negative
  Scenario: Jarvis still starts when NATS is unreachable and dispatch surfaces a degraded transport
    Given the configured NATS endpoint is unreachable
    When Jarvis completes startup
    Then Jarvis should still be available for chat
    And the supervisor should not register on the fleet
    And every dispatch attempt should be reported as transport-unavailable
    And the catalogue should fall back to the stub capability list so the
      reasoning model still sees a non-empty catalogue
    And the frontier escape route should remain available on attended sessions

  # Why: capabilities_refresh on the soft-fail path returns a degraded transport string
  @negative
  Scenario: Refreshing the catalogue while NATS is unavailable reports a degraded transport
    Given Jarvis has started in NATS-unavailable mode
    When the supervisor requests a catalogue refresh
    Then the refresh should be reported as transport-unavailable
    And the catalogue should continue to serve the stub capability list

  # Why: Hard-coded plural subjects must never be emitted — singular topic convention is law
  @negative
  Scenario: The supervisor never emits a non-canonical subject name
    Given a specialist is registered for the requested capability
    When the supervisor dispatches that capability
    Then every NATS subject the supervisor publishes to should come from the
      canonical singular-topic formatters
    And no plural-form subject should ever appear on the wire

  # ─── GROUP D: Edge Cases ────────────────────────────────────────────────

  # Why: The retry-with-redirect resilience case
  # [ASSUMPTION: confidence=high] Max 1 redirect; lexicographic ordering per DDR-017
  @edge-case @smoke
  Scenario: A timeout falls back to a second specialist that succeeds
    Given two specialists are registered for the requested capability
    And the first specialist (in lexicographic order) does not reply within the timeout
    And the second specialist replies successfully
    When the supervisor dispatches that capability
    Then the supervisor should receive the second specialist's reply
    And the routing history record should record the outcome as a successful redirect
    And the record should list one prior attempt against the first specialist
    And the chosen specialist should be the second one

  # Why: Visited-set loop guard — even if both candidates time out, no third attempt is made
  @edge-case
  Scenario: Two timeouts in a row exhaust the dispatch and never revisit the same specialist
    Given two specialists are registered for the requested capability
    And neither specialist replies within the timeout
    When the supervisor dispatches that capability
    Then the dispatch should be reported as exhausted after exactly two attempts
    And the routing history record should list both attempts in order
    And no specialist should appear more than once in the attempts list

  # Why: Specialist error also triggers retry-with-redirect
  @edge-case
  Scenario: A specialist error falls back to a second specialist that succeeds
    Given two specialists are registered for the requested capability
    And the first specialist replies with an explicit error
    And the second specialist replies successfully
    When the supervisor dispatches that capability
    Then the supervisor should receive the second specialist's reply
    And the routing history record should capture the first specialist's error reason
    And the record's outcome should be a successful redirect

  # Why: Retry-with-redirect must NOT trigger on transport failure mid-flight
  @edge-case
  Scenario: A NATS connection failure mid-dispatch surfaces transport-unavailable without a redirect
    Given two specialists are registered for the requested capability
    And the NATS transport fails after the first command is sent
    When the supervisor dispatches that capability
    Then the dispatch should be reported as transport-unavailable
    And the supervisor should not attempt to redirect to the second specialist
    And the routing history record should record the transport-unavailable outcome

  # Why: Graphiti soft-fail — dispatch keeps working when the learning substrate is down
  # [ASSUMPTION: confidence=high] Failure logs WARN not ERROR per DDR-019
  @edge-case
  Scenario: Dispatches still succeed when the routing history substrate is unreachable
    Given the configured Graphiti endpoint is unreachable at startup
    When the supervisor dispatches a capability and the specialist replies successfully
    Then the dispatch should still succeed for the reasoning model
    And the routing history write should be observed to fail as a warning, not as an error
    And no routing history record should reach the substrate for that dispatch

  # Why: Trace writes are fire-and-forget — the supervisor must not pay Graphiti latency
  @edge-case
  Scenario: A successful dispatch returns to the supervisor before its trace write completes
    Given the routing history substrate is slow to accept new records
    When the supervisor dispatches a capability and the specialist replies successfully
    Then the dispatch result should be returned to the reasoning model promptly
    And the routing history record should be written asynchronously after the dispatch returns

  # Why: Combined NATS-down + Graphiti-down — only the local-only surface remains
  @edge-case
  Scenario: Both transport and learning substrate unavailable — Jarvis still starts
    Given the configured NATS endpoint is unreachable
    And the configured Graphiti endpoint is unreachable
    When Jarvis completes startup
    Then Jarvis should still be available for chat
    And every fleet dispatch should be reported as transport-unavailable
    And no routing history record should reach the substrate
    And local subagent dispatch and frontier escape should still work on attended sessions

  # Why: Late replies after timeout are discarded; reasoning never sees stale results
  @edge-case
  Scenario: A specialist replying after the timeout is discarded
    Given a specialist is registered for the requested capability
    And that specialist replies after the configured timeout has elapsed
    When the supervisor dispatches that capability
    Then the supervisor should not surface the late reply to the reasoning model
    And the dispatch outcome should be a timeout, not a success

  # Why: Clean shutdown drains in-flight work and deregisters from the fleet
  # [ASSUMPTION: confidence=high] Bounded shutdown windows: 5s NATS drain, 5s routing-history flush
  @edge-case
  Scenario: Shutdown drains in-flight dispatches and deregisters from the fleet
    Given Jarvis has been running with at least one in-flight dispatch
    When Jarvis is asked to shut down
    Then the in-flight dispatch should be allowed to complete or be drained within
      the bounded shutdown window
    And Jarvis should deregister itself from the fleet
    And any in-flight routing history writes should be drained within the bounded flush window

  # Why: Privacy posture — sensitive content never reaches the persisted trace
  # [ASSUMPTION: confidence=high] Redaction set includes API keys, JWTs, NATS credentials, email addresses
  @edge-case @regression
  Scenario: Sensitive content in a trace record is redacted before persistence
    Given a dispatch's reasoning context contains a sensitive value such as a credential or API key
    When the routing history record is persisted
    Then the sensitive value should not appear in the persisted record
    And the redacted value should be replaced with a redaction marker

  # ─── GROUP E: Edge-case Expansion (security / contract / integration) ───

  # Why: Contract violation on the reply path is treated as a specialist error
  # and does NOT trigger redirect (DDR-017 explicit exclusion)
  @edge-case @negative
  Scenario: A malformed specialist reply is treated as a specialist error without redirect
    Given two specialists are registered for the requested capability
    And the first specialist replies with content that does not match the wire contract
    When the supervisor dispatches that capability
    Then the dispatch should be reported as a specialist error
    And the supervisor should not attempt to redirect to the second specialist
    And the routing history record should record the contract-violation reason

  # Why: Snapshot isolation (ASSUM-006) — concurrent registry rebinding
  # must not corrupt an in-flight resolution
  @edge-case
  Scenario: A specialist republishing its manifest mid-dispatch does not change the in-flight resolution
    Given a specialist is registered for the requested capability
    And the supervisor has begun resolving a dispatch against that specialist
    When the same specialist republishes a modified manifest before the reply arrives
    Then the in-flight dispatch should still target the originally resolved specialist
    And subsequent catalogue listings should reflect the new manifest

  # Why: Catalogue invalidation on deregistration must not break an in-flight call
  @edge-case
  Scenario: A specialist deregistering mid-dispatch lets the in-flight call finish against its original target
    Given a specialist is registered for the requested capability
    And a dispatch against that specialist is in flight
    When the specialist deregisters from the fleet before its reply arrives
    Then the in-flight dispatch should still complete against the original target
    And the deregistered specialist should disappear from the next catalogue listing

  # Why: Semaphore must release on every exit path or the cap leaks
  @edge-case @regression
  Scenario Outline: The concurrent dispatch slot is released on every dispatch outcome
    Given the dispatch system is fully saturated with one slot held by an in-flight dispatch
    When that in-flight dispatch finishes with outcome <outcome>
    Then a slot should be returned to the dispatch system
    And a subsequent dispatch should be accepted into flight

    Examples:
      | outcome                |
      | success                |
      | timeout                |
      | specialist error       |
      | transport unavailable  |
      | unresolved             |

  # Why: Audit-trail invariant — every command envelope identifies its source
  @edge-case @regression
  Scenario: Every command envelope the supervisor emits identifies Jarvis as the source
    Given a specialist is registered for the requested capability
    When the supervisor dispatches that capability
    Then the emitted command envelope should identify Jarvis as the source agent

  # Why: Filesystem offload uniqueness — overwriting a decision file is a bug
  # [ASSUMPTION: confidence=low] Overwrite of an existing per-decision trace file
  # is treated as a write failure (logged WARN; original preserved)
  @edge-case @negative
  Scenario: Writing a trace file that already exists for the same decision is treated as a write failure
    Given the routing history substrate is available
    And a trace file already exists at the path for a given decision id
    When the routing history writer attempts to offload another large trace at that same path
    Then the second write should be reported as a routing history write failure
    And the original trace file should remain unchanged

  # Why: Degraded specialists stay dispatch-eligible in v1; the trace records their status
  # [ASSUMPTION: confidence=medium] Manifest enum allows "degraded"; v1 lets the
  # supervisor + redirect policy handle them rather than excluding at resolution
  @edge-case
  Scenario: A specialist reporting degraded status is still eligible for dispatch and the trace records the status
    Given a specialist is registered for the requested capability with degraded status
    When the supervisor dispatches that capability and the specialist replies successfully
    Then the supervisor should receive the specialist's reply
    And the routing history record should capture the specialist's reported status at decision time
Write feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml
93 lines
# Assumptions manifest for feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature
# Generated by /feature-spec

feature: "NATS Fleet Registration and Specialist Dispatch"
generated: "2026-04-27T12:00:00Z"
stack: "python"
review_required: true

assumptions:
  - id: "ASSUM-001"
    scenario: "Jarvis republishes its manifest periodically as a heartbeat"
    assumption: "Heartbeat interval default is 30 seconds (configurable 5..300)"
    confidence: high
    basis: "API-internal §8 — heartbeat_interval_seconds = Field(default=30, ge=5, le=300); DDR-021 endorses periodic republish"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Dispatch accepts timeouts within the supported range / Dispatch rejects timeouts outside the supported range"
    assumption: "dispatch_by_capability default timeout_seconds is 60; valid range is 5..600 inclusive; values outside the range are rejected at the tool boundary"
    confidence: high
    basis: "DDR-016 pins default 60s; range preserved from FEAT-JARVIS-002 invariant"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "Concurrent dispatches at the cap all proceed / A dispatch above the concurrent cap is rejected as overloaded"
    assumption: "Concurrent dispatch cap is 8 in-flight dispatch_by_capability + queue_build invocations per supervisor process; 9th call is rejected synchronously with DEGRADED: dispatch_overloaded — wait and retry"
    confidence: high
    basis: "DDR-020 pins asyncio.Semaphore(8); operator-tunable via JARVIS_DISPATCH_CONCURRENT_CAP in range 1..64"
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "A timeout falls back to a second specialist that succeeds / Two timeouts in a row exhaust the dispatch / A specialist error falls back to a second specialist"
    assumption: "Maximum 1 redirect (2 total attempts per dispatch); resolution iterates descriptors in lexicographic agent_id order with a per-dispatch visited-set guard"
    confidence: high
    basis: "DDR-017 — caps wall-clock at 2 × timeout_seconds; deterministic across runs for trace replay"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "A trace record below/above the offload threshold"
    assumption: "Filesystem-offload threshold is 16 KB JSON-encoded for supervisor_tool_call_sequence + subagent_trace_ref; offloaded files land under ~/.jarvis/traces/{date}/{decision_id}.json"
    confidence: high
    basis: "DDR-018 — aligns with Graphiti entity-size guidance; ADR-FLEET-001 §'Large traces' filesystem-offload pattern"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "Shutdown drains in-flight dispatches and deregisters from the fleet"
    assumption: "NATS drain timeout on shutdown is 5 seconds (idempotent)"
    basis: "API-internal §1 — NATSClient.drain(timeout=5.0) signature"
    confidence: high
    human_response: "confirmed"

  - id: "ASSUM-007"
    scenario: "Shutdown drains in-flight dispatches and deregisters from the fleet"
    assumption: "Routing history flush timeout on shutdown is 5 seconds; on overflow logs WARN routing_history_flush_timeout and abandons"
    confidence: high
    basis: "DDR-019 — bounded shutdown drain prevents hanging tests + CI"
    human_response: "confirmed"

  - id: "ASSUM-008"
    scenario: "A specialist reporting degraded status is still eligible for dispatch and the trace records the status"
    assumption: "Specialists with manifest status='degraded' remain dispatch-eligible in v1; redirect-with-retry handles their failures rather than excluding at resolution time. The routing history record captures the specialist's reported status at decision time"
    confidence: medium
    basis: "AgentManifest enum permits 'degraded' but no DDR forbids dispatching to one. v1 lets the supervisor + redirect policy handle it; learning module (FEAT-J008) can suppress later via append-only DDR"
    human_response: "confirmed"

  - id: "ASSUM-009"
    scenario: "Writing a trace file that already exists for the same decision is treated as a write failure"
    assumption: "If a per-decision trace file already exists at ~/.jarvis/traces/{date}/{decision_id}.json, the routing history writer treats the second offload attempt as a write failure: logs WARN routing_history_write_failed, preserves the original file, and does not overwrite"
    confidence: low
    basis: "DDR-018 endorses 1:1 decision-id→file mapping; a collision implies a UUID re-use which is itself an error condition. Not explicitly stated in the design — this scenario surfaces an operator-decidable policy"
    human_response: "confirmed (REVIEW REQUIRED — low confidence)"

  - id: "ASSUM-010"
    scenario: "Sensitive content in a trace record is redacted before persistence"
    assumption: "The redaction set applied at the routing history write boundary covers API keys, JWT tokens, NATS credentials, and email addresses; redacted values are replaced with a redaction marker before either inline or filesystem persistence"
    confidence: high
    basis: "ADR-ARCH-029 redaction posture; design §11 contradiction-detection note enumerates the categories; structlog redact-processor runs at the write boundary, not at Pydantic validation"
    human_response: "confirmed"

  - id: "ASSUM-011"
    scenario: "A timeout falls back to a second specialist that succeeds"
    assumption: "Resolution determinism — _resolve_agent_id iterates descriptors in lexicographic agent_id order for both first-attempt and redirect candidates; ties are broken by lexicographic order, never randomly"
    confidence: high
    basis: "DDR-017 — testable, reproducible, trace-record reproducible across runs; matches Forge ADR-ARCH-015 resolver convention"
    human_response: "confirmed"

  - id: "ASSUM-012"
    scenario: "A specialist replying after the timeout is discarded"
    assumption: "Late specialist replies arriving after the supervisor-side asyncio.wait_for timeout are discarded at the NATS request/reply layer (the per-call inbox is gone); the dispatch outcome is recorded as timeout, not as a delayed success"
    confidence: high
    basis: "API-events §3 — supersedes the Phase 2 docstring's speculative 'late replies may appear in NATS after timeout' line; chosen design discards late replies"
    human_response: "confirmed"
Write feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md
118 lines
# Feature Spec Summary: NATS Fleet Registration and Specialist Dispatch

**Stack**: python
**Generated**: 2026-04-27T12:00:00Z
**Scenarios**: 36 total (5 smoke, 3 regression)
**Assumptions**: 12 total (10 high / 1 medium / 1 low confidence)
**Review required**: Yes

## Scope

FEAT-JARVIS-004 turns Jarvis from a supervisor that *reasons about dispatch*
into a fleet citizen that *actually dispatches*. The specification covers
fleet self-registration on `fleet.register`, live capability discovery via
the `NATSKVManifestRegistry`, real `agents.command.{agent_id}` /
`agents.result.{agent_id}` round-trips with timeout + retry-with-redirect,
the first live `jarvis_routing_history` trace-rich writes per ADR-FLEET-001,
and the soft-fail behaviour that keeps Jarvis as a useful chat surface when
NATS or Graphiti is unavailable. The reasoning model's tool surface is
unchanged from Phase 2 — only the transport behind the seam swaps.

## Scenario Counts by Category

| Category                                 | Count |
|------------------------------------------|-------|
| Key examples (@key-example)              | 6     |
| Boundary conditions (@boundary)          | 6     |
| Negative cases (@negative)               | 7     |
| Edge cases (@edge-case)                  | 17    |
| Smoke (@smoke)                           | 5     |
| Regression (@regression)                 | 3     |

(Tag totals overlap — every smoke and regression scenario is also tagged
under one of the four primary categories.)

## Outline-driven scenarios

Three `Scenario Outline` entries cover multiple example rows:

- **Dispatch accepts timeouts within the supported range** — 3 rows
  (5 / 60 / 600 seconds)
- **Dispatch rejects timeouts outside the supported range** — 4 rows
  (0 / 4 / 601 / 3600 seconds)
- **The concurrent dispatch slot is released on every dispatch outcome** —
  5 rows (success / timeout / specialist error / transport unavailable / unresolved)

## Deferred Items

None. All four primary groups (Key Examples, Boundary, Negative, Edge Cases)
plus the seven-scenario edge-case expansion were accepted in full during the
curation phase.

## Open Assumptions (low confidence)

- **ASSUM-009 — Existing-trace-file overwrite semantics.** The design pins
  a 1:1 decision-id → trace-file path mapping but does not explicitly state
  collision behaviour. The accepted policy treats a second offload at an
  existing path as a routing history write failure (logged WARN, original
  preserved). Verify against operator expectations before TASK-J004
  implementation lands; an alternative is to overwrite-with-warning, which
  would change the test fixture for that scenario.

## Open Assumptions (medium confidence)

- **ASSUM-008 — Degraded specialist dispatch eligibility.** The
  `AgentManifest.status` enum allows `"degraded"` but the design does not
  explicitly forbid dispatching to a degraded specialist. v1 keeps them
  dispatch-eligible and lets the redirect-with-retry policy handle their
  failures; FEAT-JARVIS-008 (`jarvis.learning`, v1.5) can suppress at
  resolution-time later via an append-only DDR. Confirm this is the
  intended runtime behaviour before tasking.

## Pinned highlights (high confidence)

The following values are pinned by DDRs and contracts in
`docs/design/FEAT-JARVIS-004/`:

- 60s default dispatch timeout, range 5..600 — DDR-016
- 1 redirect max (2 total attempts), lexicographic resolution — DDR-017
- 16 KB JSON-encoded trace-offload threshold — DDR-018
- Fire-and-forget Graphiti writes; WARN on failure — DDR-019
- 8 in-flight concurrent dispatches; DEGRADED on overflow — DDR-020
- NATS soft-fail at startup; stub catalogue fallback — DDR-021
- 30s heartbeat default; 5s drain windows on shutdown — API-internal
- Singular topic convention (no plural forms) — API-events §4
- `source_id="jarvis"` audit invariant on every emitted envelope — API-events §5
- Late replies discarded at the NATS layer — API-events §3
- Redaction at the write boundary (API keys, JWTs, NATS creds, email) —
  ADR-ARCH-029 + DDR-018

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "NATS Fleet Registration and Specialist Dispatch" \
      --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md \
      --context docs/design/FEAT-JARVIS-004/design.md \
      --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml

`/feature-plan` Step 11 will run the `bdd-linker` subagent to attach
`@task:<TASK-ID>` tags to scenarios automatically. Hand-tagging is not
required — but if Step 11 surfaces below-threshold matches, the
filesystem-offload edge cases (Group B's `above the offload threshold`,
Group E's `trace file already exists`) and the redaction scenario are the
most likely to cluster around a single TASK-J004-NN trace-richness task.

## Notes for downstream tasking

- The `ASSUM-009` low-confidence policy decision should be raised to Rich
  before the task that owns the routing history writer is started. Either
  outcome (write-failure vs overwrite-with-warning) is implementable; the
  `.feature` file currently pins the write-failure semantics.
- `ASSUM-008` interacts with the FEAT-JARVIS-008 `jarvis.learning` reader.
  If learning eventually wants to suppress degraded specialists at
  resolution time, that is an append-only DDR — no schema change.
- The five-row `Scenario Outline` covering "slot released on every
  outcome" is the regression that protects the dispatch semaphore from
  silent slot-leak bugs across all five `DispatchOutcome` literals.
Update Todos

Phase 1: Gather context (read all DDRs, ADRs, code)

Phase 2: Generate grouped scenario proposal

Phase 3: Wait for human curation A/R/M/+/?

Phase 4: Offer edge case expansion

Phase 5: Resolve assumptions

Phase 6: Write feature/assumptions/summary files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: NATS Fleet Registration and Specialist Dispatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
  features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature
  features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml
  features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md

Scenarios: 36 total
  @key-example: 6      @boundary: 6
  @negative: 7         @edge-case: 17
  @smoke: 5            @regression: 3

  Of those, 3 are Scenario Outlines covering 12 example rows total
  (3 inside-range timeouts + 4 outside-range timeouts + 5 dispatch outcomes).

Assumptions: 12 total
  high: 10 (auto-proceed)
  medium: 1 (Coach review recommended)
  low: 1 (human review required)

REVIEW REQUIRED: 1 low-confidence assumption needs verification
  ASSUM-009 — existing-trace-file overwrite policy treated as a write failure.
  See: features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml

Deferred: 0 scenario groups (all four primary groups + edge-case expansion accepted in full)

Next steps:
  Review: features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature
  Pass to feature-plan: /feature-plan "NATS Fleet Registration and Specialist Dispatch" \
    --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md \
    --context docs/design/FEAT-JARVIS-004/design.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
36 scenarios pinned across the four Specification by Example categories plus the 7-scenario expansion. One low-confidence policy decision (ASSUM-009 — existing trace-file overwrite semantics) is the only item that needs your attention before tasking; medium-confidence ASSUM-008 (degraded specialist dispatch eligibility) is worth a glance too. Ready for /feature-plan.

thanks please update the build plan to reflect the current status and provide the command syntax for the follow-on /feature-plan command
Read phase3-build-plan.md
Updating the Status Log to reflect Phase 2 close and FEAT-JARVIS-004's design + spec landing today, plus pinning Step 5's /feature-plan paths to the concrete artefacts now that the slug is known.

Edit phase3-build-plan.md
Modified
Edit phase3-build-plan.md
Modified
Now pin Step 5 (/feature-plan FEAT-JARVIS-004) to the concrete artefact paths now that the slug is known.

Edit phase3-build-plan.md
Added 26 lines
Build plan updated. Quick verification:

Bash Verify status log entries and slug pinning
IN
grep -n -E "^\| 2026-04-2[57]|REVIEW REQUIRED|feat-jarvis-004-fleet-registration-and-specialist-dispatch" docs/research/ideas/phase3-build-plan.md | head -20

OUT
17:| 2026-04-25 | **Phase 2 close** | FEAT-JARVIS-003-FIX waves F1/F2/F3 (commit `feb482e`), F8 (commits `4536bb8` → `9f49ae3` → `a6cdf57` — supervisor `make_graph` factory wired for langgraph CLI per DDR-013), F9 + F10 (commit `0ff4f40` — `langgraph-cli[inmem]` + YAML gate fix). Routing-e2e test green; `langgraph dev` spinning 2 graphs cleanly. |
18:| 2026-04-27 | **`/system-design FEAT-JARVIS-004`** | Design doc landed at [`docs/design/FEAT-JARVIS-004/design.md`](../../design/FEAT-JARVIS-004/design.md) with 7 DDRs (DDR-016..022), 3 contract docs (`API-tools.md`, `API-internal.md`, `API-events.md`), `DM-routing-history.md` (resolves JA1), and the C4 L3 diagram at `diagrams/fleet-dispatch-l3.md`. |
19:| 2026-04-27 | **`/feature-spec FEAT-JARVIS-004`** | 36 Gherkin scenarios across 4 SBE groups + 7 expansion scenarios. 12 assumptions captured (10 high / 1 medium / 1 low). Output at [`features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/`](../../../features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/). One **REVIEW REQUIRED** flag on ASSUM-009 (existing-trace-file overwrite policy). |
384:Slug pinned at `/feature-spec` time: `feat-jarvis-004-fleet-registration-and-specialist-dispatch`.
390:  --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md \
391:  --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature \
392:  --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml \
Status log + Step 5 both updated cleanly.

Ready for /feature-plan FEAT-JARVIS-004
Here's the command to run next, copy-paste ready:


cd /Users/richardwoollcott/Projects/appmilla_github/jarvis

/feature-plan "NATS Fleet Registration and Specialist Dispatch" \
  --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md \
  --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature \
  --context features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/design/FEAT-JARVIS-004/contracts/API-tools.md \
  --context docs/design/FEAT-JARVIS-004/contracts/API-internal.md \
  --context docs/design/FEAT-JARVIS-004/contracts/API-events.md \
  --context docs/design/FEAT-JARVIS-004/models/DM-routing-history.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-016-dispatch-timeout-default-60s.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-017-retry-with-redirect-policy.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-018-routing-history-schema-authoritative.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-020-concurrent-dispatch-cap-8.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md \
  --context docs/design/FEAT-JARVIS-004/decisions/DDR-022-defer-llamaswap-live-reads-to-v15.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context .guardkit/context-manifest.yaml
Pre-flight checklist
Two assumption decisions worth resolving (or flagging) before kicking off /feature-plan's clarification phase:

ASSUM-009 — existing-trace-file overwrite policy (low confidence). The .feature currently pins "treat as a write failure". Alternative is "overwrite-with-warning". The choice is implementable either way; just don't let it surface mid-AutoBuild.
ASSUM-008 — degraded specialist dispatch eligibility (medium confidence). Currently: degraded specialists stay dispatch-eligible in v1. If you'd rather exclude them at resolution time, that's an append-only DDR before tasking starts.
Build-plan changes
Status Log now shows Phase 2 close (2026-04-25), /system-design FEAT-JARVIS-004 and /feature-spec FEAT-JARVIS-004 both completed today (2026-04-27), and /feature-plan FEAT-JARVIS-004 marked as the next step.
Step 5 now uses concrete artefact paths (no more feat-jarvis-004-* globs) and pulls in all 7 DDRs + 3 contract docs + DM-routing-history alongside the spec triplet, plus a pre-flight checklist for the two unresolved assumptions.
