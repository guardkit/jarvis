# Follow-up task drafts — autobuild-runner wireup

**Source:** [RESULTS-jarvis-forge-autobuild-version-endpoint-demo-2026-05-14-preflight.md](RESULTS-jarvis-forge-autobuild-version-endpoint-demo-2026-05-14-preflight.md)
**Repo target:** all four tasks land in **`forge`** (`~/Projects/appmilla_github/forge/tasks/backlog/`)
**Status:** DRAFT — not yet converted to GuardKit task files via `/task-create`. Use these as the seed for the actual task files (you may want to adjust IDs, complexity, AC numbering to match your conventions).

---

## TASK-ABW-002 — Plumb `repo`/`branch`/`feature_yaml_path` through `dispatch_autobuild_async`

**Severity:** high (removes a hardcoded env-var single-repo limit)
**Complexity:** 3
**Estimated:** 60-90 min
**Depends on:** none (TASK-ABW-001 in place)
**Implementation mode:** direct

### Context

TASK-ABW-001 (FEAT-ABW1, commit `2188342`) wired the autobuild_runner subagent's `_node_running_wave` to spawn `guardkit autobuild feature <feature_id> --fresh --verbose` as a subprocess with `cwd=<resolved_repo_path>`. The repo is resolved from `payload.get("repo")` — `payload` is the JSON dict extracted from the launch description.

The upstream dispatch path (`forge.cli.serve.dispatcher` closure → `forge.pipeline.dispatchers.autobuild_async.dispatch_autobuild_async`) currently constructs the launch payload from only three fields:

```python
# forge/pipeline/dispatchers/autobuild_async.py:498
launch_payload: dict[str, Any] = {
    "build_id": build_id,
    "feature_id": feature_id,
    "correlation_id": correlation_id,
    "context_entries": serialised_context,
    "lifecycle_emitter": lifecycle_emitter,
}
```

`repo`/`branch`/`feature_yaml_path` from the inbound `BuildQueuedPayload` envelope are dropped at the dispatcher closure layer:

```python
# forge/cli/serve.py:460-475
async def dispatcher(
    *,
    build_id: str,
    feature_id: str,
    rationale: str = "",
) -> Any:
    return await dispatch_autobuild_async(
        build_id=build_id,
        feature_id=feature_id,
        correlation_id=feature_id,  # <- placeholder
        forward_context_builder=forward_context_builder,
        ...
    )
```

Hotfix in commit `7006c7d` patches this by reading `FORGE_DEFAULT_REPO` env var in `_resolve_repo_path` when `payload.repo` is missing. That single-host hardcoded fallback is acceptable for the 2026-05-16 demo but doesn't scale (multi-repo, multi-org).

### Scope

1. Widen `dispatch_autobuild_async`'s signature to accept `repo: str`, `branch: str | None = None`, `feature_yaml_path: str | None = None`.
2. Add these to `launch_payload` so the autobuild_runner's `_extract_launch_payload` sees them.
3. Widen the dispatcher closure in `forge.cli.serve.build_supervisor.dispatcher` to forward the same fields from the supervisor's tool-call arguments.
4. Update the supervisor's `dispatch_autobuild` tool schema to expose `repo`/`branch`/`feature_yaml_path` so the reasoning model passes them through from the `BuildQueuedPayload` context.
5. Update unit tests covering the dispatcher closure + `dispatch_autobuild_async` to assert the new fields land on `launch_payload`.
6. Remove the `FORGE_DEFAULT_REPO` env-var fallback from `autobuild_runner._resolve_repo_path` (now unnecessary). Keep the env-var name reserved for the rollback path; log a DEPRECATION warning if it's set.
7. Update the version-demo runbook §0.6 to drop `FORGE_DEFAULT_REPO` from the required sidecar env vars.

### Acceptance criteria

- **AC-ABW-002-01:** `dispatch_autobuild_async` accepts `repo`/`branch`/`feature_yaml_path` and writes them onto `launch_payload`. Existing tests still pass.
- **AC-ABW-002-02:** Dispatcher closure in `serve.py` forwards `repo`/`branch`/`feature_yaml_path` from its tool-call args.
- **AC-ABW-002-03:** Supervisor's `dispatch_autobuild` tool schema declares the three new params.
- **AC-ABW-002-04:** Wire-mediated smoke test against FEAT-9E59 with `FORGE_DEFAULT_REPO` unset succeeds: `autobuild_runner` logs the resolved repo from `payload.repo`, not the env-var fallback.
- **AC-ABW-002-05:** Runbook §0.6 updated to remove the `FORGE_DEFAULT_REPO` requirement.

### Out of scope

- Multi-repo allowlist policy (the repo path must still resolve inside `forge_config.permissions.filesystem.allowlist`; that part stays).
- The bridge thread_id mismatch (TASK-ABW-003) and langgraph backend persistence (TASK-ABW-004) — separate tasks.

---

## TASK-ABW-003 — Bridge identity provider returns stale thread_ids

**Severity:** high (root cause of the JetStream redelivery loop on any fast-completing run)
**Complexity:** 5 (investigation-heavy)
**Estimated:** 2-4 hours
**Depends on:** none
**Implementation mode:** spike-first

### Context

During the 2026-05-14 wire-mediated smokes (FEAT-EC3C), forge-prod's `_async_tasks_identity_provider` repeatedly searched for thread_id `019e1ffa-68de-7661-85e1-2443ba0a3532` on the sidecar — a thread that **never existed**. Every actual sidecar run was assigned a different thread_id by langgraph (`019e276f-…`, `019e2785-…`, `019e2788-…`). The mismatch caused:

```
WARNING: failed to resolve run_id for feature_id=FEAT-EC3C
         thread_id=019e1ffa-68de-7661-85e1-2443ba0a3532
         (Thread with ID 019e1ffa-68de-7661-85e1-2443ba0a3532 not found)
```

After 3 retries the bridge observer exits without observing the terminal snapshot, leaves the message un-acked, and JetStream redelivers every ~30 s. Each redelivery hits the dispatcher's `duplicate active build` dedup and skips dispatch, so no new thread is created.

The stale thread_id `019e1ffa-…` persisted across multiple forge-prod restarts AND a sidecar restart — strongly suggests it's stored on disk (likely in forge-state SQLite `stage_log` from an earlier session) and the identity provider is reading it from there rather than from the live dispatch.

### Hypotheses

1. **`stage_log` row carries a thread_id from a stale (pre-current-session) dispatch.** The identity provider may be selecting the wrong row, or the row may not be updated when the in-memory langgraph store rotates.
2. **Race between `astart_async_task` returning the thread_id and `stage_log` upsert.** If the upsert lags, the bridge might read an empty/old `thread_id`.
3. **`pending-FEAT-EC3C` placeholder pattern.** The bridge log shows `attach feature_id=FEAT-EC3C thread_id=pending-FEAT-EC3C run_id=pending-FEAT-EC3C` — the placeholder is supposed to be replaced once `astart_async_task` resolves. If the replacement uses the wrong key, the placeholder might never get updated.

### Scope

1. **Spike (investigation):** trace the lifecycle of the thread_id in `stage_log` across one full dispatch attempt: pre-dispatch placeholder → post-`astart_async_task` upsert → bridge observer attach. Identify where the stale `019e1ffa-…` is coming from.
2. **Fix:** depending on root cause, either purge stale `stage_log` rows on dispatch, fix the upsert key, or change the bridge to query by `(build_id, feature_id, correlation_id)` rather than thread_id.
3. **Regression test:** a focused integration test that completes a fake `autobuild_runner` run in < 100 ms and asserts the bridge ack-s the message.

### Acceptance criteria

- **AC-ABW-003-01:** Root cause documented in `forge/docs/decisions/` (or equivalent).
- **AC-ABW-003-02:** A fresh wire-mediated dispatch for `feature_id=FEAT-EC3C` (or any other id) returns a snapshot via the bridge regardless of how stale the prior `stage_log` rows are.
- **AC-ABW-003-03:** The "Thread with ID … not found" 404 loop is eliminated for runs that successfully reach a terminal node.
- **AC-ABW-003-04:** Regression test exercises a sub-200 ms run that gets acked by the bridge (proves the fix isn't dependent on long run windows).

### Out of scope

- Persistent langgraph backend (TASK-ABW-004) — orthogonal fix path; TASK-ABW-003 should resolve the identity provider regardless of backend choice.

---

## TASK-ABW-004 — Langgraph in-memory backend evicts thread state on run end

**Severity:** high (forces the bridge into post-run fetch race; underlies TASK-ABW-003's symptom)
**Complexity:** 5
**Estimated:** 1-2 days (depends on path chosen)
**Depends on:** TASK-ABW-003 should land first so we can tell which symptom each fix solves
**Implementation mode:** plan-first (architectural decision)

### Context

The sidecar runs `langgraph dev --allow-blocking` with the bundled in-memory backend. Thread + run state is evicted shortly after a graph reaches a terminal node — for runs that complete in tens of ms, the bridge's `_observer_loop` and its `_run_state_source` fetch-on-empty fallback both 404 because the thread is gone before either subscribes.

The pre-existing run_state_source.py comment acknowledges this:

> placeholder-body run finished in ~16 ms before the bridge could subscribe

That comment refers to the original stub `_node_running_wave`. Even after TASK-ABW-001 lands a real subprocess call, runs that fast-fail on payload validation (the FEAT-EC3C-style failure) re-trigger the same race.

### Decision needed

Two paths:

**Path A — Persistent backend.** Move the langgraph runtime to a persistent backend (postgres, sqlite, or langgraph's own checkpoint backend). Threads survive across run completion; the bridge can fetch terminal snapshots reliably.

**Path B — Bridge observes the live transition stream rather than post-run fetch.** The state-channel writes inside the runner (`_snapshot_update` / `_update_state`) emit deltas synchronously during the run. The bridge can attach to that stream pre-dispatch and observe each transition without ever needing a post-run fetch.

Path A is the langgraph-canonical fix; Path B avoids the persistence dependency but requires bridge refactor.

### Scope (TBD pending decision)

If Path A:
1. Pick backend (sqlite is fast; postgres if we want production parity).
2. Configure `langgraph dev` / `langgraph.json` for the chosen backend.
3. Update sidecar boot in the version-demo runbook §0.6.
4. Verify thread state persists for ≥ 5 minutes post-terminal.

If Path B:
1. Refactor `lifecycle_bridge.observer` to subscribe before dispatch and route on live state-channel events.
2. Drop or simplify the `run_state_source` fetch-on-empty fallback.
3. Update tests.

### Acceptance criteria

- **AC-ABW-004-01:** A fast-failing (sub-200 ms) run emits a `pipeline.build-failed.*` envelope within 5 s of the terminal node firing — NOT after the 5-min deadline timer.
- **AC-ABW-004-02:** JetStream redelivery loop is eliminated for ALL run shapes (fast-fail, fast-success, long-running success).
- **AC-ABW-004-03:** No regression to long-running (≥ 5 min) builds.

### Out of scope

- TASK-ABW-003's identity-provider fix is independent; could land before or after.

---

## TASK-ABW-005 — Coach's SDK test execution wrapper errors before approving

**Severity:** low (cosmetic — Coach approves regardless; tests actually pass)
**Complexity:** 2
**Estimated:** 30-60 min
**Depends on:** none
**Implementation mode:** direct

### Context

The 2026-05-14 standalone preflight (`guardkit autobuild feature FEAT-9E59 --fresh --verbose`) logged this sequence around Coach validation:

```
INFO:  Starting Coach validation for TASK-VER-001 turn 1
WARNING: claude_agent_sdk._internal.query: Fatal error in message reader:
         Command failed with exit code 1 (exit code: 1)
ERROR: guardkit.orchestrator.quality_gates.coach_validator:
       SDK coach test execution failed (error_class=Exception):
       Command failed with exit code 1 (exit code: 1)
INFO:  Coach approved TASK-VER-001 turn 1
```

The Coach's checkpoint payload recorded `tests: pass, count: 0` — meaning the wrapper-driven test run reported zero tests executed (because the wrapper errored), yet Coach treated this as "approved". When `pytest -q` is run directly against the same worktree afterwards: **150 passed, 8 failed** (failures are pre-existing DB-connection issues unrelated to FEAT-9E59).

So: the *code* is fine. The Coach wrapper's SDK invocation has a transport issue that causes test execution to fail silently before any test discovery happens. Coach then approves on whatever the Player turn 1 produced.

### Hypotheses

1. **Subprocess spawn failure in `coach_validator`'s claude_agent_sdk path.** Possibly env-var inheritance, working directory, or sandboxing issue.
2. **The wrapped command itself fails to find/launch pytest.** A `cwd` or `sys.path` mismatch when running through the SDK transport.

### Scope

1. Reproduce the failure: run the standalone preflight, isolate the Coach wrapper's claude_agent_sdk call.
2. Identify the root cause (subprocess output capture should reveal the underlying exit-1 reason).
3. Either fix the wrapper or make Coach's approval *conditional* on a real `tests_run > 0`.
4. If Coach should fail the turn when tests don't execute, document that change explicitly — operators currently rely on Coach approval being equivalent to "Player's claims verified".

### Acceptance criteria

- **AC-ABW-005-01:** Root cause of "Command failed with exit code 1" identified and documented.
- **AC-ABW-005-02:** Either (a) fix lands and a successful Coach turn now reports `tests_run > 0` AND the underlying tests actually executed, or (b) Coach refuses to approve a turn when `tests_run == 0`.
- **AC-ABW-005-03:** Standalone preflight for FEAT-9E59 produces a Coach checkpoint with `tests: pass, count: N` where N > 0.

### Out of scope

- Fixing the underlying 8 pre-existing test failures (DB connection refused on 127.0.0.1:5432). Those are environment setup issues, not FEAT-9E59-related.

---

## TASK-ABW-006 — Forge lifecycle events share a workqueue stream; jarvis can't subscribe

**Severity:** high (notification drain into the chat surface is 100% broken)
**Complexity:** 3
**Estimated:** 2-4 hours
**Depends on:** none
**Implementation mode:** plan-first (a stream-topology decision precedes the change)
**Repo target:** spans `nats-infrastructure` (stream/consumer config) and `forge`
(lifecycle-bridge publish target); minor or no change in `jarvis`.

### Context

`jarvis serve-nats` (the OpenWebUI-facing gateway) is supposed to subscribe to
forge lifecycle events — `pipeline.build-started.>`, `pipeline.stage-complete.>`,
`pipeline.build-complete.>`, `pipeline.build-failed.>` — via
`ForgeNotificationsSubscriber`, so build progress drains back into the chat
turn (`ForgeNotification.render_line()`).

On the 2026-05-15 demo host this subscription **fails at every serve-nats
startup**:

```
jarvis_forge_subscriber_start_failed
nats: BadRequestError: code=400 err_code=10100
  description='filtered consumer not unique on workqueue stream'
```

Root cause: the `PIPELINE` JetStream stream is a **workqueue**-retention
stream. Workqueue streams forbid overlapping filtered consumers — each message
is delivered to exactly one consumer. `forge-prod` already owns the
`forge-serve` consumer on `PIPELINE`; jarvis's attempt to add a second
filtered consumer is rejected. The subscriber soft-fails (DDR-021) and
`forge_subscriber` is set to `None`, so **every chat turn logs
`notifications_drained: 0`** — no forge event ever reaches the chat.

This worked on 2026-05-13 (`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`
recorded `notifications_drained=2`). It regressed sometime after — either
`PIPELINE` was switched to workqueue retention, or `forge-serve`'s filter
subject was widened to overlap the lifecycle subjects.

Note this is **distinct from** the bridge fast-fail bug (TASK-ABW-003/004):
ABW-003/004 is about forge-prod *publishing* lifecycle envelopes late/batched;
ABW-006 is about jarvis being structurally unable to *consume* them at all.
Both must be fixed for live chat notifications to work.

### Decision needed

Lifecycle/notification events should not share a workqueue stream with the
`build-queued` work items. Options:

**Path A — dedicated notifications stream (preferred).** Route
`pipeline.build-started/stage-complete/build-complete/build-failed` to a
separate stream with `limits` or `interest` retention (multiple overlapping
consumers allowed). An idle `NOTIFICATIONS` stream already exists on the host
and looks built for exactly this. `pipeline.build-queued.>` stays on the
`PIPELINE` workqueue (its once-only dispatch semantics are correct).

**Path B — change `PIPELINE` retention.** Switch `PIPELINE` to `interest`/
`limits` retention so multiple filtered consumers are allowed. Simpler config
change but loses the workqueue once-only delivery guarantee that the
build-queued dispatch path may rely on — needs checking against the
forge-prod consumer's assumptions.

Path A is the cleaner separation of concerns.

### Scope (Path A)

1. Confirm the `NOTIFICATIONS` stream's subjects/retention; decide whether to
   reuse it or add a `LIFECYCLE` stream.
2. Update forge's lifecycle bridge to publish `build-started/stage-complete/
   build-complete/build-failed` to the notifications stream's subject space
   (may just be a stream-binding change if subjects stay `pipeline.*`, or a
   subject rename).
3. Point jarvis's `ForgeNotificationsSubscriber` (`_get_lifecycle_subjects`)
   at the new stream/subjects.
4. Leave `pipeline.build-queued.>` on `PIPELINE`.
5. Verify end-to-end: a wire-mediated build drains `notifications_drained >= 1`
   into a serve-nats chat turn.

### Acceptance criteria

- **AC-ABW-006-01:** `jarvis serve-nats` startup logs `jarvis_forge_subscriber_started`
  and `forge_notifications_subscribed` — no `forge_subscriber_start_failed`.
- **AC-ABW-006-02:** A wire-mediated FEAT-9E59 build produces at least one
  chat turn with `notifications_drained >= 1`.
- **AC-ABW-006-03:** `pipeline.build-queued.>` dispatch still works — forge-prod
  consumes and builds (no regression to the queue path).
- **AC-ABW-006-04:** The stream topology (which stream carries which subjects,
  retention rationale) is documented in `nats-infrastructure`.

### Out of scope

- The bridge fast-fail / batched-envelope behaviour (TASK-ABW-003/004) — a
  separate fix; ABW-006 only restores jarvis's ability to *consume* lifecycle
  events.
