# ADR-ARCH-018: CalibrationAdjustment approvals via CLI only in v1

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Resolves:** JA5 (CalibrationAdjustment approval UX)

## Context

`jarvis.learning` proposes `CalibrationAdjustment` entities for Rich's confirmation. Multiple surfaces could support the approval round-trip (CLI, Telegram, Dashboard, Reachy voice). Supporting all surfaces in v1 adds trace complexity (which adapter approved? does the approval re-enter learning?) and voice semantics for "approve CalibrationAdjustment ADJ-42" are genuinely unclear.

## Decision

**CLI only in v1.** The operator CLI (`jarvis approve-adjustment ADJ-042`) is the single approval surface. Approval events are recorded to Graphiti with `adapter_id=cli`, clean trace.

Telegram, Dashboard, and Reachy may graduate to approval surfaces in v1.5+ once CalibrationAdjustment volume and Rich's preferred flow are observable.

## Alternatives considered

1. **CLI + Telegram** *(rejected for v1)*: More flexible for ambient use; adds trace complexity.
2. **All four adapters at launch** *(rejected)*: Complex; Reachy voice approval semantics unclear ("Jarvis, approve adjustment 42" → TTS confirms → durable side-effect is surprising-risky).

## Consequences

- Calibration approvals batch on the CLI — Rich's morning workflow includes `jarvis adjustments pending` as a natural step.
- Clean trace — one `adapter_id` value for all confirmations.
- Lower UX friction once Rich forms the habit; higher initial cost (needs to sit at the CLI).
- Proposals expire if not acted on in a configurable window (`ASSUM-pending-adjustment-ttl`, deferred to /system-design).
