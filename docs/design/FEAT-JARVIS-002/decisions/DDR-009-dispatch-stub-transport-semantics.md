# DDR-009: Phase 2 dispatch-tool stub transport semantics

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** Fleet Dispatch Context; `jarvis.tools.dispatch`
- **Related ADRs:** ADR-ARCH-021 (structured errors); ADR-SP-014 Pattern A via Forge pipeline architecture
- **Related decisions:** DDR-005 (dispatch tool name/signature); DDR-008 (capabilities delivery)

## Context

The Phase 2 scope document lists an open question: *"`call_specialist` timeout + retry semantics. Even stubbed, the tool needs a defensible timeout default and a retry-with-redirect behaviour spec so FEAT-JARVIS-004 swaps transports cleanly."* Same question applies to `queue_build` — even stubbed, the return-value shape and error-category set need to match what the real transport will produce.

Phase 2 stubs must:

- Build **real** `nats_core.events` payloads — this keeps FEAT-JARVIS-004/005 a transport-level swap (per scope doc invariant ¶7 *"stubbed transport ≠ stubbed schema"*).
- Log publishes with distinct, grep-able prefixes so the FEAT-JARVIS-004/005 AutoBuild task can locate the swap points mechanically.
- Return strings that a reasoning model behaves identically to in Phase 2 (stub) and Phase 3+ (real) — per DDR-005, the tool docstring is the contract.

## Decision

### `dispatch_by_capability` — Phase 2 stub behaviour

1. **Resolution.** Look up `tool_name` against the in-memory capability registry.
   - Exact `CapabilityToolSummary.tool_name` match → resolves to that `agent_id`.
   - No exact match but `intent_pattern` supplied → highest-confidence match among registered specialists (Phase 2 stub: simple substring match on descriptor `role`/`description`; the real resolver in `NATSKVManifestRegistry` is richer in Phase 3).
   - No resolution → return `ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>`.

2. **Payload validation.**
   - `payload_json` must parse to a JSON object literal. On failure → `ERROR: invalid_payload — payload_json is not a JSON object literal`.
   - `timeout_seconds` must be between 5 and 600 inclusive. Out of range → `ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>`.

3. **Payload construction (always, even on stub).**
   ```python
   command = CommandPayload(
       command=tool_name,
       args=json.loads(payload_json),
       correlation_id=correlation_id or str(uuid4()),
   )
   envelope = MessageEnvelope(
       source_id="jarvis",
       event_type=EventType.COMMAND,
       correlation_id=command.correlation_id,
       payload=command.model_dump(mode="json"),
   )
   ```
   Topic that *would* be published: `Topics.Agents.COMMAND.format(agent_id=resolved_agent_id)` → `"agents.command.<agent_id>"` (singular per ADR-SP-016).

4. **Logged publish (the grep anchor).**
   ```
   JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y> correlation_id=<z>
     topic=agents.command.<y> payload_bytes=<n>
   ```

5. **Stub response.** A module-level hook `_stub_response_hook: Callable[[CommandPayload], StubResponse] | None`
   controls the behaviour for tests:
   - Unset (default) → return a canned `ResultPayload(command=tool_name, result={"stub": True, "tool_name": tool_name}, correlation_id=<same>, success=True)` serialised as JSON.
   - Set to `stub_timeout` → return `TIMEOUT: agent_id=<y> tool_name=<x> timeout_seconds=<n>`.
   - Set to `stub_error` → return `ERROR: specialist_error — agent_id=<y> detail=<canned>`.

6. **No retry.** Even in Phase 3+, retry is **not** a property of this tool — the reasoning model decides whether to re-dispatch after reading the structured error. This is fleet-consistent with Forge's equivalent: retry is a reasoning decision, not a mechanical one. [ADR-ARCH-024](../../../architecture/decisions/ADR-ARCH-024-pattern-b-watcher-failure-policy.md) constrains retry to the Pattern B watcher subsystem, not the dispatch surface.

### `queue_build` — Phase 2 stub behaviour

1. **Validation.** `feature_id` matches `^FEAT-[A-Z0-9]{3,12}$`. `repo` matches `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`. `originating_adapter` ∈ the `OriginatingAdapter` literal. Invalid inputs return structured errors; valid inputs proceed to payload construction.

2. **Payload construction.**
   ```python
   payload = BuildQueuedPayload(
       feature_id=feature_id,
       repo=repo,
       branch=branch,
       feature_yaml_path=feature_yaml_path,
       triggered_by="jarvis",
       originating_adapter=originating_adapter,
       originating_user=config.user_id or "rich",
       correlation_id=correlation_id or str(uuid4()),
       parent_request_id=parent_request_id,
       requested_at=now_utc(),
       queued_at=now_utc(),
   )
   envelope = MessageEnvelope(
       source_id="jarvis",
       event_type=EventType.BUILD_QUEUED,
       correlation_id=payload.correlation_id,
       payload=payload.model_dump(mode="json"),
   )
   ```
   Topic: `Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)` → `"pipeline.build-queued.<feature_id>"`.

3. **Logged publish.**
   ```
   JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
     topic=pipeline.build-queued.<x> payload_bytes=<n>
   ```

4. **Return.** Always returns a JSON `QueueBuildAck`:
   ```json
   {
     "feature_id": "<x>",
     "correlation_id": "<z>",
     "queued_at": "<iso8601>",
     "publish_target": "pipeline.build-queued.<x>",
     "status": "queued"
   }
   ```
   There is no failure mode in the stub beyond input validation — the real JetStream publish in FEAT-JARVIS-005 can add `DEGRADED: stream_unavailable` and `ERROR: stream_publish_failed` categories without changing this shape.

5. **No retry.** Same reasoning as `dispatch_by_capability` — retry is a reasoning decision.

### Timeout defaults

- `dispatch_by_capability.timeout_seconds` default: **60 s**. Rationale: specialist round-trips observed in prior fleet work cluster around 5–45 s; 60 s catches the long tail without tying up the reasoning model for unreasonable durations.
- `queue_build`: no timeout — Pattern A is fire-and-forget. The JetStream publish in FEAT-JARVIS-005 will use a transport-level 3 s publish-ACK budget that's internal to the adapter, not a tool parameter.

## Alternatives considered

1. **Retry inside the tool with exponential backoff.** Rejected — violates the "retry is reasoning" principle (ADR-ARCH-024's Pattern B exception is the only retrying subsystem). Baking retry into the dispatch tool would make the reasoning model blind to intermittent failures and would conflict with how specialist-agents handle idempotency (they don't in v1 — duplicate commands produce duplicate work).

2. **Construct a fake payload (drop the `nats-core` model build).** Rejected — violates scope invariant ¶7. Real payloads at the stub boundary ensure FEAT-JARVIS-004/005 are transport-only swaps.

3. **Skip logging the stub publishes.** Rejected — without the `JARVIS_DISPATCH_STUB` / `JARVIS_QUEUE_BUILD_STUB` grep anchors, the FEAT-JARVIS-004 AutoBuild run has to find the swap points by hand.

4. **Use structured logging (`structlog`) for the publish line at DEBUG.** Adopted partially — the log is structured JSON per Phase 1's `configure_logging()`, but emitted at **INFO** so it shows up in the default `jarvis chat` session log. Rich has asked for visible evidence during attended sessions that dispatch happened.

## Consequences

- **+** FEAT-JARVIS-004 (specialist dispatch) replaces one log line and one stub hook with a real NATS req/reply; tool docstring and return shape unchanged.
- **+** FEAT-JARVIS-005 (queue_build JetStream) replaces one log line with `js.publish(subject, payload=envelope.model_dump_json().encode())`; tool docstring and return shape unchanged.
- **+** The structured-error vocabulary committed here (`unresolved | invalid_payload | invalid_timeout | timeout | specialist_error | transport_stub`) is the stable vocabulary the reasoning model learns; Phase 3+ adds `transport_unavailable | publish_failed | stream_down` without removing any category.
- **+** `queue_build` is ready to honour the Pattern A constraint: Jarvis never awaits a build.
- **−** Tests must assert on log lines to verify the stub publishes happened — brittle if the format drifts. Mitigation: the log-line format is asserted verbatim in `test_tools_dispatch.py` so any drift is caught.
- **−** `dispatch_by_capability`'s in-process "no retry" is one of the things that might bite on transient NATS errors in Phase 3+. If that becomes an operational issue, an ADR can add bounded retry *at the adapter* (not in the tool); the tool docstring would not change.
