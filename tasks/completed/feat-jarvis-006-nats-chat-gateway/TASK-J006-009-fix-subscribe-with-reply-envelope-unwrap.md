---
id: TASK-J006-009
title: Fix subscribe_with_reply to unwrap MessageEnvelope before CommandPayload validation
task_type: bug
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 5
implementation_mode: task-work
complexity: 2
priority: critical
status: completed
dependencies:
  - TASK-J006-005
created: 2026-05-12 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
completed: 2026-05-12 00:00:00+00:00
completed_location: tasks/completed/feat-jarvis-006-nats-chat-gateway/
previous_state: in_review
state_transition_reason: |
  Code-complete: AC-009-01/02/03 unit-green; AC-009-04 (live GB10 rerun) is
  operator action and remains pending. See "Operator follow-up" section below
  — the demo-blocker won't fully clear until AC-009-04 is observed on the
  GB10 build that has this patch applied.
tags:
  - nats
  - infrastructure
  - bug
  - demo-blocker
  - wire-contract
test_results:
  status: passing
  coverage: null
  last_run: 2026-05-12
  notes: |
    tests/test_nats_client.py — 28 passed in 0.69s
    New unit tests:
      TestSubscribeEnvelopeUnwrap::test_envelope_wrapped_command_payload_is_unwrapped_and_delivered  (AC-009-01)
      TestSubscribeEnvelopeUnwrap::test_undecodable_bytes_are_logged_and_absorbed                    (AC-009-03)
    Pre-existing flat-payload regression coverage:
      TestSubscribeWithReply::test_subscribe_with_reply_handler_receives_payload_and_reply_to        (AC-009-02)
---

# Task: Fix `subscribe_with_reply` to unwrap `MessageEnvelope` before `CommandPayload` validation

## Severity / impact

**P0 — demo-blocker for the 2026-05-16 DDD Southwest demo.**

Live verification on GB10 (2026-05-12) discovered that the jarvis chat-gateway
subscriber cannot decode messages published by the production OpenWebUI pipe.
All AC-005-03..06 fail because the inbound command is rejected before reaching
the chat handler. See evidence in
`docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12.md` and
`docs/runbooks/evidence/feat-jarvis-006-first-run/jarvis-serve-nats-smoke.log`
(grep `nats_subscribe_decode_failed`).

## Bug specification

### Wire contract divergence

| Side | Behaviour | Source |
|---|---|---|
| Fleet-gateway pipe (production traffic) | Publishes `MessageEnvelope { version, event_type, source_id, correlation_id, payload: CommandPayload }` | `fleet-gateway/common/envelope.py:96` `build_command_envelope` |
| **Jarvis subscriber (this bug)** | Decodes raw `msg.data` as **flat** `CommandPayload` — no envelope unwrap | `jarvis/src/jarvis/infrastructure/nats_client.py:272` `CommandPayload.model_validate_json(msg.data)` |
| Study-tutor (proven reference template) | Decodes `MessageEnvelope`, then `CommandPayload.model_validate(envelope.payload)` | `study-tutor/src/study_tutor/adapters/command_router.py:124` |

The implementation runbook
(`docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md`) cites
the study-tutor `command_router` as authoritative under "Pre-read mandate"
and lists `nats_core.envelope.MessageEnvelope` as the canonical wire envelope
(see jarvis `src/jarvis/infrastructure/chat_handler.py:104` import). The
subscriber decode path is the one place this contract is broken.

### Reproduction (2026-05-12 GB10 evidence)

1. `jarvis serve-nats --nats nats://rich:****@localhost:4222` running on GB10
2. OpenWebUI pipe (`fleet-gateway/openwebui/nats_fleet_pipe.deploy.py`) deployed
   and Valves `NATS_URL` set to the authenticated broker URL
3. Operator sends a chat message via Jarvis model in OpenWebUI
4. Wire-tap on `agents.command.jarvis` captures the envelope-wrapped
   `CommandPayload` (correlation_id `422a025f-3961-4bc2-bcf7-2b816012001e`)
5. Serve-nats log shows:
   ```json
   {"subject":"agents.command.jarvis","error_class":"ValidationError",
    "error":"1 validation error for CommandPayload\ncommand\n  Field required",
    "event":"nats_subscribe_decode_failed","level":"error"}
   ```
6. No `chat_invoke_start` log line; no result envelope published; OpenWebUI
   times out with "Jarvis did not respond within 120s"

The flat-payload contract still works (Phase 2.3 `nats request` with
`{"command":"chat","args":{...}}` succeeds end-to-end). The bug is therefore
*decode strictness* in the subscriber, not a missing path elsewhere.

### Expected vs actual

**Expected:** subscriber accepts envelope-wrapped payloads (production wire
format) AND flat `CommandPayload` (runbook §2.3 smoke contract), routes the
unwrapped `CommandPayload` to the registered handler.

**Actual:** subscriber accepts only flat `CommandPayload`; envelope-wrapped
payloads fail `pydantic.ValidationError` at the wrapper boundary and are
logged-and-dropped.

## Recommended fix scope

**File:** `src/jarvis/infrastructure/nats_client.py` (lines 266–280, the
`_on_message` wrapper inside `subscribe_with_reply`).

**Patch sketch (~10 LOC):**

```python
async def _on_message(msg: Msg) -> None:
    # Try envelope-wrapped path first (production wire from
    # fleet-gateway and other agents — matches the study-tutor
    # template, see TASK-J006-009).
    try:
        envelope = MessageEnvelope.model_validate_json(msg.data)
    except Exception:
        envelope = None

    try:
        if envelope is not None:
            payload = CommandPayload.model_validate(envelope.payload)
        else:
            # Fallback: flat CommandPayload (preserves the
            # runbook §2.3 nats-cli smoke contract).
            payload = CommandPayload.model_validate_json(msg.data)
    except Exception as exc:
        logger.error(
            "nats_subscribe_decode_failed",
            subject=subject,
            error_class=type(exc).__name__,
            error=str(exc),
        )
        return

    # ... unchanged from here
```

Imports needed: `from nats_core.envelope import MessageEnvelope` (already in
sibling modules).

## Acceptance Criteria

- **AC-009-01:** `subscribe_with_reply` decodes envelope-wrapped
  `CommandPayload` published via `nats_core.envelope.MessageEnvelope`
  (production wire format) and routes the unwrapped payload to the
  registered handler. Unit test fixture: byte-for-byte output of
  `common.envelope.build_command_envelope(...)`.
- **AC-009-02:** `subscribe_with_reply` continues to decode flat
  `CommandPayload` bytes (runbook §2.3 smoke contract). Existing test
  in `tests/test_nats_client_subscribe_with_reply.py` (or equivalent)
  must remain green without modification.
- **AC-009-03:** Decode failures (neither shape valid) continue to be
  logged-and-absorbed via `nats_subscribe_decode_failed`; the
  subscription's reader task is not torn down.
- **AC-009-04:** Live verification on GB10: rerun runbook Phase 3.4
  Turn 1 from OpenWebUI; the supervisor reply renders in OpenWebUI;
  wire-tap captures both directions; AC-005-03 of TASK-J006-005 flips
  ✅. Evidence captured in
  `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-<DATE>.md`.

## Implementation Notes

- Keep the fix in `nats_client.py` — do not push envelope/flat juggling
  into the chat handler or further upstream. The wrapper boundary is the
  documented decode-and-type-the-handler-input contract.
- Match study-tutor's pattern: decode envelope, then `model_validate` the
  payload field. Do not introduce a new ad-hoc envelope schema.
- The fallback (flat `CommandPayload`) is intentional, not legacy: it
  preserves the runbook's `nats request` smoke recipe so future operators
  can probe the bus without building an envelope by hand. Add a one-line
  code comment naming the runbook §2.3 contract so the fallback is not
  pruned in a future cleanup pass.

## Out of scope

- Refactoring the wire contract (e.g. forcing the runbook to use envelopes
  in its smoke recipe). Doing so would push complexity onto every diagnostic
  surface; the fallback in the subscriber is cheaper.
- Touching `chat_handler.py` — the handler signature already takes a
  `CommandPayload`, which is what `_on_message` will continue to deliver.
- Anything in `fleet-gateway` — the pipe's wire format is correct.

## Implementation summary (2026-05-12)

**Patch landed.** `src/jarvis/infrastructure/nats_client.py` (`_on_message`
inside `subscribe_with_reply`) now:

1. Imports `MessageEnvelope` from `nats_core.envelope`.
2. Tries `MessageEnvelope.model_validate_json(msg.data)` first; on success,
   validates `envelope.payload` as `CommandPayload` (production wire format
   — fleet-gateway and other agents, study-tutor template).
3. Falls back to flat `CommandPayload.model_validate_json(msg.data)` when
   the envelope shape doesn't parse (runbook §2.3 smoke contract).
4. Logs and absorbs failures of *both* paths via the existing
   `nats_subscribe_decode_failed` event — the subscription reader task is
   not torn down.

Total change: +24 / −5 LOC in `nats_client.py` (one import + a rewritten
decode block with one comment block citing TASK-J006-009 and the runbook).
Handler signature and the `in_flight` accounting downstream are unchanged.

### AC verification status

| AC | Status | Evidence |
|---|---|---|
| AC-009-01 envelope-wrapped decode | ✅ green | `tests/test_nats_client.py::TestSubscribeEnvelopeUnwrap::test_envelope_wrapped_command_payload_is_unwrapped_and_delivered` — synthesises a byte-for-byte `build_command_envelope` wire (correlation_id `422a025f-…001e` from the GB10 repro) and asserts the inner `CommandPayload` reaches the handler with `_INBOX.envelope.42` as `reply_to`. |
| AC-009-02 flat decode unchanged | ✅ green | `TestSubscribeWithReply::test_subscribe_with_reply_handler_receives_payload_and_reply_to` continues to pass without modification (runbook §2.3 contract). |
| AC-009-03 decode failure absorbed | ✅ green | `TestSubscribeEnvelopeUnwrap::test_undecodable_bytes_are_logged_and_absorbed` — drives `b"this is not json"` through the registered callback and asserts (a) handler not invoked, (b) `in_flight == 0`, (c) `nats_subscribe_decode_failed` on stdout. |
| AC-009-04 live GB10 verification | ⏳ pending operator | Requires rerunning runbook Phase 3.4 Turn 1 from OpenWebUI on GB10 against the patched build. Will produce `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-<DATE>.md` and flip AC-005-03 of TASK-J006-005. |

### Test run (2026-05-12)

```
$ .venv/bin/python -m pytest tests/test_nats_client.py -q
............................                                             [100%]
28 passed in 0.69s
```

Adjacent NATS suites (`test_lifecycle_nats_subscriptions.py`,
`test_contract_nats_core.py`) also stay green — 60 tests pass across the
three files.

Two unrelated pre-existing failures elsewhere in the repo
(`test_capabilities_real.py`, `test_phase4_dependencies.py` graphiti-core
version-pin tests) were confirmed present on the un-patched tree as well
and are tracked separately.

## Operator follow-up (AC-009-04, post-completion)

Closing this task as **code-complete** with one acceptance criterion still
gated by hardware:

- **AC-009-04** requires running the patched `jarvis serve-nats` on GB10
  against the live OpenWebUI pipe and capturing the wire-tap evidence into
  `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-<DATE>.md`.
  That observation flips AC-005-03 on TASK-J006-005 (parent demo task)
  and is the final gate before the 2026-05-16 DDD Southwest demo can be
  declared safe.

If the GB10 run surfaces a regression that contradicts the unit tests in
this task, **reopen this task**; do not silently let the demo-block leak
into TASK-J006-005's verification window.

## See also

- Evidence: `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12.md` (this session)
- Runbook: `docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md` §3.4 / AC-005-03
- Parent task: `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-005-live-openwebui-demo-verification.md`
- Reference template: `study-tutor/src/study_tutor/adapters/command_router.py:124`
- Wire schema: `nats-core/src/nats_core/envelope.py` (MessageEnvelope), `nats-core/src/nats_core/events/_agent.py` (CommandPayload)
