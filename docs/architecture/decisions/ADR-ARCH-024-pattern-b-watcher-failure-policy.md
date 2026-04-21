# ADR-ARCH-024: Pattern B watcher failure policy — retry-3×-then-notify

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Resolves:** JA7 (watcher failure modes)

## Context

Pattern B watchers run async, potentially for hours or days. They hit external APIs (Forge queue, calendar, NVIDIA driver channels, etc.). Transient failures (network blip, API rate limit) are common. Permanent failures (deprecated endpoint, auth expired) need to surface to Rich.

## Decision

Default watcher failure policy — **silent log + retry 3× with exponential backoff, then notify and enter DEAD state:**

- Attempt 1 fails → structured log at WARN level; retry after 15s
- Attempt 2 fails → log; retry after 60s
- Attempt 3 fails → log; retry after 5m
- Attempt 4 fails → emit a `NotificationPayload` to the originating adapter ("Watcher 'NVIDIA 590 driver channel' failed persistently — check logs"); watcher enters DEAD state; `jarvis_ambient_history` records the full trace

DEAD watchers do not count against the 10-concurrent ceiling (ADR-ARCH-013). They remain visible via `jarvis watchers list` (operator CLI) until explicitly purged.

Per-watcher override: a watcher spec may override to `fail_fast=True` (kill on first error + notify) for cases where transient failure is semantically wrong (e.g. monitoring a local process expected to never disappear).

## Alternatives considered

1. **Kill immediately on first error + notify** *(rejected as default)*: Too noisy; transient network blips would flood notifications.
2. **Silent log + retry forever** *(rejected)*: Silent watchers doing nothing for days are dangerous; Rich never learns the integration broke.
3. **Configurable per-watcher at spec time** *(partially adopted as override)*: Most flexible; kept as override, not default.

## Consequences

- Failure events are a rich learning signal (`jarvis.learning` detects "this watcher type fails at rate X across restarts") — can propose `CalibrationAdjustment` to retry policy or notify earlier.
- Notification-fatigue mitigation: one notification per DEAD watcher, not one per failed attempt.
- Operators can see DEAD watchers via CLI; they remain in the log but not in active count.
