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
