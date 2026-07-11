# WS3-S8 tracker sweep — dangling-reference pointer notes (jarvis, 2026-07-11)

The `guardkit task audit` dangling-reference pass names three task ids referenced by
first-party code / feature YAMLs that no task file in this repo declares. Per the
WS3-S8 rules these are recorded here (never invented into task files) and reported as
residuals — a `docs/state` note does not resolve the audit row (by design), so each
will continue to surface until the reference itself is retired or the id is filed.

- **TASK-FORGE-FRR-F010C** — referenced by `src/jarvis/infrastructure/forge_notifications.py`.
  Cross-repo: `FORGE-FRR-*` is a **forge** task id (forge-response-router family), named
  in a jarvis code comment/marker. It belongs to the forge tracker, not jarvis; no jarvis
  task file should declare it. Retire by updating the code reference during the next forge
  wire-dispatch session, or leave as an intentional cross-repo breadcrumb.

- **TASK-JNB-101** — referenced by `.guardkit/features/FEAT-BF39.yaml`. BF39's description
  notes forge-side `TASK-JNB-101/102/106` "should land before TASK-JNB-107" — i.e. the 101
  series is the **forge/cross-repo** half of the notification-bridge reply path, never filed
  as a jarvis task file. FEAT-BF39 is completed (JNB-103/104/105/107); the 101 reference is a
  cross-repo dependency note, not a missing jarvis task.

- **TASK-SPL003F-001** — referenced by `src/jarvis/infrastructure/planning_notifier.py`.
  An `SPL-003-FIX`-family id named in code; FEAT-SPL-003 is still `in_progress`. No task file
  declares SPL003F-001; it is either a planned-but-unfiled follow-up or a stale code marker.
  Left for the owning SPL-003 session to file or remove — not resolvable mechanically here.
