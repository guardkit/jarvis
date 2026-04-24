---
id: TASK-J002-023
title: "pyproject + dependency management"
task_type: scaffolding
status: backlog
created: 2026-04-24T06:55:00Z
updated: 2026-04-24T06:55:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 25
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags: [phase-2, jarvis, feat-jarvis-002]
scenarios_covered:
  []
test_results:
  status: pending
  coverage: null
  last_run: null
---
# pyproject + dependency management

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 25 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Add Phase-2 runtime dependencies (langchain-tavily, asteval, nats-core, pyyaml). Deliberately DOES NOT add nats-py — Phase 2 scope invariant forbids a live NATS client. Phase 1 dependencies are untouched.

## Acceptance Criteria

- [ ] `pyproject.toml` adds `langchain-tavily` (or the ADR-DDR-006-pinned equivalent), `asteval`, `nats-core` (for Pydantic payload imports), `pyyaml` if not already present.
- [ ] `nats-py` (the NATS client library) is NOT added — Phase 2 scope invariant.
- [ ] `uv lock` is regenerated; `uv sync` completes clean.
- [ ] Phase 1 dependencies are untouched.

## Scenarios Covered

_No direct scenario coverage — supporting task._

## Test Execution Log

_Populated by `/task-work` during implementation._
