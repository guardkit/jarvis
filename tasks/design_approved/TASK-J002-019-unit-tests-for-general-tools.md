---
complexity: 5
created: 2026-04-24 06:55:00+00:00
dependencies:
- TASK-J002-008
- TASK-J002-009
- TASK-J002-010
- TASK-J002-011
estimated_minutes: 90
feature_id: FEAT-J002
id: TASK-J002-019
implementation_mode: task-work
parent_review: TASK-REV-J002
priority: high
scenarios_covered:
- all Group-A/B/C/D general-tool scenarios listed in TASK-J002-008/009/010/011
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-002
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: Unit tests for general tools
updated: 2026-04-24 06:55:00+00:00
wave: 4
---

# Unit tests for general tools

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 4 | **Mode:** task-work | **Complexity:** 5/10 | **Est.:** 90 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

pytest suite exercising every general-tool scenario in the .feature: read_file (9 scenarios), search_web (6), get_calendar_events (2), calculate (4). Uses fake_tavily_response fixture — no real network.

## Acceptance Criteria

- [ ] `tests/test_tools_general.py` exercises every Group-A / Group-B / Group-C / Group-D / Group-E scenario in the `.feature` file that targets a general tool.
- [ ] `read_file`: happy path + 1MB-boundary table + traversal + null-byte + symlink + not-found + not-a-file + too-large + encoding (9 scenarios).
- [ ] `search_web`: happy path + max_results table + missing key + empty query + DEGRADED + hostile-snippet-passthrough (6 scenarios).
- [ ] `get_calendar_events`: stub empty + invalid_window (2 scenarios).
- [ ] `calculate`: happy path + division_by_zero + overflow + unsafe tokens table (4 scenarios).
- [ ] Uses `fake_tavily_response` fixture (monkeypatched Tavily client). No real network.
- [ ] Each @tool's `Every tool converts internal errors into structured strings rather than raising` coverage row is asserted.

## Scenarios Covered

- all Group-A/B/C/D general-tool scenarios listed in TASK-J002-008/009/010/011

## Test Execution Log

_Populated by `/task-work` during implementation._