/system-arch "Jarvis: General Purpose DeepAgent with dispatch tools — attended surface of the three-surface fleet" \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-build-plan-conversation-starter.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/general-purpose-agent.md \
  --context docs/research/ideas/reachy-mini-integration.md \
  --context docs/research/ideas/nemoclaw-assessment.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context .guardkit/context-manifest.yaml


  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ARCHITECTURE DOCUMENTATION CREATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

docs/architecture/
  ├── ARCHITECTURE.md              (index + summary)
  ├── domain-model.md              (7 bounded contexts, DDD context map, aggregates, events)
  ├── system-context.md            (C4 Level 1 Mermaid)
  ├── container.md                 (C4 Level 2 Mermaid)
  ├── assumptions.yaml             (15 ASSUM entries)
  └── decisions/
      ├── ADR-ARCH-001-local-first-inference-via-llama-swap.md   [FOUNDATIONAL]
      ├── ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md
      ├── ADR-ARCH-003-jarvis-is-the-gpa.md
      ├── ADR-ARCH-004-jarvis-registers-on-fleet-register.md
      ├── ADR-ARCH-005-seven-bounded-contexts.md
      ├── ADR-ARCH-006-five-group-module-layout.md
      ├── ADR-ARCH-007-adapter-services-as-separate-containers.md
      ├── ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md
      ├── ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md
      ├── ADR-ARCH-010-python-312-and-deepagents-pin.md
      ├── ADR-ARCH-011-single-jarvis-reasoner-subagent.md
      ├── ADR-ARCH-012-swap-aware-voice-latency-policy.md
      ├── ADR-ARCH-013-pattern-b-watcher-ceiling.md
      ├── ADR-ARCH-014-docker-on-gb10-deployment.md
      ├── ADR-ARCH-015-ci-ruff-mypy-pytest.md
      ├── ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md
      ├── ADR-ARCH-017-static-skill-declaration-v1.md
      ├── ADR-ARCH-018-calibration-approvals-cli-only-v1.md
      ├── ADR-ARCH-019-dashboard-read-only-live-trace-viewport.md
      ├── ADR-ARCH-020-trace-richness-by-default.md
      ├── ADR-ARCH-021-tools-return-structured-errors.md
      ├── ADR-ARCH-022-constitutional-rules-belt-and-braces.md
      ├── ADR-ARCH-023-permissions-constitutional-not-reasoning-adjustable.md
      ├── ADR-ARCH-024-pattern-b-watcher-failure-policy.md
      ├── ADR-ARCH-025-deepagents-0-6-upgrade-gated.md
      ├── ADR-ARCH-026-no-horizontal-scaling.md
      ├── ADR-ARCH-027-attended-only-cloud-escape-hatch.md
      ├── ADR-ARCH-028-watcher-durability.md
      ├── ADR-ARCH-029-personal-use-compliance-posture.md
      └── ADR-ARCH-030-budget-envelope.md

Graphiti seeding (5 background jobs):
  • bwgcwcf4v — ADR directory → architecture_decisions (30 ADRs)
  • bigrp6dhx — ARCHITECTURE.md → project overview
  • b2jriowe9 — domain-model.md → full_doc
  • bfzf5yvcy — system-context.md → full_doc
  • bxhdbfm6o — container.md → full_doc

Open questions resolved in-session: JA2, JA3, JA4, JA5, JA6, JA7, JA8
Deferred to /system-design: JA1 (jarvis_routing_history Pydantic schema)

Next steps:
  1. Review: docs/architecture/ARCHITECTURE.md
  2. Check seeding progress: BashOutput for the five bg jobs above
  3. Design APIs / schemas: /system-design "Jarvis"
  4. Plan features: /system-plan "feature description"
Session summary
Captured 30 ADRs + C4 diagrams across 6 categories. Mid-session you corrected my cloud-LLM blind spot — that forced the foundational ADR-ARCH-001 (local-first inference via llama-swap) and a re-take of the subagent roster (single jarvis-reasoner on gpt-oss-120b instead of four cloud models) plus the cloud escape hatch (ADR-ARCH-027, constitutionally attended-only). Preference saved to memory so the mistake won't recur.

Graphiti seeding runs locally via GB10 vLLM — I'll be notified when the five background jobs finish. Meanwhile, the markdown artefacts are ready for review regardless of seeding state.





/system-design FEAT-JARVIS-001 \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/architecture/decisions/ADR-J-004-supervisor-model-default.md \
  --context docs/architecture/decisions/ADR-J-005-memory-store-backend.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../specialist-agent/pyproject.toml \
  --context ../forge/pyproject.toml \
  --context .guardkit/context-manifest.yaml

Summary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SYSTEM DESIGN — FEAT-JARVIS-001
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Created: docs/design/FEAT-JARVIS-001/
├── design.md                                   ← top-level consolidated doc
├── contracts/
│   ├── API-cli.md                              (3 subcommands, env vars, exit codes)
│   └── API-internal.md                         (module boundaries, public APIs, stability)
├── models/
│   ├── DM-jarvis-reasoning.md                  (Session, Adapter, AppState, exceptions)
│   └── DM-config.md                            (JarvisConfig BaseSettings)
├── diagrams/
│   └── supervisor-container-l3.md              ⚠ AWAITING APPROVAL
└── decisions/
    ├── DDR-001 — no network protocols Phase 1
    ├── DDR-002 — Memory Store keyed by user_id
    ├── DDR-003 — CLI = chat/version/health only
    └── DDR-004 — thread_id == session_id 1:1

Protocols NOT generated (by design — see DDR-001):
  openapi.yaml | mcp-tools.json | a2a-schemas.yaml

Contradictions with 30 existing ADRs: 0
Graphiti: 9 seeding commands ready, awaiting [Y/N]

Pending gates:
  1. C4 L3 diagram approval → [A/R/R]
  2. Graphiti seeding → [Y/N]

Next in pipeline (per phase1-build-plan.md Steps 3–5):
  /feature-spec FEAT-JARVIS-001 --context docs/design/FEAT-JARVIS-001/design.md ...
  /feature-plan FEAT-JARVIS-001
  AutoBuild
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Committed as b259206 — 12 files, 3211 insertions. Branch is now 3 commits ahead of origin/main; nothing pushed. C4 L3 approval and Graphiti seeding are still outstanding whenever you want to revisit.

Pending gates:
  1. C4 L3 diagram approval → [A]pprove
  2. Graphiti seeding → [Y]

  Graphiti seeding succeeded — all 9 artefacts ingested across 42 episodes total.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ GRAPHITI SEEDING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

contracts/API-cli.md                  →  1 episode
contracts/API-internal.md             → 11 episodes (chunked — large)
models/DM-jarvis-reasoning.md         → 10 episodes (chunked — large)
models/DM-config.md                   →  1 episode
decisions/DDR-001..004.md             →  4 episodes (1 each, --type adr)
design.md                             → 14 episodes (chunked — large)
─────────────────────────────────────────────
Total: 9 files, 42 episodes → FalkorDB @ whitestocks:6379
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Warnings were just benign "document too large, auto-chunking" notes — no failures.

/system-design FEAT-JARVIS-001 is complete. Design artefacts + approval + Graphiti seeding all landed. Branch is 4 commits ahead of origin/main, nothing pushed. Next per phase1-build-plan.md Step 3: /feature-spec FEAT-JARVIS-001 --context docs/design/FEAT-JARVIS-001/design.md ...




/feature-spec "Project Scaffolding, Supervisor Skeleton & Session Lifecycle: pyproject.toml with deepagents>=0.5.3,<0.6 pin, src/jarvis/ layer structure, DeepAgents supervisor via create_deep_agent(), thread-per-session with Memory Store, jarvis CLI (chat/version/health), smoke tests" \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/architecture/decisions/ADR-J-004-supervisor-model-default.md \
  --context docs/architecture/decisions/ADR-J-005-memory-store-backend.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context ../forge/src/forge/cli/main.py \
  --context ../specialist-agent/src/specialist_agent/cli/main.py \
  --context .guardkit/context-manifest.yaml


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Project Scaffolding, Supervisor Skeleton & Session Lifecycle
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md

Scenarios: 35 total
@key-example: 8   @boundary: 7
@negative: 8      @edge-case: 12
@smoke: 6         @regression: 3
@security: 3      @concurrency: 2   @integration: 2

Assumptions: 6 total
high: 0
medium: 4 (ASSUM-001, 004, 005, 006 — Coach review recommended)
low: 2 (ASSUM-002, 003 — human review required)

REVIEW REQUIRED: 2 low-confidence assumptions need verification
See: features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml

ASSUM-002: "/exit" case/whitespace handling — not pinned in any contract
ASSUM-003: Concurrent invoke on same session — refuse vs. serialise not pinned
Deferred: 0 scenario groups

Next steps:

Review low-confidence assumptions (ASSUM-002, 003) — either confirm now or leave for the Coach gate at /task-review
Run Step 4 of the Phase 1 build plan:

/feature-plan "Project Scaffolding, Supervisor Skeleton & Session Lifecycle" \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/research/ideas/phase1-build-plan.md


/feature-plan "Project Scaffolding, Supervisor Skeleton & Session Lifecycle" \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md \
  --context docs/architecture/decisions/ADR-ARCH-006-five-group-module-layout.md \
  --context docs/architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md \
  --context docs/architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md \
  --context docs/architecture/decisions/ADR-ARCH-015-ci-ruff-mypy-pytest.md \
  --context docs/architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md \
  --context docs/architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \


Feature planning complete. Here is the summary:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ FEATURE PLANNING COMPLETE — FEAT-JARVIS-001
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Feature: Project Scaffolding, Supervisor Skeleton & Session Lifecycle
Review task: TASK-REV-J001 (review_complete, decision=implement)
Structured YAML: .guardkit/features/FEAT-JARVIS-001.yaml
Feature folder: tasks/backlog/project-scaffolding-supervisor-sessions/

Artefacts created
README.md — feature overview + task table
IMPLEMENTATION-GUIDE.md — data-flow diagram, integration-contract sequence diagram, task-dependency graph, §4 Integration Contracts (3 contracts), wave structure, invariants, risks
11 subtask files (see table below)
Task breakdown (11 tasks · 6 waves)
Wave	Tasks	Type of wave
1	TASK-J001-001, -002, -010	parallel (3)
2	TASK-J001-003, -004	parallel (2)
3	TASK-J001-005, -006	parallel (2)
4	TASK-J001-007	serial
5	TASK-J001-008	serial
6	TASK-J001-009, -011	parallel (2)
Aggregate complexity: 7/10 · Total effort: ~600 min (10 hrs sum; critical path ~7 hrs) · Timeline: 3–4 working days

Integration contracts pinned
SUPERVISOR_MODEL_ENDPOINT (TASK-003 → TASK-006): provider-prefixed model + OPENAI_BASE_URL to llama-swap
COMPILED_SUPERVISOR_GRAPH (TASK-006 → TASK-007): ainvoke must pass both config.thread_id and store kwargs
APP_STATE (TASK-005 → TASK-008): logging configured before config validation
Pre-flight validation
✅ All 11 task files exist
✅ All dependencies reference valid task IDs
✅ No intra-wave dependency conflicts (caught and fixed T009/T011 → split to wave 6)
✅ All tasks have task_type in frontmatter (CoachValidator compatible)
✅ Consumer tasks have consumer_context + seam test stubs
✅ .guardkit/features/FEAT-JARVIS-001.yaml schema valid

Next steps

/feature-build FEAT-JARVIS-001        # autonomous Player-Coach
# or wave-by-wave:
/task-work TASK-J001-001 --implement-only   # wave 1 (in parallel with -002, -010)

════════════════════════════════════════════════════════════
FEATURE RESULT: SUCCESS
════════════════════════════════════════════════════════════

Feature: FEAT-JARVIS-001 - Project Scaffolding, Supervisor Skeleton & Session Lifecycle
Status: COMPLETED
Tasks: 11/11 completed
Total Turns: 12
Duration: 57m 36s

                                  Wave Summary
╭────────┬──────────┬────────────┬──────────┬──────────┬──────────┬─────────────╮
│  Wave  │  Tasks   │   Status   │  Passed  │  Failed  │  Turns   │  Recovered  │
├────────┼──────────┼────────────┼──────────┼──────────┼──────────┼─────────────┤
│   1    │    3     │   ✓ PASS   │    3     │    -     │    4     │      -      │
│   2    │    2     │   ✓ PASS   │    2     │    -     │    2     │      -      │
│   3    │    2     │   ✓ PASS   │    2     │    -     │    2     │      -      │
│   4    │    1     │   ✓ PASS   │    1     │    -     │    1     │      -      │
│   5    │    1     │   ✓ PASS   │    1     │    -     │    1     │      -      │
│   6    │    2     │   ✓ PASS   │    2     │    -     │    2     │      -      │
╰────────┴──────────┴────────────┴──────────┴──────────┴──────────┴─────────────╯

Execution Quality:
  Clean executions: 11/11 (100%)

SDK Turn Ceiling:
  Invocations: 5
  Ceiling hits: 0/5 (0%)

                                  Task Details
╭──────────────────────┬────────────┬──────────┬─────────────────┬──────────────╮
│ Task                 │ Status     │  Turns   │ Decision        │  SDK Turns   │
├──────────────────────┼────────────┼──────────┼─────────────────┼──────────────┤
│ TASK-J001-001        │ SUCCESS    │    1     │ approved        │      -       │
│ TASK-J001-002        │ SUCCESS    │    2     │ approved        │      -       │
│ TASK-J001-010        │ SUCCESS    │    1     │ approved        │      -       │
│ TASK-J001-003        │ SUCCESS    │    1     │ approved        │      46      │
│ TASK-J001-004        │ SUCCESS    │    1     │ approved        │      -       │
│ TASK-J001-005        │ SUCCESS    │    1     │ approved        │      45      │
│ TASK-J001-006        │ SUCCESS    │    1     │ approved        │      44      │
│ TASK-J001-007        │ SUCCESS    │    1     │ approved        │      47      │
│ TASK-J001-008        │ SUCCESS    │    1     │ approved        │      48      │
│ TASK-J001-009        │ SUCCESS    │    1     │ approved        │      -       │
│ TASK-J001-011        │ SUCCESS    │    1     │ approved        │      -       │
╰──────────────────────┴────────────┴──────────┴─────────────────┴──────────────╯

Worktree: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
Branch: autobuild/FEAT-JARVIS-001

Next Steps:
  1. Review: cd /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  2. Diff: git diff main
  3. Merge: git checkout main && git merge autobuild/FEAT-JARVIS-001
  4. Cleanup: guardkit worktree cleanup FEAT-JARVIS-001
INFO:guardkit.cli.display:Final summary rendered: FEAT-JARVIS-001 - completed
INFO:guardkit.orchestrator.review_summary:Review summary written to /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/FEAT-JARVIS-001/review-summary.md
✓ Review summary: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/autobuild/FEAT-JARVIS-001/review-summary.md
INFO:guardkit.orchestrator.feature_orchestrator:Feature orchestration complete: FEAT-JARVIS-001, status=completed, completed=11/11
richardwoollcott@Mac jarvis %



/task-review FEAT-JARVIS-001 \
  --context tasks/FEAT-JARVIS-001-*.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md

Review complete. Report saved at .claude/reviews/FEAT-JARVIS-001-review-report.md.


=========================================================================
REVIEW COMPLETE: FEAT-JARVIS-001
=========================================================================

Mode: Architectural (post-build gate, Step 6 of phase1-build-plan.md)
Depth: Standard
Score: 82/100

Quality gates:
  pytest:  340 / 341 passing   (1 env-fragile failure — F2)
  ruff src/jarvis/:  CLEAN
  ruff tests/:       7 errors  (outside Success Criterion #6)
  mypy src/jarvis/:  5 errors  (BREAKS Success Criterion #6)

Findings: 8
  HIGH (block success criteria):
    F1  mypy not clean on src/jarvis/ — 5 errors, all trivial
    F2  test_jarvis_version_command env-fragile under py3.14 vs .venv py3.12
  MEDIUM:
    F3  AppState.supervisor/session_manager typed Any with stale comments;
        CLI uses dataclasses.replace to stitch them in
    F4  JarvisConfig() validation happens BEFORE structlog is configured
  LOW:
    F5  correlation_id docstring says ULID, code uses UUID
    F6  ruff errors in tests/ (scoped outside success criterion)
    F7  SessionManager concurrency fine for asyncio single-loop; fragile
        when FEAT-006 adds a second driver
    F8  HumanMessage import at function scope instead of module top

Strengths:
  ✓ All 6 ASSUM-* pins implemented in code (not just docs)
  ✓ DDR-002 (user-keyed store), DDR-003 (3 CLI cmds), DDR-004 (thread=session)
  ✓ Invariants clean: no NATS / Telegram / Graphiti / subagent / custom-tool
    imports; 8 reserved packages stubbed with FEAT-* markers
  ✓ Hexagonal boundary enforced by AST + runtime import-graph tests
  ✓ Supervisor is token-free at build time (no-LLM-call test passes)
  ✓ Secret redaction wired into structlog processors

Recommendations (all trivial; ~30–60 min total):
  R1  Fix 5 mypy errors (REQUIRED for Success Criterion #6)
  R2  Stabilise sys.executable subprocess test (REQUIRED for Criterion #5)
  R3  Tighten AppState typing + collapse dataclasses.replace bootstrap
  R4  Configure logging at CLI entry, before JarvisConfig()
  R5  Cosmetic: correlation_id docstring, hoist HumanMessage, ruff --fix tests/

Decision Options:
  [A]ccept — close Phase 1 as-is (WILL miss Success Criteria #5 and #6)
  [R]evise — I fix R1+R2 (required) and optionally R3–R5 in this session
  [I]mplement — create a fix subtask folder under tasks/backlog/
  [C]ancel — discard review

Recommended: [R]evise. The fixes are trivial and close Phase 1 cleanly
against the build plan's own success criteria.

Your choice [A/R/I/C]?
=========================================================================
FEAT-JARVIS-001-review-report.md
I

================================================================================
✅ Feature Implementation Structure Created
================================================================================

Created: tasks/backlog/phase1-review-fixes/
  ├── README.md
  ├── IMPLEMENTATION-GUIDE.md
  ├── TASK-J001-FIX-001-mypy-clean-src.md
  ├── TASK-J001-FIX-002-python-version-pin.md
  ├── TASK-J001-FIX-003-bootstrap-refactor.md
  └── TASK-J001-FIX-004-cosmetic-polish.md

--------------------------------------------------------------------------------
📋 Execution Strategy:
--------------------------------------------------------------------------------

Wave 1 (parallel — no file conflicts):
  ⚡ FIX-001: Fix mypy type errors in src/jarvis/
     Workspace: phase1-review-fixes-wave1-1   Mode: direct        ~15 min
  ⚡ FIX-002: Pin Python 3.12 + stabilise subprocess test
     Workspace: phase1-review-fixes-wave1-2   Mode: direct        ~10 min

Wave 2 (parallel after Wave 1):
  ⚡ FIX-003: Tighten AppState typing + move logging to CLI entry
     Workspace: phase1-review-fixes-wave2-1   Mode: task-work     ~35 min
  ⚡ FIX-004: correlation_id docstring, HumanMessage hoist, ruff tests/
     Workspace: phase1-review-fixes-wave2-2   Mode: direct        ~15 min

Total: ~75 min sequential · ~50 min wall-clock with parallel waves.
All tasks reference parent_review=TASK-REV-J001, feature_id=FEAT-JARVIS-001.
================================================================================
🚀 Next Steps:
================================================================================
1. Review: tasks/backlog/phase1-review-fixes/IMPLEMENTATION-GUIDE.md
2. Review: tasks/backlog/phase1-review-fixes/README.md
3. Start Wave 1: /task-work TASK-J001-FIX-001   and   /task-work TASK-J001-FIX-002
4. Gate between waves: pytest + ruff + mypy must be green on src/jarvis/
5. Start Wave 2: /task-work TASK-J001-FIX-003   and   /task-work TASK-J001-FIX-004
================================================================================


implement TASK-J001-FIX-001

 TASK-J001-FIX-001 complete. All acceptance criteria met:

  Changes (3 files, +14/-8):
  - src/jarvis/agents/supervisor.py — parameterised two CompiledStateGraph references as CompiledStateGraph[Any, Any, Any, Any] (the
  generic takes 4 type params: StateT, ContextT, InputT, OutputT; DeepAgents' inner _InputAgentState / _OutputAgentState are private so
  the Any fallback applies). Added Any to the existing typing import.
  - src/jarvis/sessions/manager.py — same parameterisation on SessionManager._supervisor; widened __init__ to a multi-line signature to
  stay under the 88-char limit.
  - src/jarvis/infrastructure/logging.py — removed unused # type: ignore[arg-type] (line 65); widened _redact_secrets to match
  structlog.types.Processor (Any, str, MutableMapping[str, Any] → Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...]).
  Redaction body unchanged.

  Quality gates:
  - uv run mypy src/jarvis/ — clean on two consecutive runs (0 errors, was 5)
  - uv run ruff check src/jarvis/ — clean
  - uv run pytest tests/ — 339 pass / 2 fail, identical to the pre-task baseline (verified via git stash). The two failures are
  pre-existing:
    - test_jarvis_version_command — handled by FIX-002
    - test_returns_compiled_state_graph — unrelated: a local env issue where init_chat_model("openai:…") now instantiates
  openai.AsyncOpenAI eagerly, which requires OPENAI_API_KEY. Present on the unmodified baseline too, so it's out of scope for FIX-001
  (worth raising separately).

  Diff confined to the three listed files; no pyproject.toml changes needed.

/task-complete TASK-J001-FIX-001


implement TASK-J001-FIX-002

 All three changes landed and the acceptance checks pass. Summary of what changed:

  Files changed:
  - .python-version (NEW) — single line 3.12, pins the interpreter so uv ignores ambient 3.14 venvs.
  - README.md — added one-sentence note at top of Quickstart steering users to uv run; preserved the existing pip install/pytest/venv
  content (the developer-surface test parametrizes on those).
  - tests/test_build_system.py — added diagnostic pre-assertion in test_jarvis_version_command that runs import jarvis under
  sys.executable first and fails loudly with a message pointing to uv run pytest if drift recurs (no silent skip).

  Acceptance check results:
  - cat .python-version → 3.12 ✓
  - uv run python -c "import sys; print(sys.executable)" → …/jarvis/.venv/bin/python3 ✓
  - uv run pytest tests/test_build_system.py::TestAC004EntryPoint::test_jarvis_version_command -v → 1 passed on a clean .venv ✓
  - Full suite: 341 passed, 0 failed (matches coach target exactly).

  One caveat worth flagging:
  - The task's acceptance script says uv sync --dev, but dev deps here are declared under [project.optional-dependencies].dev, not
  [dependency-groups].dev. uv sync --dev installs runtime deps only; you need uv sync --extra dev (or --all-extras) to get pytest.
  That's out of scope for FIX-002 but worth a follow-up.
  - One other test (test_supervisor.py::TestBuildSupervisorReturnsGraph::test_returns_compiled_state_graph) needs OPENAI_API_KEY set
  in the ambient env — pre-existing, untouched by this task, explicitly out of scope per the task doc ("no other F-* fixes").


/task-complete TASK-J001-FIX-002



/task-work TASK-J001-FIX-003

TASK-J001-FIX-003 complete and moved to in_review.

  Summary of changes

  - src/jarvis/infrastructure/lifecycle.py — AppState now uses concrete types (CompiledStateGraph, BaseStore, SessionManager); no more
   Any fields or stale "None until TASK-J001-…" comments. New build_app_state(config) factory returns a fully-wired AppState in one
  step (with startup kept as a backwards-compatible alias).
  - src/jarvis/cli/main.py — _configure_default_logging() runs at CLI entry before any JarvisConfig() load; _create_app_state
  collapses to load config → build_app_state(config) (no more dataclasses.replace); ValidationError, ConfigurationError, and generic
  startup failures are now emitted via structlog before SystemExit(1).
  - src/jarvis/infrastructure/__init__.py — re-exports build_app_state alongside startup.
  - tests/test_infrastructure.py — tests that previously relied on startup returning a partial AppState(supervisor=None,
  session_manager=None) now mock build_supervisor and assert the new complete-state contract.

  Quality gates
  - uv run mypy src/jarvis/ → clean (26 files).
  - uv run pytest → 340 passed, 1 pre-existing failure (test_supervisor.py::test_returns_compiled_state_graph) that also fails on
  2fc9ab7 untouched — outside scope.
  - uv run ruff check / ruff format --check → clean.
  - Coach greps: no Any on AppState fields, no dataclasses.replace in src/jarvis/, no "None until TASK" comments.
  - JARVIS_LOG_LEVEL=bogus uv run jarvis health → emits {"event":"jarvis_config_invalid", …} structlog JSON, exits 1.

✻ Brewed for 12m 5s

※ recap: Completing TASK-J001-FIX-003 (tighten AppState typing, move logging config to CLI entry) for FEAT-JARVIS-001 review wave 2.
  Task is implemented, tests/mypy/ruff green, and the file is now in tasks/in_review/ awaiting your review. (disable recaps in
  /config)



/task-work TASK-J001-FIX-004

TASK-J001-FIX-004 complete. Summary:

  Changes
  - src/jarvis/sessions/session.py:29 — docstring reworded: ULID wording replaced with UUID4-placeholder note citing FEAT-004 /
  ADR-ARCH-020.
  - src/jarvis/sessions/manager.py — hoisted from langchain_core.messages import HumanMessage to module top; removed the function-local
  import inside invoke.
  - tests/test_smoke_end_to_end.py, tests/test_supervisor_no_llm_call.py — ruff --fix removed unused imports (Any, CompiledStateGraph,
  pytest) and sorted the import block.
  - tests/test_build_system.py, tests/test_import_graph.py, tests/test_supervisor_no_llm_call.py — annotated REQUIRED_PATTERNS,
  HIGHER_PACKAGES, TOKEN_CONSUMING_METHODS with typing.ClassVar[list[str]].
  - Task file moved to tasks/completed/TASK-J001-FIX-004/ with status: completed.

  Gates
  - uv run ruff check src/jarvis/ tests/ → All checks passed.
  - uv run mypy src/jarvis/ → clean (26 files).
  - uv run pytest tests/ → 341 passed (with OPENAI_API_KEY set — matches baseline; single remaining failure is a pre-existing env-fragile
   supervisor test unrelated to this task).

✻ Brewed for 3m 36s

※ recap: Goal was Phase 1 review-fix cleanup; just finished TASK-J001-FIX-004 (docstring, import hoist, ruff/ClassVar tidy) with ruff,
  mypy, and 341-test pytest all green. Next: commit the changes. (disable recaps in /config)



# ===========================================================================
# 2026-04-22 — Phase 1 Step 7 regression debug + Step 8 day-1 validation
# ===========================================================================

# Step 7: kicked off the regression check per phase1-build-plan.md §Step 7
# (pasted the plan block into zsh, which produced a pile of `command not
# found` warnings for the literal prose lines — harmless, the real commands
# underneath still ran).

uv sync --dev
uv run pytest tests/ -v --tb=short --cov=src/jarvis

# 339 passing / 2 failing:
#   1. test_build_system.py::TestAC004EntryPoint::test_jarvis_version_command
#      — subprocess's sys.executable resolved to /usr/local/bin/python
#        (system Python 3.14), where jarvis isn't installed. Root cause:
#        `uv sync --dev` in uv 0.11.2 binds to PEP 735 [dependency-groups],
#        which this project didn't declare; dev deps lived under
#        [project.optional-dependencies].dev, so pytest was never installed
#        into .venv/bin, and `uv run pytest` silently fell through $PATH to
#        the system 3.14 pytest. 339 other tests passed by accident because
#        system 3.14's global site-packages happens to include langchain,
#        openai, etc.
#   2. test_supervisor.py::TestBuildSupervisorReturnsGraph
#        ::test_returns_compiled_state_graph — the only test in that class
#        that did NOT patch init_chat_model, so it attempted to construct a
#        real AsyncOpenAI client and failed without OPENAI_API_KEY. Bug in
#        the test, not the production code; contradicts AC-001's own
#        "without network" docstring.

# Investigation confirmed (a) .venv was Python 3.12.4 per pyvenv.cfg but
# lacked pytest; (b) the 3.14 framework had pytest 9.0.2 globally. Fix was
# two-layered: patch the AC-001 test to use the fake_llm fixture, and move
# dev deps to PEP 735 [dependency-groups].dev so bare `uv sync` hydrates
# them. Also updated README Quickstart to use `uv sync` + `uv run` (removing
# the pip-install dance), adjusted TestAC004ReadmeQuickstart to expect
# "uv sync" instead of "pip install", and swept phase2/3/4-build-plan.md so
# they don't re-introduce `uv sync --dev`.

# Verified on a clean venv:
rm -rf .venv && uv sync
uv run pytest tests/ --tb=short --cov=src/jarvis   # 341 passed
uv run ruff check src/jarvis/ tests/               # clean
uv run mypy src/jarvis/                            # clean

# Commit 84daf08:
#   "Fix phase-1 regression: move dev deps to PEP 735 [dependency-groups]"
#   9 files changed, +183/-57.

# ---------------------------------------------------------------------------
# Step 8: Day-1 conversation validation.
# Pasted the plan block again — zsh took `<provider API key env var>` as
# input redirection (`< provider`) and errored. The `<ADR-pinned default>`
# line WAS a valid quoted export though, and so JARVIS_SUPERVISOR_MODEL got
# set to the literal placeholder "<ADR-pinned default>" in the shell.

unset JARVIS_SUPERVISOR_MODEL    # cleared the stale export
uv run jarvis health             # → "Provider 'openai' requires OPENAI_BASE_URL"

# .env already existed with OPENAI_API_KEY and GOOGLE_API_KEY but no JARVIS_
# prefix — invisible to JarvisConfig. Rewrote to use cloud OpenAI (Path A
# from the options I offered). *Keys from the first paste were rotated
# immediately — they got captured in the chat transcript before we caught
# it.*

# With .env populated, jarvis health *still* failed:
#   "The api_key client option must be set..."
# Root cause: pydantic-settings reads .env into JarvisConfig but does NOT
# export to os.environ. langchain's AsyncOpenAI reads OPENAI_API_KEY from
# os.environ directly. Nothing bridged the two.

# Fix (Option 2 — proper, not just a shell `set -a; source .env` hack):
#   src/jarvis/cli/main.py — call load_dotenv(override=False) at the Click
#     group callback so .env seeds os.environ before any subcommand runs.
#   tests/conftest.py — autouse `_isolate_dotenv` fixture that chdirs to
#     tmp_path, so JarvisConfig's relative env_file=".env" resolves to a
#     nonexistent file during tests (the operator's real .env was leaking
#     into tests that had been passing only because .env didn't exist).
#   tests/test_cli.py — autouse `_stub_load_dotenv` + new TestDotenvBridge
#     class (3 tests: version/no-args invoke load_dotenv; override=False).

# Verified:
uv run jarvis health
# Building supervisor graph with model=openai:gpt-4o-mini
# Supervisor graph compiled successfully
# supervisor: ok
# memory store: ready

uv run jarvis chat
# → supervisor responds correctly on first turn. BUT:
#   > Remember that my DDD Southwest talk is on 16 May.
#   [ack]
#   > When is my DDD Southwest talk?
#   I couldn't find any information about your DDD Southwest talk.

# Within-session recall broken. Root cause: build_supervisor called
# create_deep_agent(...) without checkpointer=, defaulting to None. The
# SessionManager.invoke() flow passes config={"configurable": {"thread_id":
# session.thread_id}} every turn (DDR-004), but without a saver, thread_id
# keys nothing and each turn starts empty. All existing tests passed
# because they mock create_deep_agent and AsyncMock the `ainvoke` call —
# they never exercise the real DeepAgents middleware with a real
# checkpointer. Live OpenAI traffic was the only path that exposed it.

# Fix captured as TASK-J001-FIX-005:
#   src/jarvis/agents/supervisor.py — import InMemorySaver from
#     langgraph.checkpoint.memory; pass checkpointer=InMemorySaver() to
#     create_deep_agent(). Within-process recall now works; cross-process
#     recall still requires a persistent saver + persistent store, which
#     lands in FEAT-JARVIS-007.
#   tests/test_supervisor.py — new TestWithinSessionRecall class (4
#     regression guards): graph.checkpointer is not None; it's an
#     InMemorySaver specifically (pins the Phase 1 choice); create_deep_agent
#     was called with a non-None checkpointer= kwarg (catches DeepAgents
#     parameter renames); two build_supervisor calls produce graphs with
#     distinct savers (guards the idempotency contract).
#   tasks/completed/TASK-J001-FIX-005/TASK-J001-FIX-005.md — task record.
#   docs/research/ideas/phase1-build-plan.md — Success Criterion #4 split
#     into within-session (now met) + cross-session (deferred to
#     FEAT-JARVIS-007) halves; status log + narrative status updated.

uv run pytest tests/                 # 348 passed (+3 dotenv, +4 recall)
uv run ruff check src/jarvis/ tests/ # clean
uv run mypy src/jarvis/              # clean

# Commit c38c8e5:
#   "Fix day-1 multi-turn recall and .env→os.environ bridging (FIX-005)"
#   7 files changed, +296/-4.

# Live re-verification on the committed code:
uv run jarvis chat
# > Remember that my DDD SouthWest Talk is 16th May
# Got it! Your DDD SouthWest Talk is scheduled for May 16th.
# > When is my DDD SouthWest Talk?
# Your DDD SouthWest Talk is on May 16th.

# Phase 1 is closed. Next: push c38c8e5 to origin/main, then FEAT-JARVIS-002.

# ---------------------------------------------------------------------------
# Lessons worth carrying into Phase 2:
#   1. Two ways .env can leak into production code and tests: pydantic's
#      env_file relative path, and any code that reads os.environ directly
#      (langchain clients). Both need explicit handling.
#   2. Mocking create_deep_agent and AsyncMock-ing ainvoke in unit tests is
#      necessary (avoids token spend) but not sufficient — at least one test
#      per feature should exercise the *real* compiled graph with a real
#      saver and real store, even if the model is faked. FIX-005 would have
#      been caught at test time by such a test.
#   3. `uv sync --dev` vs `uv sync --extra dev` behaves very differently
#      depending on where dev deps are declared. Using [dependency-groups]
#      is the least-surprise path and means bare `uv sync` Just Works.
# ===========================================================================






/system-design FEAT-JARVIS-002 \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../nats-core/docs/design/contracts/agent-manifest-contract.md \
  --context ../nats-core/src/nats_core/manifest.py \
  --context ../nats-core/src/nats_core/topics.py \
  --context ../nats-core/src/nats_core/payloads/ \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/prompts/supervisor_prompt.py \
  --context .guardkit/context-manifest.yaml



📋 Design Summary
Feature: FEAT-JARVIS-002 — Core Tools & Capability-Driven Dispatch Tools

9 tools shipped on the Phase 1 supervisor:

Cluster	Tools	Transport
General	read_file, search_web, get_calendar_events, calculate	real (fs / Tavily / stub / asteval)
Capability catalogue	list_available_capabilities, capabilities_refresh, capabilities_subscribe_updates	real read / no-op / no-op over in-memory stub registry
Dispatch	dispatch_by_capability, queue_build	stubbed — real nats-core payloads built and logged; no network I/O
5 DDRs captured:

DDR-005 — Dispatch tool is dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60), superseding scope-doc call_specialist(agent_id, ...) (aligns with ADR-ARCH-003 / ADR-ARCH-016-equivalent — no hardcoded agent_id).
DDR-006 — Tavily as v1 web-search provider behind a swappable protocol.
DDR-007 — asteval for calculate (AST-based, no eval, 1 s time cap).
DDR-008 — Capabilities reach the supervisor via BOTH {available_capabilities} prompt injection AND the list_available_capabilities tool.
DDR-009 — Stub-transport semantics: build real nats-core payloads, log with JARVIS_DISPATCH_STUB / JARVIS_QUEUE_BUILD_STUB grep anchors, 60 s default timeout, no in-tool retry.
2 contradictions with scope doc resolved:

C1 — call_specialist(agent_id=...) vs fleet-wide capability-driven pattern → resolved via DDR-005 (rename + re-shape).
C2 — four cloud subagents vs ADR-ARCH-011 (single jarvis-reasoner on gpt-oss-120b) → flagged and deferred to /system-design FEAT-JARVIS-003.

🔍 Review gate — your decision
Look for:

Cyclic imports or leaking state (caps must not import factory).
Separation of concerns (dispatch depends on caps, not vice versa).
Missing persistence: Phase 2 has none (in-memory stub + no NATS) — acceptable per scope?
Any module with too many dependencies.
[A]pprove — I'll seed to Graphiti next
[R]evise — tell me what to change and I'll regenerate
[Reject] — drop this design and restart

Waiting for your call before proceeding to seeding.

A
Approved. Proceeding to Graphiti seeding.

Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH corpus

Draft DDRs (dispatch name, Tavily, asteval, capabilities delivery, stub semantics)

Write C4 L3 diagram

Present C4 L3 review gate to user + await approval

Offer Graphiti seeding commands
Quick Graphiti reachability probe before offering commands.

Bash Check Graphiti connectivity via guardkit CLI
IN
guardkit graphiti status 2>&1 | head -20

OUT
╔════════════════════════════════════════╗
║       Graphiti Knowledge Status        ║
╚════════════════════════════════════════╝

  Status: ENABLED
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"

  System Knowledge:
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"
    • product_knowledge: 84
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"
    • command_workflows: 100
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"
    • patterns: 100
Graphiti is reachable. Here are the seeding commands — 9 commands total (1 top-level design.md + 2 contracts + 2 models + 5 DDRs).


# Top-level design doc — indexed to project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/design.md \
  --group project_design

# API contracts — indexed to project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-tools.md \
  --group project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-internal.md \
  --group project_design

# Data models — indexed to project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-tool-types.md \
  --group project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md \
  --group project_design

# DDRs — indexed to architecture_decisions (matches how FEAT-JARVIS-001 DDRs were seeded)
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-006-tavily-as-web-search-provider.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-008-capabilities-both-tool-and-prompt-injection.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-009-dispatch-stub-transport-semantics.md \
  --group architecture_decisions
Want me to run these now? [Y]es / [N]o (I'll seed later)

Each seeding call takes ~5–20 s (embedding + entity extraction); the whole batch is ~1–3 min. I'll run them sequentially so failures are easy to isolate.

Y

✅ SYSTEM DESIGN COMPLETE — FEAT-JARVIS-002
All 10 artefacts seeded successfully.

Graphiti seeding results
#	Artefact	Episode	Nodes	Edges
1	design.md	full_doc	—	—
2	contracts/API-tools.md	full_doc	—	—
3	contracts/API-internal.md	full_doc	26	52
4	models/DM-tool-types.md	full_doc	6	10
5	models/DM-stub-registry.md	full_doc	15	16
6	DDR-005 (dispatch_by_capability)	adr	10	4
7	DDR-006 (Tavily)	adr	11	5
8	DDR-007 (asteval)	adr	5	5
9	DDR-008 (capabilities delivery)	adr	7	9
10	DDR-009 (stub transport semantics)	adr	21	40
Cosmetic warnings: all 5 DDRs got "Missing required section: Status" because I wrote **Status:** Accepted (bold field) rather than ## Status (heading). Parser still accepted and indexed them. Easy fix for future consistency if needed — the FEAT-JARVIS-001 DDRs may use the same convention.

Files written

docs/design/FEAT-JARVIS-002/
├── design.md
├── contracts/API-tools.md
├── contracts/API-internal.md
├── models/DM-tool-types.md
├── models/DM-stub-registry.md
├── diagrams/fleet-dispatch-l3.md           (reviewed + approved, not seeded)
└── decisions/
    ├── DDR-005-dispatch-by-capability-supersedes-call-specialist.md
    ├── DDR-006-tavily-as-web-search-provider.md
    ├── DDR-007-asteval-for-calculate.md
    ├── DDR-008-capabilities-both-tool-and-prompt-injection.md
    └── DDR-009-dispatch-stub-transport-semantics.md
Next steps (per phase2-build-plan.md)
/system-design FEAT-JARVIS-003 — async subagents (needs reconciliation with ADR-ARCH-011's single-reasoner supersede — flagged in contradiction C2).
/feature-spec FEAT-JARVIS-002 — Gherkin scenarios grounded in this design.
/feature-plan FEAT-JARVIS-002 — task breakdown per phase2-build-plan.md Step 7.
AutoBuild in commit order: config → types → general → capabilities → dispatch → prompt → supervisor factory → supervisor-with-tools test.


/system-design FEAT-JARVIS-003 \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/design/FEAT-JARVIS-002/design.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/prompts/supervisor_prompt.py \
  --context src/jarvis/config/settings.py \
  --context .guardkit/context-manifest.yaml


  Phase 6 — Summary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SYSTEM DESIGN COMPLETE — FEAT-JARVIS-003
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Created under docs/design/FEAT-JARVIS-003/:


FEAT-JARVIS-003/
├── design.md                                        ← main design doc (~31 KB)
├── contracts/
│   ├── API-subagent.md                              ← AsyncSubAgent entry + input schema
│   ├── API-tools.md                                 ← escalate_to_frontier + 5 middleware tools
│   └── API-internal.md                              ← module-level Python API
├── models/
│   └── DM-subagent-types.md                         ← RoleName, AsyncTaskInput, SwapStatus,
│                                                    #   FrontierTarget, FrontierEscalationContext
├── diagrams/
│   └── jarvis-reasoning-l3.md                       ← C4 L3 (review gate PENDING)
└── decisions/
    ├── DDR-010-single-async-subagent-supersedes-four-roster.md     ← Reconciles scope with ADR-ARCH-001/011
    ├── DDR-011-role-enum-closed-v1.md                              ← critic/researcher/planner
    ├── DDR-012-subagent-module-import-compilation.md               ← Fail-fast at startup
    ├── DDR-013-langgraph-json-at-repo-root.md                      ← Matches Forge ADR-ARCH-031
    ├── DDR-014-escalate-to-frontier-in-dispatch-tool-module.md     ← Three-layer belt+braces
    └── DDR-015-llamaswap-adapter-with-stubbed-health.md            ← Retires JA6 cleanly
Next steps:

Approve / revise the C4 L3 diagram above.
Approve / skip Graphiti seeding (commands above).
Proceed to /feature-spec FEAT-JARVIS-003 — Gherkin scenarios grounded in this design.
Then /feature-plan FEAT-JARVIS-003 — task breakdown with adjusted commit order (single subagent + frontier tool).
Then AutoBuild per phase2-build-plan.md Step 8, adjusted to the reframed shape (config → llamaswap adapter → role prompts → jarvis_reasoner graph → subagent_registry → escalate_to_frontier → supervisor prompt update → supervisor factory update → langgraph.json → tests).
The scope doc's C2 contradiction from FEAT-JARVIS-002 is now fully resolved. The thesis — one reasoning model that knows which reasoning model to use — survives at full strength as role-dispatch + constitutional frontier escape.





GUARDKIT_LOG_LEVEL=DEBUG guardkit autobuild feature FEAT-JARVIS-001 --verbose --max-turns 30