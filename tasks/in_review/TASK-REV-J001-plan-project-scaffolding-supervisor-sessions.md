---
id: TASK-REV-J001
title: "Plan: Project Scaffolding, Supervisor Skeleton & Session Lifecycle (FEAT-JARVIS-001)"
status: review_complete
task_type: review
priority: high
feature_id: FEAT-JARVIS-001
tags: [jarvis, phase-1, scaffolding, supervisor, sessions, feat-jarvis-001]
complexity: 7
decision: implement
clarification:
  context_a:
    timestamp: 2026-04-21T00:00:00Z
    decisions:
      focus: all
      depth: standard
      tradeoff: balanced
      extensibility: yes
  context_b:
    timestamp: 2026-04-21T00:00:00Z
    decisions:
      approach: recommended_option_1_per_module_top_down
      execution: auto_detect_parallel_waves
      testing: standard
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Plan: Project Scaffolding, Supervisor Skeleton & Session Lifecycle

Review task created by `/feature-plan` for FEAT-JARVIS-001. The feature has already been fully specified by `/system-arch` (30 ADRs), `/system-design FEAT-JARVIS-001` (design.md + contracts + models + DDRs + C4 L3), and `/feature-spec FEAT-JARVIS-001` (35 BDD scenarios, 6 assumptions all confirmed, `review_required: false`).

## Scope

See [features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md](../../features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md) for the canonical scope statement. This review task decomposes the design + feature-spec into an ordered, complexity-scored task plan for AutoBuild consumption.

## Invariants (from phase1-build-plan.md §Invariants)

- DeepAgents pin: `deepagents>=0.5.3,<0.6` (ADR-ARCH-010)
- Five-group module layout (ADR-ARCH-006): Shell / Domain / Tools / Adapters / Cross-cutting
- Thread-per-session + user-keyed Memory Store (ADR-ARCH-009, DDR-002, DDR-004)
- Supervisor = DeepAgents built-ins only (write_todos, virtual filesystem, task) — no custom tools, no subagents (FEAT-002/003)
- CLI exactly three commands: chat/version/health (DDR-003)
- Local-first inference via llama-swap on `promaxgb10-41b1:9000` (ADR-ARCH-001, user memory)
- No NATS, Telegram, Graphiti, subagents, custom tools, skills, or learning in Phase 1

## Assumption-resolved behaviours (load-bearing)

- ASSUM-001: blank-line chat turn silently skipped (no invoke, no event)
- ASSUM-002: `/exit` matches case-sensitively, whitespace-trimmed
- ASSUM-003: concurrent invoke on same session refused with error (not serialised)
- ASSUM-004: REPL reads next line only after prior reply printed
- ASSUM-005: pydantic.ValidationError at config load → exit code 1
- ASSUM-006: non-CLI adapters raise `JarvisError` from `SessionManager.start_session`
