---
complexity: 3
created: 2026-05-01 00:00:00+00:00
dependencies: []
discovered_on_machine: GB10 (promaxgb10-41b1)
discovered_on_date: 2026-05-01
discovered_via_correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
estimated_minutes: 60
feature_id: FEAT-JARVIS-INTERNAL-001-FRR
id: TASK-FRR-003
implementation_mode: task-work
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md
priority: medium
status: in_review
tags:
- jarvis
- feat-jarvis-internal-001-followups
- ddr-019
- ddr-029
- routing-history
- soft-fail
- observability
task_type: bugfix
title: DDR-019 trace-offload — autocreate ~/.jarvis/traces and stop silently dropping traces on the floor
updated: 2026-05-01 00:00:00+00:00
wave: 1
---

# DDR-019 trace-offload directory autocreate + non-silent drop

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Wave:** 1 | **Mode:** task-work (TDD) | **Complexity:** 3/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — phase 8.3 (local trace offload — ⚠️ none written)
**ADR/DDR:** DDR-019 (Graphiti soft-fail — local trace offload), DDR-029 (`JarvisRoutingHistoryEntry` payload shape)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-01, correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`

## Description

With `JARVIS_GRAPHITI_ENDPOINT` unset, jarvis takes the DDR-019 soft-fail offload path — graphiti is unreachable, so the routing-history writer should fall back to writing the trace JSON locally to `${JARVIS_TRACES_DIR}/<correlation_id>.json` (default `~/.jarvis/traces/`).

During the 2026-05-01 first real run on the GB10, the chat log emitted:

```
{"event": "routing_history_write_failed", ...}
```

for the FEAT-43DE queue. But `~/.jarvis/traces/` did not exist on the host (verified post-run: `ls ~/.jarvis/traces/` → `No such file or directory`) and **no file was written** — the trace was silently dropped on the floor. The DDR-019 soft-fail path appears to drop the trace when both `graphiti_endpoint` is `None` AND no traces dir is provisioned, rather than autocreating the default.

This task makes the soft-fail path actually soft-fail safely: `mkdir -p` the configured traces dir if it doesn't exist, write the trace, and if **both** Graphiti and the local offload fail, emit a clear distinct log event documenting the offload destination and both error paths — never silently drop.

## Acceptance Criteria

- [ ] **TDD red phase.** A new unit/integration test (e.g. `tests/test_routing_history_offload.py::TestSoftFailOffload`) is written and FAILS against the current `main` branch. Specific test cases:
  - With `JARVIS_GRAPHITI_ENDPOINT` unset and `JARVIS_TRACES_DIR=<tmp_path>/traces` (where `<tmp_path>/traces` does NOT exist yet), after a successful `queue_build` for `FEAT-XYZ` with `correlation_id=<uuid>`, the file `<tmp_path>/traces/<uuid>.json` exists with a valid `JarvisRoutingHistoryEntry` payload that round-trips through `JarvisRoutingHistoryEntry.model_validate_json(...)`.
  - With `JARVIS_GRAPHITI_ENDPOINT` unset and the traces dir un-creatable (e.g. parent dir is read-only), the log emits a clear `routing_history_offload_failed` (or similar) event with both error paths reported (graphiti = unreachable, local = `PermissionError: ...`). The `routing_history_write_failed` line is no longer the silent terminal state.
  Commit the failing tests on a single commit before the fix lands.
- [ ] At startup (or at first-write — implementer's choice; document the choice in code), the routing-history writer calls `Path(traces_dir).mkdir(parents=True, exist_ok=True)` if the configured `JARVIS_TRACES_DIR` doesn't exist. Failures are caught and reported (not raised) — the writer keeps trying on subsequent writes if the failure was transient.
- [ ] When graphiti is unreachable AND the traces dir exists or was just created, write the trace JSON to `<traces_dir>/<correlation_id>.json` with the canonical `JarvisRoutingHistoryEntry` payload per DDR-029. The payload must round-trip cleanly through `model_validate_json(...)`.
- [ ] The current `routing_history_write_failed` log line is split into two distinct events:
  - **`routing_history_offloaded_locally`** — graphiti unreachable, local write succeeded; payload includes `correlation_id`, `traces_dir`, `path`, and the graphiti error.
  - **`routing_history_offload_failed`** — both graphiti AND local write failed; payload includes `correlation_id`, `traces_dir`, the graphiti error, AND the local-write error. This is the new "the trace is genuinely lost" event — operationally distinct from the success-with-offload case.
- [ ] **Integration test green phase.** All tests now pass — the unset-graphiti path produces a real on-disk file, and the both-paths-failed case produces the structured `routing_history_offload_failed` event with both error paths.
- [ ] Existing graphiti-soft-fail unit tests in `tests/` are preserved or extended; no test regressions.
- [ ] When graphiti **is** reachable and writes succeed, no offload file is written (verify the happy path is unchanged).
- [ ] `mypy src/jarvis/infrastructure/routing_history.py` and `ruff check src/jarvis/infrastructure/routing_history.py` remain at zero violations.
- [ ] Add a one-line note to `.env.example` near `JARVIS_TRACES_DIR` clarifying that the dir is autocreated on first use; default is `~/.jarvis/traces/`.

## Files Expected to Change

- `src/jarvis/infrastructure/routing_history.py` — the DDR-019 soft-fail offload path; add the `mkdir -p` and the dual-event logging.
- `tests/test_routing_history_offload.py` — **NEW** TDD red-then-green test covering the autocreate path, the happy path, and the both-paths-failed path.
- `tests/test_routing_history.py` (or equivalent existing file) — preserve / extend the existing soft-fail tests.
- `.env.example` — add the `JARVIS_TRACES_DIR` autocreate note.

## References

- **Parent runbook results:** [`docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
  - Per-phase row 8.3: *"Chat log shows `routing_history_write_failed` but no file landed in `~/.jarvis/traces/` (directory does not exist). The DDR-019 soft-fail path appears to drop on the floor when both `graphiti_endpoint` is `None` AND no traces dir is provisioned, rather than autocreating the default `~/.jarvis/traces/`. Jarvis gap-fold candidate"*.
  - Recommended follow-up #6.
- **Source files:** `src/jarvis/infrastructure/routing_history.py` (DDR-019 soft-fail offload path; DDR-029 trace shape).
- **DDRs:** DDR-019 (Graphiti soft-fail — local trace offload), DDR-029 (`JarvisRoutingHistoryEntry` payload shape).
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-01.
- **correlation_id:** `a58ec9a7-27c6-485a-beac-e18675639a10`.
- **Evidence:** `/tmp/runbook-evidence/phase6-7-chat-v2.log` (search for `routing_history_write_failed`).

## Notes

- The split into two log events (`routing_history_offloaded_locally` vs `routing_history_offload_failed`) is the operationally important change — the current single-event design conflates "I worked around graphiti being down" with "I genuinely lost the trace", and operators need to triage those differently.
- "Autocreate at startup vs. first-write" is the implementer's call. First-write has the advantage that a misconfigured `JARVIS_TRACES_DIR` doesn't crash startup; startup has the advantage that the failure surfaces before any traces are written. Pick one and document the rationale in a code comment.
- The `model_validate_json` round-trip assertion in the test is non-negotiable — DDR-029 is the canonical schema; if the offload format drifts away from it, downstream graphiti-rehydration tooling breaks.
- Out of scope: building the graphiti-rehydration tool that reads `~/.jarvis/traces/*.json` and replays them into Graphiti once it's reachable again. That's a separate (future) feature; this task only makes sure the files exist to be replayed.
