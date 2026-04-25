---
id: TASK-J002-010
title: Implement get_calendar_events tool
task_type: feature
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 2
wave: 2
implementation_mode: direct
estimated_minutes: 40
dependencies:
- TASK-J002-004
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Retrieving calendar events in Phase 2 returns an empty list
- Requesting calendar events for an unknown window returns an invalid-window error
- Every tool converts internal errors into structured strings rather than raising
swap_point_note: 'Stub returns empty list; real provider in v1.5. Grep anchor: `Phase
  2 stub` inside get_calendar_events docstring.'
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:51:44.453743'
  last_updated: '2026-04-24T20:58:05.675222'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-24T20:51:44.453743'
    player_summary: "Added get_calendar_events to src/jarvis/tools/general.py as a\
      \ @tool(parse_docstring=True) function with argument annotation Literal[\"today\"\
      , \"tomorrow\", \"this_week\"] = \"today\" and the byte-for-byte docstring from\
      \ API-tools.md \xA71.3. Preserved the pre-existing read_file tool that already\
      \ lived in the module (TASK-J002-008 landed it before this turn). Valid windows\
      \ return json.dumps([]) == \"[]\" \u2014 a JSON array of CalendarEvent-shaped\
      \ dicts (empty but still an array) so the FEAT-JARVIS-007 morning-br"
    player_success: true
    coach_success: true
---
# Implement get_calendar_events tool

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 40 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Phase 2 stub returning an empty CalendarEvent JSON array for any valid window. Return shape matches the real-provider contract so the FEAT-JARVIS-007 morning-briefing skill parses identically against stub and real data.

## Acceptance Criteria

- [ ] `src/jarvis/tools/general.py` exposes `get_calendar_events(window: str = "today") -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring matches API-tools.md §1.3 byte-for-byte; argument type annotation is `Literal["today","tomorrow","this_week"]`.
- [ ] Returns JSON `"[]"` (Phase 2 stub) for any valid `window`.
- [ ] Rejects invalid window with `ERROR: invalid_window — must be one of today/tomorrow/this_week, got <value>` listing the allowed windows.
- [ ] Returned shape is a JSON array of `CalendarEvent`-shaped dicts (even when empty) so FEAT-JARVIS-007's morning-briefing skill parses identically against stub and real data.
- [ ] Never raises.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Retrieving calendar events in Phase 2 returns an empty list
- Requesting calendar events for an unknown window returns an invalid-window error
- Every tool converts internal errors into structured strings rather than raising

## Swap-Point Note

Stub returns empty list; real provider in v1.5. Grep anchor: `Phase 2 stub` inside get_calendar_events docstring.

## Test Execution Log

_Populated by `/task-work` during implementation._
