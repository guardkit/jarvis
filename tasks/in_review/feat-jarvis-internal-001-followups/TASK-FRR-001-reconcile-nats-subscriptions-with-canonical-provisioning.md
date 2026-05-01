---
complexity: 5
created: 2026-05-01 00:00:00+00:00
dependencies: []
discovered_on_machine: GB10 (promaxgb10-41b1)
discovered_on_date: 2026-05-01
discovered_via_correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
estimated_minutes: 120
feature_id: FEAT-JARVIS-INTERNAL-001-FRR
id: TASK-FRR-001
implementation_mode: task-work
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md
previous_state: backlog
priority: high
state_transition_reason: Automatic transition for task-work execution
status: in_progress
tags:
- jarvis
- feat-jarvis-internal-001-followups
- nats
- jetstream
- ddr-027
- ddr-030
- infrastructure-reconciliation
task_type: bugfix
title: Reconcile NATS subscriptions (fleet register, KV bind, forge_subscriber) with canonical provisioning
updated: 2026-05-01 12:00:00+00:00
wave: 1
---

# Reconcile NATS subscriptions with canonical provisioning

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Wave:** 1 | **Mode:** task-work (TDD) | **Complexity:** 5/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — phases 5.1 (jarvis chat boots — caveat) and 7.1 (between-prompt notifications — ❌ as expected); operator-side gap row "Jarvis fleet register, KV bind, and forge_subscriber attach all fail at startup..."
**ADR/DDR:** DDR-027 (forge_subscriber consumer config — `deliver_policy=NEW`), DDR-030 (between-prompt notification rendering)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-01, correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`

## Description

The 2026-05-01 first real run on the GB10 surfaced **three independent startup-time NATS errors** in the `jarvis chat` lifecycle, all caused by the jarvis-side subscription config not matching the canonical provisioning in `nats-infrastructure`:

1. `jarvis_fleet_register_failed` — `nats: BadRequestError code=400 err_code=10058 description='stream name already in use with a different configuration'`. The fleet-register hop hits a config mismatch between what jarvis expects on the FLEET / JARVIS streams and what `nats-infrastructure/streams/stream-definitions.json` provisions.
2. `jarvis_live_capabilities_registry_failed` — `Failed to bind agent-registry KV bucket: BadRequestError code=10058 description='stream name already in use with a different configuration'`. The KV bucket bind config mismatch causes the routing-history live capabilities registry to fall back to **stub mode** (`capabilities_mode: stub` in startup logs); the fleet observer never sees `jarvis` as a registered agent.
3. `jarvis_forge_subscriber_start_failed` — `BadRequestError code=10101 description='consumer must be deliver all on workqueue stream'`. Jarvis tries to attach a consumer with `deliver_policy=NEW` (per DDR-027) against the PIPELINE stream, but PIPELINE is a workqueue-retention stream, and workqueue requires `deliver_policy=all`.

**Why this matters:**
- Failure (3) means jarvis cannot subscribe to `pipeline.stage-complete.*` events even when forge starts publishing them. The DDR-030 between-prompt notification rendering path is **dead** until this is fixed.
- Failure (1) and (2) mean the routing-history live capabilities registry falls back to stub mode and the fleet observer never sees `jarvis` as a registered agent.

**Why Option A (change jarvis) is almost certainly the right answer:**
There are two reconciliation paths:
- **Option A**: change jarvis's consumer config (forge_subscriber attach uses `deliver_policy=all`; fleet register uses the canonical stream config; KV bind uses the canonical bucket config) so it interoperates with `nats-infrastructure`'s definitions.
- **Option B**: change `nats-infrastructure`'s definitions to match what jarvis needs (e.g. PIPELINE retention switches off workqueue) — only viable if forge doesn't depend on workqueue semantics.

Forge's `forge-serve` durable consumer **does** depend on workqueue retention to drain messages once acked (verified via `forge-prod` consumer info in the GB10 run: `delivered=1, acked=1, num_pending=0` — workqueue retention is what removes the message after ack so `state.messages=0`). So Option A is almost certainly the right answer; this task adopts it. If during implementation an unexpected dependency on `deliver_policy=NEW` semantics is discovered, escalate before flipping to Option B (forge would have to be re-validated against non-workqueue retention, which is out of scope for this task).

## Acceptance Criteria

- [ ] **TDD red phase.** A new integration test (e.g. `tests/test_lifecycle_nats_subscriptions.py`) is written and FAILS against the current `main` branch, exercising all three failure modes:
  - The fleet-register hop produces a `jarvis_fleet_register_failed` warning when the JARVIS / FLEET streams are provisioned per `nats-infrastructure/streams/stream-definitions.json`.
  - The capabilities registry KV bind produces a `jarvis_live_capabilities_registry_failed` warning under the same provisioning.
  - The forge_subscriber attach produces a `jarvis_forge_subscriber_start_failed` warning with `code=10101 description='consumer must be deliver all on workqueue stream'`.
  Commit the failing tests on a single commit before the fix lands so the regression is auditable.
- [ ] `forge_subscriber` consumer config changes from `deliver_policy=NEW` to `deliver_policy=all` (or whatever `JsApiConsumerCreateRequest` flag the canonical workqueue requires). Update DDR-027 (or its successor DDR) to reflect the new policy choice and the workqueue rationale; cite the forge-side workqueue dependency.
- [ ] Fleet-register stream config (the JARVIS / FLEET streams jarvis expects) matches the canonical shape in `nats-infrastructure/streams/stream-definitions.json`. If jarvis was attempting to assert a stream config (e.g. via `stream_create`/`update`), narrow that to "lookup-only" or align the asserted config to canonical.
- [ ] `agent-registry` KV bucket bind matches the canonical shape in `nats-infrastructure`'s KV definitions. Same lookup-only / config-aligned posture.
- [ ] **Integration test green phase.** All three integration tests now pass — fresh `jarvis chat` startup against canonical `nats-infrastructure` provisioning produces **zero** `jarvis_fleet_register_failed` / `jarvis_live_capabilities_registry_failed` / `jarvis_forge_subscriber_start_failed` warnings in the structured log.
- [ ] `capabilities_mode` reports `live` (not `stub`) at startup once the KV bind succeeds; `tests/test_lifecycle_startup_phase3.py` (or wherever capabilities_mode is asserted) gains an explicit assertion of this.
- [ ] With a future forge that publishes real `pipeline.stage-complete.*` events, jarvis's between-prompt notification drain renders them per DDR-030. Add (or extend) a contract test that mocks a stage-complete publish on PIPELINE and asserts the supervisor's notification queue surfaces the rendered line on the next prompt.
- [ ] All existing FEAT-J004 and FEAT-J005 contract tests still pass; in particular the fleet observer / routing-history capability snapshot tests.
- [ ] `mypy src/jarvis/` and `ruff check src/jarvis/` remain at zero violations on the touched files.
- [ ] No regression in `tests/test_lifecycle_startup_phase3.py` — startup phases still complete in the documented order.

## Files Expected to Change

- `src/jarvis/infrastructure/lifecycle.py` — startup phases for fleet_register / KV bind / forge_subscriber attach. Adjust consumer-create payloads to match canonical streams.
- `src/jarvis/infrastructure/nats/forge_subscriber.py` (or wherever the consumer-create call lives) — flip `deliver_policy=NEW` → `deliver_policy=all`.
- `src/jarvis/infrastructure/nats/fleet_register.py` (or equivalent) — align stream-config assertions to canonical, or drop the assertion entirely if lookup-only is correct.
- `src/jarvis/infrastructure/nats/capabilities_registry.py` (or equivalent) — align KV bucket-bind config to canonical.
- `tests/test_lifecycle_nats_subscriptions.py` — **NEW** integration test (red-then-green) covering all three failure modes.
- `tests/test_lifecycle_startup_phase3.py` — extend to assert `capabilities_mode == "live"` when KV bind succeeds.
- DDR-027 (or successor) — document the workqueue-driven `deliver_policy=all` choice.

## References

- **Parent runbook results:** [`docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
  - Per-phase rows: 5.1 (jarvis chat boots — caveat about workqueue config errors); 7.1 (between-prompt notifications — ❌ as expected, root cause `forge_subscriber_start_failed`).
  - Operator-side gap row: "Jarvis fleet register, KV bind, and forge_subscriber attach all fail at startup against canonical NATS provisioning..."
  - Recommended follow-up #4.
- **Canonical NATS provisioning:** `nats-infrastructure/streams/stream-definitions.json` (PIPELINE / FLEET / JARVIS stream shapes, `agent-registry` KV bucket shape).
- **Source files:** `src/jarvis/infrastructure/lifecycle.py` startup phases for fleet_register / KV bind / forge_subscriber attach; `src/jarvis/infrastructure/nats/*` for the per-subsystem subscribe/bind logic.
- **DDRs:** DDR-027 (forge_subscriber consumer config — needs revision per this task), DDR-030 (between-prompt notification rendering, currently dead because of failure (3)).
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-01.
- **correlation_id:** `a58ec9a7-27c6-485a-beac-e18675639a10`.
- **Evidence:** `/tmp/runbook-evidence/phase5.0-health.log`, `/tmp/runbook-evidence/phase6-7-chat-v2.log` (search for `jarvis_fleet_register_failed`, `jarvis_live_capabilities_registry_failed`, `jarvis_forge_subscriber_start_failed`).

## Notes

- This is the **highest-impact** of the four FRR follow-ups because failure (3) blocks the entire DDR-030 notification path, which is the headline UX claim of the FEAT-JARVIS-INTERNAL-001 runbook.
- The TDD red-then-green split is mandatory because the regression spans a cross-repo contract (jarvis ↔ nats-infrastructure ↔ forge); the failing-test commit gives us a durable artefact that the canonical provisioning was, in fact, the runtime shape on 2026-05-01.
- If during implementation a forth NATS-side mismatch surfaces (e.g. NOTIFICATIONS or AGENTS stream config drift), capture it in the same task and extend the test scope; do not split into a fifth task unless it touches a different config domain.
- Out of scope: forge-side `dispatch_payload` real-orchestrator wiring (tracked as forge follow-up #1 in the RESULTS file). This task closes the *receive* side; the *publish* side is forge's problem.
