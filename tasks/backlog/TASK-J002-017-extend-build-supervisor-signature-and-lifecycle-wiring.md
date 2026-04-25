---
id: TASK-J002-017
title: "Extend build_supervisor signature and lifecycle wiring"
task_type: feature
status: backlog
created: 2026-04-24T06:55:00Z
updated: 2026-04-24T06:55:00Z
priority: high
complexity: 4
wave: 3
implementation_mode: task-work
estimated_minutes: 70
dependencies: ["TASK-J002-015", "TASK-J002-016"]
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags: [phase-2, jarvis, feat-jarvis-002]
scenarios_covered:
  - "The supervisor is built with all nine Phase 2 tools wired"
  - "The capability catalogue is injected into the supervisor system prompt at session start"
  - "Building the supervisor with no registered capabilities renders a safe prompt fallback"
consumer_context:
  - task: TASK-J002-003
    consumes: "CapabilityDescriptor"
    framework: "LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent"
    driver: "pydantic v2"
    format_note: "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore'); agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension']; as_prompt_block() renders deterministic text (see DM-tool-types.md §'Prompt-block shape')."
  - task: TASK-J002-015
    consumes: "assemble_tool_list"
    framework: "LangChain BaseTool list consumed by create_deep_agent"
    driver: "langchain-core"
    format_note: "assemble_tool_list(config, capability_registry) -> list[BaseTool] returns the 9 tools in stable alphabetical order (calculate, capabilities_refresh, capabilities_subscribe_updates, dispatch_by_capability, get_calendar_events, list_available_capabilities, queue_build, read_file, search_web); closure-binds capability_registry into capability + dispatch tools (snapshot isolation)."
swap_point_note: "`assemble_tool_list` and `load_stub_registry` are the two lifecycle seams rewritten in FEAT-JARVIS-004. Grep anchors: `assemble_tool_list`, `load_stub_registry`."
test_results:
  status: pending
  coverage: null
  last_run: null
---
# Extend build_supervisor signature and lifecycle wiring

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 3 | **Mode:** task-work | **Complexity:** 4/10 | **Est.:** 70 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Extend build_supervisor with keyword-only tools and available_capabilities kwargs (Phase 1 callers unaffected). Wire lifecycle.build_app_state to load the stub registry, assemble the tool list, and pass both into build_supervisor. AppState gains a capability_registry field.

## Acceptance Criteria

- [ ] `jarvis.agents.supervisor.build_supervisor` gains two keyword-only kwargs: `tools: list[BaseTool] | None = None` and `available_capabilities: list[CapabilityDescriptor] | None = None`. Phase 1 callers (no kwargs) still work.
- [ ] When `available_capabilities` is None or empty, `{available_capabilities}` is replaced with the exact string `"No capabilities currently registered."` per `.feature` L305.
- [ ] When non-empty, descriptors are rendered via `CapabilityDescriptor.as_prompt_block()` in deterministic order by `agent_id`, joined with `"\n\n"`.
- [ ] When `tools` is None, passes `tools=[]` to `create_deep_agent` (Phase 1 behaviour preserved).
- [ ] `jarvis.infrastructure.lifecycle.build_app_state` gains steps: `capability_registry = load_stub_registry(config.stub_capabilities_path)`, `tool_list = assemble_tool_list(config, capability_registry)`, then passes both into `build_supervisor(config, tools=tool_list, available_capabilities=capability_registry)`.
- [ ] `AppState` gains `capability_registry: list[CapabilityDescriptor]` field.
- [ ] Startup still completes in under 2 seconds with the 4-entry stub registry (no network).
- [ ] Seam test: calling `build_app_state(test_config)` returns an `AppState` whose `supervisor` has 9 tools wired and `capability_registry` has 4 entries.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- The supervisor is built with all nine Phase 2 tools wired
- The capability catalogue is injected into the supervisor system prompt at session start
- Building the supervisor with no registered capabilities renders a safe prompt fallback

## Swap-Point Note

`assemble_tool_list` and `load_stub_registry` are the two lifecycle seams rewritten in FEAT-JARVIS-004. Grep anchors: `assemble_tool_list`, `load_stub_registry`.

## Test Execution Log

_Populated by `/task-work` during implementation._
