---
id: TASK-J002-004
title: "Define WebResult, CalendarEvent, DispatchError Pydantic models"
task_type: declarative
status: backlog
created: 2026-04-24T06:55:00Z
updated: 2026-04-24T06:55:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 40
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags: [phase-2, jarvis, feat-jarvis-002]
scenarios_covered:
  - "Searching the web with a configured provider returns result summaries"
  - "Retrieving calendar events in Phase 2 returns an empty list"
swap_point_note: "n/a — stable schema across phases."
test_results:
  status: pending
  coverage: null
  last_run: null
---
# Define WebResult, CalendarEvent, DispatchError Pydantic models

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 40 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Define the three return-shape and error-envelope Pydantic models the general and dispatch tools use to structure their outputs per ADR-ARCH-021.

## Acceptance Criteria

- [ ] `src/jarvis/tools/types.py` defines `WebResult(BaseModel)` with `title: str (min_length=1)`, `url: str (min_length=1)`, `snippet: str = ""`, `score: float (ge=0, le=1) = 0.0`.
- [ ] Defines `CalendarEvent(BaseModel)` with `id: str`, `title: str`, `start: datetime`, `end: datetime`, `location: str | None`, `description: str | None`, and a `@model_validator(mode="after")` asserting `end >= start`.
- [ ] Defines `DispatchError(BaseModel)` with `category: Literal["unresolved","invalid_payload","invalid_timeout","timeout","specialist_error","transport_stub"]`, `detail: str`, `agent_id: str | None`, `tool_name: str | None`, `correlation_id: str`, and `to_tool_string() -> str` method rendering `"ERROR: <category> — <detail>"` or `"TIMEOUT: ..."` per ADR-ARCH-021 conventions.
- [ ] All three models use `ConfigDict(extra="ignore")`.

## Scenarios Covered

- Searching the web with a configured provider returns result summaries
- Retrieving calendar events in Phase 2 returns an empty list

## Swap-Point Note

n/a — stable schema across phases.

## Test Execution Log

_Populated by `/task-work` during implementation._
