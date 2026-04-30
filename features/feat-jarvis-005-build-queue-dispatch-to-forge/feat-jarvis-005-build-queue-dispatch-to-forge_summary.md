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
