---
id: TASK-J003-024
title: langgraph.json smoke validation
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 5
implementation_mode: direct
estimated_minutes: 22
dependencies: [TASK-J003-016]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, deployment, ddr-013]
---

# langgraph.json smoke validation

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Confirms DDR-013 conformance without spinning a real server: JSON valid, both graphs declared, ASGI transport, `langgraph dev --help` returns 0 under the test harness.

## Acceptance Criteria

- [ ] `tests/test_langgraph_json.py` asserts `langgraph.json` at repo root is valid JSON (parses with `json.loads`).
- [ ] Asserts the parsed object declares both `jarvis` and `jarvis_reasoner` graph names.
- [ ] Asserts both graph entries declare ASGI transport (per DDR-013).
- [ ] Runs `subprocess.run(["python", "-m", "langgraph", "dev", "--help"], ...)` and asserts return code 0 under the test harness — this confirms the langgraph-cli dev dep is importable but does NOT spin a server (no port binding, no graph compilation beyond what `--help` triggers).
- [ ] No live HTTP server spun up; no port bound.
- [ ] `uv run pytest tests/test_langgraph_json.py -v` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
