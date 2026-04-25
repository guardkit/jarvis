---
id: TASK-J002-016
title: Extend supervisor_prompt with Tool-Usage section + {available_capabilities}
task_type: feature
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 3
wave: 2
implementation_mode: direct
estimated_minutes: 45
dependencies:
- TASK-J002-003
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- The capability catalogue is injected into the supervisor system prompt at session
  start
- Building the supervisor with no registered capabilities renders a safe prompt fallback
consumer_context:
- task: TASK-J002-003
  consumes: CapabilityDescriptor
  framework: LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent
  driver: pydantic v2
  format_note: "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore');\
    \ agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension'];\
    \ as_prompt_block() renders deterministic text (see DM-tool-types.md \xA7'Prompt-block\
    \ shape')."
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:27:08.343076'
  last_updated: '2026-04-25T16:33:04.195896'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:27:08.343076'
    player_summary: "Added a new '## Available Capabilities' section (containing the\
      \ {available_capabilities} placeholder) and a '## Tool Usage' preference-list\
      \ section to SUPERVISOR_SYSTEM_PROMPT, inserted between the Attended-Conversation\
      \ Posture and Trace Richness sections per AC-001. The Tool Usage list mirrors\
      \ design \xA710 verbatim in spirit: prefer calculate over mental arithmetic,\
      \ list_available_capabilities at most once per session, prefer dispatch_by_capability\
      \ over repeating specialist work, queue_build only"
    player_success: true
    coach_success: true
---
# Extend supervisor_prompt with Tool-Usage section + {available_capabilities}

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** direct | **Complexity:** 3/10 | **Est.:** 45 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Add a {available_capabilities} placeholder and a Tool Usage preference list to SUPERVISOR_SYSTEM_PROMPT. Phase 1 content is preserved verbatim (TASK-J001-004 scope invariant). No mention of deprecated tool names.

## Acceptance Criteria

- [ ] `src/jarvis/prompts/supervisor_prompt.py` `SUPERVISOR_SYSTEM_PROMPT` gains a `{available_capabilities}` placeholder inserted after the attended-conversation section and before the Trace Richness section.
- [ ] Gains a `## Tool Usage` section with the preference list from design §10 (prefer calculate over mental arithmetic; list_available_capabilities at most once per session; prefer dispatch_by_capability over repeating specialist work; queue_build only when feature explicitly named; return structured-error strings as-is).
- [ ] Phase 1 content is preserved verbatim (TASK-J001-004 scope invariant): attended-conversation posture, identity, model-selection philosophy unchanged; no mention of `call_specialist`, `start_async_task`, `morning-briefing`, named subagents, or skills.
- [ ] The `{domain_prompt}` placeholder remains at the bottom of the prompt (per existing domain-prompt-injection pattern).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- The capability catalogue is injected into the supervisor system prompt at session start
- Building the supervisor with no registered capabilities renders a safe prompt fallback

## Test Execution Log

_Populated by `/task-work` during implementation._
