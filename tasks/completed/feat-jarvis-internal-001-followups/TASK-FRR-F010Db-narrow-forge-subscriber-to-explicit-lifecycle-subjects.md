---
id: TASK-FRR-F010Db
title: Narrow forge_subscriber from pipeline.> (Option A) to explicit lifecycle subjects (Option B) to avoid workqueue consumer overlap
status: completed
created: 2026-05-04T00:00:00Z
updated: 2026-05-04T13:15:00Z
completed: 2026-05-04T13:15:00Z
priority: high
task_type: fix
tags:
  - forge-subscriber
  - notifications
  - ddr-030
  - jetstream
  - workqueue
  - regression
  - feat-forge-010-followup
  - first-real-run-followup
  - task-frr-f010d-followup
  - subject-filter
complexity: 2
estimated_minutes: 60
estimated_effort: "30-90 minutes (filter constant + subscribe call + regression test)"
parent_feature: FEAT-JARVIS-INTERNAL-001-FRR
related_tasks:
  - TASK-FRR-F010D       # the regressing task this amends — DO NOT re-open it; this is a fresh sibling
  - TASK-FRR-001         # introduced the forge_subscriber wiring + DDR-027 deliver_policy choices
  - TASK-FORGE-FRR-F010C # forge-side correlation_id threading — fully landed; this jarvis fix completes the rendering pipeline once F010.E unblocks autobuild
correlation_id: dfad8e7f-92af-4b5f-896f-ca75ad8343bf
discovered_on:
  date: 2026-05-04
  machine: GB10 (promaxgb10-41b1)
  context: "Joint live-wire validation rerun late afternoon — TASK-FRR-F010D's Option A widening to pipeline.> overlapped with forge-serve's pipeline.build-queued.> filter on the workqueue PIPELINE stream; JetStream rejected the bind"
context_files:
  - docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md
  - src/jarvis/infrastructure/forge_notifications.py
  - src/jarvis/infrastructure/lifecycle.py
  - tasks/completed/feat-jarvis-internal-001-followups/TASK-FRR-F010D-widen-forge-subscriber-subject-filter.md
test_results:
  status: passed
  coverage: 89
  last_run: 2026-05-04T13:07:40Z
  notes: |
    93 tests pass on the forge_notifications surface (subscriber + docstring +
    schema). 52 lifecycle/integration/session tests pass (1 skipped, unrelated
    to this task). Coverage on src/jarvis/infrastructure/forge_notifications.py
    is 89% (183 stmts / 21 miss); missing lines are pre-existing defensive
    backstops (malformed-JSON drop, hung-broker timeout in stop(), debug-log
    branch for unsupported event_type, etc.) that were already uncovered before
    this change. Two unrelated failures in test_phase4_dependencies.py are
    pre-existing — caused by the recent graphiti-core fork pin (commits b06b52f
    + be13f25) switching to a direct git ref, which the dependency-shape test
    does not yet account for. Live-wire AC-1 / AC-6 deferred to operator per
    the task body.
---

# Narrow forge_subscriber from `pipeline.>` (Option A) to explicit lifecycle subjects (Option B)

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Mode:** task-work (TDD) | **Complexity:** 2/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md) — Addendum 2, "F010.D-jarvis — Option A widening to `pipeline.>` causes JetStream workqueue consumer conflict"
**ADR/DDR:** DDR-030 (CLI between-prompt notifications), DDR-027 (ephemeral push consumer / deliver_policy)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-04 late afternoon, correlation_id `dfad8e7f-92af-4b5f-896f-ca75ad8343bf`
**Predecessor:** [TASK-FRR-F010D](../../completed/feat-jarvis-internal-001-followups/TASK-FRR-F010D-widen-forge-subscriber-subject-filter.md) — completed; renderer / payload-discriminator / source-id-gate work all stays in place; only the subject filter is amended here. The `b` suffix is the existing convention for follow-up tasks on the same scope (cf. `TASK-FORGE-FRR-001b` in the forge repo).

## TL;DR

TASK-FRR-F010D shipped the right rendering / payload-handling work but the wrong subject filter (Option A — `pipeline.>`). Option A overlaps with `forge-serve`'s `pipeline.build-queued.>` filter on the **workqueue-retention** PIPELINE stream, and JetStream's workqueue policy forbids overlapping filters across consumers — so the subscriber fails to bind on every boot. This task switches the filter to Option B (the explicit four-subject set excluding `build-queued`), which has the same rendering coverage with no overlap.

## Symptom (verbatim from RESULTS Addendum 2)

Boot log line emitted on every late-afternoon rerun start:

```json
{"error_class": "BadRequestError",
 "error": "nats: BadRequestError: code=400 err_code=10100 description='filtered consumer not unique on workqueue stream'",
 "event": "jarvis_forge_subscriber_start_failed", "level": "warning",
 "logger": "jarvis.infrastructure.lifecycle",
 "timestamp": "2026-05-04T12:22:51.515049Z"}
```

The success log lines `forge_notifications_subscribed` and `jarvis_forge_subscriber_bound_session_manager` from the morning rerun are **absent** from the late-afternoon rerun — direct confirmation that the subscriber never started. Confirm via consumer ls: `nats consumer ls PIPELINE` shows only `forge-serve`; jarvis's `forge-subscriber` consumer never appeared because it never bound.

## Why (root cause analysis)

1. The PIPELINE stream is workqueue-retention (`retention=workqueue` per the canonical `nats-infrastructure` provisioning).
2. Workqueue streams enforce that **every consumer's subject filter must be non-overlapping** with every other consumer's filter — otherwise JetStream rejects the bind with `err_code=10100`.
3. The existing `forge-serve` durable consumer (forge daemon) already filters `pipeline.build-queued.>` on PIPELINE.
4. TASK-FRR-F010D widened jarvis's `forge_subscriber` filter to `pipeline.>` (which is a **superset** of `pipeline.build-queued.>`) — so the new bind overlaps with the existing forge-serve consumer's filter, and JetStream rejects.
5. The original TASK-FRR-F010D task body recommended Option A on cheapness grounds and warned about non-lifecycle traffic noise but **did not anticipate the workqueue overlap rule** — that's the blind spot this task fills.

## The Option B fix

The four lifecycle subjects (`pipeline.build-started.>`, `pipeline.stage-complete.>`, `pipeline.build-complete.>`, `pipeline.build-failed.>`) are **disjoint** from `pipeline.build-queued.>` — so a multi-subject filter consisting of just those four is non-overlapping with `forge-serve`'s filter, and JetStream will accept the bind.

Two implementation shapes inside Option B (both viable; recommend the first):

- **B1 (recommended): one consumer with multi-subject filter.** JetStream's `ConsumerConfig.filter_subjects` (plural) supports a list. Single bind, single consumer record. Minimal code change.
- **B2: four separate consumers.** One per subject. More boilerplate, higher consumer count, but each filter is trivially exact. Use only if `filter_subjects` (plural) doesn't work in the version of `nats-py` we ship.

## Implementation site

- `src/jarvis/infrastructure/forge_notifications.py` — read it now to confirm the layout. Identify:
  - The helper that currently returns the filter — TASK-FRR-F010D renamed it `_get_stage_complete_subject` → `_get_pipeline_subject` returning `Topics.Pipeline.ALL` (see `src/jarvis/infrastructure/forge_notifications.py:372-392`). Either rename it again to `_get_lifecycle_subjects` (returns a list) or keep the name and change the return value (list of 4 strings). Update the docstring to record the workqueue-overlap rationale (one-line note).
  - The `start()` subscribe call site that consumes the helper (`src/jarvis/infrastructure/forge_notifications.py:479-521`). Update from a single-subject `js.subscribe(pipeline_subject, ...)` call to either:
    - **B1:** a multi-subject consumer using `nats.js.api.ConsumerConfig(filter_subjects=[...])` passed via `js.subscribe(..., config=...)` (or the equivalent push-consumer creation API on the version of `nats-py` we ship), or
    - **B2:** four `js.subscribe(...)` calls collected into `self._subscriptions: list`, each calling back to `self._on_message`. `stop()` then iterates the list and `unsubscribe()`-s each.
  - Update the `forge_notifications_subscribed` INFO log to report `subjects=[...]` (a list field) rather than `subject="pipeline.>"`.
- `nats_core.Topics.Pipeline` (sibling editable package) — confirm the four subject template constants exist with the expected names (probably `BUILD_STARTED`, `STAGE_COMPLETE`, `BUILD_COMPLETE`, `BUILD_FAILED`). If they don't exist, add them. (One-line additions, mirroring the existing `STAGE_COMPLETE` template.)

## Acceptance Criteria

- [ ] **AC-1 (live-wire, deferred to operator):** `forge_subscriber` binds successfully against the canonical workqueue PIPELINE stream — boot log shows `forge_notifications_subscribed` (with the four subjects listed) and `jarvis_forge_subscriber_bound_session_manager`. The `jarvis_forge_subscriber_start_failed` warning **does not appear**. *Unit-testable equivalent satisfied via AC-2.*
- [x] **AC-2:** Regression test added — `TestStart.test_filter_subjects_disjoint_from_workqueue_overlap` in `tests/test_forge_notifications_subscriber.py` asserts the structural invariant the JetStream broker enforces (filter excludes `pipeline.>` and any `pipeline.build-queued.*` subject). This is the **regression-protection test that would have caught Option A**. The companion `TestStart.test_start_subscribes_with_deliver_policy_all` asserts the filter is exactly the four-subject lifecycle list passed via `ConsumerConfig.filter_subjects`.
- [x] **AC-3:** Existing tests already cover all four subjects: `TestHappyPath` (stage_complete), `TestBuildStartedRouting`, `TestBuildCompleteRouting`, `TestBuildFailedRouting`. Each asserts `ForgeNotification.render_line()` produces a non-empty rendered line. All continue to pass post-fix.
- [x] **AC-4:** Wire-level filter narrower-than-`pipeline.>` invariant covered by `TestStart.test_filter_subjects_disjoint_from_workqueue_overlap` (asserts `pipeline.build-queued.>` not in filter list, no filter under `pipeline.build-queued.*`). The defence-in-depth `source_id != "forge"` gate is also still covered by the existing `TestLifecycleEventDropsOwnPublishes` test.
- [x] **AC-5:** All F010.D-shipped tests (renderer / payload-discriminator / source-id-gate tests from `tests/test_forge_notifications_subscriber.py`) continue to pass — F010.D's renderer/payload work is unchanged; only `_get_pipeline_subject` → `_get_lifecycle_subjects` (returns list) and the `start()` subscribe call site changed.
- [ ] **AC-6 (cross-repo, deferred to operator):** re-run jarvis runbook §6.2+§7 against forge built from a commit including TASK-FORGE-FRR-F010E (or send a synthetic `pipeline.build-failed.FEAT-XXX` publish à la the F010.C verification recipe in the RESULTS Addendum 2). Confirm chat REPL renders at least one `[HH:MM] Forge FEAT-XXX: build-failed (...)` line during the second turn. Capture the new correlation_id in completion notes.

## Files Expected to Change

- `src/jarvis/infrastructure/forge_notifications.py` — `_get_pipeline_subject` helper return value (and possibly rename to `_get_lifecycle_subjects`); `start()` `subscribe(...)` call site; possibly `stop()` if Option B2 is used (subscription becomes a list). ~5-15 lines for B1; ~20-40 lines for B2.
- Possibly `src/nats_core/...` (the sibling editable package) — if the four lifecycle subject template constants don't exist on `Topics.Pipeline`, add them. Trivial.
- `tests/test_forge_notifications_subscriber.py` — extend or add new test class covering AC-2 (workqueue-overlap regression), AC-3 (four-subject coverage), AC-4 (build-queued.* NOT received).

## Implementation Summary

**Outcome:** Shipped Option B (the explicit four-subject lifecycle filter) on
`ForgeNotificationsSubscriber`, replacing TASK-FRR-F010D's Option A widening to
`pipeline.>` that had been rejected by JetStream on every boot
(`err_code=10100 'filtered consumer not unique on workqueue stream'`).

**Approach:**

- Renamed `_get_pipeline_subject() -> str` to `_get_lifecycle_subjects() -> list[str]`
  in `src/jarvis/infrastructure/forge_notifications.py`. The helper now derives the
  four wildcards (`pipeline.{build-started,stage-complete,build-complete,build-failed}.>`)
  by substituting `>` for `{feature_id}` on the canonical
  `nats_core.Topics.Pipeline.{BUILD_STARTED,STAGE_COMPLETE,BUILD_COMPLETE,BUILD_FAILED}`
  templates — same lazy-import pattern as the pre-F010D
  `_get_stage_complete_subject` helper, preserving the schema-import-isolation
  invariant.
- Updated `start()` to pass the multi-subject filter via
  `nats.js.api.ConsumerConfig(filter_subjects=[...])` (Option B1: single consumer,
  multi-subject filter). The positional `subject` arg is the first lifecycle
  subject, used only for `js.subscribe`'s stream lookup
  (`find_stream_name_by_subject`); when `config.filter_subjects` is set,
  `js.subscribe` ignores it for filter purposes per the nats.js.client source
  (`if not config.filter_subjects: config.filter_subject = subject`).
- Updated the `forge_notifications_subscribed` log line from `subject="pipeline.>"`
  to `subjects=<list of 4>` so the boot log makes the disjoint filter visible.
- Updated module-level comment block, `_get_lifecycle_subjects` docstring, and
  `start()` docstring with the workqueue-overlap rationale (`err_code=10100`,
  why the filter is narrow, why the four subjects are disjoint from
  `pipeline.build-queued.>` by construction).
- Added `TestStart.test_filter_subjects_disjoint_from_workqueue_overlap` regression
  test in `tests/test_forge_notifications_subscriber.py` — asserts the structural
  invariant the JetStream broker enforces (filter excludes `pipeline.>`, excludes
  `pipeline.build-queued.>`, no filter starts with `pipeline.build-queued.`). This
  is the test that would have caught Option A pre-merge.
- Updated the existing `TestStart.test_start_subscribes_with_deliver_policy_all`
  to assert the new call shape (positional `subject` is one of the four lifecycle
  subjects; `kwargs["config"].filter_subjects` is the four-subject set).
- Updated the docstring-invariant test in
  `tests/test_forge_notifications_docstring.py` to expect the renamed helper
  symbol (matching the F010D-style rename comment pattern).

**Test Results:**

- 93 tests pass on the forge_notifications surface (subscriber + docstring +
  schema). 52 lifecycle/integration/session/end-to-end tests pass (1 skipped,
  unrelated). Coverage on `src/jarvis/infrastructure/forge_notifications.py` is
  89% (183 stmts / 21 miss); the 21 missing lines are pre-existing defensive
  backstops (malformed-JSON drop, hung-broker timeout in `stop()`, debug-log
  branch for unsupported event_type) that were already uncovered before this
  change.
- Two unrelated failures in `tests/test_phase4_dependencies.py` are pre-existing
  — caused by the recent graphiti-core fork pin (commits `b06b52f` + `be13f25`)
  switching `graphiti-core` to a direct git ref, which the dependency-shape test
  does not yet account for.

**Acceptance Criteria:**

- AC-2, AC-3, AC-4, AC-5 satisfied via the test suite (see test results above).
- AC-1 (live-wire boot-log evidence) and AC-6 (cross-repo runbook §6.2+§7
  rerun) deferred to operator per the task body.

**Lessons:**

- The workqueue-retention overlap rule (`err_code=10100 'filtered consumer not
  unique on workqueue stream'`) is a JetStream invariant that bites any
  consumer whose subject filter is a superset of an existing workqueue
  consumer's filter. TASK-FRR-F010D's Option A treated `pipeline.>` as cheap;
  in fact it overlapped with forge-serve's `pipeline.build-queued.>` and was
  rejected on every boot. **General rule:** on a workqueue stream, every
  consumer's filter must be disjoint from every other's, so always prefer
  explicit subject lists (or `filter_subjects` plural) over namespace
  catch-alls.
- nats-py's `js.subscribe` accepts `config=ConsumerConfig(filter_subjects=[...])`
  and ignores the positional `subject` arg for filter purposes when
  `filter_subjects` (plural) is set on the config. The positional arg is still
  used for `find_stream_name_by_subject` lookup, so passing one of the filter
  subjects there avoids hard-coding the stream name.
- The structural-shape regression test (filter excludes `pipeline.>` and
  `pipeline.build-queued.>` subjects) catches Option A regressions without
  needing a live broker — broker-side enforcement encoded as a unit-level
  invariant.

**Files Changed:**

- `src/jarvis/infrastructure/forge_notifications.py` (~30 lines: helper rename
  + return-type change, `start()` ConsumerConfig wiring, log shape, docstrings).
- `tests/test_forge_notifications_subscriber.py` (~70 lines: new
  `_LIFECYCLE_SUBJECTS` constant, updated assertion in
  `test_start_subscribes_with_deliver_policy_all`, new
  `test_filter_subjects_disjoint_from_workqueue_overlap` regression test,
  expanded `TestStart` class docstring).
- `tests/test_forge_notifications_docstring.py` (~12 lines: docstring-invariant
  symbol updated to `_get_lifecycle_subjects` with rename history comment).

## Implementation Notes

- **Why not just re-open TASK-FRR-F010D?** The audit trail. F010D's first pass landed real work (the renderer/payload-discriminator/source_id-gate are all correct). Re-opening would muddy the "completed" status it earned for that work and the runbook re-run evidence. Filing a fresh sibling preserves both: F010D = "renderer/payload work shipped"; F010Db = "subject filter narrowed to avoid workqueue overlap (regression amend)".
- **The workqueue-overlap rule is a NATS / JetStream invariant**, not a forge-specific rule. The same constraint would have caught any other code that tried to bind a `pipeline.>` consumer on PIPELINE while `forge-serve` is up. Worth a one-line note in the helper's docstring once the fix lands so future readers understand why the filter is narrow.
- **DDR-027 deliver_policy** (TASK-FRR-001's reasoning: workqueue retention → `DeliverPolicy.ALL`) is unaffected by this change. The deliver_policy is per-consumer; the filter is per-consumer; both stay valid.
- **No cross-repo block:** this fix lands independently of TASK-FORGE-FRR-F010E (the StructuredTool gap blocking autobuild). Once F010Db lands, the subscriber binds successfully — even on a system where forge can't successfully autobuild yet, jarvis will at least render `build-failed` envelopes from the path-rejection codepath (which is on the wire today per F010.C).
- **Source-id gate stays:** F010D's `envelope.source_id != "forge"` gate inside `_handle_message` (`forge_notifications.py:702-708`) becomes structurally redundant once the filter excludes `pipeline.build-queued.>` (the only legitimate jarvis self-publish), but it's cheap and worth keeping as defence-in-depth against future publishers that mis-set `source_id`.
- **Reproducer for the implementer to validate the fix locally:**
  1. Apply the Option B change.
  2. Boot jarvis chat against the GB10 NATS (`JARVIS_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222`) while `forge-prod` is running with the existing `forge-serve` consumer attached.
  3. Confirm the boot log emits `forge_notifications_subscribed` and `jarvis_forge_subscriber_bound_session_manager` with no warning.
  4. Confirm `nats consumer ls PIPELINE` now shows two consumers: `forge-serve` and the new jarvis `forge-subscriber` (or whatever the durable name is — read `forge_notifications.py` to confirm the name).
  5. Run the synthetic publish recipe from RESULTS Addendum 2 (the `feature_yaml_path: /etc/passwd` envelope) — confirm the chat REPL's second turn now includes a rendered `[HH:MM] Forge FEAT-43DE: build-failed (path outside allowlist)` line.

## References

- **Source-of-truth (jarvis):**
  - `src/jarvis/infrastructure/forge_notifications.py:372-392` — `_get_pipeline_subject()` helper; current value is `Topics.Pipeline.ALL` (= `pipeline.>`); needs to switch to a list of the four lifecycle subject templates.
  - `src/jarvis/infrastructure/forge_notifications.py:479-521` — `start()` method; the `forge_notifications_subscribed` log site is at line 517-521 and the single-subject `js.subscribe(...)` call is at line 510-515.
  - `src/jarvis/infrastructure/forge_notifications.py:702-708` — the `source_id != "forge"` gate (defence-in-depth; stays).
  - `src/jarvis/infrastructure/lifecycle.py` (around line 654-675 per F010D's research notes) — where the subscriber is instantiated and the warning log line `jarvis_forge_subscriber_start_failed` is emitted.
- **Source-of-truth (sibling repo):**
  - `nats_core.Topics.Pipeline` constants module (path TBD by the implementer) — confirm or add `BUILD_STARTED`, `STAGE_COMPLETE`, `BUILD_COMPLETE`, `BUILD_FAILED` template constants.
- **Source-of-truth (operational):**
  - `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md` — Addendum 2, specifically the F010.D regression subsection (boot log + consumer-ls evidence + workqueue-overlap root-cause writeup).
- **Sibling tasks:**
  - `../../completed/feat-jarvis-internal-001-followups/TASK-FRR-F010D-widen-forge-subscriber-subject-filter.md` — the predecessor; the renderer / payload-discriminator / source-id-gate work it shipped is correct and stays in place.
  - `../../completed/feat-jarvis-internal-001-followups/TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md` — introduced the `forge_subscriber` wiring this fix amends; also revised DDR-027 to `DeliverPolicy.ALL` for workqueue compatibility (same DDR informs the workqueue-overlap rule this task fixes).
  - `../../../../forge/tasks/completed/.../TASK-FORGE-FRR-F010C-thread-inbound-correlation-id-on-outbound-envelopes.md` — the forge-side correlation_id threading; fully landed; once this jarvis fix lands, F010.C's threading delivers user-visible value (rendered notifications carry the right `correlation_id` and route to the right session).
  - `../../../../forge/tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-F010E-...md` (sibling task being filed in parallel) — forge-side `StructuredTool.start_async_task` fix; its closure is what unblocks the full per-stage envelope sequence (`build-started + stage-complete*N + build-complete`); this jarvis F010Db fix is independent and lands first.
- **DDRs:** DDR-027 (ephemeral push consumer; revised to `DeliverPolicy.ALL` per TASK-FRR-001 — same workqueue-retention reasoning that surfaces the overlap rule this task fixes), DDR-028 (LRU correlation-cap), DDR-029 (routing-history edge — stage-complete-only; unaffected), DDR-030 (CLI between-prompt notifications — the user-visible contract this task unblocks).
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-04 late afternoon rerun.
- **correlation_id:** `dfad8e7f-92af-4b5f-896f-ca75ad8343bf`.
