---
id: TASK-J003-016
title: langgraph.json at repo root — two graphs + ASGI transport
task_type: scaffolding
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 4
implementation_mode: direct
estimated_minutes: 33
dependencies: [TASK-J003-008, TASK-J003-015]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, deployment, ddr-013]
---

# langgraph.json at repo root — two graphs + ASGI transport

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Per DDR-013: `langgraph.json` at repo root; two graphs; ASGI transport. Matches Forge ADR-ARCH-031; no packaging gymnastics.

## Acceptance Criteria

- [ ] `langgraph.json` lives at repo root (NOT under `src/` per DDR-013).
- [ ] File is valid JSON (parses with `json.loads`).
- [ ] Declares a graph named `jarvis` bound to the supervisor module (e.g. `"./src/jarvis/agents/supervisor.py:graph"` or equivalent path the langgraph CLI can resolve).
- [ ] Declares a graph named `jarvis_reasoner` bound to `"./src/jarvis/agents/subagents/jarvis_reasoner.py:graph"`.
- [ ] Both graphs declare ASGI transport (per ADR-ARCH-031 default; co-deployed).
- [ ] Dependencies section lists `.` so the local package is installable.
- [ ] Environment block references `.env` so provider keys load.
- [ ] Scenario anchor: *The repo-root langgraph manifest declares both graphs with ASGI transport*.
- [ ] Lint/format: JSON conventionally formatted (2-space indent); no trailing commas.
