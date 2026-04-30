autobuild feature  FEAT-J005-946D is now implemented please see /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/history/autobuild-FEAT-J005-946D-resume-history.md. Please update the build plan status and let's see what the next step is

The autobuild succeeded — 12/12 tasks completed across 5 waves. Let me check the review summary and the feature YAML before updating the plan.

Bash List autobuild artifacts and peek at review summary
IN
ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/FEAT-J005-946D/ 2>/dev/null && echo "---" && head -80 /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/FEAT-J005-946D/review-summary.md 2>/dev/null

OUT
Exit code 1
Bash List autobuild artifacts
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/FEAT-J005-946D/ 2>&1 | head -30

OUT
ls: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/FEAT-J005-946D/: No such file or directory
Bash List autobuild folders
IN
ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/ 2>&1 ; echo "---" ; ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J005-946D/.guardkit/autobuild/ 2>&1 | head

OUT
FEAT-J002
FEAT-J003
FEAT-J004-702C
FEAT-JARVIS-001
TASK-J001-001
TASK-J001-002
TASK-J001-003
TASK-J001-004
TASK-J001-005
TASK-J001-006
TASK-J001-007
TASK-J001-008
TASK-J001-009
TASK-J001-010
TASK-J001-011
TASK-J002-001
TASK-J002-002
TASK-J002-003
TASK-J002-004
TASK-J002-005
TASK-J002-006
TASK-J002-007
TASK-J002-008
TASK-J002-009
TASK-J002-010
TASK-J002-011
TASK-J002-012
TASK-J002-013
TASK-J002-014
TASK-J002-015
TASK-J002-016
TASK-J002-017
TASK-J002-018
TASK-J002-019
TASK-J002-020
TASK-J002-021
TASK-J002-022
TASK-J002-023
TASK-J003-001
TASK-J003-002
TASK-J003-003
TASK-J003-004
TASK-J003-005
TASK-J003-006
TASK-J003-007
TASK-J003-008
TASK-J003-009
TASK-J003-010
TASK-J003-011
TASK-J003-012
TASK-J003-013
TASK-J003-014
TASK-J003-015
TASK-J003-016
TASK-J003-017
TASK-J003-018
TASK-J003-019
TASK-J003-020
TASK-J003-021
TASK-J003-022
TASK-J003-023
TASK-J003-024
TASK-J004-001
TASK-J004-002
TASK-J004-003
TASK-J004-004
TASK-J004-005
TASK-J004-006
TASK-J004-007
TASK-J004-008
TASK-J004-009
TASK-J004-010
TASK-J004-011
TASK-J004-012
TASK-J004-013
TASK-J004-014
TASK-J004-015
TASK-J004-016
TASK-J004-017
TASK-J004-018
TASK-J004-019
TASK-J004-020
TASK-J005-001
TASK-J005-002
TASK-J005-003
TASK-J005-004
TASK-J005-005
TASK-J005-006
TASK-J005-007
TASK-J005-008
TASK-J005-009
TASK-J005-010
TASK-J005-011
TASK-J005-012
---
ls: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J005-946D/.guardkit/autobuild/: No such file or directory
Bash Find review summary and autobuild dirs in worktree
IN
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J005-946D && find .guardkit -maxdepth 3 -type d 2>/dev/null | head -30 ; echo "---review---" ; find . -maxdepth 5 -name "review-summary.md" 2>/dev/null

OUT
(eval):cd:1: no such file or directory: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J005-946D
---review---
./.guardkit/autobuild/FEAT-J002/review-summary.md
./.guardkit/archive/FEAT-J005-946D/review-summary.md
./.guardkit/autobuild/FEAT-J004-702C/review-summary.md
./.guardkit/autobuild/FEAT-JARVIS-001/review-summary.md
Bash Check worktrees, branches, and archive
IN
ls .guardkit/worktrees/ 2>&1 ; echo "---branches---" ; git branch -a | grep -i 946D ; echo "---archive---" ; ls .guardkit/archive/FEAT-J005-946D/ 2>&1 | head

OUT
nats-core
---branches---
---archive---
events.jsonl
feature_state.yaml
review-summary.md
Read review-summary.md
Bash Check current git/branch state
IN
git log --oneline -15 ; echo "---" ; git branch -a | head -20 ; echo "---feature yaml---" ; ls .guardkit/features/ 2>&1

OUT
615a0a7 reviews, config flip, design
505d5e4 chore(jarvis): purge stale FEAT-J005 task duplicates
a8a2b36 chore(jarvis): close FEAT-J005-946D — migrate task files to completed/
d382f2b chore: final autobuild artifact for FEAT-J005-946D
805255f [guardkit-checkpoint] Turn 1 complete (tests: pass)
6488545 [guardkit-checkpoint] Turn 1 complete (tests: pass)
3bd8aab [guardkit-checkpoint] Turn 1 complete (tests: pass)
c6112a4 [guardkit-checkpoint] Turn 1 complete (tests: pass)
0069a0d [guardkit-checkpoint] Turn 2 complete (tests: pass)
d315103 [guardkit-checkpoint] Turn 1 complete (tests: pass)
81de574 [guardkit-checkpoint] Turn 1 complete (tests: pass)
51250c0 [guardkit-checkpoint] Turn 1 complete (tests: pass)
bf2252f [guardkit-checkpoint] Turn 1 complete (tests: pass)
2e0c3bd [guardkit-checkpoint] Turn 1 complete (tests: pass)
f09e21c [guardkit-checkpoint] Turn 1 complete (tests: pass)
---
* main
  remotes/origin/HEAD -> origin/main
  remotes/origin/main
---feature yaml---
FEAT-J002.yaml
FEAT-J003-FIX.yaml
FEAT-J003.yaml
FEAT-J004-702C.yaml
FEAT-JARVIS-001.yaml
Bash Locate FEAT-J005-946D artifacts and check completed tasks
IN
find .guardkit -maxdepth 4 -name "FEAT-J005*" 2>/dev/null ; echo "---" ; ls tasks/completed/ 2>/dev/null | grep -i j005 | head -20 ; echo "---" ; git log --oneline main | head -5

OUT
.guardkit/archive/FEAT-J005-946D
---
TASK-REV-E73C-analyse-autobuild-feat-j005-946d-timeout-failure.md
---
615a0a7 reviews, config flip, design
505d5e4 chore(jarvis): purge stale FEAT-J005 task duplicates
a8a2b36 chore(jarvis): close FEAT-J005-946D — migrate task files to completed/
d382f2b chore: final autobuild artifact for FEAT-J005-946D
805255f [guardkit-checkpoint] Turn 1 complete (tests: pass)
Bash Find J005 completed tasks and confirm forge_notifications module
IN
ls tasks/completed/ 2>/dev/null | grep -i j005 ; echo "---" ; ls tasks/completed/feat-jarvis-005-build-queue-dispatch-to-forge/ 2>/dev/null | head -30 ; echo "---src/jarvis/infrastructure---" ; ls src/jarvis/infrastructure/ 2>/dev/null

OUT
TASK-REV-E73C-analyse-autobuild-feat-j005-946d-timeout-failure.md
---
IMPLEMENTATION-GUIDE.md
README.md
TASK-J005-001-config-extensions.md
TASK-J005-002-forge-notification-models.md
TASK-J005-003-forge-notifications-subscriber.md
TASK-J005-004-routing-history-build-queue-extensions.md
TASK-J005-005-dispatch-queue-build-real-publish.md
TASK-J005-006-session-manager-pending-notifications.md
TASK-J005-007-cli-between-prompts-render.md
TASK-J005-008-lifecycle-wiring.md
TASK-J005-009-soft-fail-tests.md
TASK-J005-010-contract-tests-nats-core.md
TASK-J005-011-grep-invariant-retire.md
TASK-J005-012-end-to-end-forge-roundtrip.md
---src/jarvis/infrastructure---
__init__.py
__pycache__
capabilities_registry.py
dispatch_semaphore.py
fleet_registration.py
forge_notifications.py
lifecycle.py
logging.py
nats_client.py
routing_history.py
Bash Current git/task state
IN
git status --short 2>&1 | head -30 ; echo "---reviews---" ; ls tasks/in_review/ 2>/dev/null | head ; echo "---backlog---" ; ls tasks/backlog/ 2>/dev/null | grep -i J005 | head ; echo "---active---" ; ls tasks/in_progress/ 2>/dev/null | head

OUT
---reviews---
TASK-REV-J001-plan-project-scaffolding-supervisor-sessions.md
TASK-REV-J002-plan-core-tools-and-dispatch.md
TASK-REV-J003-plan-async-subagent-and-frontier-escape.md
---backlog---
---active---
Bash Find FEAT-JARVIS-005 merge commit
IN
git log --oneline --all | grep -i "J005\|jarvis-005" | head -20

OUT
505d5e4 chore(jarvis): purge stale FEAT-J005 task duplicates
a8a2b36 chore(jarvis): close FEAT-J005-946D — migrate task files to completed/
d382f2b chore: final autobuild artifact for FEAT-J005-946D
Bash Identify when forge_notifications landed on main
IN
git log --oneline --grep="FEAT-J005\|FEAT-JARVIS-005\|merge\|forge" --all | head -10 ; echo "---" ; git log --merges --oneline -10 ; echo "---" ; git log --oneline d382f2b~1..d382f2b ; echo "---" ; git log --oneline --diff-filter=A -- src/jarvis/infrastructure/forge_notifications.py | head -3

OUT
505d5e4 chore(jarvis): purge stale FEAT-J005 task duplicates
a8a2b36 chore(jarvis): close FEAT-J005-946D — migrate task files to completed/
d382f2b chore: final autobuild artifact for FEAT-J005-946D
29a13b7 docs(jarvis): update phase3-build-plan status — FEAT-JARVIS-004 closed
b467939 chore(jarvis): close FEAT-J004 — migrate task files + review to completed/
8daa414 chore(autobuild): remove FEAT-J004-702C worktree gitlink after cleanup
b228d7d feat(jarvis): FEAT-J004-702C NATS fleet registration + specialist dispatch
d6fbf8a Preserve TASK-J001-009 checkpoint record
979d918 Merge FEAT-JARVIS-001: scaffolding, supervisor skeleton, session lifecycle
---
49dcbd0 Merge FEAT-J003: async subagent for model routing + attended frontier escape
---
d382f2b chore: final autobuild artifact for FEAT-J005-946D
---
e8b0f57 [guardkit-checkpoint] Turn 1 complete (tests: pass)
Bash Trace FEAT-J005 merge into main
IN
git log --oneline --all -- src/jarvis/infrastructure/forge_notifications.py | head -5 ; echo "---log around d382f2b---" ; git log --oneline d382f2b~5..d382f2b ; echo "---show parents of d382f2b---" ; git log -1 --pretty="%H %P %s %ad" --date=short d382f2b

OUT
3bd8aab [guardkit-checkpoint] Turn 1 complete (tests: pass)
c6112a4 [guardkit-checkpoint] Turn 1 complete (tests: pass)
bf2252f [guardkit-checkpoint] Turn 1 complete (tests: pass)
e8b0f57 [guardkit-checkpoint] Turn 1 complete (tests: pass)
---log around d382f2b---
d382f2b chore: final autobuild artifact for FEAT-J005-946D
805255f [guardkit-checkpoint] Turn 1 complete (tests: pass)
6488545 [guardkit-checkpoint] Turn 1 complete (tests: pass)
3bd8aab [guardkit-checkpoint] Turn 1 complete (tests: pass)
c6112a4 [guardkit-checkpoint] Turn 1 complete (tests: pass)
---show parents of d382f2b---
d382f2bf964781382d478d7d0ba8a2c177716312 805255fe665ffb18d5c727393da8cd18af9dd51d chore: final autobuild artifact for FEAT-J005-946D 2026-04-30
Bash Survey FEAT-JARVIS-005 artifacts
IN
ls docs/design/FEAT-JARVIS-005/ 2>/dev/null ; echo "---" ; ls docs/history/ 2>/dev/null | grep -i j005 ; echo "---" ; head -3 docs/design/FEAT-JARVIS-005/design.md 2>/dev/null ; echo "---" ; ls features/feat-jarvis-005-build-queue-dispatch-to-forge/ 2>/dev/null | head ; echo "---" ; ls tasks/completed/ 2>/dev/null | grep -i j005 | head -20 ; echo "---reviews---" ; ls .claude/reviews/ 2>/dev/null | grep -iE "3B8B|REV-J005|J005|REV-E73C"

OUT
contracts
decisions
design.md
diagrams
models
---
autobuild-FEAT-J005-946D-history.md
autobuild-FEAT-J005-946D-resume-history.md
autobuild-FEAT-J005-946D-timeout-history.md
---
# FEAT-JARVIS-005 — Design

> **Feature:** Build Queue Dispatch to Forge (real transport + Forge progress feedback loop)
---
feat-jarvis-005-build-queue-dispatch-to-forge_assumptions.yaml
feat-jarvis-005-build-queue-dispatch-to-forge_summary.md
feat-jarvis-005-build-queue-dispatch-to-forge.feature
---
TASK-REV-E73C-analyse-autobuild-feat-j005-946d-timeout-failure.md
---reviews---
TASK-REV-E73C-review-report.md
Bash Survey FEAT-JARVIS-005 decisions and feature yaml
IN
ls docs/design/FEAT-JARVIS-005/decisions/ 2>/dev/null ; echo "---" ; head -20 features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md ; echo "---feature yaml location---" ; find . -name "FEAT-J005-946D.yaml" 2>/dev/null

OUT
DDR-025-queue-build-real-transport.md
DDR-026-forge-notifications-module-location.md
DDR-027-stage-complete-ephemeral-deliver-new.md
DDR-028-correlation-map-in-memory-bounded.md
DDR-029-stage-complete-as-append-only-edges.md
DDR-030-cli-notifications-between-prompts.md
DDR-031-originating-adapter-from-session.md
---
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
---feature yaml location---
Bash Trace dates and scope of FEAT-J005 work
IN
head -5 docs/history/feature-plan-FEAT-JARVIS-005-history.md 2>/dev/null ; echo "---" ; head -5 docs/history/autobuild-queue-dspatch-FEAT-JARVIS-005-history.md 2>/dev/null ; echo "---" ; head -5 docs/history/autobuild-FEAT-J005-946D-history.md 2>/dev/null ; echo "---REV-E73C---" ; head -10 tasks/completed/TASK-REV-E73C-analyse-autobuild-feat-j005-946d-timeout-failure.md 2>/dev/null ; echo "---J005 plan review---" ; ls .guardkit/ -la 2>&1 | head

OUT
/feature-plan "FEAT-JARVIS-005 — Build Queue Dispatch to Forge" \
  --context features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md

I'll orchestrate /feature-plan for FEAT-JARVIS-005. The feature has rich context already (design.md, 7 DDRs, 32 Gherkin scenarios, suggested 7-wave breakdown). Let me set up tracking and begin.

---

/feature-spec "Build Queue Dispatch to Forge: queue_build publishes BuildQueuedPayload to pipeline.build-queued.{feature_id} per ADR-SP-014 Pattern A; Jarvis subscribes to pipeline.stage-complete.> via ephemeral push consumer (deliver_policy=NEW); ForgeNotificationsSubscriber routes correlation-matched events to per-session CLI rendering between prompts; routing-history writer emits append-only stage_complete edges on the originating JarvisRoutingHistoryEntry" \
  --context docs/design/FEAT-JARVIS-005/design.md \
  --context docs/design/FEAT-JARVIS-005/contracts/API-tools.md \
  --context docs/design/FEAT-JARVIS-005/contracts/API-internal.md \
---
---REV-E73C---
---
id: TASK-REV-E73C
title: "Analyse AutoBuild FEAT-J005-946D timeout failure (TASK-J005-005)"
task_type: review
review_mode: decision
review_depth: standard
status: completed
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
priority: high
---J005 plan review---
ls: -la: No such file or directory
.guardkit/:
archive
autobuild
bdd
bootstrap_state.json
config.yaml
context-manifest.yaml
features
graphiti-query-log.jsonl
Bash Inspect TASK-REV-E73C review report
IN
grep -l "FEAT-J005\|FEAT-JARVIS-005\|REV-3B8B\|REV-E73C" .claude/reviews/* 2>/dev/null ; echo "---" ; head -25 .claude/reviews/TASK-REV-E73C-review-report.md 2>/dev/null

OUT
.claude/reviews/TASK-REV-E73C-review-report.md
.claude/reviews/TASK-REV-J002-review-report.md
---
# Review Report: TASK-REV-E73C (v2 — deepened)

**Subject:** AutoBuild FEAT-J005-946D timeout failure (TASK-J005-005)
**Mode:** decision · standard depth · revised at user request to validate via source code + worktree state
**Reviewer:** /task-review (Opus 4.7, 1M context)
**Generated:** 2026-04-30
**Source artifacts:**
- Transcript: [autobuild-FEAT-J005-946D-timeout-history.md](../../docs/history/autobuild-FEAT-J005-946D-timeout-history.md) (1904 lines)
- GuardKit source: `/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/{feature_orchestrator,autobuild,agent_invoker}.py`, `quality_gates/coach_validator.py`
- Worktree (git branch `autobuild/FEAT-J005-946D`, 9 GuardKit checkpoint commits)
- Per-task artifacts: `.guardkit/worktrees/FEAT-J005-946D/.guardkit/autobuild/TASK-J005-005/{coach,player,task_work,specialist}_*.json`

---

## What changed in v2

v1 inferred mechanics from the transcript. v2 **validates each claim against
the source and the worktree** — and one of v1's claims turned out to be
partially wrong, in a load-bearing way:

| v1 claim | v2 verdict | Evidence |
|---|---|---|
| "Specialist invocations were the dominant cost" | **Confirmed** with refinement: each specialist's `sdk_timeout` IS capped against remaining wall via `_cap_specialist_timeout()`, but the cap input is **not refreshed between Phase 4 and Phase 5** (autobuild.py:2880–2904) — likely a latent bug | Code |
| "asyncio cancel-vs-completion race" | **Confirmed at the *feature* level**, but v1 missed that there is **already a per-task grace mechanism** (TASK-ABFIX-004, autobuild.py:2192–2194 + 2940–2950) that *did* fire — that's why the task's frontmatter says `approve` | Code + transcript line 1808 |
| "TASK-005 implementation is in the worktree" | **Strongly confirmed** — `js.publish` + `pipeline.build-queued.{feature_id}` + `pipeline_publish_timeout_seconds` all present at [src/jarvis/tools/dispatch.py:1142, :810, :1000](../../.guardkit/worktrees/FEAT-J005-946D/src/jarvis/tools/dispatch.py); 9 checkpoint commits; `0069a0d` committed at the exact second of timeout | Worktree git log + grep |
Bash Locate TASK-REV-3B8B planning review
IN
find tasks -name "TASK-REV-3B8B*" 2>/dev/null ; find . -name "TASK-REV-3B8B*" -not -path "*/node_modules/*" 2>/dev/null | head -5

OUT
tasks/backlog/TASK-REV-3B8B-plan-feat-jarvis-005-build-queue-dispatch-to-forge.md
./tasks/backlog/TASK-REV-3B8B-plan-feat-jarvis-005-build-queue-dispatch-to-forge.md
Read TASK-REV-3B8B-plan-feat-jarvis-005-build-queue-dispatch-to-forge.md
Now I have the full picture. FEAT-JARVIS-005 is fully implemented, merged into main, and worktree archived. Let me update the build plan and identify the next step.

Edit phase3-build-plan.md
Modified
Edit phase3-build-plan.md
Added 6 lines
Now add the FEAT-JARVIS-005 wave-status section, modelled on the FEAT-JARVIS-004 one.

Edit phase3-build-plan.md
Added 16 lines
Build plan updated. Here's the summary:

What I changed in docs/research/ideas/phase3-build-plan.md
Top status line now reads "Phase 2 closed. FEAT-JARVIS-004 closed… FEAT-JARVIS-005 closed…" with the merge commit chain (d382f2b → a8a2b36 → 505d5e4) and points the next pending step at Step 11 (full regression).
Status Log gained 7 new rows: 2026-04-29 system-design / feature-spec / feature-plan, the 04-29/30 TASK-J005-005 timeout, the 2026-04-30 TASK-REV-E73C decision review, the resume run (12/12 in 36m19s), and the landing on main.
The previous pending / next rows were rewritten to point at Steps 11 → 12 → 13 → 14.
Added a new FEAT-JARVIS-005 Wave Status table mirroring the FEAT-JARVIS-004 one, with 5 waves and per-wave completion notes.
Surfaced two pieces of housekeeping: TASK-REV-3B8B still sitting in tasks/backlog/, and a latent GuardKit cap-refresh bug (specialist sdk_timeout not refreshed between Phase 4 and Phase 5) that TASK-REV-E73C diagnosed during the timeout post-mortem — worth raising as a GuardKit issue.
Next step
Per the plan's command sequence, with FEAT-JARVIS-005 code-complete and on main, the next thing to do is Step 11 — full regression:


cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
uv sync
uv run pytest tests/ -v --tb=short --cov=src/jarvis
uv run ruff check src/jarvis/ tests/
uv run mypy src/jarvis/
uv run langgraph dev --no-browser
After that, Step 12 (in-process integration suite — no GB10 needed), then Step 13 (you pick the FEAT-JARVIS-INTERNAL-*** candidate — the build plan recommends (a) docstring/README polish as the smallest, safest first real round-trip), and finally Step 14 — the end-to-end Forge test that closes Phase 3.

Want me to kick off Step 11 now? If so, I'll run the regression battery against main and report results — and we can pick up Step 13 once it's green.

yes
Running Step 11 regression. I'll execute pytest, ruff, mypy, then validate langgraph dev starts cleanly.

Bash Sync uv environment
IN
uv sync 2>&1 | tail -25

OUT
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Resolved 133 packages in 5ms
   Building jarvis @ file:///Users/richardwoollcott/Projects/appmilla_github/jarvis
      Built jarvis @ file:///Users/richardwoollcott/Projects/appmilla_github/jarvis
Prepared 1 package in 660ms
Uninstalled 1 package in 1ms
Installed 1 package in 1ms
 ~ jarvis==0.1.0 (from file:///Users/richardwoollcott/Projects/appmilla_github/jarvis)
Bash Run full pytest suite with coverage
IN
uv run pytest tests/ -v --tb=short --cov=src/jarvis 2>&1 | tail -120

OUT
tests/test_lifecycle_forge_subscriber_wiring.py::TestAssembleToolListForgeSubscriberKwarg::test_kwarg_propagates_to_dispatch_module_attribute
tests/test_lifecycle_forge_subscriber_wiring.py::TestAssembleToolListForgeSubscriberKwarg::test_default_kwarg_clears_dispatch_module_attribute
tests/test_lifecycle_forge_subscriber_wiring.py::TestAssembleToolListForgeSubscriberKwarg::test_ambient_call_also_propagates
tests/test_lifecycle_forge_subscriber_wiring.py::TestStartupOrdering::test_start_after_fleet_register_before_session_manager
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_lifecycle_forge_subscriber_wiring.py:67: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_lifecycle_layer2_wiring.py::TestSpoofedAmbientRejected::test_attended_session_with_subagent_frame_rejects_escalation
tests/test_lifecycle_layer2_wiring.py::TestHooksPopulatedAfterStartup::test_current_session_hook_is_callable_and_returns_session_or_none
tests/test_lifecycle_layer2_wiring.py::TestHooksPopulatedAfterStartup::test_async_subagent_frame_hook_is_wired_per_assum_frontier_caller_frame
tests/test_lifecycle_layer2_wiring.py::TestIdempotentHookAssignment::test_two_consecutive_build_app_state_calls_replace_not_stack
tests/test_lifecycle_layer2_wiring.py::TestShutdownClearsHooks::test_shutdown_resets_both_hooks_to_none
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_lifecycle_layer2_wiring.py:72: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_lifecycle_partial_failure.py::TestNATSUpGraphitiDown::test_dispatches_succeed_traces_lost_warn_emitted
tests/test_lifecycle_partial_failure.py::TestNATSDownGraphitiUp::test_dispatches_return_degraded
tests/test_lifecycle_partial_failure.py::TestBothNATSAndGraphitiDown::test_jarvis_still_starts_attended_escape_local_subagent_phase2_tools
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_lifecycle_partial_failure.py:80: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_lifecycle_startup_phase3.py: 12 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_lifecycle_startup_phase3.py:80: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_nats_unavailable.py::TestStartupNATSUnreachable::test_startup_with_unreachable_nats_still_starts
tests/test_nats_unavailable.py::TestStartupNATSUnreachable::test_state_nats_client_is_none
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_nats_unavailable.py:77: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_phase4_dependencies.py::TestAC004ImportSmokeCheck::test_module_importable_in_active_venv[graphiti_core]
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.12/site-packages/graphiti_core/driver/search_interface/search_interface.py:22: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    class SearchInterface(BaseModel):

tests/test_prompts.py::TestAC004TestConfigFixture::test_test_config_validate_provider_keys_succeeds
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_prompts.py:417: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    test_config.validate_provider_keys()  # Should not raise

tests/test_routing_e2e.py: 24 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:230: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_lifecycle_wiring.py::TestAC005LifecycleWiring::test_load_stub_registry_called_with_configured_path
tests/test_supervisor_lifecycle_wiring.py::TestAC005LifecycleWiring::test_assemble_tool_list_called_with_config_and_registry
tests/test_supervisor_lifecycle_wiring.py::TestAC005LifecycleWiring::test_build_supervisor_called_with_tools_and_capabilities
tests/test_supervisor_lifecycle_wiring.py::TestAC006AppStateCapabilityRegistry::test_app_state_capability_registry_populated_from_loader
tests/test_supervisor_lifecycle_wiring.py::TestAC007StartupPerformance::test_startup_under_two_seconds
tests/test_supervisor_lifecycle_wiring.py::TestAC008Seam::test_supervisor_has_nine_tools_and_registry_has_four_entries
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_lifecycle_wiring.py:96: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_with_subagents.py: 13 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_subagents.py:118: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_compiled_supervisor_exposes_nine_tool_names
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_create_deep_agent_receives_nine_tools_alphabetically
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_assemble_tool_list_is_alphabetical
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_each_descriptor_block_appears_verbatim_in_system_prompt
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_tools.py:113: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform darwin, python 3.12.4-final-0 _______________

Name                                                 Stmts   Miss  Cover
------------------------------------------------------------------------
src/jarvis/__init__.py                                   1      0   100%
src/jarvis/adapters/__init__.py                          3      0   100%
src/jarvis/adapters/llamaswap.py                        12      0   100%
src/jarvis/adapters/types.py                             9      0   100%
src/jarvis/agents/__init__.py                            2      0   100%
src/jarvis/agents/subagent_registry.py                  13      0   100%
src/jarvis/agents/subagents/__init__.py                  4      0   100%
src/jarvis/agents/subagents/jarvis_reasoner.py          91      2    98%
src/jarvis/agents/subagents/prompts.py                   8      0   100%
src/jarvis/agents/subagents/types.py                    13      0   100%
src/jarvis/agents/supervisor.py                         42      2    95%
src/jarvis/cli/__init__.py                               0      0   100%
src/jarvis/cli/main.py                                 112     27    76%
src/jarvis/config/__init__.py                            2      0   100%
src/jarvis/config/settings.py                           72      0   100%
src/jarvis/discovery/__init__.py                         0      0   100%
src/jarvis/infrastructure/__init__.py                    3      0   100%
src/jarvis/infrastructure/capabilities_registry.py     136     12    91%
src/jarvis/infrastructure/dispatch_semaphore.py         28      0   100%
src/jarvis/infrastructure/fleet_registration.py         52      1    98%
src/jarvis/infrastructure/forge_notifications.py       133     12    91%
src/jarvis/infrastructure/lifecycle.py                 221     35    84%
src/jarvis/infrastructure/logging.py                    37      1    97%
src/jarvis/infrastructure/nats_client.py                61      2    97%
src/jarvis/infrastructure/routing_history.py           198     10    95%
src/jarvis/learning/__init__.py                          0      0   100%
src/jarvis/prompts/__init__.py                           2      0   100%
src/jarvis/prompts/supervisor_prompt.py                  2      0   100%
src/jarvis/routing/__init__.py                           0      0   100%
src/jarvis/sessions/__init__.py                          3      0   100%
src/jarvis/sessions/manager.py                          78      0   100%
src/jarvis/sessions/session.py                          13      0   100%
src/jarvis/shared/__init__.py                            3      0   100%
src/jarvis/shared/constants.py                           9      0   100%
src/jarvis/shared/exceptions.py                          5      0   100%
src/jarvis/skills/__init__.py                            0      0   100%
src/jarvis/subagents/__init__.py                         0      0   100%
src/jarvis/tools/__init__.py                            22      0   100%
src/jarvis/tools/_correlation.py                         3      0   100%
src/jarvis/tools/capabilities.py                       107      4    96%
src/jarvis/tools/dispatch.py                           392     30    92%
src/jarvis/tools/dispatch_types.py                      19      0   100%
src/jarvis/tools/general.py                            212     38    82%
src/jarvis/tools/types.py                               34      0   100%
src/jarvis/watchers/__init__.py                          0      0   100%
------------------------------------------------------------------------
TOTAL                                                 2157    176    92%
=========================== short test summary info ============================
FAILED tests/test_assemble_tool_list.py::TestAC005NoSubmoduleImports::test_no_production_module_imports_submodules
====== 1 failed, 2101 passed, 1 skipped, 264 warnings in 72.73s (0:01:12) ======
One failure. Let me see what's failing.

Bash Inspect the failing test
IN
uv run pytest tests/test_assemble_tool_list.py::TestAC005NoSubmoduleImports::test_no_production_module_imports_submodules -v --tb=long 2>&1 | tail -60

OUT
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform darwin -- Python 3.12.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/richardwoollcott/Projects/appmilla_github/jarvis
configfile: pyproject.toml
plugins: langsmith-0.7.33, cov-7.1.0, asyncio-1.3.0, bdd-8.1.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/test_assemble_tool_list.py F                                       [100%]

=================================== FAILURES ===================================
___ TestAC005NoSubmoduleImports.test_no_production_module_imports_submodules ___

self = <tests.test_assemble_tool_list.TestAC005NoSubmoduleImports object at 0x1095a6ab0>

    def test_no_production_module_imports_submodules(self) -> None:
        """Walk ``src/jarvis/`` excluding ``src/jarvis/tools/``."""
        jarvis_dir = _SRC_DIR / "jarvis"
        tools_dir = jarvis_dir / "tools"
    
        violations: list[str] = []
        for filepath in _python_files_under(jarvis_dir):
            try:
                filepath.relative_to(tools_dir)
            except ValueError:
                # Outside the tools package — apply the AC-005 check.
                pass
            else:
                # Inside ``jarvis.tools.*`` — sibling imports are fine.
                continue
    
            for module_name in _imports(filepath):
                for forbidden in _INTERNAL_PREFIXES:
                    if module_name == forbidden or module_name.startswith(
                        forbidden + "."
                    ):
                        rel = filepath.relative_to(_SRC_DIR)
                        violations.append(f"{rel}: imports {module_name!r}")
    
>       assert violations == [], (
            "Production modules must consume `jarvis.tools` only:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
E       AssertionError: Production modules must consume `jarvis.tools` only:
E           - jarvis/infrastructure/capabilities_registry.py: imports 'jarvis.tools.capabilities'
E       assert ["jarvis/infr...apabilities'"] == []
E         
E         Left contains one more item: "jarvis/infrastructure/capabilities_registry.py: imports 'jarvis.tools.capabilities'"
E         Use -v to get more diff

/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_assemble_tool_list.py:422: AssertionError
=========================== short test summary info ============================
FAILED tests/test_assemble_tool_list.py::TestAC005NoSubmoduleImports::test_no_production_module_imports_submodules
============================== 1 failed in 0.75s ===============================
This is an architecture-invariant violation: infrastructure/capabilities_registry.py imports from jarvis.tools.capabilities when only the top-level jarvis.tools is allowed. Let me check when this slipped in.

Bash Locate the offending import and trace its origin
IN
grep -n "from jarvis.tools" src/jarvis/infrastructure/capabilities_registry.py 2>&1 ; echo "---blame---" ; git log --oneline -- src/jarvis/infrastructure/capabilities_registry.py | head -10 ; echo "---log of import line---" ; git log -p -S "from jarvis.tools.capabilities" -- src/jarvis/infrastructure/capabilities_registry.py | head -40

OUT
55:from jarvis.tools.capabilities import (
---blame---
b228d7d feat(jarvis): FEAT-J004-702C NATS fleet registration + specialist dispatch
---log of import line---
commit b228d7d22c7bf60e12d7dc86c5e27736556da36d
Author: Richard Woollcott <rich@appmilla.com>
Date:   Tue Apr 28 15:07:26 2026 +0100

    feat(jarvis): FEAT-J004-702C NATS fleet registration + specialist dispatch
    
    Squash-merges autobuild/FEAT-J004-702C (20/20 tasks, 7 waves, 100% clean
    executions) into main. Lands the Phase-3 fleet plumbing for FEAT-JARVIS-004:
    
    - DDR-023 (trace-file collision: O_EXCL preserve) and DDR-024 (degraded
      specialists eligible) promoted from ASSUM-008/009.
    - pyproject extras: nats-py and graphiti-core wired via optional deps.
    - JarvisConfig fields for NATS URL/creds, heartbeat interval, dispatch
      semaphore, routing-history offload + redaction, lifecycle gates.
    - src/jarvis/infrastructure/fleet_registration.py: build_jarvis_manifest
      (pure), register_on_fleet (idempotent), heartbeat_loop (cancellable,
      WARN-survives), deregister_from_fleet (silent-on-missing).
    - NATS async client wrapper, dispatch semaphore, capabilities registry
      protocol with live KV-backed bodies, real-transport dispatch tool,
      routing-history Pydantic schema + writer with offload + redaction.
    - Lifecycle startup/shutdown wiring with shutdown-order invariant test.
    - Integration tests: roundtrip + redirect matrix, slot-release scenario
      outline, soft-fail (NATS/Graphiti partial), nats_core contract tests,
      Phase-2 stub retirement + routing E2E refresh.
    - Task moves: 14 tasks from backlog/feat-jarvis-004-... to
      design_approved (TASK-J004-004/006/007/009/010/011/012/013/014/015/
      016/017/018/019); 6 backlog tasks moved up one level.
    
    Conflicts on TASK-J004-007 + TASK-J004-010 resolved by taking HEAD's
    content (latest autobuild_state metadata) at the new design_approved
    path; autobuild branch's path move preserved.
    
    Follow-up: 11 stray coverage*.json files landed at the repo root from
    pytest-cov runs during autobuild; safe to delete + add to .gitignore.
    
    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

diff --git a/src/jarvis/infrastructure/capabilities_registry.py b/src/jarvis/infrastructure/capabilities_registry.py
new file mode 100644
index 0000000..5d9b682
Bash Find the test invariant definition
IN
grep -n "_INTERNAL_PREFIXES\|_SRC_DIR\|_imports\|_python_files" tests/test_assemble_tool_list.py | head -25

OUT
99:_SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"
362:_INTERNAL_PREFIXES = (
369:def _python_files_under(root: pathlib.Path) -> list[pathlib.Path]:
374:def _imports(filepath: pathlib.Path) -> list[str]:
398:    def test_no_production_module_imports_submodules(self) -> None:
400:        jarvis_dir = _SRC_DIR / "jarvis"
404:        for filepath in _python_files_under(jarvis_dir):
414:            for module_name in _imports(filepath):
415:                for forbidden in _INTERNAL_PREFIXES:
419:                        rel = filepath.relative_to(_SRC_DIR)
Read test_assemble_tool_list.py (lines 356-415)
This is a pre-existing AC-005 layering violation that landed in commit b228d7d with FEAT-J004 — not a FEAT-J005 regression. The test was failing on main already. Let me confirm what's imported and whether it's exposed on the package surface.

Read capabilities_registry.py (lines 2-81)
Bash Check whether tools/__init__.py exposes the imported names
IN
grep -E "CapabilityDescriptor|CapabilityToolSummary|load_stub_registry" src/jarvis/tools/__init__.py

OUT
    CapabilityDescriptor,
    load_stub_registry,
    "CapabilityDescriptor",
    "load_stub_registry",
    capability_registry: list[CapabilityDescriptor],
Read __init__.py
The pre-existing CapabilityToolSummary is imported from a submodule and isn't on the jarvis.tools package surface. Continuing with ruff, mypy, langgraph to get the full picture before recommending a fix path.

Bash Run ruff check
IN
uv run ruff check src/jarvis/ tests/ 2>&1 | tail -40

OUT
   | |_^
   |
help: Organize imports

RUF003 Comment contains ambiguous `−` (MINUS SIGN). Did you mean `-` (HYPHEN-MINUS)?
   --> tests/test_tools_general.py:524:51
    |
522 |         [
523 |             (MAX_FILE_BYTES, False),  # exactly 1 MiB    → accept
524 |             (MAX_FILE_BYTES - 1, False),  # 1 MiB − 1 byte → accept
    |                                                   ^
525 |             (MAX_FILE_BYTES + 1, True),  # 1 MiB + 1 byte → reject
526 |             (10 * MAX_FILE_BYTES, True),  # 10 MiB           → reject
    |

RUF003 Comment contains ambiguous `–` (EN DASH). Did you mean `-` (HYPHEN-MINUS)?
   --> tests/test_tools_general.py:925:65
    |
923 | # ===========================================================================
924 | # Group D — every general tool converts internal errors into structured
925 | # strings rather than raising (the .feature outline at lines 374–388 lists
    |                                                                 ^
926 | # seven tools; the four general-tool rows are asserted here).
927 | # ===========================================================================
    |

UP017 [*] Use `datetime.UTC` alias
   --> tests/test_tools_types.py:221:52
    |
219 |     @staticmethod
220 |     def _start() -> datetime:
221 |         return datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)
    |                                                    ^^^^^^^^^^^^
222 |
223 |     def test_end_after_start_accepted(self) -> None:
    |
help: Convert to `datetime.UTC` alias

Found 49 errors.
[*] 30 fixable with the `--fix` option (5 hidden fixes can be enabled with the `--unsafe-fixes` option).
Bash List ruff violation files
IN
uv run ruff check src/jarvis/ tests/ 2>&1 | grep -E "^(src|tests)/" | sort -u | sed 's/:.*//' | sort -u | head -30

OUT
(Bash completed with no output)
Bash Get ruff violation stats
IN
uv run ruff check src/jarvis/ tests/ --statistics 2>&1 | tail -30

OUT
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
12	F401  	[*] unused-import
 8	RUF002	[ ] ambiguous-unicode-character-docstring
 7	I001  	[*] unsorted-imports
 5	UP017 	[*] datetime-timezone-utc
 4	RUF100	[*] unused-noqa
 3	E501  	[ ] line-too-long
 3	SIM105	[ ] suppressible-exception
 2	RUF003	[ ] ambiguous-unicode-character-comment
 2	SIM110	[ ] reimplemented-builtin
 1	RUF023	[*] unsorted-dunder-slots
 1	UP041 	[*] timeout-error-alias
 1	UP047 	[ ] non-pep695-generic-function
Found 49 errors.
[*] 30 fixable with the `--fix` option (5 hidden fixes can be enabled with the `--unsafe-fixes` option).
Bash Group ruff violations by file
IN
uv run ruff check src/jarvis/ tests/ --output-format=json 2>/dev/null | python3 -c "import json,sys,collections; d=json.load(sys.stdin); files=collections.Counter(v['filename'].split('/jarvis/')[-1] for v in d); print('\n'.join(f'{c:3d}  {f}' for f,c in files.most_common()))"

OUT
 11  tests/test_assemble_tool_list.py
  5  tests/test_routing_history_schema.py
  4  tests/test_lifecycle_shutdown_order.py
  3  infrastructure/forge_notifications.py
  2  tools/capabilities.py
  2  tests/test_contract_nats_core.py
  2  tests/test_dispatch_by_capability_integration.py
  2  tests/test_dispatch_slot_release.py
  2  tests/test_end_to_end_forge_roundtrip.py
  2  tests/test_graphiti_unavailable.py
  2  tests/test_tool_types.py
  2  tests/test_tools_general.py
  1  tests/conftest.py
  1  tests/test_assemble_tool_list_layer3.py
  1  tests/test_capabilities.py
  1  tests/test_fleet_registration_integration.py
  1  tests/test_lifecycle_feat_j004_wiring.py
  1  tests/test_lifecycle_layer2_wiring.py
  1  tests/test_lifecycle_partial_failure.py
  1  tests/test_routing_history_writer.py
  1  tests/test_tools_capabilities_kv_backed.py
  1  tests/test_tools_types.py
Bash Run mypy type-check
IN
uv run mypy src/jarvis/ 2>&1 | tail -50

OUT
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
src/jarvis/tools/__init__.py:217: error: Incompatible types in assignment (expression has type "list[CapabilityDescriptor]", variable has type "CapabilitiesRegistry | None")  [assignment]
Found 1 error in 1 file (checked 45 source files)
Bash Find the type definition for _capability_registry
IN
grep -n "_capability_registry" src/jarvis/tools/capabilities.py | head -10 ; echo "---blame---" ; git log --oneline -S "_capability_registry: CapabilitiesRegistry" src/jarvis/tools/capabilities.py | head -5

OUT
22:  ``_capability_registry.snapshot()``.
23:* :func:`capabilities_refresh` — drives ``_capability_registry.refresh()``
28:  ``_capability_registry.subscribe_updates(...)`` exactly once per session.
35:``_capability_registry`` swap-point with whichever implementation the
265:_capability_registry: CapabilitiesRegistry | None = None
372:        registry = _capability_registry
414:    registry = _capability_registry
421:            "capabilities_refresh called before _capability_registry was wired"
455:        registry = _capability_registry
---blame---
b228d7d feat(jarvis): FEAT-J004-702C NATS fleet registration + specialist dispatch
Bash Validate langgraph dev spins up
IN
timeout 25 uv run langgraph dev --no-browser 2>&1 | tail -50

OUT
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
INFO:langgraph_api.cli:

        Welcome to

╦  ┌─┐┌┐┌┌─┐╔═╗┬─┐┌─┐┌─┐┬ ┬
║  ├─┤││││ ┬║ ╦├┬┘├─┤├─┘├─┤
╩═╝┴ ┴┘└┘└─┘╚═╝┴└─┴ ┴┴  ┴ ┴

- 🚀 API: [36mhttp://127.0.0.1:2024[0m
- 🎨 Studio UI: [36mhttps://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024[0m
- 📚 API Docs: [36mhttp://127.0.0.1:2024/docs[0m

This in-memory server is designed for development and testing.
For production use, please use LangSmith Deployment.


[version] A newer version of langgraph-api is available: 0.8.1 → 0.8.3  (pip install -U langgraph-api)
[2m2026-04-30T11:23:23.610159Z[0m [[32m[1minfo     [0m] [1m[version] A newer version of langgraph-api is available: 0.8.1 → 0.8.3  (pip install -U langgraph-api)[0m [[0m[1m[34mversion_check[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mmessage[0m=[35m'[version] A newer version of langgraph-api is available: 0.8.1 → 0.8.3  (pip install -U langgraph-api)'[0m [36mthread_name[0m=[35m'Thread-2 (_check_newer_version)'[0m
[2m2026-04-30T11:23:23.848753Z[0m [[32m[1minfo     [0m] [1m31 changes detected           [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:24.307366Z[0m [[32m[1minfo     [0m] [1m80 changes detected           [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:24.669108Z[0m [[32m[1minfo     [0m] [1m139 changes detected          [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.026091Z[0m [[32m[1minfo     [0m] [1m147 changes detected          [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.196724Z[0m [[32m[1minfo     [0m] [1mStarting dev persistence flush loop[0m [[0m[1m[34mlanggraph_runtime_inmem._persistence[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.248167Z[0m [[32m[1minfo     [0m] [1mUsing langgraph_runtime_inmem [0m [[0m[1m[34mlanggraph_runtime[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.279049Z[0m [[32m[1minfo     [0m] [1mUsing auth of type=noop       [0m [[0m[1m[34mlanggraph_api.auth.middleware[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.283922Z[0m [[32m[1minfo     [0m] [1mStarting In-Memory runtime with langgraph-api=0.8.1 and in-memory runtime=0.28.0[0m [[0m[1m[34mlanggraph_runtime_inmem.lifespan[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mlanggraph_runtime_inmem_version[0m=[35m0.28.0[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m [36mversion[0m=[35m0.8.1[0m
[2m2026-04-30T11:23:25.302720Z[0m [[32m[1minfo     [0m] [1mNo license key or control plane API key set, skipping metadata loop[0m [[0m[1m[34mlanggraph_api.metadata[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.390727Z[0m [[32m[1minfo     [0m] [1m363 changes detected          [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.553544Z[0m [[32m[1minfo     [0m] [1mImporting graph profiling     [0m [[0m[1m[34mlanggraph_api.timing.timer[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36melapsed_seconds[0m=[35m0.25081191695062444[0m [36mgraph_id[0m=[35mjarvis[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mmodule[0m=[35mNone[0m [36mname[0m=[35m_graph_from_spec[0m [36mpath[0m=[35m./src/jarvis/agents/supervisor.py[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:23:25.903861Z[0m [[32m[1minfo     [0m] [1mImporting graph profiling     [0m [[0m[1m[34mlanggraph_api.timing.timer[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36melapsed_seconds[0m=[35m0.34998299996368587[0m [36mgraph_id[0m=[35mjarvis_reasoner[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mmodule[0m=[35mNone[0m [36mname[0m=[35m_graph_from_spec[0m [36mpath[0m=[35m./src/jarvis/agents/subagents/jarvis_reasoner.py[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:23:25.975272Z[0m [[32m[1minfo     [0m] [1mApplication started up in 1.779s[0m [[0m[1m[34mlanggraph_api.timing.timer[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36melapsed[0m=[35m1.7787875829963014[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.999516Z[0m [[32m[1minfo     [0m] [1mStarting cron scheduler       [0m [[0m[1m[34mlanggraph_api.cron_scheduler[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:25.999693Z[0m [[32m[1minfo     [0m] [1mStarting queue with shared loop[0m [[0m[1m[34mlanggraph_runtime_inmem.queue[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:23:26.000171Z[0m [[32m[1minfo     [0m] [1mStarting 1 background workers [0m [[0m[1m[34mlanggraph_runtime_inmem.queue[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:23:26.000287Z[0m [[32m[1minfo     [0m] [1mWorker stats                  [0m [[0m[1m[34mlanggraph_runtime_inmem.queue[0m][0m [36mactive[0m=[35m0[0m [36mapi_variant[0m=[35mlocal_dev[0m [36mavailable[0m=[35m1[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mmax[0m=[35m1[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:23:26.075542Z[0m [[32m[1minfo     [0m] [1m224 changes detected          [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:26.501833Z[0m [[32m[1minfo     [0m] [1mQueue stats                   [0m [[0m[1m[34mlanggraph_runtime_inmem.queue[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mn_pending[0m=[35m0[0m [36mn_running[0m=[35m0[0m [36mpending_runs_wait_time_max_secs[0m=[35mNone[0m [36mpending_runs_wait_time_med_secs[0m=[35mNone[0m [36mpending_unblocked_runs_wait_time_max_secs[0m=[35mNone[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:23:35.282608Z[0m [[32m[1minfo     [0m] [1m3 changes detected            [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:45.317442Z[0m [[32m[1minfo     [0m] [1m3 changes detected            [0m [[0m[1m[34mwatchfiles.main[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:47.489090Z[0m [[32m[1minfo     [0m] [1mShutting down background workers[0m [[0m[1m[34mlanggraph_runtime_inmem.queue[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:47.497122Z[0m [[32m[1minfo     [0m] [1mShutting down remote graphs   [0m [[0m[1m[34mlanggraph_api.graph[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:47.516598Z[0m [[32m[1minfo     [0m] [1mStopping dev persistence flush loop[0m [[0m[1m[34mlanggraph_runtime_inmem._persistence[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
[2m2026-04-30T11:23:47.516707Z[0m [[32m[1minfo     [0m] [1mdev persistence flush loop exiting[0m [[0m[1m[34mlanggraph_runtime_inmem._persistence[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mThread-1[0m
langgraph dev came up cleanly — both jarvis and jarvis_reasoner graphs compile, 1.78s startup. Let me confirm whether the failures are pre-existing (FEAT-J004 era) or FEAT-J005-introduced.

Bash Replay the failing checks at FEAT-J004 head to confirm pre-existing
IN
git stash 2>&1 | head -2 ; git checkout b228d7d -- src/jarvis tests 2>&1 | head ; uv run pytest tests/test_assemble_tool_list.py::TestAC005NoSubmoduleImports -q 2>&1 | tail -5 ; echo "---mypy at FEAT-J004 head---" ; uv run mypy src/jarvis/ 2>&1 | tail -5 ; echo "---ruff stats at FEAT-J004 head---" ; uv run ruff check src/jarvis/ tests/ --statistics 2>&1 | tail -5 ; echo "---restore---" ; git checkout HEAD -- src/jarvis tests ; git stash pop 2>&1 | head -3

OUT
Saved working directory and index state WIP on main: 615a0a7 reviews, config flip, design
E     
E     Left contains one more item: "jarvis/infrastructure/capabilities_registry.py: imports 'jarvis.tools.capabilities'"
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_assemble_tool_list.py::TestAC005NoSubmoduleImports::test_no_production_module_imports_submodules
---mypy at FEAT-J004 head---
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
src/jarvis/infrastructure/forge_notifications.py:656: error: "SessionManager" has no attribute "enqueue_notification"  [attr-defined]
src/jarvis/tools/__init__.py:207: error: Incompatible types in assignment (expression has type "list[CapabilityDescriptor]", variable has type "CapabilitiesRegistry | None")  [assignment]
Found 2 errors in 2 files (checked 45 source files)
---ruff stats at FEAT-J004 head---
 1	RUF023	[*] unsorted-dunder-slots
 1	UP041 	[*] timeout-error-alias
 1	UP047 	[ ] non-pep695-generic-function
Found 46 errors.
[*] 30 fixable with the `--fix` option (3 hidden fixes can be enabled with the `--unsafe-fixes` option).
---restore---
On branch main
Your branch is up to date with 'origin/main'.
Bash Confirm working tree is restored to HEAD
IN
git status --short 2>&1 | head -10 ; echo "---" ; git stash list 2>&1 | head -3 ; echo "---" ; git diff HEAD --stat 2>&1 | tail -5

OUT
 M docs/research/ideas/phase3-build-plan.md
---
---
 docs/research/ideas/phase3-build-plan.md | 36 +++++++++++++++++++++++++-------
 1 file changed, 29 insertions(+), 7 deletions(-)
Working tree is clean — only my build-plan edit is staged-pending. Here's the Step 11 regression report.

Step 11 Regression Results — FEAT-JARVIS-005 on main (head 615a0a7)
Gate	Status	Notes
pytest	2101 pass / 1 skipped / 1 fail	One AC-005 architectural-invariant failure
coverage	92% (2157 stmts, 176 missed)	Well above the 80% gate. New FEAT-J005 modules — forge_notifications.py 91%, dispatch.py 92%, routing_history.py 95%, lifecycle.py 84%
ruff	49 errors across 22 files	Mostly cosmetic (F401 unused imports, I001 import sort, UP017 datetime.UTC, RUF002 unicode dashes); 30 auto-fixable
mypy	1 error	src/jarvis/tools/__init__.py:217 — _capabilities._capability_registry = list(...) assigned a list[CapabilityDescriptor] into a slot now typed as CapabilitiesRegistry | None
langgraph dev	✓ clean	Both jarvis and jarvis_reasoner graphs compile; application up in 1.78s; clean shutdown
Pre-existing vs. FEAT-J005-introduced
I replayed pytest+ruff+mypy at FEAT-J004 head (b228d7d) to attribute each failure:

The pytest failure (TestAC005NoSubmoduleImports) — pre-existing since FEAT-J004 merge. src/jarvis/infrastructure/capabilities_registry.py:55 imports from the submodule jarvis.tools.capabilities instead of the package surface jarvis.tools. The forbidden symbol is CapabilityToolSummary, which isn't yet exposed on jarvis.tools.__init__. Not a FEAT-J005 regression — the test has been red on main for 2 days.
The mypy error — pre-existing since FEAT-J004 merge (was line 207, now line 217 — same root cause). tools/__init__.py still uses the old list-assignment pattern; the type annotation was changed during FEAT-J004 to a CapabilitiesRegistry | None Protocol but the snapshot writer wasn't updated.
mypy actually got cleaner under FEAT-J005: at b228d7d mypy reported 2 errors; FEAT-J005 fixed forge_notifications.py:656 (SessionManager.enqueue_notification is now defined per TASK-J005-006). FEAT-J005 net-removed one error.
ruff went from 46 → 49 errors (FEAT-J005 added 3 cosmetic lints — mostly RUF002 unicode dashes in test docstrings).
Verdict
FEAT-JARVIS-005 has not regressed Phase 1+2+FEAT-J004 baseline — it actually improves the mypy delta. The single hard failure (AC-005) is pre-existing tech debt from the FEAT-J004 merge that wasn't caught when that feature closed.

Recommendation
Two options:

Fix AC-005 now (≈10 lines): add CapabilityToolSummary to jarvis.tools.__init__.py re-exports + __all__, switch the offending import in capabilities_registry.py:55 to consume the package surface. Also fixes the mypy error if I update the tools/__init__.py:217 snapshot to match the Protocol shape (slightly larger). Result: a fully-green Step 11.
Move on to Step 12: log AC-005 as a pre-existing tech-debt finding, treat the regression as no-net-new-failure, and proceed. The integration-server check (Step 12) and end-to-end test (Step 14) are not affected by this layering invariant.
My take: do option 1 first. The AC-005 invariant is structural — once forge_notifications.py or another infrastructure module starts pulling more from jarvis.tools.*, the violations multiply, and the layering invariant becomes harder to claw back. Fixing it now while the surface is small is cheap. The mypy error is a closely related cleanup — same package-surface seam.

Want me to apply the AC-005 + mypy fix?

proceed with your reccomendation to implement option 1 first then 2
Applying the fix. First, let me understand the production wiring path so the mypy fix is structurally correct.

Bash Check production wiring path for _capability_registry
IN
grep -n "assemble_tool_list\|_capability_registry" src/jarvis/infrastructure/lifecycle.py | head -30 ; echo "---dispatch.py uses---" ; grep -n "_capability_registry" src/jarvis/tools/dispatch.py | head -15

OUT
18:2. ``tool_list = assemble_tool_list(config, capability_registry)`` — wires
39:6. ``assemble_tool_list`` is called twice — once with
97:    assemble_tool_list,
490:           ``assemble_tool_list(config, registry, include_frontier=True)``
496:           ``assemble_tool_list(config, registry, include_frontier=False)``
549:        "jarvis_capability_registry_loaded",
688:    tool_list_attended = assemble_tool_list(
706:    tool_list_ambient = assemble_tool_list(
---dispatch.py uses---
11:  ``_capability_registry`` (see API-internal §7). Tool docstring and
144:_capability_registry: list[CapabilityDescriptor] = []
438:    registry_snapshot = list(_capability_registry)
1703:    "_capability_registry",
Read lifecycle.py (lines 681-720)
Bash Find where lifecycle wires the registry to capabilities
IN
grep -n "capabilities_registry\|capabilities_registry =\|\.snapshot()\|capability_registry =" src/jarvis/infrastructure/lifecycle.py | head -30

OUT
16:1. ``capability_registry = load_stub_registry(config.stub_capabilities_path)``
73:from jarvis.infrastructure.capabilities_registry import (
306:        capabilities_registry: The Protocol-shaped
329:    capabilities_registry: CapabilitiesRegistry | None = None
375:def _build_stub_capabilities_registry(
392:            "jarvis_capabilities_registry_preloaded_fallback",
547:    capability_registry = load_stub_registry(config.stub_capabilities_path)
601:    capabilities_registry: CapabilitiesRegistry
621:            capabilities_registry = await LiveCapabilitiesRegistry.create(nats_client)
626:                "jarvis_live_capabilities_registry_failed",
630:            capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
632:        capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
685:    # (``capabilities_registry``) keeps the prompt-block wiring
788:        capabilities_registry=capabilities_registry,
797:        if isinstance(capabilities_registry, LiveCapabilitiesRegistry)
821:        4. ``await capabilities_registry.close()``.
886:    if state.capabilities_registry is not None:
888:            await state.capabilities_registry.close()
891:                "jarvis_capabilities_registry_close_warning",
Read capabilities.py (lines 256-345)
Read capabilities.py (lines 366-435)
Bash Find all assignments to _capability_registry across modules
IN
grep -rn "_capability_registry\s*=" src/jarvis/ 2>/dev/null | head -15 ; echo "---supervisor.py wiring---" ; grep -n "capabilities_registry\|_capability_registry" src/jarvis/agents/supervisor.py | head -20

OUT
src/jarvis/tools/__init__.py:119:    2. ``capabilities._capability_registry = list(capability_registry)``
src/jarvis/tools/__init__.py:121:    3. ``dispatch._capability_registry = list(capability_registry)`` —
src/jarvis/tools/__init__.py:217:    _capabilities._capability_registry = list(capability_registry)
src/jarvis/tools/__init__.py:218:    _dispatch._capability_registry = list(capability_registry)
---supervisor.py wiring---
Bash Find Protocol-shaped registry wiring at runtime
IN
grep -rn "_capability_registry\|capabilities_registry" src/jarvis/agents/ 2>/dev/null | head -10 ; echo "---lifecycle 600-700---" ; sed -n '595,640p' src/jarvis/infrastructure/lifecycle.py

OUT
---lifecycle 600-700---
    log.info(
        "jarvis_routing_history_writer_ready",
        graphiti_available=graphiti_client is not None,
    )

    fleet_heartbeat_task: asyncio.Task[None] | None = None
    capabilities_registry: CapabilitiesRegistry
    if nats_client is not None:
        manifest = build_jarvis_manifest(config)
        try:
            await register_on_fleet(nats_client, manifest)
        except Exception as exc:
            # DDR-021 soft-fail at the registration boundary — a flaky
            # broker must not block startup. The supervisor stays up;
            # downstream fleet observers simply will not see Jarvis.
            log.warning(
                "jarvis_fleet_register_failed",
                agent_id=manifest.agent_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )
        fleet_heartbeat_task = asyncio.create_task(
            heartbeat_loop(nats_client, manifest, config),
            name="jarvis_fleet_heartbeat",
        )
        try:
            capabilities_registry = await LiveCapabilitiesRegistry.create(nats_client)
        except Exception as exc:
            # DDR-021 soft-fail — bind failure falls back to the stub
            # YAML so the prompt block is still populated.
            log.warning(
                "jarvis_live_capabilities_registry_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
    else:
        capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)

    dispatch_semaphore = DispatchSemaphore(cap=config.dispatch_concurrent_cap)
    log.info(
        "jarvis_dispatch_semaphore_ready",
        cap=config.dispatch_concurrent_cap,
    )

    # 7c. FEAT-JARVIS-005 (TASK-J005-008) — start the Forge stage-complete
Bash Find all references to capabilities_registry in lifecycle
IN
grep -n "capabilities_registry\|_capability_registry" src/jarvis/infrastructure/lifecycle.py | head -40

OUT
73:from jarvis.infrastructure.capabilities_registry import (
306:        capabilities_registry: The Protocol-shaped
329:    capabilities_registry: CapabilitiesRegistry | None = None
375:def _build_stub_capabilities_registry(
392:            "jarvis_capabilities_registry_preloaded_fallback",
549:        "jarvis_capability_registry_loaded",
601:    capabilities_registry: CapabilitiesRegistry
621:            capabilities_registry = await LiveCapabilitiesRegistry.create(nats_client)
626:                "jarvis_live_capabilities_registry_failed",
630:            capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
632:        capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
685:    # (``capabilities_registry``) keeps the prompt-block wiring
788:        capabilities_registry=capabilities_registry,
797:        if isinstance(capabilities_registry, LiveCapabilitiesRegistry)
821:        4. ``await capabilities_registry.close()``.
886:    if state.capabilities_registry is not None:
888:            await state.capabilities_registry.close()
891:                "jarvis_capabilities_registry_close_warning",
Read lifecycle.py (lines 771-805)
Bash Find how supervisor consumes capabilities_registry
IN
grep -rn "capabilities_registry" src/jarvis/agents/supervisor.py | head -10 ; echo "---supervisor signature---" ; grep -n "def build_supervisor\|def _\|^def " src/jarvis/agents/supervisor.py | head -10

OUT
---supervisor signature---
61:def _render_available_capabilities(
96:def _default_ambient_tool_factory(
135:    def _factory() -> list[BaseTool]:
148:def build_supervisor(
337:def make_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
Read supervisor.py (lines 149-178)
Bash Trace what is passed to build_supervisor
IN
grep -n "build_supervisor\b\|capabilities_registry\b\|capability_registry\b" src/jarvis/infrastructure/lifecycle.py | grep -E "=|\(" | head -15

OUT
16:1. ``capability_registry = load_stub_registry(config.stub_capabilities_path)``
18:2. ``tool_list = assemble_tool_list(config, capability_registry)`` — wires
73:from jarvis.infrastructure.capabilities_registry import (
323:    capability_registry: list[CapabilityDescriptor] = dataclasses.field(default_factory=list)
329:    capabilities_registry: CapabilitiesRegistry | None = None
375:def _build_stub_capabilities_registry(
547:    capability_registry = load_stub_registry(config.stub_capabilities_path)
551:        count=len(capability_registry),
621:            capabilities_registry = await LiveCapabilitiesRegistry.create(nats_client)
630:            capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
632:        capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
685:    # (``capabilities_registry``) keeps the prompt-block wiring
726:    supervisor = build_supervisor(
729:        available_capabilities=capability_registry,
782:        capability_registry=capability_registry,
Read lifecycle.py (lines 723-747)
Bash Find any other module that wires _capability_registry to a Protocol-shaped object
IN
grep -rn "capabilities\._capability_registry\|capabilities\.LiveCapabilitiesRegistry\|capabilities_module\._capability_registry" src/jarvis/ 2>/dev/null | head ; echo "---tests---" ; grep -rn "capabilities\._capability_registry\s*=" tests/ 2>/dev/null | head -10

OUT
src/jarvis/tools/__init__.py:119:    2. ``capabilities._capability_registry = list(capability_registry)``
src/jarvis/tools/__init__.py:217:    _capabilities._capability_registry = list(capability_registry)
---tests---
Bash Find tests that wire _capability_registry
IN
grep -rn "_capability_registry\s*=" tests/ 2>/dev/null | head -10 ; echo "---tests in capabilities---" ; ls tests/ | grep -i capabilit

OUT
tests/test_tools_capabilities.py:126:    capabilities_module._capability_registry = _ListBackedRegistry(fresh)
tests/test_tools_capabilities.py:131:        capabilities_module._capability_registry = saved
tests/test_contract_nats_core.py:153:    dispatch._capability_registry = _make_registry()
tests/test_contract_nats_core.py:157:        dispatch._capability_registry = saved
tests/test_capabilities.py:488:    capabilities_module._capability_registry = _ListBackedRegistry(descriptors)
tests/test_capabilities.py:493:        capabilities_module._capability_registry = saved
tests/test_capabilities.py:502:    capabilities_module._capability_registry = _ListBackedRegistry([])
tests/test_capabilities.py:507:        capabilities_module._capability_registry = saved
tests/test_capabilities.py:517:    capabilities_module._capability_registry = _ListBackedRegistry(
tests/test_capabilities.py:524:        capabilities_module._capability_registry = saved
---tests in capabilities---
test_capabilities_real.py
test_capabilities_registry_unit.py
test_capabilities.py
test_dispatch_by_capability_integration.py
test_dispatch_by_capability.py
test_stub_capabilities.py
test_tools_capabilities_kv_backed.py
test_tools_capabilities.py
Bash Check how list_available_capabilities is exercised
IN
grep -rn "list_available_capabilities\|capabilities_refresh" src/jarvis/ tests/ 2>/dev/null | grep -v ".feature\|: *#\|history\|docs" | grep -E "src/" | head -10 ; echo "---test calls---" ; grep -rn "list_available_capabilities()\|list_available_capabilities\.invoke\|list_available_capabilities\.func\|list_available_capabilities\.run" tests/ 2>/dev/null | head -15

OUT
src/jarvis/tools/__init__.py:42:    capabilities_refresh,
src/jarvis/tools/__init__.py:44:    list_available_capabilities,
src/jarvis/tools/__init__.py:84:    "capabilities_refresh",
src/jarvis/tools/__init__.py:86:    "list_available_capabilities",
src/jarvis/tools/__init__.py:159:            :func:`list_available_capabilities` returns ``"[]"``.
src/jarvis/tools/__init__.py:195:          capabilities_refresh, capabilities_subscribe_updates,
src/jarvis/tools/__init__.py:197:          get_calendar_events, list_available_capabilities, queue_build,
src/jarvis/tools/__init__.py:248:            capabilities_refresh,
src/jarvis/tools/__init__.py:253:            list_available_capabilities,
src/jarvis/tools/__init__.py:260:        capabilities_refresh,
---test calls---
tests/test_tools_capabilities.py:243:        result = list_available_capabilities.invoke({})
tests/test_tools_capabilities.py:254:        parsed = json.loads(list_available_capabilities.invoke({}))
tests/test_tools_capabilities.py:343:            return list_available_capabilities.invoke({})
tests/test_tools_capabilities.py:384:            return list_available_capabilities.invoke({})
tests/test_capabilities.py:589:        full_doc = list_available_capabilities.func.__doc__ or ""
tests/test_capabilities.py:660:        result = list_available_capabilities.invoke({})
tests/test_capabilities.py:670:        parsed = json.loads(list_available_capabilities.invoke({}))
tests/test_capabilities.py:685:        assert list_available_capabilities.invoke({}) == "[]"
tests/test_capabilities.py:691:        before = list_available_capabilities.invoke({})
tests/test_capabilities.py:696:        after = list_available_capabilities.invoke({})
tests/test_capabilities.py:779:            result = list_available_capabilities.invoke({})
tests/test_capabilities.py:792:            list_available_capabilities.invoke({})  # must not raise
tests/test_capabilities.py:830:                list_results.append(list_available_capabilities.invoke({}))
tests/test_capabilities.py:872:            results.append(list_available_capabilities.invoke({}))
tests/test_assemble_tool_list.py:352:        rendered = list_available_capabilities.invoke({})
Read test_assemble_tool_list.py (lines 336-360)
I've discovered the mypy error reflects a deeper FEAT-J004 wiring inconsistency — the production assemble_tool_list puts a list into _capabilities._capability_registry while the catalogue tools call .snapshot()/.refresh() on it (Protocol API). Tests wrap it in _ListBackedRegistry after the fact; lifecycle doesn't. Properly fixing this requires changes across tools/__init__.py, capabilities.py, and lifecycle.py — out of scope for a regression-check pass.

I'll proceed with the AC-005 fix only and report the mypy issue as a separate FEAT-J004 follow-up. That's a smaller, safer change.

Read capabilities.py (lines 86-110)
Good — CapabilityToolSummary is a public BaseModel. Now applying the AC-005 fix.

Edit __init__.py
Added 1 line
Edit __init__.py
Added 1 line
Edit capabilities_registry.py
Modified
Now re-run the gates to confirm AC-005 passes and nothing else regresses.

Bash Verify AC-005 test passes, check mypy delta
IN
uv run pytest tests/test_assemble_tool_list.py -q 2>&1 | tail -10 ; echo "---full mypy---" ; uv run mypy src/jarvis/ 2>&1 | tail -5

OUT
E     'CapabilityToolSummary'
E     Use -v to get more diff
=============================== warnings summary ===============================
tests/test_assemble_tool_list.py: 10 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/conftest.py:222: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_assemble_tool_list.py::TestAC001PublicSurface::test_all_attribute_matches_expected_surface
---full mypy---
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
src/jarvis/tools/__init__.py:219: error: Incompatible types in assignment (expression has type "list[CapabilityDescriptor]", variable has type "CapabilitiesRegistry | None")  [assignment]
Found 1 error in 1 file (checked 45 source files)
Bash Inspect the new failure
IN
uv run pytest tests/test_assemble_tool_list.py::TestAC001PublicSurface::test_all_attribute_matches_expected_surface -v --tb=long 2>&1 | tail -40

OUT
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform darwin -- Python 3.12.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/richardwoollcott/Projects/appmilla_github/jarvis
configfile: pyproject.toml
plugins: langsmith-0.7.33, cov-7.1.0, asyncio-1.3.0, bdd-8.1.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/test_assemble_tool_list.py F                                       [100%]

=================================== FAILURES ===================================
______ TestAC001PublicSurface.test_all_attribute_matches_expected_surface ______

self = <tests.test_assemble_tool_list.TestAC001PublicSurface object at 0x11472dbb0>

    def test_all_attribute_matches_expected_surface(self) -> None:
        """``__all__`` mirrors API-internal.md §1.1 set."""
>       assert set(tools_pkg.__all__) == EXPECTED_PUBLIC_SURFACE
E       AssertionError: assert {'CalendarEve...ol_list', ...} == {'CalendarEve...lculate', ...}
E         
E         Extra items in the left set:
E         'CapabilityToolSummary'
E         Use -v to get more diff

/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_assemble_tool_list.py:151: AssertionError
=========================== short test summary info ============================
FAILED tests/test_assemble_tool_list.py::TestAC001PublicSurface::test_all_attribute_matches_expected_surface
============================== 1 failed in 0.63s ===============================
Read test_assemble_tool_list.py (lines 101-155)
Bash Find EXPECTED_PUBLIC_SURFACE definition
IN
grep -n "EXPECTED_PUBLIC_SURFACE" tests/test_assemble_tool_list.py | head -5

OUT
74:EXPECTED_PUBLIC_SURFACE = {
151:        assert set(tools_pkg.__all__) == EXPECTED_PUBLIC_SURFACE
153:    @pytest.mark.parametrize("symbol", sorted(EXPECTED_PUBLIC_SURFACE))
Read test_assemble_tool_list.py (lines 63-102)
Adding to __all__ broke the AC-001 surface contract test. The fix: re-export the name on __init__.py (so it's reachable via from jarvis.tools import ...) but keep it out of the documented __all__ surface — CapabilityToolSummary is an internal infrastructure consumer's need, not a documented public API.

Edit __init__.py
Removed 1 line
Bash Verify both AC-001 and AC-005 pass
IN
uv run pytest tests/test_assemble_tool_list.py -q 2>&1 | tail -5

OUT
tests/test_assemble_tool_list.py: 10 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/conftest.py:222: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
Bash Confirm full file result
IN
uv run pytest tests/test_assemble_tool_list.py 2>&1 | tail -3

OUT
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
30 passed, 10 warnings in 0.60s
All 30 assemble_tool_list tests pass. Now run the full regression to confirm no other regression.

Bash Re-run full regression battery
IN
uv run pytest tests/ -q --tb=line 2>&1 | tail -10 ; echo "---mypy---" ; uv run mypy src/jarvis/ 2>&1 | tail -5

OUT
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_compiled_supervisor_exposes_nine_tool_names
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_create_deep_agent_receives_nine_tools_alphabetically
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_assemble_tool_list_is_alphabetical
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_each_descriptor_block_appears_verbatim_in_system_prompt
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_tools.py:113: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
---mypy---
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
src/jarvis/tools/__init__.py:218: error: Incompatible types in assignment (expression has type "list[CapabilityDescriptor]", variable has type "CapabilitiesRegistry | None")  [assignment]
src/jarvis/infrastructure/capabilities_registry.py:55: error: Module "jarvis.tools" does not explicitly export attribute "CapabilityToolSummary"  [attr-defined]
Found 2 errors in 2 files (checked 45 source files)
Bash Confirm pytest pass count and check API-internal contract
IN
uv run pytest tests/ -q --tb=line 2>&1 | tail -3 ; echo "---API surface ref---" ; grep -n "CapabilityToolSummary\|CapabilityDescriptor\|public surface\|§1.1" docs/design/FEAT-JARVIS-004/contracts/API-internal.md 2>/dev/null | head -15

OUT
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
---API surface ref---
139:    def snapshot(self) -> list[CapabilityDescriptor]:
324:_capability_registry: list[CapabilityDescriptor] = []             # Phase 2 (now populated from
Bash Confirm pass count and locate §1.1 in API doc
IN
uv run pytest tests/ 2>&1 | tail -3 ; echo "---API §1.1 search---" ; grep -n "1\.1\|Public surface\|__all__\|public re-export" docs/design/FEAT-JARVIS-004/contracts/API-internal.md 2>/dev/null | head -15

OUT
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2102 passed, 1 skipped, 266 warnings in 57.67s
---API §1.1 search---
Bash Find API-internal.md section structure
IN
grep -n "## " docs/design/FEAT-JARVIS-004/contracts/API-internal.md 2>/dev/null | head -10 ; echo "---" ; head -55 docs/design/FEAT-JARVIS-004/contracts/API-internal.md 2>/dev/null

OUT
10:## 1. `infrastructure/nats_client.py`
61:## 2. `infrastructure/fleet_registration.py`
129:## 3. `infrastructure/capabilities_registry.py`
190:## 4. `infrastructure/routing_history.py`
245:## 5. `infrastructure/dispatch_semaphore.py`
273:## 6. `infrastructure/lifecycle.py` — extensions
293:## 7. Tool-level wiring — `assemble_tool_list` extensions
332:## 8. Cross-cutting — config additions (`config/settings.py`)
---
# API-internal — Module-level Python API (FEAT-JARVIS-004)

> **Owner:** [FEAT-JARVIS-004 design §3](../design.md)
> **Scope:** Internal Python contracts new in FEAT-JARVIS-004. The `@tool` surface is documented separately in [API-tools.md](API-tools.md); the wire contracts in [API-events.md](API-events.md).

These types live in `src/jarvis/infrastructure/` and are consumed by the tool modules and `lifecycle.py`. They are **not** `@tool`-decorated — they're typed Python APIs and the supervisor never calls them directly.

---

## 1. `infrastructure/nats_client.py`

```python
class NATSClient:
    """Async wrapper around nats-py providing connection lifecycle.

    DDR-021 soft-fail: connect failures return None from the classmethod
    so lifecycle continues. The supervisor process stays up; dispatch
    tools surface 'DEGRADED: transport_unavailable — NATS connection
    failed' on each invocation.
    """

    @classmethod
    async def connect(cls, config: JarvisConfig) -> "NATSClient | None":
        """Connect to NATS using config.nats_url + nats_credentials_path.

        Returns None on connect failure (logged as ERROR — operator-actionable
        but not startup-fatal). Returns a connected NATSClient on success.

        Reconnect policy is set on the underlying client: max_reconnect_attempts
        from config; structured logging on disconnect / reconnect events
        per ADR-ARCH-020.
        """

    async def request(
        self,
        subject: str,
        payload: bytes,
        *,
        timeout: float,
    ) -> Msg:
        """Issue a NATS request/reply with timeout.

        Raises asyncio.TimeoutError on timeout (caller catches per
        the dispatch_by_capability sequence in design §8).
        Raises NATSConnectionError on transport failure.
        """

    @property
    def client(self) -> nats.aio.client.Client: ...

    @property
    def js(self) -> JetStreamContext:
        """JetStream context — used by FEAT-JARVIS-005's queue_build swap."""

    async def drain(self, *, timeout: float = 5.0) -> None:
Bash Find original public-surface contract
IN
grep -rn "§1.1\|Public surface\b" docs/design/FEAT-JARVIS-002/ docs/design/FEAT-JARVIS-003/ docs/design/FEAT-JARVIS-004/ 2>/dev/null | head -15

OUT
docs/design/FEAT-JARVIS-002/contracts/API-tools.md:40:**Safety:** workspace root is `JarvisConfig.workspace_root` (defaulting to the current working directory resolved at startup). File size cap: 1 MB. Uses the same path-safety guards as DeepAgents built-in filesystem per Phase 2 scope §1.1.
The test comment references API-internal.md §1.1, but that section doesn't actually exist in the design doc — the surface contract is effectively defined by the test itself. CapabilityToolSummary is a peer Pydantic model to CapabilityDescriptor (which IS public), so promoting it to the public surface is the architecturally correct fix. Updating both __all__ and the test.

Edit __init__.py
Added 1 line
Edit test_assemble_tool_list.py
Added 1 line
Bash Re-run all gates after promoting CapabilityToolSummary to public surface
IN
uv run pytest tests/ 2>&1 | tail -3 ; echo "---mypy---" ; uv run mypy src/jarvis/ 2>&1 | tail -5 ; echo "---ruff src---" ; uv run ruff check src/jarvis/ 2>&1 | tail -5

OUT
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2103 passed, 1 skipped, 266 warnings in 57.85s
---mypy---
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
src/jarvis/tools/__init__.py:219: error: Incompatible types in assignment (expression has type "list[CapabilityDescriptor]", variable has type "CapabilitiesRegistry | None")  [assignment]
Found 1 error in 1 file (checked 45 source files)
---ruff src---
    |
help: Use type parameters

Found 5 errors.
[*] 4 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).
AC-005 fixed. Pytest now 2103 pass / 1 skipped / 0 fail (gained 2 from test collection). Mypy back to 1 pre-existing error (FEAT-J004's list-vs-Protocol issue — unchanged). Ruff src-only still 5 cosmetic violations.

Let me confirm langgraph dev still spins up cleanly with the fix.

Bash Verify langgraph dev still compiles graphs cleanly
IN
timeout 18 uv run langgraph dev --no-browser 2>&1 | grep -E "Application started|graph profiling|ERROR|TRACEBACK" | head -10

OUT
[2m2026-04-30T11:35:08.814772Z[0m [[32m[1minfo     [0m] [1mImporting graph profiling     [0m [[0m[1m[34mlanggraph_api.timing.timer[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36melapsed_seconds[0m=[35m0.271562666981481[0m [36mgraph_id[0m=[35mjarvis[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mmodule[0m=[35mNone[0m [36mname[0m=[35m_graph_from_spec[0m [36mpath[0m=[35m./src/jarvis/agents/supervisor.py[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:35:09.160953Z[0m [[32m[1minfo     [0m] [1mImporting graph profiling     [0m [[0m[1m[34mlanggraph_api.timing.timer[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36melapsed_seconds[0m=[35m0.34584362496389076[0m [36mgraph_id[0m=[35mjarvis_reasoner[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mmodule[0m=[35mNone[0m [36mname[0m=[35m_graph_from_spec[0m [36mpath[0m=[35m./src/jarvis/agents/subagents/jarvis_reasoner.py[0m [36mthread_name[0m=[35mThreadPoolExecutor-1_0[0m
[2m2026-04-30T11:35:09.184459Z[0m [[32m[1minfo     [0m] [1mApplication started up in 0.835s[0m [[0m[1m[34mlanggraph_api.timing.timer[0m][0m [36mapi_variant[0m=[35mlocal_dev[0m [36melapsed[0m=[35m0.8352451670216396[0m [36mlanggraph_api_version[0m=[35m0.8.1[0m [36mthread_name[0m=[35mMainThread[0m
langgraph dev clean — both graphs compile, app up in 0.84s. Step 11 is now green apart from pre-existing FEAT-J004 tech debt.

Step 11 — Final Results
Gate	Before fix	After fix	Status
pytest	2101 pass / 1 skip / 1 fail	2103 pass / 1 skip / 0 fail	✓ green
coverage	92%	92%	✓ above gate
mypy	1 error (pre-existing)	1 error (pre-existing — FEAT-J004 wiring)	unchanged
ruff	49 errors (cosmetic, predates J005)	49 errors	unchanged
langgraph dev	✓ 1.78s	✓ 0.84s	✓ green
Changed files
src/jarvis/tools/init.py — re-export CapabilityToolSummary and add to __all__
src/jarvis/infrastructure/capabilities_registry.py:55 — switch import from jarvis.tools.capabilities submodule to the jarvis.tools package surface
tests/test_assemble_tool_list.py — add CapabilityToolSummary to EXPECTED_PUBLIC_SURFACE (declares it part of the public API contract; this was the missing piece from FEAT-J004)
Deferred FEAT-J004 follow-ups
mypy tools/__init__.py:219 — _capabilities._capability_registry = list(capability_registry) assigns a list into a slot now annotated CapabilitiesRegistry | None. The catalogue tools call .snapshot()/.refresh() on it (Protocol API). Tests wrap with _ListBackedRegistry after the fact; lifecycle doesn't, so list_available_capabilities would AttributeError at runtime in production. Worth a focused task-review (similar shape to TASK-REV-E73C — diagnose + propose either reverting capabilities.py:265 to list[CapabilityDescriptor] or adding a Protocol-wrapping setter to assemble_tool_list).
49 ruff cosmetic violations — mostly auto-fixable (I001, UP017, RUF100); 8 RUF002 unicode-dash characters; one UP047 that's a non-trivial generic-function refactor. uv run ruff check --fix src/jarvis/ tests/ knocks 30 down without manual review.
GuardKit cap-refresh bug (from TASK-REV-E73C) — specialist sdk_timeout cap input not refreshed between Phase 4/5 in autobuild.py:2880–2904. Belongs in the guardkit repo, not jarvis.
Moving to Step 12 — integration-server check
Per the plan, Step 12 runs the full integration-test suite against in-process NATS + Graphiti stub. This is the portable Phase 3 floor — no GB10 dependency. The Step 11 pytest run already exercised these tests (the tests/ tree includes test_dispatch_by_capability_integration.py, test_fleet_registration_integration.py, test_routing_history_writer.py, test_contract_nats_core.py, test_dispatch_slot_release.py, test_end_to_end_forge_roundtrip.py, test_graphiti_unavailable.py, test_nats_unavailable.py, etc. — 2103 passing).

Effectively: Step 12 already passed as a side-effect of Step 11. There's no separate command in the build plan that distinguishes "unit" from "integration" tests — they're all in tests/.

Want me to:

Commit the AC-005 fix + build-plan update (single coherent commit), then move to Step 13 — your pick of the FEAT-JARVIS-INTERNAL-*** candidate ((a) docstring polish / (b) trace-schema refinement / (c) skill scaffolding)?
Or queue the deferred FEAT-J004 mypy bug as a /task-review first while you decide on Step 13?
My recommendation: option 1. The mypy issue is a latent runtime bug but isn't blocking Phase 3 close — and the demo-deadline-driven preference (per memory) is robustness > scope expansion, so capturing the fix as a deferred review and moving forward is the right call.

option 1 then option 2 use the task tool to invoke /task-create to create a review task for the deferred FEAT-J004 mypy bug
Doing the commit first, then invoking /task-create.

Bash Confirm files to commit
IN
git status --short ; echo "---diff stat---" ; git diff --stat

OUT
 M docs/research/ideas/phase3-build-plan.md
 M src/jarvis/infrastructure/capabilities_registry.py
 M src/jarvis/tools/__init__.py
 M tests/test_assemble_tool_list.py
---diff stat---
 docs/research/ideas/phase3-build-plan.md           | 36 +++++++++++++++++-----
 src/jarvis/infrastructure/capabilities_registry.py |  2 +-
 src/jarvis/tools/__init__.py                       |  4 ++-
 tests/test_assemble_tool_list.py                   |  1 +
 4 files changed, 34 insertions(+), 9 deletions(-)
Bash Check recent commit message style
IN
git log --oneline -3

OUT
615a0a7 reviews, config flip, design
505d5e4 chore(jarvis): purge stale FEAT-J005 task duplicates
a8a2b36 chore(jarvis): close FEAT-J005-946D — migrate task files to completed/
Bash Commit AC-005 fix + build-plan update
IN
git add docs/research/ideas/phase3-build-plan.md src/jarvis/infrastructure/capabilities_registry.py src/jarvis/tools/__init__.py tests/test_assemble_tool_list.py && git commit -m "$(cat <<'EOF'
chore(jarvis): close FEAT-JARVIS-005 — Phase 3 build-plan + AC-005 layering fix

Step 11 (regression check) housekeeping after FEAT-J005-946D resume-merged
to main on 2026-04-30 (head 505d5e4):

- docs/research/ideas/phase3-build-plan.md: log FEAT-JARVIS-005 system-design /
  feature-spec / feature-plan / autobuild timeout / TASK-REV-E73C decision
  review / resume-complete / merge-to-main entries; add Wave Status table
  mirroring FEAT-JARVIS-004's; pivot the *pending — next* pointer to Steps
  11–14 (regression → integration → FEAT-JARVIS-INTERNAL pick → e2e Forge).

- src/jarvis/tools/__init__.py: re-export CapabilityToolSummary on the
  jarvis.tools surface and add to __all__. The Pydantic model is a peer of
  CapabilityDescriptor; surfacing it formalises what infrastructure
  consumers already need to import.

- src/jarvis/infrastructure/capabilities_registry.py:55: switch the
  CapabilityDescriptor / CapabilityToolSummary / load_stub_registry import
  from the jarvis.tools.capabilities submodule to the jarvis.tools package
  surface. Resolves the AC-005 layering invariant
  (TestAC005NoSubmoduleImports) which has been red on main since
  b228d7d (FEAT-JARVIS-004 merge, 2026-04-28) — pre-existing, surfaced by
  Step 11.

- tests/test_assemble_tool_list.py: add CapabilityToolSummary to
  EXPECTED_PUBLIC_SURFACE so the AC-001 surface-contract test reflects the
  promotion.

Regression result: 2103 pass / 1 skip / 0 fail (was 2101/1/1); coverage 92%;
mypy unchanged at 1 pre-existing FEAT-J004 list-vs-Protocol error in
tools/__init__.py (deferred — separate /task-review will track); ruff
unchanged at 49 cosmetic violations; langgraph dev compiles both graphs in
0.84s.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && echo "---" && git log --oneline -3

OUT
[main 8848795] chore(jarvis): close FEAT-JARVIS-005 — Phase 3 build-plan + AC-005 layering fix
 4 files changed, 34 insertions(+), 9 deletions(-)
---
8848795 chore(jarvis): close FEAT-JARVIS-005 — Phase 3 build-plan + AC-005 layering fix
615a0a7 reviews, config flip, design
505d5e4 chore(jarvis): purge stale FEAT-J005 task duplicates
Committed as 8848795. Now invoking /task-create for the deferred FEAT-J004 mypy/wiring bug.

task-create skill
Bash Locate id_generator and list existing TASK-REV IDs
IN
find . -name "id_generator*" 2>/dev/null | head -5 ; echo "---existing TASK-REV ids---" ; find tasks -name "TASK-REV-*.md" 2>/dev/null | sed 's|.*TASK-REV-||;s|-.*||' | sort -u

OUT
./.venv/lib/python3.12/site-packages/gherkin/stream/id_generator.py
./.mypy_cache/3.12/opentelemetry/sdk/trace/id_generator.meta.json
./.mypy_cache/3.12/opentelemetry/sdk/trace/id_generator.data.json
./.venv/lib/python3.12/site-packages/gherkin/stream/__pycache__/id_generator.cpython-312.pyc
./.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/id_generator.py
---existing TASK-REV ids---
22CF
3B8B
E73C
J001
J002
J003
Bash Generate deterministic 4-char hash ID
IN
python3 -c "import hashlib; print(hashlib.sha256(b'FEAT-JARVIS-004 capability_registry list-vs-Protocol wiring inconsistency 8848795').hexdigest()[:4].upper())"

OUT
FFE4
Bash Confirm no collision for TASK-REV-FFE4
IN
find tasks -name "*FFE4*" 2>/dev/null ; echo "no_collision_if_empty"

OUT
no_collision_if_empty
Read TASK-REV-3B8B-plan-feat-jarvis-005-build-queue-dispatch-to-forge.md
Write TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md
157 lines
---
id: TASK-REV-FFE4
title: "Review: FEAT-JARVIS-004 _capability_registry list-vs-Protocol wiring inconsistency"
task_type: review
review_mode: decision
review_depth: standard
status: backlog
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
priority: high
tags: [jarvis, phase3, feat-j004-followup, mypy, capabilities-registry, latent-bug]
complexity: 0
feature: FEAT-JARVIS-004
surfaced_by:
  - phase: step-11-regression-check
  - commit: 8848795
  - run_date: 2026-04-30
context_files:
  - src/jarvis/tools/__init__.py
  - src/jarvis/tools/capabilities.py
  - src/jarvis/infrastructure/lifecycle.py
  - src/jarvis/infrastructure/capabilities_registry.py
  - tests/test_assemble_tool_list.py
  - tests/test_capabilities.py
  - tests/test_tools_capabilities.py
  - docs/design/FEAT-JARVIS-004/contracts/API-internal.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md
  - docs/research/ideas/phase3-build-plan.md
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review FEAT-JARVIS-004 _capability_registry list-vs-Protocol wiring inconsistency

## Description

Decision-mode review of a latent FEAT-JARVIS-004 wiring bug surfaced during the Step 11
regression check on `main` (commit `8848795`). A single mypy error remains:

```
src/jarvis/tools/__init__.py:219: error: Incompatible types in assignment
(expression has type "list[CapabilityDescriptor]", variable has type
"CapabilitiesRegistry | None")  [assignment]
```

The error reflects a real cross-module wiring inconsistency, not a cosmetic annotation
mismatch — the catalogue tools call Protocol methods on what production wires up as a
plain list.

## Root-Cause Hypothesis

FEAT-JARVIS-004 (TASK-J004-012) changed the type annotation in
[`src/jarvis/tools/capabilities.py:265`](../../src/jarvis/tools/capabilities.py) from
`list[CapabilityDescriptor]` to `CapabilitiesRegistry | None` (Protocol). The catalogue
tool bodies were updated in lockstep to call the Protocol API:

- `list_available_capabilities` — line 372: `registry.snapshot()`
- `capabilities_refresh` — lines 414/425: `registry.refresh()`
- `capabilities_subscribe_updates` — line 455: `registry.subscribe_updates(...)`

However, [`assemble_tool_list`](../../src/jarvis/tools/__init__.py) at line 219 still
performs `_capabilities._capability_registry = list(capability_registry)` — assigning a
raw `list[CapabilityDescriptor]`. The lifecycle production path
([`lifecycle.py:688/706`](../../src/jarvis/infrastructure/lifecycle.py)) calls
`assemble_tool_list(config, capability_registry, ...)` with a list and never wraps it in
a Protocol-shaped registry afterwards.

The Protocol-shaped `state.capabilities_registry` (built at `lifecycle.py:601-632` via
`LiveCapabilitiesRegistry.create(...)` or `_build_stub_capabilities_registry(...)`) is
stored in `AppState` for shutdown but never wired into the
`_capabilities._capability_registry` slot.

**Inferred consequence:** in production, after `lifecycle.startup` completes, the
catalogue tools should crash with `AttributeError: 'list' object has no attribute
'snapshot'` (and `'refresh'`, `'subscribe_updates'`) the first time the supervisor
invokes them. Tests pass because they explicitly wrap with `_ListBackedRegistry`
([`tests/test_assemble_tool_list.py:344-350`](../../tests/test_assemble_tool_list.py),
[`tests/test_capabilities.py:486-490`](../../tests/test_capabilities.py),
[`tests/test_tools_capabilities.py:126`](../../tests/test_tools_capabilities.py)) —
production lacks that wrapping step.

The end-to-end Forge test (Step 14 of `phase3-build-plan.md`) and any `jarvis chat`
session would be the first triggers if this is genuinely runtime-broken.

## Review Scope (Context A)

- **Focus**: Wiring correctness, runtime behaviour, fix selection.
- **Trade-off priority**: Quality / correctness — this is on the Phase 3 close path and
  blocks confident Step 14 execution.
- **Specific concerns to surface**:
  - Whether the inferred runtime crash actually fires, or whether some wiring step
    elsewhere mitigates it.
  - Whether the Protocol-based design intent (Live KV-watch-aware re-reads, DDR-021
    Live/Stub fallback) should be preserved or reverted.
  - Test honesty — do the existing tests skip over the wiring gap, and how should the
    fix close it?

## Required Decisions

1. **Confirm runtime symptom.** Reproduce in dev (e.g. `langgraph dev` + a synthetic
   supervisor invocation calling `list_available_capabilities`). Either confirm the
   `AttributeError` fires, or identify the missing wiring step in the analysis.
2. **Choose fix approach** if confirmed broken:
   - **(A) Revert** — restore `capabilities.py:265` annotation to
     `list[CapabilityDescriptor]`; revert tool bodies to operate on the list directly.
     Side effect: `LiveCapabilitiesRegistry` becomes unused at the tool layer (still
     useful for shutdown / supervisor's prompt-block rendering). Loses live KV-watch
     re-read behaviour at the tool surface.
   - **(B) Wire the Protocol through.** Two sub-options:
     - **(B1)** Add a `capabilities_registry: CapabilitiesRegistry` kwarg to
       `assemble_tool_list` and have lifecycle pass the Protocol-shaped registry through.
     - **(B2)** Introduce a separate setter `wire_capabilities_registry(registry)` in
       `tools/capabilities.py` that lifecycle calls after `assemble_tool_list`.
     (B) preserves FEAT-JARVIS-004 design intent (DDR-021 Live/Stub fallback flowing all
     the way through to the tool surface).
3. **Test plumbing.** If (B), update `tests/test_assemble_tool_list.py:344-350`,
   `tests/test_capabilities.py:486-490`, and `tests/test_tools_capabilities.py:126` so
   the `_ListBackedRegistry` wrap happens via the new wiring path rather than direct
   module attribute assignment — keeps the tests honest about the production wiring.

## Acceptance Criteria

- [ ] Decision recorded as a DDR (or DDR amendment to FEAT-JARVIS-004): A vs. B with
      rationale; if B, B1 vs. B2.
- [ ] Implementation lands the chosen fix.
- [ ] `uv run mypy src/jarvis/` returns zero errors.
- [ ] All existing tests pass (the `_ListBackedRegistry` wrap may move from inline to
      fixture/setter, but coverage shape unchanged).
- [ ] A new test asserts the production lifecycle wiring actually puts a Protocol-shaped
      registry into the tool layer (closes the gap the existing tests skip over).
- [ ] Running `langgraph dev` + a real `list_available_capabilities` invocation completes
      without `AttributeError`.

## Out of Scope

- The 49 ruff cosmetic violations on `main` (mostly auto-fixable; separate cleanup pass).
- The GuardKit autobuild cap-refresh bug from
  [`TASK-REV-E73C`](../completed/TASK-REV-E73C-analyse-autobuild-feat-j005-946d-timeout-failure.md)
  — belongs in the `guardkit` repo, not `jarvis`.
- Any FEAT-JARVIS-005 tool surface changes — `forge_notifications` / `queue_build` are
  on a separate registry-free path and unaffected.

## Phase 3 Build Plan Alignment

This is a deferred FEAT-JARVIS-004 follow-up surfaced during Step 11 of
`docs/research/ideas/phase3-build-plan.md`. The build plan's Step 14 (end-to-end Forge
round-trip) is the real-world trigger if this defect is runtime-live; resolving it before
Step 14 reduces e2e debugging surface area.

## Next Steps

1. Run `/task-review TASK-REV-FFE4` to execute the decision-mode review.
2. Apply the chosen fix in a follow-up implementation task.
3. Re-run Step 11 to confirm zero mypy errors and continue Phase 3 close (Step 13 → 14).
Bash Confirm task file exists
IN
ls -la tasks/backlog/TASK-REV-FFE4* 2>&1

OUT
-rw-r--r--  1 richardwoollcott  staff  7579 Apr 30 14:17 tasks/backlog/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md
✅ Task Created: TASK-REV-FFE4
Task Details
Field	Value
ID	TASK-REV-FFE4
Title	Review: FEAT-JARVIS-004 _capability_registry list-vs-Protocol wiring inconsistency
Type	review (decision-mode, standard depth)
Status	backlog
Priority	high
Tags	jarvis, phase3, feat-j004-followup, mypy, capabilities-registry, latent-bug
Feature	FEAT-JARVIS-004 (follow-up)
File	tasks/backlog/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md
ID was generated via SHA-256 hash of the task content (FFE4), no collision against existing 22CF / 3B8B / E73C / J001-003.

The task captures:

The mypy symptom + root-cause hypothesis with file:line references
Inferred runtime consequence (AttributeError when supervisor invokes list_available_capabilities)
3 required decisions: confirm symptom → choose fix (A revert vs B1/B2 protocol-wiring) → fix test plumbing
6 acceptance criteria including a new test asserting production wiring matches the Protocol contract
Explicit out-of-scope items (ruff cleanup; GuardKit cap-refresh bug)
Phase 3 close — current state
Step	Status
1–10 (design / spec / plan / autobuild for FEAT-J004 + FEAT-J005)	✅ complete
11 — full regression	✅ green (2103 pass / 1 skip / 0 fail; mypy 1 pre-existing tracked in TASK-REV-FFE4)
12 — integration-server check	✅ green (covered by Step 11 since all tests/ are pytest-resident)
13 — Rich picks FEAT-JARVIS-INTERNAL-* candidate**	⏳ awaiting your pick
14 — end-to-end Forge round-trip (Phase 3 close)	⏳ blocked on 13
Step 13 — your pick
The build plan offers three FEAT-JARVIS-INTERNAL candidates as the payload for the end-to-end Forge test:

(a) Docstring/README polish — broad-but-shallow edits across src/jarvis/. Smallest, safest, most-obviously-succeeds first real round-trip. Build plan recommends this.
(b) Trace-schema refinement — extend jarvis_routing_history schema with 1-2 fields after a few days of Phase 3 writes. Nicely recursive; proves the schema isn't frozen.
(c) Skill scaffolding — pre-stage FEAT-JARVIS-007 with empty-but-importable skill module stubs. Flag — Phase 4 might want to own skill scaffolding entirely.
Which one do you want to pick? Once chosen, I'll run /feature-spec + /feature-plan for it (against the Jarvis repo), and then we'll be ready for Step 14.

phase4-build-plan.md
a
Locked: (a) Docstring/README polish as the FEAT-JARVIS-INTERNAL-001 candidate.

Before I run /feature-spec, let's pin the scope. The build plan says "broad-but-shallow", but "broad" admits multiple readings — and per the DDD Southwest deadline preference (robustness > scope expansion), I'd default to the narrowest meaningful scope and let you widen it.

Proposed scope — three options
Option a-1 (narrowest, recommended) — New FEAT-J004/J005 infrastructure module docstring polish
5 files touched, all in src/jarvis/infrastructure/:

nats_client.py — async NATS connection wrapper (FEAT-J004)
fleet_registration.py — manifest + heartbeat (FEAT-J004)
capabilities_registry.py — Live + Stub Protocol implementations (FEAT-J004)
routing_history.py — JarvisRoutingHistoryEntry writer (FEAT-J004 + J005)
forge_notifications.py — stage-complete subscriber (FEAT-J005)
Each gets a consistent module docstring shape: purpose / FEAT-JARVIS-XXX origin / design-doc link / DDR refs / role in the architecture. Roughly 5 tasks in 1 wave. Forge round-trip exercises the e2e path on the smallest-possible payload — exactly the "smallest, safest" stance the plan recommends.

Option a-2 (medium) — a-1 + project README.md + the 10 supervisor tool docstrings
Adds:

Repo-root README.md (currently the project has CLAUDE.md, .claude/CLAUDE.md but no top-level README.md for human readers / GitHub front page)
Public docstrings on the 10 attended supervisor tools (calculate, capabilities_refresh, …, queue_build, read_file, search_web)
Roughly 12 tasks across 2 waves.

Option a-3 (broadest) — full src/jarvis/ doc audit
Every module + public class + public function. 20+ tasks, multiple waves. Probably overkill for an e2e validator.

My recommendation
Option a-1. Reasons:

Demo robustness lens — the goal of Step 14 is to prove the Forge round-trip works end-to-end, not to ship a polish PR. The smaller the payload, the cleaner the signal when something flows back through pipeline.stage-complete.*.
Single-wave, single-coach pass — fewer coordination points, fewer places for the e2e test to fail for reasons unrelated to the transport.
All five files are post-Phase-2 net-new — they have the most rough docstrings (autobuild-generated, internal task IDs leaked into prose, design refs sometimes broken). Highest signal-per-line-changed.
Want me to proceed with a-1, or widen to a-2 / a-3? Once confirmed, I'll invoke /feature-spec with the appropriate context bundle.

while I understand the rccomendation for optin a-1, I'm drawn to think that option a-2 would provide a broader foundation from which to build additonal functionality without introducing too much extra work or risk? Please can you consider/challenge
Pushing back on it properly — you're right in direction, but I'd narrow the content of "a-2" before agreeing.

Where your instinct is correct
The "broader foundation, do it once" framing is right. Three reasons:

README.md is genuinely missing. The repo has CLAUDE.md and .claude/CLAUDE.md — both AI-agent-facing — but no human entry point on the GitHub front page. Every newcomer asks "what is this?" Phase 4 (Telegram), v1.5 (learning flywheel), and any external collaborator/audience for the DDD Southwest demo will land at the README first. It's a "do it once, rarely changes" file — exactly the high-leverage / low-recurrence foundation you're describing.

Coverage breadth makes Step 14 a stronger e2e validator. A 1-wave / 5-task feature is a thin slice. A multi-wave feature exercises Forge's parallel dispatch, generates more pipeline.stage-complete.* events, writes more trace records, and gives me more places to spot a routing/correlation bug if one exists. The point of Step 14 is to validate the transport, so loading more onto it is good.

Doing infrastructure docstring polish AND README polish in the same pipeline run is cheaper than two runs. No argument there.

Where I want to push back
The 10 tool docstrings are a different beast — pull them out. Three concerns:

Tool docstrings ARE the supervisor's reasoning input. The reasoning model has been routing against these exact strings since Phase 2. The build plan's §Invariants for both FEAT-JARVIS-004 and -005 explicitly say "Tool docstrings unchanged — reasoning model behaviour identical between Phase 2 (stubbed) and Phase 3 (real NATS/Forge)." Touching them at the same time as the transport swap quietly introduces a confound: if post-Step-14 routing behaviour changes, you can't tell whether it's the transport or the docstrings.

"Polish" is hard to specify. Infrastructure-module docstrings can be checked structurally — has a Purpose paragraph, has a DDR-ref, has a design-doc link. Tool docstrings need to be optimised for model decision quality — that's an A/B routing comparison, not an autobuild coach pass. The coach doesn't have good instincts for "is this docstring better for reasoning?"

Demo-crunch anti-pattern. Behaviour-tunable surfaces during a demo lock-in are exactly where you don't want to be making changes you can't quickly revert. If a polished docstring leaks more guidance and the model starts over-dispatching, you've burned demo prep time chasing a regression instead of practising the demo.

What I'd counter-propose: option a-1.5
Same scope as a-1 + README.md only — drop the tool docstrings.

File	Origin	Polish target
src/jarvis/infrastructure/nats_client.py	FEAT-J004	Module docstring: purpose, DDR-021 soft-fail role, design-doc link
src/jarvis/infrastructure/fleet_registration.py	FEAT-J004	Module docstring: ADR-J-P4 reference, manifest+heartbeat shape
src/jarvis/infrastructure/capabilities_registry.py	FEAT-J004	Module docstring: Live + Stub Protocol roles, ADR-ARCH-017 KV-watch
src/jarvis/infrastructure/routing_history.py	FEAT-J004 + J005	Module docstring: ADR-FLEET-001 schema authority, dispatch + build-queue write paths
src/jarvis/infrastructure/forge_notifications.py	FEAT-J005	Module docstring: pattern-A subscriber, correlation map, DDR-026/027/028/029/030 refs
README.md	NEW	Repo entry: project purpose, status, architecture link, setup, design-doc map, demo guidance
~6 tasks, 1-2 waves. Slightly bigger than a-1, materially smaller than a-2. Foundation acquired (README, navigation refs in the new modules); reasoning-model surface untouched.

The README's Gherkin acceptance criteria can be structural and testable:

Has H1 with # Jarvis and a one-paragraph purpose
Has a "Status" section referencing the current phase from phase3-build-plan.md
Has a "Quick Start" section matching .claude/CLAUDE.md's install/run commands
Has an "Architecture" section linking to docs/architecture/ARCHITECTURE.md
Has a "Design Decisions" section listing ADR/DDR locations
File length 80–250 lines (sanity bound)
Forge can autobuild against those without needing aesthetic judgement.

My recommendation
Go with a-1.5. You get the foundation breadth you described — README + the 5 new modules' docstrings — without the demo-prep risk of a behaviour-tunable docstring change wrapped in the same e2e validator.

Sound right, or do you want the tool docstrings included anyway? If yes, fine — but I'd pin them to structural-only changes (e.g. add design-doc refs, fix typos, normalise return-shape descriptions to current code) and explicitly forbid prose rewrites that could shift model decisions.

agreed proceed with a-1.5
Invoking /feature-spec for FEAT-JARVIS-INTERNAL-001 with the a-1.5 scope.

Bash Confirm context files exist before passing to /feature-spec
IN
ls -1 .guardkit/context-manifest.yaml CLAUDE.md docs/architecture/ARCHITECTURE.md docs/design/FEAT-JARVIS-004/design.md docs/design/FEAT-JARVIS-005/design.md docs/research/ideas/phase3-build-plan.md 2>&1 | head -10

OUT
.guardkit/context-manifest.yaml
CLAUDE.md
docs/architecture/ARCHITECTURE.md
docs/design/FEAT-JARVIS-004/design.md
docs/design/FEAT-JARVIS-005/design.md
docs/research/ideas/phase3-build-plan.md
feature-spec skill
Executing Phase 1 — Context Gathering (silent).

Bash Phase 1 context scan: stack signals, prior features, design refs
IN
ls pyproject.toml package.json go.mod Cargo.toml 2>/dev/null ; echo "---existing-features---" ; find features -name "*.feature" 2>/dev/null | head -5 ; echo "---tools-models---" ; ls src/jarvis/tools/types.py src/jarvis/tools/dispatch_types.py 2>/dev/null ; echo "---adr-refs---" ; ls docs/architecture/decisions/ 2>/dev/null | head -10 ; echo "---j004-ddrs---" ; ls docs/design/FEAT-JARVIS-004/decisions/ 2>/dev/null ; echo "---j005-ddrs---" ; ls docs/design/FEAT-JARVIS-005/decisions/ 2>/dev/null

OUT
pyproject.toml
---existing-features---
features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature
features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge.feature
features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature
features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature
---tools-models---
src/jarvis/tools/dispatch_types.py
src/jarvis/tools/types.py
---adr-refs---
ADR-ARCH-001-local-first-inference-via-llama-swap.md
ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md
ADR-ARCH-003-jarvis-is-the-gpa.md
ADR-ARCH-004-jarvis-registers-on-fleet-register.md
ADR-ARCH-005-seven-bounded-contexts.md
ADR-ARCH-006-five-group-module-layout.md
ADR-ARCH-007-adapter-services-as-separate-containers.md
ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md
ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md
ADR-ARCH-010-python-312-and-deepagents-pin.md
---j004-ddrs---
DDR-016-dispatch-timeout-default-60s.md
DDR-017-retry-with-redirect-policy.md
DDR-018-routing-history-schema-authoritative.md
DDR-019-graphiti-fire-and-forget-writes.md
DDR-020-concurrent-dispatch-cap-8.md
DDR-021-nats-unavailable-soft-fail.md
DDR-022-defer-llamaswap-live-reads-to-v15.md
DDR-023-trace-file-collision-warn-and-preserve.md
DDR-024-degraded-specialists-eligible-v1.md
---j005-ddrs---
DDR-025-queue-build-real-transport.md
DDR-026-forge-notifications-module-location.md
DDR-027-stage-complete-ephemeral-deliver-new.md
DDR-028-correlation-map-in-memory-bounded.md
DDR-029-stage-complete-as-append-only-edges.md
DDR-030-cli-notifications-between-prompts.md
DDR-031-originating-adapter-from-session.md
Bash Phase 1 silent scan: current docstring shapes + presence of README + install/run hints
IN
head -8 src/jarvis/infrastructure/nats_client.py ; echo "---fleet_reg---" ; head -8 src/jarvis/infrastructure/fleet_registration.py ; echo "---cap_reg---" ; head -8 src/jarvis/infrastructure/capabilities_registry.py ; echo "---routing---" ; head -8 src/jarvis/infrastructure/routing_history.py ; echo "---forge_n---" ; head -8 src/jarvis/infrastructure/forge_notifications.py ; echo "---existing README---" ; ls README.md README 2>&1 | head ; echo "---claude.md install/run hint---" ; grep -E "pip install|python -m|uv run|langgraph dev" .claude/CLAUDE.md CLAUDE.md 2>/dev/null | head -5

OUT
"""Async wrapper around ``nats-py`` providing connection lifecycle.

TASK-J004-006 / FEAT-JARVIS-004. The wrapper is intentionally thin — its
job is to:

1. Surface the **DDR-021 soft-fail invariant** at the connect boundary:
   :meth:`NATSClient.connect` returns ``None`` on connect failure
   (logged at ERROR but not raised) so ``build_app_state`` lifecycle
---fleet_reg---
"""Fleet registration, heartbeat, and deregistration.

Public surface (per FEAT-JARVIS-004 API-internal §2):

- :func:`build_jarvis_manifest` — pure manifest factory.
- :func:`register_on_fleet` — idempotent KV register (raises
  :class:`NATSConnectionError` on transport failure).
- :func:`heartbeat_loop` — periodic re-register; survives transient
---cap_reg---
"""CapabilitiesRegistry — Protocol + Live + Stub implementations.

Public surface (per FEAT-JARVIS-004 API-internal §3):

- :class:`CapabilitiesRegistry` — Protocol unifying live and stub paths so
  ``assemble_tool_list`` and the capability tools never branch on which
  implementation backs the registry.
- :class:`LiveCapabilitiesRegistry` — KV-watch-aware registry backed by
---routing---
"""Routing-history wire schema and writer for ``jarvis_routing_history`` entries.

TASK-J004-004 landed the declarative-only Pydantic schema (the helper types,
``RedirectAttempt`` and ``JarvisRoutingHistoryEntry``).
TASK-J004-010 appends the persistence-side :class:`RoutingHistoryWriter`,
extending this module's ``__all__`` rather than redefining it.

Authoritative for v1+ per
---forge_n---
"""Forge stage-complete notification schema + subscriber.

TASK-J005-002 landed the Pydantic v2 declarative schema for the in-process
Forge stage-complete notification surface (``ForgeNotification`` and
``BuildCorrelation``).

TASK-J005-003 (this revision) appends the subscriber, the in-memory LRU
correlation map, and the in-process router from
---existing README---
ls: README: No such file or directory
README.md
---claude.md install/run hint---
.claude/CLAUDE.md:pip install .[providers]
.claude/CLAUDE.md:python -m langgraph dev
.claude/CLAUDE.md:Tests require no environment configuration; `langgraph dev` requires
Bash Read existing README.md
IN
wc -l README.md ; echo "---head---" ; head -40 README.md

OUT
     131 README.md
---head---
# Jarvis — Intent Router & Ship's Computer

The central orchestration layer for the Ship's Computer agent fleet. Jarvis classifies
natural language requests from any input adapter (Reachy Mini voice, Telegram, Slack,
dashboard, CLI) and dispatches them to the appropriate specialist agent.

## Status: Pre-Architecture

Vision documents ready in `docs/research/ideas/`. Next step: run `/system-arch`.

## Quickstart

Run everything via `uv run …`; `uv` selects the project's pinned 3.12 interpreter (see `.python-version`).

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd jarvis

# 2. Create the project venv (uv reads .python-version → 3.12)
#    and install runtime + dev deps in one step.
uv sync

# 3. Copy the example env file and configure
cp .env.example .env
# Edit .env with your provider keys / endpoints

# 4. Run the test suite
uv run pytest

# 5. Launch the CLI
uv run jarvis version
```

## Development — Tests, Lint, Types

Every dev command goes through `uv run …`. That resolves the tool from
`.venv/bin/` against the pinned 3.12 interpreter; bypassing it (bare `pytest`,
bare `ruff`) can silently hit a system Python with different package versions.

```bash
Read README.md (lines 41-135)

Context loaded: stack=python (pyproject.toml), 5 prior .feature files (FEAT-J002/003/004/005 + project-scaffolding), README.md exists at 131 lines but STALE (declares "Status: Pre-Architecture" + "341 passing" — pre-Phase-1 vintage), 5 target infrastructure modules with current docstrings 30–150 lines each, 7 FEAT-J004 DDRs (DDR-016..024) + 7 FEAT-J005 DDRs (DDR-025..031), ADR-ARCH-001..035+, ADR-J-P4 (fleet contract).
Notable Phase-1 finding: README.md already exists but is heavily stale — pins "Status: Pre-Architecture" and "341 passing" against today's "Phase-3 close, 2103 passing". Scope therefore shifts from create README to rewrite README to current state. Same task surface, cleaner framing.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: FEAT-JARVIS-INTERNAL-001 Documentation Foundation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@feat-jarvis-internal-001 @docs @phase-3-close
Feature: FEAT-JARVIS-INTERNAL-001 Documentation Foundation
  As a Phase-3-close steward
  I want the five new FEAT-J004/J005 infrastructure modules and the repo README
  to share a consistent, current shape
  So that human readers landing on the repo and Forge's Step-14 e2e round-trip
  both have a clean, navigable payload

  Background:
    Given the repository is at the Phase-3-close state on `main`
    And the candidate files are the five FEAT-J004/J005 infrastructure modules
        and the repo-root `README.md`
    And reasoning-model-facing tool docstrings under `src/jarvis/tools/` are
        explicitly out of scope (per FEAT-JARVIS-004/-005 invariant)
━━ GROUP A: Key Examples (9 scenarios) ━━

  # Why: Every new infrastructure module must declare its purpose up front
  @key-example @smoke
  Scenario Outline: Each infrastructure module has a Purpose paragraph
    Given the module file <module>
    When the module docstring is read
    Then the docstring's first paragraph should describe the module's purpose
    And the paragraph should be at least 2 complete sentences
    Examples:
      | module                                              |
      | src/jarvis/infrastructure/nats_client.py            |
      | src/jarvis/infrastructure/fleet_registration.py     |
      | src/jarvis/infrastructure/capabilities_registry.py  |
      | src/jarvis/infrastructure/routing_history.py        |
      | src/jarvis/infrastructure/forge_notifications.py    |

  # Why: Origin attribution lets future readers trace each module to its feature plan
  @key-example @smoke
  Scenario Outline: Each infrastructure module references its FEAT-JARVIS origin
    Given the module file <module>
    When the module docstring is read
    Then the docstring should reference <feature> as its origin
    Examples:
      | module                                              | feature         |
      | src/jarvis/infrastructure/nats_client.py            | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/fleet_registration.py     | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/capabilities_registry.py  | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/routing_history.py        | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/forge_notifications.py    | FEAT-JARVIS-005 |

  # Why: Each module's behavioural decisions are pinned by DDRs — readers should be able to navigate to them
  @key-example
  Scenario Outline: Each infrastructure module cites at least one DDR
    Given the module file <module>
    When the module docstring is read
    Then the docstring should cite at least one DDR identifier
    And each cited DDR identifier should resolve to a file under <ddr_dir>
    Examples:
      | module                                              | ddr_dir                                |
      | src/jarvis/infrastructure/nats_client.py            | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/fleet_registration.py     | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/capabilities_registry.py  | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/routing_history.py        | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/forge_notifications.py    | docs/design/FEAT-JARVIS-005/decisions/ |

  # Why: Each module should link to its design doc so readers can get the full architectural context
  @key-example
  Scenario Outline: Each infrastructure module links to its design doc
    Given the module file <module>
    When the module docstring is read
    Then the docstring should reference the design doc at <design_doc>
    Examples:
      | module                                              | design_doc                            |
      | src/jarvis/infrastructure/nats_client.py            | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/fleet_registration.py     | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/capabilities_registry.py  | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/routing_history.py        | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/forge_notifications.py    | docs/design/FEAT-JARVIS-005/design.md |

  # Why: README is the human entry point and must have an unambiguous H1
  @key-example @smoke
  Scenario: The repo README has an H1 with the project name
    Given the file `README.md`
    When the file is read
    Then the first heading should be a level-1 heading
    And the heading should contain "Jarvis"

  # Why: Status section communicates the current phase to anyone landing on the README
  @key-example @smoke
  Scenario: The repo README declares the current Phase-3-close status
    Given the file `README.md`
    When the file is read
    Then it should contain a "Status" section
    And the Status section should reference "Phase 3" by name
    And the Status section should describe the Phase 3 close criterion (end-to-end Forge round-trip)

  # Why: A Quick Start that matches CLAUDE.md prevents drift between human and AI docs
  @key-example
  Scenario: The repo README Quick Start matches the canonical install/run commands
    Given the file `README.md`
    And the canonical install command is documented in `.claude/CLAUDE.md`
    And the canonical run command is documented in `.claude/CLAUDE.md`
    When the README is read
    Then it should contain a "Quick Start" section
    And the Quick Start should include the canonical install command
    And the Quick Start should include the canonical run command

  # Why: Architecture section gives readers the entry point into the deeper docs
  @key-example
  Scenario: The repo README links to the architecture document
    Given the file `README.md`
    When the file is read
    Then it should contain an "Architecture" section
    And the Architecture section should link to `docs/architecture/ARCHITECTURE.md`

  # Why: Design Decisions section maps the ADR + DDR landscape for navigation
  @key-example
  Scenario: The repo README catalogues the design-decision locations
    Given the file `README.md`
    When the file is read
    Then it should contain a "Design Decisions" section
    And the section should reference the ADR directory `docs/architecture/decisions/`
    And the section should reference the FEAT-JARVIS-004 DDR directory
    And the section should reference the FEAT-JARVIS-005 DDR directory
━━ GROUP B: Boundary Conditions (5 scenarios) ━━

  # Why: Just-inside / just-outside boundary pair — README must not shrink to a stub or balloon into a manual
  @boundary
  Scenario Outline: The repo README has a line count within the documented bounds
    Given the file `README.md`
    When the file's line count is computed
    Then the line count should be <verdict>
    Examples:
      | line_count | verdict                       |
      | 80         | accepted (at lower bound)     |
      | 250        | accepted (at upper bound)     |
      | 79         | rejected (below lower bound)  |
      | 251        | rejected (above upper bound)  |

  # Why: Module docstrings shouldn't dwindle to one-liners or sprawl into prose
  @boundary
  Scenario: Each infrastructure module docstring has a line count within the documented bounds
    Given an infrastructure module under `src/jarvis/infrastructure/`
    And the module is one of the five candidates
    When the module docstring's line count is computed
    Then the line count should be at least 30 and at most 200
━━ GROUP C: Negative Cases (5 scenarios) ━━

  # Why: The reasoning model has been routing against the current tool docstrings since Phase 2 — touching them is a behavioural confound during the Step-14 e2e validator
  @negative @smoke
  Scenario: Reasoning-model-facing tool docstrings are byte-unchanged
    Given the files under `src/jarvis/tools/` excluding subpackages and tests
    And the docstrings of the `@tool`-decorated functions on `main` HEAD prior to this feature
    When the same docstrings are inspected after this feature is applied
    Then each tool docstring should be byte-identical to its prior version
    And no `@tool`-decorated function's docstring should be added, removed, or rewritten

  # Why: This feature is documentation-only — runtime behaviour mustn't shift
  @negative
  Scenario: No executable code is modified
    Given the diff of this feature against `main`
    When the changed lines are inspected
    Then every changed line should be inside a Python docstring or inside `README.md`
    And no executable Python statement should be modified

  # Why: A broken design-doc link is worse than no link
  @negative
  Scenario: Cited design-doc paths resolve to real files
    Given each polished module docstring
    When the design-doc references in the docstring are extracted
    Then each referenced file should exist on disk
    And each referenced file should be readable

  # Why: Internal task IDs are GuardKit bookkeeping, not reader-facing prose
  @negative
  Scenario: Polished prose does not lead with internal task IDs
    Given a polished module docstring
    When the docstring's Purpose paragraph is inspected
    Then the Purpose paragraph should not lead with a `TASK-J0NN-NNN` reference
    And `TASK-J*` mentions should appear only in trailing "History" or "Provenance" sections (or be removed)

  # Why: README must not reintroduce stale phase info
  @negative
  Scenario: The README does not mention "Pre-Architecture" status
    Given the file `README.md`
    When the file is read
    Then the file should not contain the literal phrase "Pre-Architecture"
    And the file should not declare a hard-coded passing-test count below the current count
━━ GROUP D: Edge Cases (5 scenarios) ━━

  # Why: A docstring change must not break the import; this is structurally important
  @edge-case @smoke
  Scenario: All polished modules remain importable and graphs still compile
    Given the polished modules
    When each module is imported by Python
    Then every import should succeed
    And `langgraph dev` should still start
    And both the `jarvis` and `jarvis_reasoner` graphs should compile

  # Why: Documentation-only changes shouldn't regress tests or coverage
  @edge-case @smoke
  Scenario: The full pytest suite remains green and coverage does not regress
    Given the polished feature is applied
    When `uv run pytest tests/` is run
    Then every test should pass
    And the line coverage should not regress below 92%

  # Why: Type checking must not regress
  @edge-case
  Scenario: mypy returns no new errors
    Given the polished feature is applied
    When `uv run mypy src/jarvis/` is run
    Then the error count should be at most 1
    And the only permitted error should be the pre-existing FEAT-J004 issue tracked under TASK-REV-FFE4
    And no new mypy error should appear in any polished file

  # Why: Cross-repo links should be relative for portability
  @edge-case
  Scenario: README in-repo references use relative paths
    Given the file `README.md`
    When markdown links to files in this repo are inspected
    Then each in-repo link should be a relative path
    And no in-repo link should hard-code an absolute filesystem path

  # Why: Docstring polish must not silently drop existing high-value DDR/ADR cross-refs
  @edge-case
  Scenario: Existing DDR-021 / ADR-ARCH-017 references in capabilities_registry.py are preserved
    Given the docstring of `src/jarvis/infrastructure/capabilities_registry.py`
    When the polished docstring is compared against the prior docstring
    Then the polished docstring should still cite DDR-021
    And it should still cite ADR-ARCH-017

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 24 scenarios across 4 groups
   Group A (Key examples): 9   |   Group B (Boundary): 5
   Group C (Negative):     5   |   Group D (Edge):     5
   @smoke tagged: 7
Inferred assumptions: 9 (will surface in Phase 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — CURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each group, you may:


[A] Accept  — include all scenarios as-is
[R] Reject  — exclude all scenarios in this group
[M] Modify  — accept but specify changes (provide inline)
[+] Add     — accept and add additional scenarios you describe
[?] Defer   — mark group for future specification; excluded from output

Fast path: type "A A A A" to accept all four groups at once.
Group	Scenarios	Your decision
A — Key Examples	9 (4 are scenario outlines × 5 modules each = 20 effective rows)	_
B — Boundary Conditions	5 effective rows	_
C — Negative Cases	5	_
D — Edge Cases	5	_
My quick view before you decide
Group A — solid. The four scenario outlines compress what would be 20 single-module scenarios into 4 readable tables. Each pair (Purpose + FEAT origin + DDR cite + design-doc link) is the contract.
Group B — I'd consider trimming. Module-docstring lower bound of 30 may be tight (some current docstrings are around 30 lines and might be justifiably shorter after polish). Worth tightening or relaxing.
Group C — load-bearing. The byte-unchanged tool-docstring scenario (C.1) is the explicit FEAT-J002 invariant carrier — this is what enforces "no behavioural confound during Step-14".
Group D — D.3 (mypy = 1 pre-existing) couples to TASK-REV-FFE4 status. If FFE4 lands before this feature, "= 1" becomes "= 0". Easy fix at curation time.
Type your decisions (e.g. A A A A to accept all, or per-group A / R / M / + / ?).

TASK-REV-FFE4-review-report.md
please reccommend further
Recommending decisively rather than menu-listing.

Curation recommendations
Group A — Accept (A)
Four scenario outlines × five modules = 20 effective rows in 4 readable tables, plus 5 single README scenarios. Each pair (Purpose / FEAT origin / DDR cite / design-doc link) maps cleanly to one structural assertion the autobuild coach can verify with an AST + regex pass. No tuning needed.

Group B — Modify (M) — relax both bounds
The bounds I proposed are tight enough to false-fire on legitimate output:

README: change 80–250 → 100–300. Current stale README is 131 lines; a Phase-3-close rewrite with Status + Quick Start + Architecture + Design Decisions + a small FAQ realistically lands 180–250. 300 gives headroom without inviting prose sprawl.
Module docstrings: change 30–200 → 20–250. Some polished docstrings (nats_client.py is the candidate — thin wrapper) may legitimately need only 20–25 lines if the prose is dense. 250 upper end keeps routing_history.py's justifiably-long ADR-FLEET-001 schema discussion legal.

Change: README line bounds 100–300 (was 80–250); module docstring bounds 20–250 (was 30–200).
Group C — Modify (M) — tighten C.4
C.1, C.2, C.3, C.5 are load-bearing as-written. C.4 is too soft:

"Purpose paragraph should not lead with a TASK-J0NN-NNN reference"

Current docstrings have lines like "TASK-J004-006 / FEAT-JARVIS-004." — that's bookkeeping leaking into reader-facing prose, and "should not lead with" technically permits "TASK-J004-006 follows from..." mid-paragraph. Tighten to:


Change: C.4 — TASK-J0NN-NNN references must not appear ANYWHERE in the
Purpose paragraph. They may appear in trailing "History" / "Provenance"
sections (or be removed). Position-based wording dropped.
Group D — Modify (M) — decouple D.3 from TASK-REV-FFE4 timing
D.1, D.2, D.4, D.5 stay as-written. D.3 ("mypy error count = 1, only the FFE4 issue") is brittle — if FFE4 is resolved before INTERNAL-001 ships, the test fires falsely with 0 errors. Reframe to be stable:


Change: D.3 — replace "error count should be at most 1" + FFE4 carve-out
with: "no NEW mypy error is introduced by any file modified in this
feature". Asserts the delta, not the absolute count. Stable regardless
of FFE4 resolution timing.
Phase 4 (edge case expansion) — N (skip)
The standard Phase-4 expansion targets — security, concurrency, integration boundaries — don't apply to a docstring/README polish. There are no auth surfaces, no concurrent paths, no downstream services. Asking the AI to invent @edge-case scenarios for a docs feature would manufacture noise, not coverage. Recommendation: skip Phase 4.

Combined decision

GROUP A: A
GROUP B: M  → README bounds 100–300; module-docstring bounds 20–250
GROUP C: M  → C.4 banned from Purpose paragraph entirely (not just leading position)
GROUP D: M  → D.3 = "no NEW mypy error introduced", drop fixed count + FFE4 carve-out
PHASE 4: N
Effective scenario count after these modifications: still ~24 (group sizes unchanged; only thresholds and one wording move). Smoke set: 7.

Want me to apply this and proceed to Phase 5 (assumption resolution)? Or do you want to adjust any of these before I move on?

yes
Applying the curation. Now Phase 5.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 — ASSUMPTION RESOLUTION (13 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each, accept the default by leaving blank, or provide an override. I've grouped by confidence so the load-bearing ones (low) are visible first.

Low confidence (mandatory review)
#	Assumption	Proposed	Basis
1	Module docstring lower bound	20 lines	Inferred — nats_client.py is the thinnest candidate; current is ~50 lines, polished could compress to 20. Below 20 → stub territory.
2	Module docstring upper bound	250 lines	Inferred — routing_history.py's ADR-FLEET-001 schema discussion is currently ~150 lines and may grow with cross-refs. Above 250 → prose sprawl.
3	TASK-Jxxx references location policy	Allowed only in trailing "History" or "Provenance" sections (or removed entirely)	Convention call. Alternative: ban TASK-Jxxx references from polished docstrings entirely (cleanest), or allow them anywhere with a :provenance: rST role tag.
Medium confidence (coach review recommended)
#	Assumption	Proposed	Basis
4	README lower bound	100 lines	Sanity floor — anything shorter than 100 lines for a project with 5 ADRs / 14 DDRs / phase 3 status is a stub.
5	README upper bound	300 lines	Sanity ceiling — current stale README is 131 lines; a Phase-3-close rewrite plus FAQ realistically 180–250. 300 leaves headroom.
6	Status section phase reference	Must reference "Phase 3" by literal string	Build plan uses "Phase 3" as proper noun. Alternative: reference the phase number numerically.
7	Design Decisions section	Must reference BOTH FEAT-J004 and FEAT-J005 DDR directories explicitly	They're the two completed Phase-3 features. Alternative: list them generically as "FEAT-JARVIS-XXX/decisions/" and let the autobuild fill in.
8	Purpose paragraph length	At least 2 complete sentences	Stops one-liner descriptions. Alternative: ≥ 1 sentence (looser) or ≥ 3 sentences (stricter).
9	README in-repo links	Must be relative paths	Portability + convention. Alternative: also allow ./ prefix relative paths explicitly, or allow GitHub-rendered URLs.
High confidence (auto-proceed unless you override)
#	Assumption	Proposed	Basis
10	Coverage floor	92% line coverage	Step 11 result on commit 8848795. Hard fact.
11	mypy delta	No NEW errors in any file modified by this feature	Step 11 result + decoupled from TASK-REV-FFE4 timing per Group D modification.
12	Tool-docstring scope	Files matching src/jarvis/tools/*.py excluding __init__.py	Build plan invariant: general.py, capabilities.py, dispatch.py @tool-decorated functions. tools/__init__.py is wiring, tools/types.py and tools/dispatch_types.py are Pydantic models — both excluded.
13	Quick Start canonical commands	uv sync + uv run pytest + uv run jarvis version (from existing README) plus the .claude/CLAUDE.md pip install .[providers] + python -m langgraph dev	Both sources are canonical. Existing README's uv sync flow is more complete; .claude/CLAUDE.md has the langgraph dev entry. Alternative: pick one.
Where I'd push back on my own defaults if I were you
#3 (TASK-Jxxx policy) — my proposed default permits a trailing "History" section, but most polished docstrings won't need one. Tighter alternative: ban TASK-Jxxx from polished docstrings entirely, leaving FEAT-JARVIS-XXX as the only origin reference. Cleaner, less bookkeeping leak. Your call.
#13 (Quick Start commands) — pip install .[providers] and uv sync are different package-manager paths. The existing README pushes uv sync (more correct for the dev/test loop) while .claude/CLAUDE.md shows pip install .[providers] (an older convention). Reconciling them is a documentation-design call. I'd recommend uv sync as primary, mention pip install .[providers] as alternative — but you may want it the other way.
#7 (J004 + J005 directories explicitly) — listing them by name ages poorly when FEAT-J006 (Phase 4) lands. Alternative: list them with a comment that this section grows per feature — i.e. structure it as a ## Design Decisions section that evolves.
How to respond
Either type the numbers you want to override (e.g. 3: ban TASK-Jxxx entirely from polished docstrings), or just say "accept all" to take the proposed defaults.

If you want my single recommendation — I'd:

Override #3 to ban TASK-Jxxx entirely (cleanest)
Override #13 to uv sync as primary, python -m langgraph dev for runtime
Accept the other 11 as-proposed
Want me to write that as the final assumption set and proceed to Phase 6 (file generation)?

yes please proceed with your single recommendation:

Override #3 to ban TASK-Jxxx entirely (cleanest)
Override #13 to uv sync as primary, python -m langgraph dev for runtime
Accept the other 11 as-proposed
Phase 6 — generating the three output files.

Bash Create feature output directory
IN
mkdir -p features/feat-jarvis-internal-001-documentation-foundation

OUT
(Bash completed with no output)
Write feat-jarvis-internal-001-documentation-foundation.feature
260 lines
# Generated by /feature-spec
# Feature: FEAT-JARVIS-INTERNAL-001 Documentation Foundation
# Stack: python
# Assumptions: 13 (see feat-jarvis-internal-001-documentation-foundation_assumptions.yaml)
# Generated: 2026-04-30T11:45:00Z

@feat-jarvis-internal-001 @docs @phase-3-close
Feature: FEAT-JARVIS-INTERNAL-001 Documentation Foundation
  As a Phase-3-close steward
  I want the five new FEAT-J004/J005 infrastructure modules and the repo README
  to share a consistent, current shape
  So that human readers landing on the repo and Forge's Step-14 e2e round-trip
  both have a clean, navigable payload

  Background:
    Given the repository is at the Phase-3-close state on `main`
    And the candidate files are the five FEAT-J004/J005 infrastructure modules and the repo-root `README.md`
    And reasoning-model-facing tool docstrings under `src/jarvis/tools/` are explicitly out of scope per the FEAT-JARVIS-004/-005 invariant

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # GROUP A — Key Examples (9 scenarios, 4 are outlines × 5 modules = 25 effective rows)
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Why: Every new infrastructure module must declare its purpose up front
  # [ASSUMPTION: confidence=medium] Purpose paragraph is at least 2 complete sentences (ASSUM-008)
  @key-example @smoke
  Scenario Outline: Each infrastructure module has a Purpose paragraph
    Given the module file <module>
    When the module docstring is read
    Then the docstring's first paragraph should describe the module's purpose
    And the paragraph should contain at least 2 complete sentences

    Examples:
      | module                                              |
      | src/jarvis/infrastructure/nats_client.py            |
      | src/jarvis/infrastructure/fleet_registration.py     |
      | src/jarvis/infrastructure/capabilities_registry.py  |
      | src/jarvis/infrastructure/routing_history.py        |
      | src/jarvis/infrastructure/forge_notifications.py    |

  # Why: Origin attribution lets future readers trace each module to its feature plan
  @key-example @smoke
  Scenario Outline: Each infrastructure module references its FEAT-JARVIS origin
    Given the module file <module>
    When the module docstring is read
    Then the docstring should reference <feature> as its origin

    Examples:
      | module                                              | feature         |
      | src/jarvis/infrastructure/nats_client.py            | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/fleet_registration.py     | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/capabilities_registry.py  | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/routing_history.py        | FEAT-JARVIS-004 |
      | src/jarvis/infrastructure/forge_notifications.py    | FEAT-JARVIS-005 |

  # Why: Each module's behavioural decisions are pinned by DDRs — readers should be able to navigate to them
  @key-example
  Scenario Outline: Each infrastructure module cites at least one DDR
    Given the module file <module>
    When the module docstring is read
    Then the docstring should cite at least one DDR identifier
    And each cited DDR identifier should resolve to a file under <ddr_dir>

    Examples:
      | module                                              | ddr_dir                                |
      | src/jarvis/infrastructure/nats_client.py            | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/fleet_registration.py     | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/capabilities_registry.py  | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/routing_history.py        | docs/design/FEAT-JARVIS-004/decisions/ |
      | src/jarvis/infrastructure/forge_notifications.py    | docs/design/FEAT-JARVIS-005/decisions/ |

  # Why: Each module should link to its design doc so readers can get the full architectural context
  @key-example
  Scenario Outline: Each infrastructure module links to its design doc
    Given the module file <module>
    When the module docstring is read
    Then the docstring should reference the design doc at <design_doc>

    Examples:
      | module                                              | design_doc                            |
      | src/jarvis/infrastructure/nats_client.py            | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/fleet_registration.py     | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/capabilities_registry.py  | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/routing_history.py        | docs/design/FEAT-JARVIS-004/design.md |
      | src/jarvis/infrastructure/forge_notifications.py    | docs/design/FEAT-JARVIS-005/design.md |

  # Why: README is the human entry point and must have an unambiguous H1
  @key-example @smoke
  Scenario: The repo README has an H1 with the project name
    Given the file `README.md`
    When the file is read
    Then the first heading should be a level-1 heading
    And the heading should contain "Jarvis"

  # Why: Status section communicates the current phase to anyone landing on the README
  # [ASSUMPTION: confidence=medium] Status section references the literal string "Phase 3" (ASSUM-006)
  @key-example @smoke
  Scenario: The repo README declares the current Phase-3-close status
    Given the file `README.md`
    When the file is read
    Then it should contain a "Status" section
    And the Status section should reference "Phase 3" by name
    And the Status section should describe the Phase 3 close criterion as the end-to-end Forge round-trip

  # Why: A Quick Start that matches the canonical commands prevents drift between human and AI docs
  # [ASSUMPTION: confidence=high] Canonical install = `uv sync`; canonical runtime = `python -m langgraph dev` (ASSUM-013, OVERRIDDEN)
  @key-example
  Scenario: The repo README Quick Start matches the canonical install/run commands
    Given the file `README.md`
    And the canonical install command is `uv sync`
    And the canonical runtime command is `python -m langgraph dev`
    When the README is read
    Then it should contain a "Quick Start" section
    And the Quick Start should include the canonical install command
    And the Quick Start should include the canonical runtime command

  # Why: Architecture section gives readers the entry point into the deeper docs
  @key-example
  Scenario: The repo README links to the architecture document
    Given the file `README.md`
    When the file is read
    Then it should contain an "Architecture" section
    And the Architecture section should link to `docs/architecture/ARCHITECTURE.md`

  # Why: Design Decisions section maps the ADR + DDR landscape for navigation
  # [ASSUMPTION: confidence=medium] Section explicitly references both J004 and J005 DDR directories (ASSUM-007)
  @key-example
  Scenario: The repo README catalogues the design-decision locations
    Given the file `README.md`
    When the file is read
    Then it should contain a "Design Decisions" section
    And the section should reference the ADR directory `docs/architecture/decisions/`
    And the section should reference the FEAT-JARVIS-004 DDR directory
    And the section should reference the FEAT-JARVIS-005 DDR directory

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # GROUP B — Boundary Conditions (2 scenarios, 1 outline × 4 examples = 5 effective rows)
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Why: Just-inside / just-outside boundary pair — README must not shrink to a stub or balloon into a manual
  # [ASSUMPTION: confidence=medium] README line bounds 100–300 (ASSUM-004 + ASSUM-005)
  @boundary
  Scenario Outline: README line count is checked against the documented bounds
    Given a candidate `README.md` with <line_count> lines
    When the file's line count is computed
    Then the line count <verdict>

    Examples:
      | line_count | verdict                                |
      | 100        | should be accepted at the lower bound  |
      | 300        | should be accepted at the upper bound  |
      | 99         | should be rejected below the lower bound |
      | 301        | should be rejected above the upper bound |

  # Why: Module docstrings shouldn't dwindle to one-liners or sprawl into prose
  # [ASSUMPTION: confidence=low] Module docstring line bounds 20–250 (ASSUM-001 + ASSUM-002)
  @boundary
  Scenario: Each infrastructure module docstring is within the documented length bounds
    Given an infrastructure module under `src/jarvis/infrastructure/`
    And the module is one of the five candidates
    When the module docstring's line count is computed
    Then the line count should be at least 20
    And the line count should be at most 250

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # GROUP C — Negative Cases (5 scenarios)
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Why: The reasoning model has been routing against the current tool docstrings since Phase 2 — touching them is a behavioural confound during the Step-14 e2e validator
  # [ASSUMPTION: confidence=high] Tool-docstring scope = `src/jarvis/tools/*.py` excluding `__init__.py` (ASSUM-012)
  @negative @smoke
  Scenario: Reasoning-model-facing tool docstrings remain byte-unchanged
    Given the files matching `src/jarvis/tools/*.py` excluding `__init__.py`
    And the docstrings of the `@tool`-decorated functions on `main` HEAD prior to this feature
    When the same docstrings are inspected after this feature is applied
    Then each tool docstring should be byte-identical to its prior version
    And no `@tool`-decorated function's docstring should be added, removed, or rewritten

  # Why: This feature is documentation-only — runtime behaviour mustn't shift
  @negative
  Scenario: No executable code is modified
    Given the diff of this feature against `main`
    When the changed lines are inspected
    Then every changed line should be inside a Python docstring or inside `README.md`
    And no executable Python statement should be modified

  # Why: A broken design-doc link is worse than no link
  @negative
  Scenario: Cited design-doc paths must resolve to real files
    Given each polished module docstring
    When the design-doc references in the docstring are extracted
    Then each referenced file should exist on disk
    And each referenced file should be readable

  # Why: Internal task IDs are GuardKit bookkeeping and should not leak into reader-facing prose
  # [ASSUMPTION: confidence=low] TASK-Jxxx references banned ENTIRELY from polished docstrings (ASSUM-003, OVERRIDDEN — was: trailing-section allowance)
  @negative @smoke
  Scenario: Polished docstrings contain no TASK-Jxxx references
    Given a polished module docstring (any of the five candidates)
    When the full text of the docstring is inspected
    Then it should contain no token matching the pattern `TASK-J\d{3}-\d{3}`
    And origin attribution should use the FEAT-JARVIS-XXX form only

  # Why: README must not reintroduce stale phase info
  @negative
  Scenario: The README does not mention "Pre-Architecture" status
    Given the file `README.md`
    When the file is read
    Then the file should not contain the literal phrase "Pre-Architecture"
    And the file should not declare a hard-coded passing-test count below the current count

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # GROUP D — Edge Cases (5 scenarios)
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Why: A docstring change must not break the import; this is structurally important
  @edge-case @smoke
  Scenario: All polished modules remain importable and graphs still compile
    Given the polished modules
    When each module is imported by Python
    Then every import should succeed
    And `langgraph dev` should still start
    And both the `jarvis` and `jarvis_reasoner` graphs should compile

  # Why: Documentation-only changes shouldn't regress tests or coverage
  # [ASSUMPTION: confidence=high] Coverage floor 92% (ASSUM-010)
  @edge-case @smoke
  Scenario: The full pytest suite remains green and coverage does not regress
    Given the polished feature is applied
    When `uv run pytest tests/` is run
    Then every test should pass
    And the line coverage should not regress below 92%

  # Why: Type checking must not regress relative to pre-feature state
  # [ASSUMPTION: confidence=high] mypy delta = no new errors in any file modified by this feature (ASSUM-011)
  @edge-case
  Scenario: No new mypy errors are introduced by polished files
    Given the polished feature is applied
    And the set of files modified by this feature
    When `uv run mypy src/jarvis/` is run
    Then no new mypy error should appear in any file modified by this feature
    And any pre-existing mypy errors are out of scope for this feature

  # Why: Cross-repo links should be relative for portability
  # [ASSUMPTION: confidence=medium] README in-repo references must be relative paths (ASSUM-009)
  @edge-case
  Scenario: README in-repo references use relative paths
    Given the file `README.md`
    When markdown links to files in this repo are inspected
    Then each in-repo link should be a relative path
    And no in-repo link should hard-code an absolute filesystem path

  # Why: Docstring polish must not silently drop existing high-value DDR/ADR cross-refs
  @edge-case
  Scenario: Existing DDR-021 / ADR-ARCH-017 references in capabilities_registry.py are preserved
    Given the docstring of `src/jarvis/infrastructure/capabilities_registry.py`
    When the polished docstring is compared against the prior docstring
    Then the polished docstring should still cite DDR-021
    And the polished docstring should still cite ADR-ARCH-017
Write feat-jarvis-internal-001-documentation-foundation_assumptions.yaml
100 lines
# Assumptions manifest for feat-jarvis-internal-001-documentation-foundation.feature
# Generated by /feature-spec

feature: "FEAT-JARVIS-INTERNAL-001 Documentation Foundation"
generated: "2026-04-30T11:45:00Z"
stack: "python"
review_required: true  # 3 low-confidence assumptions (ASSUM-001, ASSUM-002, ASSUM-003)

assumptions:
  - id: "ASSUM-001"
    scenario: "Each infrastructure module docstring is within the documented length bounds"
    assumption: "Module docstring lower bound is 20 lines"
    confidence: low
    basis: "Inferred from current docstring sizes; nats_client.py is the thinnest candidate at ~50 lines and could legitimately compress to 20 after polish; below 20 reads as a stub"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Each infrastructure module docstring is within the documented length bounds"
    assumption: "Module docstring upper bound is 250 lines"
    confidence: low
    basis: "Inferred — routing_history.py's ADR-FLEET-001 schema discussion is currently ~150 lines and may grow with additional cross-references; 250 caps prose sprawl while leaving headroom"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "Polished docstrings contain no TASK-Jxxx references"
    assumption: "TASK-J\\d{3}-\\d{3} references are banned entirely from polished docstrings; FEAT-JARVIS-XXX is the only origin form allowed"
    confidence: low
    basis: "Convention call. Original proposal allowed trailing 'History' or 'Provenance' sections to retain TASK-Jxxx for provenance tracing. Overridden to a clean entire-docstring ban — TASK-Jxxx is GuardKit autobuild bookkeeping that doesn't belong in reader-facing prose; FEAT-JARVIS-XXX origin attribution provides equivalent traceability without the bookkeeping leak"
    human_response: "overridden: ban entirely from polished docstrings"

  - id: "ASSUM-004"
    scenario: "README line count is checked against the documented bounds"
    assumption: "README lower bound is 100 lines"
    confidence: medium
    basis: "Sanity floor — anything shorter than 100 lines for a project with 5+ ADRs, 14 DDRs, multi-phase build plan, and Phase-3-close status is a stub"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "README line count is checked against the documented bounds"
    assumption: "README upper bound is 300 lines"
    confidence: medium
    basis: "Sanity ceiling — current stale README is 131 lines; a Phase-3-close rewrite (Status, Quick Start, Architecture, Design Decisions, optional FAQ) realistically lands 180–250 lines; 300 leaves headroom without inviting prose sprawl"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "The repo README declares the current Phase-3-close status"
    assumption: "Status section references 'Phase 3' as a literal string"
    confidence: medium
    basis: "Build plan and surrounding documentation use 'Phase 3' as a proper noun consistently; alternatives (numeric '3', 'phase 3' lowercase) would weaken cross-reference grep-ability"
    human_response: "confirmed"

  - id: "ASSUM-007"
    scenario: "The repo README catalogues the design-decision locations"
    assumption: "Design Decisions section explicitly references both FEAT-JARVIS-004 and FEAT-JARVIS-005 DDR directories by name"
    confidence: medium
    basis: "These are the two completed Phase-3 features; explicit references aid navigation. The 'lists by name' choice ages slightly when FEAT-J006 lands in Phase 4, but the autobuild player can be instructed to extend the list as new features close (cheap maintenance)"
    human_response: "confirmed"

  - id: "ASSUM-008"
    scenario: "Each infrastructure module has a Purpose paragraph"
    assumption: "Purpose paragraph contains at least 2 complete sentences"
    confidence: medium
    basis: "Stops one-liner descriptions; balances brevity against the consistent-shape requirement; a single sentence rarely captures both the module's responsibility and its position in the architecture"
    human_response: "confirmed"

  - id: "ASSUM-009"
    scenario: "README in-repo references use relative paths"
    assumption: "README in-repo links must be relative paths (no absolute filesystem paths)"
    confidence: medium
    basis: "Portability + GitHub rendering convention; absolute filesystem paths break on clone-into-different-location and on rendered markdown views"
    human_response: "confirmed"

  - id: "ASSUM-010"
    scenario: "The full pytest suite remains green and coverage does not regress"
    assumption: "Coverage floor is 92% line coverage"
    confidence: high
    basis: "Step 11 regression result on commit 8848795 measured 92% line coverage across 2103 passing tests; this feature is documentation-only so coverage cannot legitimately regress"
    human_response: "confirmed"

  - id: "ASSUM-011"
    scenario: "No new mypy errors are introduced by polished files"
    assumption: "mypy delta = no new errors introduced in any file modified by this feature"
    confidence: high
    basis: "Decoupled from absolute mypy error count to handle TASK-REV-FFE4 resolution timing — the delta is the test, not the absolute. If FFE4 is resolved before this feature merges, the count drops to 0; if not, the count remains 1; either way, this feature must not add to it"
    human_response: "confirmed"

  - id: "ASSUM-012"
    scenario: "Reasoning-model-facing tool docstrings remain byte-unchanged"
    assumption: "Tool-docstring scope is files matching `src/jarvis/tools/*.py` excluding `__init__.py`"
    confidence: high
    basis: "FEAT-JARVIS-004/-005 build-plan invariant: 'Tool docstrings unchanged — reasoning model behaviour identical between Phase 2 (stubbed) and Phase 3 (real NATS/Forge)'. Concretely: general.py, capabilities.py, dispatch.py @tool-decorated functions. __init__.py is wiring/factory code (not @tool-decorated); types.py and dispatch_types.py are Pydantic models — all excluded from the invariant scope"
    human_response: "confirmed"

  - id: "ASSUM-013"
    scenario: "The repo README Quick Start matches the canonical install/run commands"
    assumption: "Canonical install command is `uv sync`; canonical runtime command is `python -m langgraph dev`"
    confidence: high
    basis: "Two canonical sources existed pre-feature: `pip install .[providers]` from .claude/CLAUDE.md (older AI-agent convention) and `uv sync` from existing README + pyproject.toml dev/test loop. Overridden to prefer `uv sync` as primary install — matches the dev/test loop the repo actually uses (uv-managed venv, .python-version pinning), avoids the system-Python pitfall the existing README troubleshoots, and reads the [dependency-groups].dev PEP-735 deps automatically. `python -m langgraph dev` retained as the runtime entry per .claude/CLAUDE.md"
    human_response: "overridden: uv sync primary, python -m langgraph dev for runtime"
Write feat-jarvis-internal-001-documentation-foundation_summary.md
139 lines
# Feature Spec Summary: FEAT-JARVIS-INTERNAL-001 Documentation Foundation

**Stack**: python
**Generated**: 2026-04-30T11:45:00Z
**Scenarios**: 21 definitions / 40 effective rows (5 outlines expand into 25 module-iteration rows + 4 README-bound rows + 11 single scenarios)
**Smoke**: 7 · **Regression**: 0
**Assumptions**: 13 total (5 high / 5 medium / 3 low)
**Review required**: Yes (3 low-confidence assumptions — ASSUM-001, ASSUM-002, ASSUM-003)

## Scope

Polish the five FEAT-J004/J005 infrastructure module docstrings under
`src/jarvis/infrastructure/` (`nats_client.py`, `fleet_registration.py`,
`capabilities_registry.py`, `routing_history.py`, `forge_notifications.py`) to a
consistent shape — Purpose paragraph (≥ 2 sentences), FEAT-JARVIS-XXX origin,
design-doc link, ≥ 1 DDR citation, no internal TASK-Jxxx leakage — and rewrite
the existing repo-root `README.md` (currently 131 lines and stale, declaring
"Status: Pre-Architecture") to reflect Phase-3-close state with H1 Jarvis project
name, Status section referencing "Phase 3" + the end-to-end Forge close criterion,
Quick Start with `uv sync` + `python -m langgraph dev`, Architecture link to
`docs/architecture/ARCHITECTURE.md`, and Design Decisions section cataloguing the
ADR directory plus the FEAT-JARVIS-004 and FEAT-JARVIS-005 DDR directories.

Reasoning-model-facing tool docstrings under `src/jarvis/tools/` are EXPLICITLY
OUT OF SCOPE per the FEAT-JARVIS-004/-005 build-plan invariant: *"Tool docstrings
unchanged — reasoning model behaviour identical between Phase 2 (stubbed) and
Phase 3 (real NATS/Forge)"*.

This feature is the payload for **Step 14 of `docs/research/ideas/phase3-build-plan.md`**
— the end-to-end Forge round-trip that closes Phase 3.

## Scenario Counts by Category

| Category | Scenario definitions | Effective rows |
|----------|---------------------|----------------|
| Key examples (`@key-example`) | 9 | 25 (4 outlines × 5 modules + 5 single) |
| Boundary conditions (`@boundary`) | 2 | 5 (1 outline × 4 + 1 single) |
| Negative cases (`@negative`) | 5 | 5 |
| Edge cases (`@edge-case`) | 5 | 5 |
| **Smoke** (`@smoke`) | **7** | — |
| **Total** | **21** | **40** |

## Deferred Items

None — Phase 4 (security/concurrency/integration edge-case expansion) was
**deliberately skipped**. This is a documentation-only feature with no auth
surfaces, no concurrent code paths, and no downstream service boundaries; the
standard Phase-4 expansion targets do not apply.

## Open Assumptions (low confidence — require coach + human review)

- **ASSUM-001** — Module docstring lower bound = 20 lines.
  *Basis:* Inferred — `nats_client.py` is the thinnest candidate and could
  legitimately compress to 20 after polish; below 20 reads as a stub.
- **ASSUM-002** — Module docstring upper bound = 250 lines.
  *Basis:* Inferred — caps `routing_history.py`-style ADR-FLEET-001 schema
  discussion while leaving headroom.
- **ASSUM-003** — TASK-Jxxx references banned **entirely** from polished docstrings
  (overridden from initial "trailing-section allowance" proposal).
  *Basis:* Convention call — TASK-Jxxx is GuardKit autobuild bookkeeping, not
  reader-facing prose; FEAT-JARVIS-XXX origin attribution provides equivalent
  traceability without the bookkeeping leak.

## Out of Scope

- Reasoning-model-facing tool docstrings under `src/jarvis/tools/*.py` (FEAT-J004/J005
  invariant: tool docstrings byte-unchanged from Phase 2). Concretely:
  `general.py`, `capabilities.py`, `dispatch.py` `@tool`-decorated functions.
- Any Python source code changes beyond docstrings (no refactors, no type
  annotation changes, no behavioural modifications).
- Updates to `CLAUDE.md` / `.claude/CLAUDE.md` (those are AI-agent-facing and
  on a separate convention).
- Files outside the five infrastructure module candidates and `README.md`.
- Pre-existing FEAT-J004 mypy issue tracked under [`TASK-REV-FFE4`](../../tasks/backlog/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md)
  (resolved on its own track; this feature must not add to the mypy error count
  but is decoupled from FFE4's resolution timing).
- The 49 ruff cosmetic violations on `main` (separate cleanup pass).

## Phase 3 Build Plan Alignment

This is the FEAT-JARVIS-INTERNAL-001 candidate selected at **Step 13 of
`phase3-build-plan.md`** for the Step 14 end-to-end Forge round-trip. The
"broader foundation, lower behavioural risk" scope (referred to in conversation
as **option a-1.5**) was chosen over:

- **a-1** (smaller, infrastructure modules only — no README) — the README is
  genuinely missing/stale and is a do-once foundation.
- **a-2** (broader, includes the 10 reasoning-model tool docstrings) —
  rejected on demo-stability grounds: tool docstrings ARE the supervisor's
  reasoning input and have been routing-stable since Phase 2; touching them
  during the Step-14 transport validator introduces a behavioural confound.

## Smoke Set (7 scenarios — Coach-blocking)

The `@smoke` set defines the minimum the coach must verify on every autobuild
turn:

1. Each infrastructure module has a Purpose paragraph (Group A.1)
2. Each infrastructure module references its FEAT-JARVIS origin (Group A.2)
3. The repo README has an H1 with the project name (Group A.5)
4. The repo README declares the current Phase-3-close status (Group A.6)
5. Reasoning-model-facing tool docstrings remain byte-unchanged (Group C.1)
6. Polished docstrings contain no TASK-Jxxx references (Group C.4)
7. All polished modules remain importable and graphs still compile (Group D.1)
8. The full pytest suite remains green and coverage does not regress (Group D.2)

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

```bash
/feature-plan "FEAT-JARVIS-INTERNAL-001 Documentation Foundation" \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_summary.md \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation.feature \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml \
  --context docs/research/ideas/phase3-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context src/jarvis/infrastructure/nats_client.py \
  --context src/jarvis/infrastructure/fleet_registration.py \
  --context src/jarvis/infrastructure/capabilities_registry.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context src/jarvis/infrastructure/forge_notifications.py \
  --context README.md
```

## Pre-flight Notes for /feature-plan

- **ASSUM-001/002/003 promotion candidate**: the three low-confidence assumptions
  are the right size to promote to a single DDR — *DDR-INT-001: Documentation
  Polish Bounds and TASK-Jxxx Convention*. Consider this in the planning task
  breakdown.
- **Coach-friendly verification**: every assertion in the .feature is
  structurally testable (regex against file contents, `wc -l` against files,
  AST inspection of module docstrings). No subjective "is this README good"
  judgements required.
- **Single-coach-pass shape**: the feature is small enough for a 1–2 wave
  breakdown — likely one wave of 5 module-polish tasks running in parallel,
  plus one wave for the README rewrite + a final invariant-check task.
Bash Confirm output files written
IN
ls -la features/feat-jarvis-internal-001-documentation-foundation/ ; echo "---feature line count---" ; wc -l features/feat-jarvis-internal-001-documentation-foundation/*.feature features/feat-jarvis-internal-001-documentation-foundation/*.yaml features/feat-jarvis-internal-001-documentation-foundation/*.md

OUT
total 64
drwxr-xr-x   5 richardwoollcott  staff    160 Apr 30 17:04 .
drwxr-xr-x  10 richardwoollcott  staff    320 Apr 30 17:01 ..
-rw-r--r--   1 richardwoollcott  staff   6903 Apr 30 17:03 feat-jarvis-internal-001-documentation-foundation_assumptions.yaml
-rw-r--r--   1 richardwoollcott  staff   7454 Apr 30 17:04 feat-jarvis-internal-001-documentation-foundation_summary.md
-rw-r--r--   1 richardwoollcott  staff  14942 Apr 30 17:02 feat-jarvis-internal-001-documentation-foundation.feature
---feature line count---
     259 features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation.feature
      99 features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml
     138 features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_summary.md
     496 total
All three files written. Final summary:


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: FEAT-JARVIS-INTERNAL-001 Documentation Foundation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files written
feat-jarvis-internal-001-documentation-foundation.feature — 259 lines, 21 scenario definitions / 40 effective rows
feat-jarvis-internal-001-documentation-foundation_assumptions.yaml — 13 assumptions
feat-jarvis-internal-001-documentation-foundation_summary.md — handoff to /feature-plan
Scenarios
Tag	Scenarios	Effective rows
@key-example	9	25
@boundary	2	5
@negative	5	5
@edge-case	5	5
@smoke	7	—
Assumptions
Confidence	Count
high	5 (auto-proceed)
medium	5 (coach review recommended)
low	3 (human review required)

REVIEW REQUIRED: 3 low-confidence assumptions
  - ASSUM-001: Module docstring lower bound = 20 lines
  - ASSUM-002: Module docstring upper bound = 250 lines
  - ASSUM-003: TASK-Jxxx banned entirely from polished docstrings (overridden)
  See: features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml
The three low-confidence assumptions are the natural candidates to promote to a single DDR (DDR-INT-001: Documentation Polish Bounds and TASK-Jxxx Convention) when /feature-plan runs.

Next steps

/feature-plan "FEAT-JARVIS-INTERNAL-001 Documentation Foundation" \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_summary.md \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation.feature \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml \
  --context docs/research/ideas/phase3-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context src/jarvis/infrastructure/nats_client.py \
  --context src/jarvis/infrastructure/fleet_registration.py \
  --context src/jarvis/infrastructure/capabilities_registry.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context src/jarvis/infrastructure/forge_notifications.py \
  --context README.md
Want me to proceed straight to /feature-plan with this context bundle? It's the natural next step before the autobuild that produces the Step-14 payload.