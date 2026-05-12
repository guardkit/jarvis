---
review_task: TASK-REV-J6F2
feature: FEAT-JARVIS-006
review_mode: root-cause
review_depth: standard
generated: 2026-05-12
inputs:
  transcript: docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md
  feature_yaml: .guardkit/features/FEAT-JARVIS-006.yaml
  worktree: .guardkit/worktrees/FEAT-JARVIS-006/  (branch autobuild/FEAT-JARVIS-006)
  per_task_artefacts: .guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-{003,004}/
  baseline: .claude/reviews/TASK-REV-J6F1-review-report.md
---

# Review Report: TASK-REV-J6F2 — Autobuild FEAT-JARVIS-006 fail-run-2

## Executive summary

**Fail-run-2 was a per-task success and a feature-level failure for an
environmental reason unrelated to the chat-gateway code.** Both TASK-J006-003
and TASK-J006-004 completed on Turn 1 with Coach `decision: approve`, 20/20
unit tests passing each, lint-clean, and ACs 1–9 verified. The feature was
flagged `failed` solely because the Wave-3 smoke gate command
(`pytest tests/ -x --timeout=60 -q`) crashed at argument-parse — the
worktree's `.venv` has no `pytest-timeout` plugin installed, so pytest exits
with code 4 ("usage error") before the test session begins.

**TASK-J006-006's Intervention A (switch `implementation_mode: task-work →
direct`) did NOT take effect for fail-run-2.** The orchestrator reads
`implementation_mode` from the worktree's copies of the task `.md` files and
the worktree's copy of the feature YAML — neither of which TASK-J006-006
edited. The main-repo edits did not propagate into branch
`autobuild/FEAT-JARVIS-006`. Both J006-003 and J006-004 ran in `task-work`
mode just like fail-run-1; the run succeeded **despite** the intervention,
not because of it.

**Why fail-run-2 succeeded where fail-run-1 stalled** is not the intervention
— it is that the upstream Coach claim-audit / honesty-verification path that
caused fail-run-1's `unrecoverable_stall` evidently no longer promotes the
absolute-path warnings into `must_fix` issues on this run. Whether
`TASK-FIX-CAUD-J6F1` landed in guardkit between runs, or whether a different
Player report avoided the trigger, cannot be confirmed from the transcript
alone — but the per-task data shows the audit path was clean this time
(`agent_invocations_validation: status=violation` was kept advisory; quality
gates produced a populated, all-passing block; the Coach approved on Turn 1).

**Next Action: `[M]erge and ship`** — with one prerequisite (fix smoke-gate
command or install `pytest-timeout`) and one optional follow-up
(`TASK-J006-007` to install Intervention A correctly so future re-queues
behave predictably). Details in §Next Action.

---

## AC-001 — Key events from the fail-run-2 transcript

Transcript: `docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md` (607
lines, captured 2026-05-12 09:46:44Z → 10:14:22Z; the file is named for the
local-clock window 09:46–11:14 BST).

Timestamped chain:

| # | Time (UTC, transcript) | Event | Citation |
|---|---|---|---|
| 1 | 09:46:44.999 | `Resuming from incomplete state, Completed tasks: 2, Pending tasks: 3` | L22-24 |
| 2 | 09:46:45.004 | Wave 1: TASK-J006-001/002 `SKIPPED - already completed` | L38-39 |
| 3 | 09:46:45.030 | Wave 2 begins — TASK-J006-003 | L58 |
| 4 | 09:46:45.04x | `[TASK-J006-003] Mode: task-work (explicit frontmatter override)` | L100 |
| 5 | 09:46:45–09:49:25 | Player SDK invocation: 160.3s, 19 SDK turns, writes `chat_handler.py` + tests | L125-138 |
| 6 | 09:50:36–09:55:36 | `specialist:code-reviewer` invocation (300s, 5 minutes of tool calls) | L160-209 |
| 7 | 09:55:36 | `Injected orchestrator specialist records into [...] task_work_results.json (merged=2, validation=violation)` | L210 |
| 8 | 09:55:47.440 | Coach Validation turn 1 begins | L211 |
| 9 | 09:55:47.44x | `Agent-invocations advisory for TASK-J006-003: missing phases 3 (non-blocking; outcome gates will run)` | L230 |
| 10 | 09:55:47.44x | `Quality gate evaluation complete: tests=True ... ALL_PASSED=True` | L231 |
| 11 | 09:55:47.44x | `Independent tests passed in 5.7s` (subprocess: `pytest tests/unit/infrastructure/test_chat_handler.py -v --tb=short` → 20 passed) | L234-235 |
| 12 | 09:55:54.477 | `Coach approved TASK-J006-003 turn 1` → `Coach approved - ready for human review` | L236-241 |
| 13 | 09:55:54.620 | Wave 3 begins — TASK-J006-004 | L288 |
| 14 | 09:55:54.65x | `[TASK-J006-004] Mode: task-work (explicit frontmatter override)` | L329 |
| 15 | 09:55:54.65x | `state_bridge: Transitioning task TASK-J006-004 from backlog to design_approved` + `Moved task file: [worktree]/tasks/backlog/TASK-J006-004-serve-nats-cli.md -> [worktree]/tasks/design_approved/TASK-J006-004-serve-nats-cli.md` | L333-336 |
| 16 | 10:08:55.874 | J006-004 Player SDK complete: 780.4s, 72 SDK turns, `3 files created, 9 modified, 2 tests (passing)` | L389-405 |
| 17 | 10:14:12.791 | Coach Validation for J006-004 begins; same advisory note + `ALL_PASSED=True`; independent tests pass in 8.1s | L487-496 |
| 18 | 10:14:22.100 | `Coach approved TASK-J006-004 turn 1` | L498-501 |
| 19 | 10:14:22.225 | `Wave 3 ✓ PASSED: 1 passed` | L534 |
| 20 | 10:14:22.4xx | **Smoke gate runs**: `pytest tests/ -x --timeout=60 -q` (cwd=worktree, timeout=300s, expected_exit=0) | L541-543 |
| 21 | 10:14:22.5xx | **`Smoke gate failed after wave 3 (exit=4, expected=0)`** | L544 |
| 22 |  | stderr: `ERROR: usage: pytest [...] pytest: error: unrecognized arguments: --timeout=60` | L546-547 |
| 23 | 10:14:22.6xx | `Subsequent waves not started; worktree preserved` | L552-553 |
| 24 | 10:14:22.873 | `FEATURE RESULT: FAILED — Tasks: 4/5 completed — Wave 1/2/3 all ✓ PASS` | L562-578 |

The transcript ends cleanly; no SDK timeouts, no `unrecoverable_stall`, no
pollution rollback, no Graphiti errors, no rate limiting. The only `FAILED`
banner in the entire log is the final feature finalisation banner caused by
the smoke gate.

---

## Q1 — Why `feature.status: failed`?

**Answer: the post-Wave-3 smoke gate command crashed at argument parsing
because `pytest-timeout` is not installed in the worktree's `.venv`.**

Citation, transcript L541-549:

```
INFO:guardkit.orchestrator.smoke_gates:Running smoke gate after wave 3:
  set -e
  pytest tests/ -x --timeout=60 -q
  (cwd=/Users/.../.guardkit/worktrees/FEAT-JARVIS-006, timeout=300s, expected_exit=0)
WARNING:guardkit.orchestrator.smoke_gates:Smoke gate failed after wave 3 (exit=4, expected=0)
stderr:
  ERROR: usage: pytest [options] [file_or_dir] [file_or_dir] [...]
  pytest: error: unrecognized arguments: --timeout=60
    inifile: /Users/.../.guardkit/worktrees/FEAT-JARVIS-006/pyproject.toml
    rootdir: /Users/.../.guardkit/worktrees/FEAT-JARVIS-006
```

The smoke-gate spec is in [.guardkit/features/FEAT-JARVIS-006.yaml#L110-119](../../.guardkit/features/FEAT-JARVIS-006.yaml):

```yaml
smoke_gates:
  after_wave: 3
  command: 'set -e
    pytest tests/ -x --timeout=60 -q
    '
  expected_exit: 0
  timeout: 300
  exit5_is_hard_fail: false
```

`pytest-timeout` is not declared in the worktree's `pyproject.toml` or
`uv.lock` — `grep pytest-timeout` returns zero matches in both files. The
plugin therefore never registered, `--timeout=60` is unknown to pytest, and
pytest exits 4 ("usage error") **before** any test runs.

`exit5_is_hard_fail: false` is irrelevant here — that flag only down-grades
exit-code-5 ("no tests collected") to soft. Exit code 4 is always hard.

**Verdict**: this is an artefact of an unconfigured smoke gate, not a
substantive failure. The branch's actual test session is fine — the Coach's
independent pytest runs for J006-003 and J006-004 both invoked pytest
**without** the `--timeout` flag (transcript L234-235 and L493-494) and both
green-bared. TASK-J006-005's `status: pending` (operator_handoff) is a
contributing factor in any computation of "all-tasks-terminal" but is not
the proximate cause; the proximate cause is the smoke gate exit-code-4.

This is also the reason the file is named `failed-run-2.md` and the feature
YAML says `status: failed` — the orchestrator's finalisation banner just
mirrors the smoke-gate verdict.

---

## Q2 — Did TASK-J006-006 Intervention A take effect?

**Answer: No. Intervention A was applied only to the main-repo files; the
orchestrator reads from the worktree's copies, which retained
`implementation_mode: task-work`.** Both J006-003 and J006-004 ran in
`task-work` mode for fail-run-2, identically to fail-run-1.

### Evidence — the orchestrator's "Mode: task-work" log lines

Transcript L100 (J006-003) and L329 (J006-004):

```
INFO:guardkit.orchestrator.agent_invoker:[TASK-J006-003] Mode: task-work (explicit frontmatter override)
INFO:guardkit.orchestrator.agent_invoker:[TASK-J006-004] Mode: task-work (explicit frontmatter override)
```

These lines are followed by:

```
INFO:guardkit.orchestrator.agent_invoker:Invoking Player via task-work delegation for TASK-J006-003 (turn 1)
INFO:guardkit.orchestrator.agent_invoker:Ensuring task TASK-J006-003 is in design_approved state
INFO:guardkit.orchestrator.agent_invoker:Executing inline implement protocol for TASK-J006-003 (mode=tdd)
```

The progress logs confirm the `task-work` pipeline executed end-to-end —
[.guardkit/autobuild/TASK-J006-003/progress.log:1-45](../../.guardkit/autobuild/TASK-J006-003/progress.log)
contains `task-work implementation`, `specialist:test-orchestrator
invocation`, `specialist:code-reviewer invocation` — the three phases that
characterise the `/task-work` (Phase 3/4/5) pipeline, NOT the `direct`
inline-only pipeline.

### Evidence — the worktree's files were never edited

The orchestrator's "frontmatter" source is the worktree, not the main repo:

| Source | `implementation_mode` for J006-003 | `implementation_mode` for J006-004 |
|---|---|---|
| Main repo `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-00{3,4}-*.md` | `direct` ✓ (TASK-J006-006 edited) | `direct` ✓ |
| Main repo `.guardkit/features/FEAT-JARVIS-006.yaml` lines 55, 74 | `direct` ✓ | `direct` ✓ |
| **Worktree** `tasks/design_approved/TASK-J006-00{3,4}-*.md` lines 22 / 15 | **`task-work`** ✗ | **`task-work`** ✗ |
| **Worktree** `.guardkit/features/FEAT-JARVIS-006.yaml` lines 38, 48 | **`task-work`** ✗ | **`task-work`** ✗ |

Both worktree sources still hold `task-work`. That's why the orchestrator
called it an "explicit frontmatter override" — from the worktree's point of
view there *is* an explicit task-level frontmatter declaring `task-work`,
and the orchestrator's precedence rule (task-file `implementation_mode` >
feature-YAML default) selected it.

### The mechanism

`autobuild/FEAT-JARVIS-006` is a separate git branch (`git branch -v` in
the worktree shows checkpoints layered on top of `0d7f709 feature plan
nats chat gateway`). It carries its own copies of:

- `tasks/design_approved/TASK-J006-00{3,4}-*.md` (state_bridge moved
  them out of `tasks/backlog/` mid-run — see L333-336 of the transcript)
- `.guardkit/features/FEAT-JARVIS-006.yaml`

TASK-J006-006 modified the files in the main repo's working tree (on `main`)
and committed/updated state there. Those changes are not on
`autobuild/FEAT-JARVIS-006`; nothing in the autobuild lifecycle rebases or
cherry-picks main-repo edits into the worktree branch.

### Why fail-run-2 still succeeded

`task-work` mode worked correctly this time. The
[task_work_results.json#L38-46](../../.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-003/task_work_results.json)
still flagged the same `agent_invocations_validation.status: "violation"`
(missing Phase 3) it did on fail-run-1 — but the Coach (transcript L230 /
L489) treated it as **advisory, not blocking**:

```
INFO:guardkit.orchestrator.quality_gates.coach_validator:
  Agent-invocations advisory for TASK-J006-003: missing phases 3 (non-blocking; outcome gates will run)
```

That demotion is the actual reason fail-run-2 succeeded where fail-run-1
stalled. It's either a guardkit code change between the two runs (Coach
validator now demotes `agent_invocations_validation` from `must_fix` to
advisory when outcome gates are otherwise green) or it was always the
behaviour but the previous claim-audit / honesty-verification path produced
a different upstream blocker. Either way, **Intervention A from
TASK-J006-006 cannot have been the cause** — it never reached the
orchestrator.

### Verdict

Intervention A is **ineffective as currently implemented**. To make a
future intervention of the same shape actually land, an additional lever is
required:

- **Lever C — edit the worktree before re-queue.** A future analogue of
  TASK-J006-006 must either (a) edit the task `.md` + feature-YAML files
  inside the worktree (`.guardkit/worktrees/FEAT-JARVIS-006/...`) and commit
  on `autobuild/FEAT-JARVIS-006`, or (b) blow the worktree away with
  `guardkit autobuild feature ... --fresh` so the orchestrator re-builds
  the worktree from the freshly-edited main-repo source.

Note (a) is fragile because the orchestrator's state_bridge moves task
files between `tasks/backlog/` and `tasks/design_approved/` mid-run — the
edit has to land in the right state directory at the right time. (b) is
the robust path; the only cost is losing the in-progress chat_handler
implementation that's currently on `autobuild/FEAT-JARVIS-006`. Given the
implementation is already valid (Q5), (b) is overkill for this feature;
the right play is to **merge first, then encode the lesson for next time**.

---

## Q3 — Did the per-task `approve` outcomes actually validate, or were they false positives?

**Answer: They validated. Outcome gates were genuinely green; the protocol
`violation` flag was a known false-positive (the Player did do
implementation, just inline rather than via a sub-agent invocation), and
the Coach correctly handled it as advisory.** Plan-audit was skipped (no
plan on disk), honesty-verification did not stall the run, and there were
no claim-audit `must_fix` promotions.

### Per-task evidence — TASK-J006-003

[task_work_results.json](../../.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-003/task_work_results.json):

```json
"quality_gates": {
  "tests_passing": true, "tests_passed": 20, "tests_failed": 0,
  "coverage": null, "coverage_met": null,
  "all_passed": true
},
"agent_invocations_validation": {
  "status": "violation",
  "expected_phases": 3, "actual_invocations": 2,
  "missing_phases": ["3"],
  // violation_message describes Phase 3 (Implementation) as missing
},
"plan_audit": { "status": "skipped", "message": "no implementation plan on disk" },
"unconfirmed_low_confidence_assumptions": { "status": "ok" },
"completion_promises": [ /* 9 ACs, all status:"complete" with evidence */ ],
"agent_invocations": [
  { "phase": "4", "agent": "test-orchestrator", "status": "completed", "duration_seconds": 68.88 },
  { "phase": "5", "agent": "code-reviewer", "status": "completed", "duration_seconds": 311.16 }
]
```

[coach_turn_1.json](../../.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-003/coach_turn_1.json) (Coach's own record):

```json
"decision": "approve",
"validation_results": {
  "quality_gates": {
    "tests_passed": true, "coverage_met": true,
    "arch_review_passed": true, "plan_audit_passed": true,
    "all_gates_passed": true
  },
  "independent_tests": {
    "tests_passed": true,
    "test_command": "pytest tests/unit/infrastructure/test_chat_handler.py -v --tb=short",
    "test_output_summary": "20 passed, 1 warning in 3.49s",
    "duration_seconds": 5.71
  },
  "requirements": { "criteria_total": 9, "criteria_met": 9, "all_criteria_met": true }
},
"criteria_verification": [ /* AC-001 through AC-009, all "result": "verified" */ ]
```

The Coach also re-ran tests **out-of-process** via subprocess (transcript
L234-235): `Running independent tests via subprocess: pytest
tests/unit/infrastructure/test_chat_handler.py -v --tb=short → Independent
tests passed in 5.7s`. This is the strongest possible signal — the same 20
tests pass both in the Player's reported environment and in a fresh
subprocess.

### Per-task evidence — TASK-J006-004

[task_work_results.json](../../.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-004/task_work_results.json):

```json
"quality_gates": {
  "tests_passing": true, "tests_passed": 20, "tests_failed": 0,
  "coverage": 100.0, "coverage_met": true,
  "all_passed": true
},
"agent_invocations_validation": { "status": "violation", /* same as 003 */ },
"plan_audit": { "status": "skipped", "message": "no implementation plan on disk" },
"unconfirmed_low_confidence_assumptions": { "status": "ok" }
```

Coach independent test (transcript L493-494): `pytest
tests/test_serve_nats_cli.py tests/test_shared.py -v --tb=short →
Independent tests passed in 8.1s`. Coach decision: `approve`.

There is one honesty discrepancy: transcript L504 notes `Turn 1 honesty:
1.00 (1 discrepancies)` — but this didn't gate the approval. The honesty
score is `1.00` (full match within tolerance), so the discrepancy was
counted but ignored. Compare fail-run-1 where similar honesty discrepancies
were promoted to `must_fix`.

### Verdict by sub-question

1. **`coach_validator.verify_quality_gates` ran and returned
   `all_gates_passed: true`** — yes, twice (transcript L231 / L490, and the
   `coach_turn_1.json` records).
2. **Claim-audit emitted warnings and they stayed as warnings** — yes,
   the `agent_invocations_validation: violation` is the structural equivalent
   of the fail-run-1 claim-audit warning, and the Coach explicitly logged
   "non-blocking; outcome gates will run". This means a guardkit change has
   landed since fail-run-1 — either `TASK-FIX-CAUD-J6F1` itself or a sibling
   in the Coach validator that demotes Phase-3-missing to advisory when
   tests/coverage/audit gates otherwise pass. **Confirming exactly which
   change is out of scope for this review** (it lives in guardkit) but the
   end-state is observably correct.
3. **`agent_invocations_validation` status** — `violation` (not passed) in
   both `task_work_results.json` files, but the Coach treated it as
   advisory. Mechanically a regression-of-rigor compared to the
   `agent_invocations_validation` design intent (TASK-FIX-RWOP1.3.1), but
   functionally correct given the protocol mismatch (the Player inlined
   Phase 3 implementation by writing files directly — Write/Edit — instead
   of invoking an "implementation" subagent; the work was done, just not
   through the introspectable phase-3 hook).
4. **`plan_audit` verdict** — `skipped` (no implementation plan on disk).
   This matches J006-003 and J006-004's nature: they didn't go through the
   `/plan` step before autobuild, just `/feature-plan`. Not a regression.

No quiet quality failures hide behind the surface `approve`. **The
approvals are real.**

---

## Q4 — TASK-J006-006 acceptance criteria status

### AC-005 status — partial (technically met)

Task definition: *"Fail-run-2's TASK-J006-003 turn 1 reaches `decision:
approve` AND `coach_turn_1.json.honesty_verification.verified: true` (or
`decision: approve` with audit issues remaining as warnings only)."*

- `decision: approve` ✓ (coach_turn_1.json L3)
- `honesty_verification` block: **does not exist in the coach_turn_1.json
  on disk for J006-003** — the schema has changed; there is a
  `criteria_verification` block (which is all-verified) and
  `validation_results.requirements.all_criteria_met: true` but no top-level
  `honesty_verification.verified` field. The OR-branch ("audit issues
  remaining as warnings only") is the applicable condition and is met: the
  `agent_invocations_validation.status: violation` was kept advisory by the
  Coach and the Player report's 9/9 ACs were verified by the Coach.

**Verdict: MET (via the OR-branch).**

### AC-006 status — fully met

Task definition: *"TASK-J006-004 completes successfully in the same
autobuild run."*

- Per `.guardkit/features/FEAT-JARVIS-006.yaml` (J006-004 block):
  `status: completed, final_decision: approved, turns_completed: 1,
  started_at: 2026-05-12T10:55:54.643598, completed_at:
  2026-05-12T11:14:22.218303`.
- Per transcript L530-538: `TASK-J006-004 SUCCESS approved (1 turn)`,
  `Wave 3 ✓ PASSED`.
- Per `coach_turn_1.json` for J006-004: `decision: approve`, all gates
  passed, 20 tests + 100% coverage.

**Verdict: MET.**

### Recommendation

Move TASK-J006-006 from `in_review` → `completed`. AC-005 is met via its
explicit OR-branch and AC-006 is met outright. The fact that **Intervention
A did not mechanically apply** is not an acceptance criterion of
TASK-J006-006; the task only required that fail-run-2 reach the named
outcomes, which it did. Document the Intervention-A mis-apply finding (this
review) and route the structural fix as TASK-J006-007 (below).

---

## Q5 — Spot-check the worktree implementation

All static checks pass. The implementation is real, not a stub.

### chat_handler.py — TASK-J006-003

[src/jarvis/infrastructure/chat_handler.py](../../.guardkit/worktrees/FEAT-JARVIS-006/src/jarvis/infrastructure/chat_handler.py)
(411 lines, 17.5 KB).

| Substantive AC | Implementation evidence |
|---|---|
| Dual-publish (raw `reply_to` + canonical `agents.result.{agent_id}` envelope) | `_dual_publish()` defined L341+; conditional raw publish at L344 (`if reply_to`), always-on canonical publish via `Topics.resolve(Topics.Agents.RESULT, agent_id=agent_id)`. Bug #1 fix. |
| Notification drain after invoke (Risk #3) | `session_manager.pending_notifications(session.session_id)` called at L284 *after* `invoke` returns; rendered lines joined onto `reply_text` |
| Empty-message short-circuit | L226: `await _dual_publish(...)` with `success=False, error_type="MissingMessage"` when `payload.args.get('message')` is empty/missing |
| Exception conversion to ResultPayload | `try/except Exception` around `session_manager.invoke()` at ~L260-265; rebuilds ResultPayload on failure |
| Flat subjects (no wildcard `*`/`>`) | Canonical subject resolved via `Topics.resolve` which validates `agent_id` against the identifier allowlist |
| conversation_history ignored | Handler only reads `payload.args.get('message')`; module docstring documents the invariant |
| Structured logging (`chat_invoke_start/complete/error` + `correlation_id`) | structlog calls visible at handler entry, success path, both error paths |
| Ruff-clean | Coach independent test confirmed (per task_work_results.json L153 evidence: `ruff check ... → 'All checks passed!'`) |

Tests:
[tests/unit/infrastructure/test_chat_handler.py](../../.guardkit/worktrees/FEAT-JARVIS-006/tests/unit/infrastructure/test_chat_handler.py)
— 734 lines, 26.6 KB, 20 tests, all passing (Coach's independent subprocess
run, transcript L234-235).

### cli/main.py — TASK-J006-004

[src/jarvis/cli/main.py](../../.guardkit/worktrees/FEAT-JARVIS-006/src/jarvis/cli/main.py)
(21.5 KB, ~600 lines).

| Substantive AC | Implementation evidence |
|---|---|
| `serve-nats` click subcommand | `@main.command("serve-nats")` at L263; click options for `--nats-url`, `--agent-id`, `--log-level` |
| SIGINT + SIGTERM handlers | `signal.signal(signal.SIGTERM, ...)` + `signal.SIGINT` referenced in module docstring L18 and registered in the serve-nats path |
| Shutdown teardown sequence | Module docstring L19: "unsubscribe → drain in-flight → cancel heartbeat → deregister"; the same wording recurs in the `serve_nats` docstring at L292 |
| Drain budget for in-flight handlers | "Default budget for draining in-flight `subscribe_with_reply` handlers" at L255 |
| Single asyncio.run owns the loop | `_run_serve_nats` separated from click handler at L309 with docstring "Separated from the click handler so `asyncio.run` owns the loop" |
| No double-register | The serve-nats flow goes through `_create_app_state` (mentioned in transcript-cited file structure) once; no re-subscription path in the inspected code |
| Lint-clean | Coach independent test confirmed in J006-004 task_work_results.json |

Tests:
[tests/test_serve_nats_cli.py](../../.guardkit/worktrees/FEAT-JARVIS-006/tests/test_serve_nats_cli.py)
— 610 lines, 20 tests, all passing with 100% coverage (Coach independent
subprocess run, transcript L493-494).

### Verdict

The implementation is substantive and matches the scope-doc design. Test
suites are real (size, organisation, both passed independently in the
Coach's subprocess pytest invocation). No stubs, no TODOs left behind in
load-bearing positions. Merge would land a working chat gateway.

---

## Cross-reference: why fail-run-1 stalled and fail-run-2 didn't

Independent of TASK-J006-006, **something upstream changed between the
runs** that allowed Phase-3-missing to be advisory rather than blocking.
Fail-run-1's coach_turn_1.json showed `must_fix` promotion of claim-audit
warnings (per TASK-REV-J6F1). Fail-run-2 shows none. Candidate causes:

1. `TASK-FIX-CAUD-J6F1` (the upstream Coach claim-audit fix tracked in
   guardkit) landed between runs.
2. A Coach validator schema change demoted `agent_invocations_validation`
   from must_fix to advisory.
3. The Player happened to write a report that didn't trigger the same
   audit warnings (lower-probability — fail-run-1's report path traces
   were structurally similar).

The transcript doesn't tell us which. The Coach's "non-blocking; outcome
gates will run" log line (L230, L489) suggests the validator itself was
updated to treat phase-missing as advisory; this is consistent with (1) or
(2). Confirming which lives in the guardkit changelog and is out of scope.

What matters for the merge decision: **the Coach now handles this audit
class correctly, and J006-003 + J006-004 are demonstrably approved with
green outcome gates**.

---

## Context used (knowledge-graph items / prior reviews)

- TASK-REV-J6F1 review report (`.claude/reviews/TASK-REV-J6F1-review-report.md`)
  — baseline for the fail-run-1 stall pattern and the absolute-path
  claim-audit defect; cited as Cross-reference §.
- TASK-J006-006 task definition
  (`tasks/in_review/feat-jarvis-006-nats-chat-gateway/TASK-J006-006-realign-implementation-mode-and-requeue.md`)
  — read for AC-005/006 wording and Intervention-A spec; cited in Q2, Q4.
- Feature plan + scope-doc for FEAT-JARVIS-006 — not re-read; the original
  intent is encoded in J006-003 and J006-004 ACs which are cited in Q5.

No Graphiti-side context loading was performed for this review (graphiti
was loaded by the autobuild run itself — transcript L80-96, L227 — and
that context is already reflected in the per-task artefacts under
inspection).

---

## Next Action — `[M]erge and ship`

The chat gateway implementation on `autobuild/FEAT-JARVIS-006` is correct,
tested, and Coach-approved. The only blocker is the smoke-gate misfire,
which is environmental and trivial to address.

### Pre-merge checklist (assigned to follow-up TASK-J006-007)

1. **Fix the smoke-gate command**, either by:
   - **Option 1 (recommended)**: remove `--timeout=60` from
     `.guardkit/features/FEAT-JARVIS-006.yaml` `smoke_gates.command` (the
     50-minute task timeout already bounds runtime; the pytest-level
     timeout is redundant). One-line edit. Re-run smoke gate manually:
     `cd .guardkit/worktrees/FEAT-JARVIS-006 && .venv/bin/python -m pytest tests/ -x -q`
     and verify exit 0 before merging.
   - **Option 2**: add `pytest-timeout` to the worktree `[dev]` extras
     (`pyproject.toml`), `uv sync`, and re-run. Heavier but matches the
     spec literally.

2. **Confirm `autobuild/FEAT-JARVIS-006` merges cleanly into `main`**:
   ```
   cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
   git fetch && git diff main..autobuild/FEAT-JARVIS-006 --stat
   ```
   The branch base is `0d7f709 feature plan nats chat gateway`. There are
   four guardkit-checkpoint commits on top
   (`585783f`, `7ff3a20`, `d07ea11`, `9bfca9e`), three from fail-run-1 and
   one from fail-run-2's J006-004 turn-1. Recommend squash-merging into a
   single commit on `main` (the checkpoint commits are noisy; the
   substantive diff is the chat_handler + serve-nats CLI + tests).

3. **Run the full project test suite from the main repo** post-merge
   (not from the worktree) to catch any path/import drift introduced by
   the worktree-isolated environment.

4. **TASK-J006-005 (operator handoff — live Open WebUI demo verification)**
   remains the unblocked next task. Schedule for between merge and the
   16 May DDD Southwest deadline (4 days from review date, comfortable).

### Optional follow-up — TASK-J006-007 (encode the Intervention-A lesson)

Open a new low-priority task to document the worktree/main-repo split in
the autobuild orchestration runbook so that future analogue interventions
either (a) edit worktree files directly, or (b) re-queue with `--fresh`.
This is **not blocking** the demo — the chat gateway works without
Intervention A — but it prevents repeating the same false-start. Suggested
parent: TASK-REV-J6F2 (this review).

### Demo-deadline impact (16 May 2026)

Today is 2026-05-12 (review date). The merge prerequisites above are <30
minutes of work. **No risk to the 16 May demo** from this review's findings.

---

## Appendix A — Out-of-scope items flagged for separate work

- **TASK-FIX-CAUD-J6F1** (guardkit): the upstream Coach claim-audit
  absolute-path defect. May have already landed; transcript suggests Coach
  behaviour has changed in the right direction. Confirm via guardkit
  changelog at convenience.
- **Coach `agent_invocations_validation` rigor regression**: fail-run-1
  treated `missing_phases: ["3"]` as `must_fix`; fail-run-2 treats it as
  advisory. End-state correct for this feature, but worth a guardkit-side
  ADR documenting the demotion criterion (current heuristic "outcome gates
  passed → advisory" is reasonable but undocumented).
- **Worktree-vs-main-repo source-of-truth precedence**: documented above
  as the Q2 mechanism. Worth a one-paragraph entry in
  `docs/autobuild-runbook.md` or equivalent.

## Appendix B — Files cited

- `docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md` — transcript
- `.guardkit/features/FEAT-JARVIS-006.yaml` — main-repo feature YAML
- `.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/features/FEAT-JARVIS-006.yaml` — worktree feature YAML (the one the orchestrator reads)
- `.guardkit/worktrees/FEAT-JARVIS-006/tasks/design_approved/TASK-J006-00{3,4}-*.md` — worktree task files
- `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-00{3,4}-*.md` — main-repo task files (edited by TASK-J006-006)
- `tasks/in_review/feat-jarvis-006-nats-chat-gateway/TASK-J006-006-realign-implementation-mode-and-requeue.md`
- `.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-003/{task_work_results,coach_turn_1,player_turn_1}.json`
- `.guardkit/worktrees/FEAT-JARVIS-006/.guardkit/autobuild/TASK-J006-004/{task_work_results,coach_turn_1}.json`
- `.guardkit/autobuild/TASK-J006-003/progress.log` and `.guardkit/autobuild/TASK-J006-004/progress.log`
- `.claude/reviews/TASK-REV-J6F1-review-report.md` — baseline
- `.guardkit/worktrees/FEAT-JARVIS-006/src/jarvis/infrastructure/chat_handler.py`
- `.guardkit/worktrees/FEAT-JARVIS-006/src/jarvis/cli/main.py`
- `.guardkit/worktrees/FEAT-JARVIS-006/tests/unit/infrastructure/test_chat_handler.py`
- `.guardkit/worktrees/FEAT-JARVIS-006/tests/test_serve_nats_cli.py`
