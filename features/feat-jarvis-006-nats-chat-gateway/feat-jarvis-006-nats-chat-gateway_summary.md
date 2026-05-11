# Feature Spec Summary: NATS Chat Gateway (FEAT-JARVIS-006)

**Stack**: python
**Generated**: 2026-05-11T17:00:00Z
**Scenarios**: 26 total
**Smoke**: 5 · **Regression**: 1
**Assumptions**: 13 total (7 high / 5 medium / 1 low)
**Review required**: Yes (1 low-confidence assumption — broker-side max message size contract)

## Scope

Adds `jarvis serve-nats` — a NATS subscriber on `agents.command.jarvis` that feeds inbound chat requests into the existing `session_manager.invoke()` pipeline and dual-publishes the supervisor's reply on both the requester's reply inbox (Bug #1) and the canonical `agents.result.jarvis` envelope topic. The gateway adds ONLY the command subscription and an in-flight drain counter to the existing `AppState.nats_client` — it does not clone a full NATSAdapter because `build_app_state()` already owns connect, register, heartbeat, deregister, and disconnect (Risk #5 from the scope doc resolves cleanly). Drain timeout is 30 s (study-tutor template). Forge stage-complete notifications queued during a chat turn are appended to the same reply that closes the turn (Risk #3 chosen: include rather than ignore). Inbound `conversation_history` on the request payload is ignored; the per-gateway session is the canonical history store. The broker is treated as a hard dependency — `serve-nats` refuses to start if the broker is unreachable, rejecting the chat-REPL's soft-fail mode because a degraded-boot surface would silently fail every inbound request. Phase 1 runs a single shared chat session; concurrent chats are serialised through it, accepting the trade-off that two unrelated requesters observe each other's context until per-requester sessions land in a later phase.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (`@key-example`) | 6 |
| Boundary conditions (`@boundary`) | 4 |
| Negative cases (`@negative`) | 5 (incl. 2 cross-tagged with `@edge-case`) |
| Edge cases (`@edge-case`) | 11 (incl. Group D + Group E expansion) |
| Smoke (`@smoke`) | 5 |
| Security (`@security`) | 2 |
| Concurrency (`@concurrency`) | 2 |
| Integration (`@integration`) | 1 |
| Regression (`@regression`) | 1 |

Note: tags overlap (e.g. several negative scenarios are also `@edge-case`; the dispatch-timeout scenario is `@integration`).

## Deferred Items

None. All four proposed groups (A–D) were accepted in full and the Phase-4 expansion (Group E — 6 additional scenarios across security, concurrency, data integrity, and integration boundaries) was accepted in full.

## Open Assumptions (low confidence)

| ID | Anchor |
|---|---|
| ASSUM-013 | Broker-side max message size — Jarvis does not enforce a size limit of its own; rides on broker JetStream configuration. Worth Coach verification because the gateway behaviour under an overlarge payload depends on a contract Jarvis does not control. |

## Cross-Reference: Scope-Doc Anchors Exercised

| Scope-doc anchor | Scenarios that exercise it |
|---|---|
| §Command surface (one verb: `chat`) | A.2, A.3, A.4, A.5, A.6, C.1 |
| §Command surface (ResultPayload.result shape) | A.2, A.4, A.5, E.6 |
| §What Jarvis MUST replicate Bug #1 — dual-publish | A.3, C.3, D.5, E.5 |
| §What Jarvis MUST replicate Bug #1 — subscribe-with-reply | A.1, A.2, E.5 |
| §What Jarvis MUST replicate Bug #4 — flat subject | A.1, C.5 |
| §What Jarvis MUST replicate — signal handling | D.1, E.4 |
| §What Jarvis MUST replicate — graceful shutdown ordering | B.1, B.2, D.1, E.4 |
| §Risks #3 — Forge notification drain | B.3 |
| §Risks #5 — AppState already registers on NATS | A.1 (ASSUM-001 resolution) |
| §Module mapping — manifest factory | A.1 (ASSUM-012) |
| §Design decisions — session per connection | A.6, B.4, E.3 |

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "NATS Chat Gateway (FEAT-JARVIS-006)" \
      --context features/feat-jarvis-006-nats-chat-gateway/feat-jarvis-006-nats-chat-gateway_summary.md \
      --context features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md

The scope doc remains the primary architectural reference; this summary plus the
`.feature` and `_assumptions.yaml` are the BDD layer atop it.
