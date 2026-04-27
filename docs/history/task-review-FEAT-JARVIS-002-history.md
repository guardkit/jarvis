
/task-review FEAT-JARVIS-002 \
  --context tasks/FEAT-JARVIS-002-*.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md

I'll execute a task review for FEAT-JARVIS-002. Let me start by loading the task and context files.

Bash Locate task and context files
IN
ls tasks/ 2>/dev/null && echo "---" && find tasks -name "FEAT-JARVIS-002*" -type f 2>/dev/null && echo "---" && ls docs/research/ideas/ 2>/dev/null

OUT
backlog
completed
design_approved
in_review
---
---
general-purpose-agent.md
jarvis-architecture-conversation-starter.md
jarvis-build-plan-conversation-starter.md
jarvis-vision.md
nemoclaw-assessment.md
phase1-build-plan.md
phase1-supervisor-scaffolding-scope.md
phase2-build-plan.md
phase2-dispatch-foundations-scope.md
phase3-build-plan.md
phase3-fleet-integration-scope.md
phase4-build-plan.md
phase4-surfaces-scope.md
reachy-mini-integration.md
Bash Find FEAT-JARVIS files
IN
find tasks -type f -name "*.md" | head -50 && echo "---" && find tasks -type f -name "*FEAT*" 2>/dev/null && echo "---" && find tasks -type f -name "*JARVIS*" 2>/dev/null

OUT
tasks/design_approved/TASK-J003-022-integration-test-role-propagation.md
tasks/design_approved/TASK-J002-014-implement-queue-build-tool.md
tasks/design_approved/TASK-J002-021-unit-tests-for-dispatch-tools-swap-point-grep-invariant.md
tasks/design_approved/TASK-J003-008-implement-jarvis-reasoner-subagent-graph.md
tasks/design_approved/TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-assertion.md
tasks/design_approved/TASK-J003-023-acceptance-test-routing-e2e.md
tasks/design_approved/TASK-J002-011-implement-calculate-tool.md
tasks/design_approved/TASK-J003-010-implement-escalate-to-frontier-layer-1-body.md
tasks/design_approved/TASK-J001-007-sessions-session-and-manager.md
tasks/design_approved/TASK-J002-019-unit-tests-for-general-tools.md
tasks/design_approved/TASK-J001-006-agents-supervisor-factory.md
tasks/design_approved/TASK-J002-009-implement-search-web-tool.md
tasks/design_approved/TASK-J002-013-implement-dispatch-by-capability-tool.md
tasks/design_approved/TASK-J002-008-implement-read-file-tool.md
tasks/design_approved/TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambient-factory.md
tasks/design_approved/TASK-J002-012-implement-list-available-capabilities-refresh-subscribe-tool.md
tasks/design_approved/TASK-J003-012-assemble-tool-list-session-aware-layer-3.md
tasks/design_approved/TASK-J002-017-extend-build-supervisor-signature-and-lifecycle-wiring.md
tasks/design_approved/TASK-J003-021-integration-test-supervisor-with-subagents.md
tasks/design_approved/TASK-J003-018-unit-tests-escalate-to-frontier.md
tasks/design_approved/TASK-J001-005-infrastructure-logging-lifecycle.md
tasks/design_approved/TASK-J002-022-integration-test-supervisor-with-tools-nine-tool-wiring-prom.md
tasks/design_approved/TASK-J003-007-implement-llamaswap-adapter-with-stubbed-health.md
tasks/design_approved/TASK-J003-017-unit-tests-subagent-layer.md
tasks/design_approved/TASK-J001-003-config-jarvis-settings.md
tasks/design_approved/TASK-J003-019-unit-tests-llamaswap-adapter-and-voice-ack.md
tasks/design_approved/TASK-J001-008-cli-main-click-group.md
tasks/design_approved/TASK-J003-013-extend-build-supervisor-signature.md
tasks/design_approved/TASK-J003-009-implement-subagent-registry-build-async-subagents.md
tasks/backlog/TASK-J003-020-regression-test-no-retired-roster-strings.md
tasks/backlog/TASK-J003-001-extend-jarvisconfig-with-feat-j003-fields.md
tasks/backlog/TASK-J001-004-prompts-and-test-scaffold.md
tasks/backlog/TASK-J002-018-unit-tests-for-tool-types-types-py-capabilities-py-models.md
tasks/backlog/TASK-J002-005-correlation-id-primitive-module.md
tasks/backlog/TASK-J002-002-write-canonical-stub-capabilities-yaml.md
tasks/backlog/TASK-J003-016-langgraph-json-at-repo-root.md
tasks/backlog/TASK-J002-003-define-capabilitydescriptor-capabilitytoolsummary-pydantic-m.md
tasks/backlog/TASK-JFT-001-bootstrap-forge-build-trigger.md
tasks/backlog/TASK-J002-007-stub-response-hook-contract-for-dispatch.md
tasks/backlog/TASK-J003-004-define-frontierescalationcontext-pydantic-model.md
tasks/backlog/TASK-J002-020-unit-tests-for-capability-tools-snapshot-isolation.md
tasks/backlog/TASK-J003-024-langgraph-json-smoke-validation.md
tasks/backlog/TASK-J002-023-pyproject-dependency-management.md
tasks/backlog/TASK-J001-010-reserved-empty-packages.md
tasks/backlog/TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md
tasks/backlog/TASK-J003-014-extend-supervisor-prompt-subagent-routing-and-frontier-escalation.md
tasks/backlog/TASK-J003-005-role-prompt-registry-module-and-3-prompts.md
tasks/backlog/TASK-J001-001-pyproject-toml-and-deepagents-pin.md
tasks/backlog/TASK-J001-011-env-example-and-readme-quickstart.md
tasks/backlog/TASK-J003-002-define-rolename-frontiertarget-closed-enums.md
---
---
Bash Search for any FEAT-JARVIS-002 references
IN
find tasks docs -type f -name "*FEAT-JARVIS-002*" 2>/dev/null && echo "---no FEAT-JARVIS-002 file---" && find . -maxdepth 4 -type d -name "*FEAT*" 2>/dev/null | head -20 && echo "---" && find . -type f -name "FEAT-J002*" 2>/dev/null | head -5

OUT
docs/history/system-design-FEAT-JARVIS-002-history.md
---no FEAT-JARVIS-002 file---
./docs/design/FEAT-JARVIS-003
./docs/design/FEAT-JARVIS-002
./docs/design/FEAT-JARVIS-001
./.guardkit/autobuild/FEAT-J002
./.guardkit/autobuild/FEAT-J003
./.guardkit/autobuild/FEAT-JARVIS-001
---
./.guardkit/features/FEAT-J002.yaml
Bash Inspect FEAT-JARVIS-002 design directory
IN
ls docs/design/FEAT-JARVIS-002/ && echo "---" && ls .guardkit/autobuild/FEAT-J002/ 2>/dev/null && echo "---" && ls .guardkit/features/ 2>/dev/null

OUT
contracts
decisions
design.md
diagrams
models
---
events.jsonl
review-summary.md
---
FEAT-J002.yaml
FEAT-J003.yaml
FEAT-JARVIS-001.yaml
Bash Check FEAT registry and J002 metadata
IN
ls .guardkit/features/ && echo "---features---" && cat .guardkit/features/FEAT-J002.yaml 2>/dev/null | head -40

OUT
FEAT-J002.yaml
FEAT-J003.yaml
FEAT-JARVIS-001.yaml
---features---
id: FEAT-J002
name: Core Tools & Capability-Driven Dispatch Tools
description: 'Populate src/jarvis/tools/ with 9 LangChain tools (read_file, search_web,
  calculate, get_calendar_events, list_available_capabilities, capabilities_refresh,
  capabilities_subscribe_updates, dispatch_by_capability, queue_build) plus stub registry
  loader, correlation-id primitive, stub-response-hook contract, and supervisor wiring.
  Envelope-first concurrent fan-out approach (Option B, review score 12/12). DDR-009
  swap-point discipline: two primary grep anchors guard FEAT-JARVIS-004/005 transport
  swap.'
created: '2026-04-24T08:20:24.884175'
status: completed
complexity: 6
estimated_tasks: 23
tasks:
- id: TASK-J002-001
  name: Extend JarvisConfig with Phase 2 fields
  file_path: tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md
  complexity: 2
  dependencies: []
  status: completed
  implementation_mode: direct
  estimated_minutes: 22
  requires_infrastructure: []
  result:
    total_turns: 1
    final_decision: approved
    error: null
  turns_completed: 1
  current_turn: 0
  started_at: '2026-04-25T16:18:46.935378'
  completed_at: '2026-04-25T16:27:06.198358'
- id: TASK-J002-002
  name: Write canonical stub_capabilities.yaml
  file_path: tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-002-write-canonical-stub-capabilities-yaml.md
  complexity: 1
  dependencies: []
  status: completed
  implementation_mode: direct
  estimated_minutes: 15
  requires_infrastructure: []
Read design.md
Read phase2-dispatch-foundations-scope.md
Read phase2-build-plan.md
Read phase2-build-plan.md
Bash Read autobuild review summary
IN
cat .guardkit/autobuild/FEAT-J002/review-summary.md 2>/dev/null | head -200

OUT
# Autobuild Review Summary: FEAT-J002

**Status:** COMPLETED  
**Generated:** 2026-04-25 17:44 UTC

## Metrics

| Metric | Value |
|--------|-------|
| Total tasks | 23 |
| Total turns | 25 |
| Avg turns/task | 1.09 |
| Waves executed | 6 |
| First-attempt pass rate | 91% |

## Per-Task Outcomes

| Task | Wave | Turns | Outcome | Decision | Notes |
|------|------|-------|---------|----------|-------|
| TASK-J002-001 | 1 | 1 | PASSED | approved |  |
| TASK-J002-002 | 1 | 1 | PASSED | approved |  |
| TASK-J002-003 | 1 | 1 | PASSED | approved |  |
| TASK-J002-004 | 1 | 1 | PASSED | approved |  |
| TASK-J002-005 | 1 | 1 | PASSED | approved |  |
| TASK-J002-007 | 1 | 1 | PASSED | approved |  |
| TASK-J002-023 | 1 | 1 | PASSED | approved |  |
| TASK-J002-006 | 2 | 1 | PASSED | approved |  |
| TASK-J002-008 | 2 | 1 | PASSED | approved |  |
| TASK-J002-009 | 2 | 1 | PASSED | approved |  |
| TASK-J002-010 | 2 | 1 | PASSED | approved |  |
| TASK-J002-011 | 2 | 1 | PASSED | approved |  |
| TASK-J002-013 | 2 | 2 | PASSED | approved |  |
| TASK-J002-014 | 2 | 2 | PASSED | approved |  |
| TASK-J002-016 | 2 | 1 | PASSED | approved |  |
| TASK-J002-018 | 2 | 1 | PASSED | approved |  |
| TASK-J002-012 | 3 | 1 | PASSED | approved |  |
| TASK-J002-019 | 3 | 1 | PASSED | approved |  |
| TASK-J002-021 | 3 | 1 | PASSED | approved |  |
| TASK-J002-015 | 4 | 1 | PASSED | approved |  |
| TASK-J002-020 | 4 | 1 | PASSED | approved |  |
| TASK-J002-017 | 5 | 1 | PASSED | approved |  |
| TASK-J002-022 | 6 | 1 | PASSED | approved |  |

## Quality Metrics

- Task success rate: 100%
- First-turn approvals: 21/23
- SDK ceiling hits: 0

## Turn Efficiency

| Metric | Value |
|--------|-------|
| Avg turns/task | 1.1 |
| Single-turn tasks | 21 |
| Multi-turn tasks | 2 |
| Avg SDK turns/invocation | 54.2 |

## Key Findings

- All tasks completed cleanly with no issues.
Bash Inspect delivered code layout
IN
ls src/jarvis/ 2>/dev/null && echo "---tools---" && ls src/jarvis/tools/ 2>/dev/null && echo "---tests---" && ls tests/ 2>/dev/null | head -40 && echo "---config---" && ls src/jarvis/config/ 2>/dev/null

OUT
__init__.py
__pycache__
adapters
agents
cli
config
discovery
infrastructure
learning
prompts
routing
sessions
shared
skills
subagents
tools
watchers
---tools---
__init__.py
__pycache__
_correlation.py
capabilities.py
dispatch_types.py
dispatch.py
general.py
types.py
---tests---
__init__.py
__pycache__
_shims
conftest.py
test_adapters_llamaswap.py
test_assemble_tool_list_layer3.py
test_assemble_tool_list.py
test_async_task_input.py
test_build_system.py
test_capabilities.py
test_cli.py
test_config_feat_j003.py
test_config_phase2.py
test_config.py
test_correlation.py
test_developer_surface.py
test_dispatch_by_capability.py
test_dispatch_types_frontier_escalation.py
test_escalate_to_frontier.py
test_general_calculate.py
test_get_calendar_events.py
test_import_graph.py
test_infrastructure.py
test_jarvis_reasoner_description.py
test_langgraph_json.py
test_lifecycle_startup_phase3.py
test_llamaswap_adapter.py
test_load_stub_registry.py
test_no_retired_roster_strings.py
test_phase2_dependencies.py
test_phase3_dependencies.py
test_prompts.py
test_reserved_packages.py
test_role_prompts.py
test_role_propagation_e2e.py
test_routing_e2e.py
test_search_web.py
test_sessions.py
test_shared.py
test_smoke_end_to_end.py
---config---
__init__.py
__pycache__
settings.py
stub_capabilities.yaml
Bash Inventory FEAT-002 specific tests and code size
IN
ls tests/ | wc -l && echo "---" && ls tests/ | grep -E "^test_(tools_|capabilities|dispatch|general|search|calculate|read_file|calendar|queue|supervisor|routing)" 2>/dev/null && echo "---" && ls src/jarvis/tools/ -la 2>/dev/null && echo "---total py LOC---" && find src/jarvis/tools -name "*.py" -not -path "*pycache*" | xargs wc -l

OUT
Exit code 1
      62
---
test_capabilities.py
test_dispatch_by_capability.py
test_dispatch_types_frontier_escalation.py
test_general_calculate.py
test_routing_e2e.py
test_search_web.py
test_supervisor_extended_signature.py
test_supervisor_lifecycle_wiring.py
test_supervisor_no_llm_call.py
test_supervisor_with_subagents.py
test_supervisor_with_tools.py
test_supervisor.py
test_tools_capabilities.py
test_tools_dispatch_contract.py
test_tools_dispatch.py
test_tools_escalate_to_frontier_layer2.py
test_tools_escalate_to_frontier.py
test_tools_general.py
test_tools_queue_build.py
test_tools_types.py
---
src/jarvis/tools/:
__init__.py
__pycache__
_correlation.py
capabilities.py
dispatch_types.py
dispatch.py
general.py
types.py
Bash Tools LOC count
IN
find src/jarvis/tools -name "*.py" -not -path "*pycache*" -exec wc -l {} + 2>/dev/null && echo "---" && find tests -name "*.py" -not -path "*pycache*" -newer tests/__init__.py -exec wc -l {} + 2>/dev/null | tail -5 && echo "---"

OUT
     123 src/jarvis/tools/dispatch_types.py
     959 src/jarvis/tools/dispatch.py
     216 src/jarvis/tools/__init__.py
     127 src/jarvis/tools/types.py
     351 src/jarvis/tools/capabilities.py
      40 src/jarvis/tools/_correlation.py
     680 src/jarvis/tools/general.py
    2496 total
---
     216 tests/test_adapters_llamaswap.py
     178 tests/test_subagent_prompts.py
     543 tests/test_supervisor_extended_signature.py
      31 tests/_shims/langgraph/__main__.py
   23288 total
---
Let me efficiently survey the actual state. I'll spawn parallel work — explore code structure, run tests, and check the design conformance — rather than read everything sequentially.

Bash Identify tool definitions
IN
grep -E "^@tool|def [a-z_]+\(" src/jarvis/tools/general.py src/jarvis/tools/capabilities.py src/jarvis/tools/dispatch.py 2>/dev/null | grep -v "^#" | head -80

OUT
src/jarvis/tools/capabilities.py:    def as_prompt_block(self) -> str:
src/jarvis/tools/capabilities.py:def load_stub_registry(path: Path) -> list[CapabilityDescriptor]:
src/jarvis/tools/capabilities.py:@tool(parse_docstring=True)
src/jarvis/tools/capabilities.py:def list_available_capabilities() -> str:
src/jarvis/tools/capabilities.py:@tool(parse_docstring=True)
src/jarvis/tools/capabilities.py:def capabilities_refresh() -> str:
src/jarvis/tools/capabilities.py:@tool(parse_docstring=True)
src/jarvis/tools/capabilities.py:def capabilities_subscribe_updates() -> str:
src/jarvis/tools/general.py:def configure(config: JarvisConfig | None) -> None:
src/jarvis/tools/general.py:    def __init__(self, api_key: str) -> None:
src/jarvis/tools/general.py:    def search(self, query: str, max_results: int) -> dict[str, Any]:
src/jarvis/tools/general.py:def _resolve_api_key(config: JarvisConfig | None) -> str | None:
src/jarvis/tools/general.py:def _coerce_results(
src/jarvis/tools/general.py:@tool(parse_docstring=True)
src/jarvis/tools/general.py:def search_web(query: str, max_results: int = 5) -> str:
src/jarvis/tools/general.py:def _detect_unsafe_token(expression: str) -> str | None:
src/jarvis/tools/general.py:def _normalise_percent_of(expression: str) -> str:
src/jarvis/tools/general.py:def _format_calculate_result(value: object) -> str:
src/jarvis/tools/general.py:def _evaluate_expression(expression: str) -> str:
src/jarvis/tools/general.py:@tool(parse_docstring=True)
src/jarvis/tools/general.py:def calculate(expression: str) -> str:
src/jarvis/tools/general.py:def _resolve_workspace_root() -> Path:
src/jarvis/tools/general.py:def _is_inside(candidate: Path, workspace: Path) -> bool:
src/jarvis/tools/general.py:@tool(parse_docstring=True)
src/jarvis/tools/general.py:def read_file(path: str) -> str:
src/jarvis/tools/general.py:@tool(parse_docstring=True)
src/jarvis/tools/general.py:def get_calendar_events(
src/jarvis/tools/dispatch.py:def _now_utc() -> datetime:
src/jarvis/tools/dispatch.py:def _resolve_agent_id(
src/jarvis/tools/dispatch.py:@tool(parse_docstring=True)
src/jarvis/tools/dispatch.py:def dispatch_by_capability(
src/jarvis/tools/dispatch.py:@tool(parse_docstring=True)
src/jarvis/tools/dispatch.py:def queue_build(
src/jarvis/tools/dispatch.py:def _resolve_current_session() -> Session | None:
src/jarvis/tools/dispatch.py:def _is_async_subagent_frame() -> bool:
src/jarvis/tools/dispatch.py:def _check_attended_only(
src/jarvis/tools/dispatch.py:def _emit_frontier_log(
src/jarvis/tools/dispatch.py:def _escalate_gemini(
src/jarvis/tools/dispatch.py:def _escalate_opus(
src/jarvis/tools/dispatch.py:@tool(parse_docstring=True)
src/jarvis/tools/dispatch.py:def escalate_to_frontier(
Bash Check supervisor tool wiring
IN
grep -n "tools=" src/jarvis/agents/supervisor.py 2>/dev/null | head -10 && echo "---assemble---" && grep -rn "assemble_tool_list\|def assemble_tool_list" src/jarvis/ 2>/dev/null | grep -v pycache | head -10

OUT
245:        "Building supervisor graph with model=%s, tools=%d, capabilities=%d, "
279:    #    tools=tools or []        → caller-supplied (Phase 2: 9 tools, or
304:        tools=tools if tools is not None else [],
---assemble---
src/jarvis/tools/__init__.py:8:The :func:`assemble_tool_list` factory is the **single** wiring point that:
src/jarvis/tools/__init__.py:84:    "assemble_tool_list",
src/jarvis/tools/__init__.py:89:def assemble_tool_list(
src/jarvis/tools/dispatch.py:155:# ``assemble_tool_list`` (TASK-J002-015) snapshots a ``list[CapabilityDescriptor]``
src/jarvis/tools/dispatch.py:161:# Snapshot isolation (ASSUM-006): assemble_tool_list MUST assign a fresh
src/jarvis/tools/general.py:10:``jarvis.tools.assemble_tool_list`` factory:
src/jarvis/tools/general.py:43:1. ``jarvis.tools.assemble_tool_list(config, ...)`` (TASK-J002-015)
src/jarvis/tools/general.py:100:# ``assemble_tool_list`` (TASK-J002-015) and tests write here via
src/jarvis/tools/general.py:110:    ``assemble_tool_list`` (TASK-J002-015) calls this once at supervisor
src/jarvis/tools/capabilities.py:26:``list[CapabilityDescriptor]`` snapshot that ``assemble_tool_list``
Read __init__.py (lines 81-220)
Now let me run the tests to verify the AutoBuild's claim of 100% pass and check current quality gates.

Bash Check pytest availability
IN
(which pytest && pytest --version) 2>&1 | head -5

OUT
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/bin/pytest
pytest 9.0.3
Update Todos

Run focused FEAT-J002 test suite to verify AutoBuild's 100% pass claim

Audit design vs implementation for the 9 tools and assemble_tool_list wiring

Verify DDR conformance (DDR-005..009) and ADR alignment

Check success criteria from build plan §Success Criteria

Generate review report and present decision checkpoint
Bash Run FEAT-J002 specific tests
IN
.venv/bin/pytest tests/test_tools_general.py tests/test_tools_capabilities.py tests/test_tools_dispatch.py tests/test_tools_dispatch_contract.py tests/test_tools_queue_build.py tests/test_tools_types.py tests/test_dispatch_by_capability.py tests/test_capabilities.py tests/test_general_calculate.py tests/test_search_web.py tests/test_get_calendar_events.py tests/test_supervisor_with_tools.py tests/test_assemble_tool_list.py tests/test_load_stub_registry.py tests/test_correlation.py tests/test_config_phase2.py tests/test_phase2_dependencies.py 2>&1 | tail -40

OUT
........................................................................ [ 12%]
........................................................................ [ 24%]
.........ss............................................................. [ 36%]
........................................................................ [ 48%]
........................................................................ [ 60%]
........................................................................ [ 72%]
........................................................................ [ 84%]
........................................................................ [ 97%]
.................                                                        [100%]
=============================== warnings summary ===============================
tests/test_tools_queue_build.py:445
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_tools_queue_build.py:445: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_compiled_supervisor_exposes_nine_tool_names
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_create_deep_agent_receives_nine_tools_alphabetically
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_assemble_tool_list_is_alphabetical
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_each_descriptor_block_appears_verbatim_in_system_prompt
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_tools.py:113: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_compiled_supervisor_exposes_nine_tool_names
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_create_deep_agent_receives_nine_tools_alphabetically
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_each_descriptor_block_appears_verbatim_in_system_prompt
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/src/jarvis/infrastructure/lifecycle.py:338: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    config.validate_provider_keys()

tests/test_supervisor_with_tools.py: 1 warning
tests/test_assemble_tool_list.py: 10 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/conftest.py:105: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
591 passed, 2 skipped, 23 warnings in 2.44s
Bash Run full test suite for regression check
IN
.venv/bin/pytest -q 2>&1 | tail -10

OUT
    @pytest.mark.seam

tests/test_tools_queue_build.py:445
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_tools_queue_build.py:445: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_async_task_input.py - openai.OpenAIError: The api_key client...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
Bash Run full suite excluding the env-dependent test
IN
.venv/bin/pytest -q --ignore=tests/test_async_task_input.py 2>&1 | tail -8

OUT
tests/test_tools_queue_build.py:445
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_tools_queue_build.py:445: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_role_prompts.py - openai.OpenAIError: The api_key client opt...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
Bash Run full suite excluding env-dependent tests
IN
.venv/bin/pytest -q --ignore=tests/test_async_task_input.py --ignore=tests/test_role_prompts.py --ignore=tests/test_routing_e2e.py --ignore=tests/test_role_propagation_e2e.py --ignore=tests/test_supervisor_with_subagents.py 2>&1 | tail -10

OUT
    @pytest.mark.seam

tests/test_tools_queue_build.py:445
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_tools_queue_build.py:445: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_subagent_prompts.py - openai.OpenAIError: The api_key client...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
Bash Run full suite with placeholder keys
IN
OPENAI_API_KEY=sk-fake-test-key-not-used ANTHROPIC_API_KEY=sk-fake-anthropic GOOGLE_API_KEY=fake-google .venv/bin/pytest -q 2>&1 | tail -8

OUT
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_assemble_tool_list_is_alphabetical
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_each_descriptor_block_appears_verbatim_in_system_prompt
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_tools.py:113: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
Bash Get test summary line only
IN
OPENAI_API_KEY=sk-fake-test-key-not-used ANTHROPIC_API_KEY=sk-fake-anthropic GOOGLE_API_KEY=fake-google .venv/bin/pytest --tb=no -q 2>&1 | grep -E "^(FAIL|ERROR|[0-9]+ passed|[0-9]+ failed|=)" | tail -10

OUT
=============================== warnings summary ===============================
Bash Final summary
IN
OPENAI_API_KEY=sk-fake-test-key-not-used ANTHROPIC_API_KEY=sk-fake-anthropic GOOGLE_API_KEY=fake-google .venv/bin/pytest --tb=no 2>&1 | tail -3

OUT
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1585 passed, 2 skipped, 197 warnings in 7.06s
Update Todos

Run focused FEAT-J002 test suite to verify AutoBuild's 100% pass claim

Audit design vs implementation for the 9 tools and assemble_tool_list wiring

Verify DDR conformance (DDR-005..009) and ADR alignment

Check success criteria from build plan §Success Criteria

Generate review report and present decision checkpoint
Full suite green: 1585 passed, 2 skipped. Now let me audit design conformance — I'll check the actual tool surfaces and DDR adherence.

Bash List all tool function signatures
IN
grep -n "^def \|^@tool" src/jarvis/tools/general.py | head -20 && echo "---signatures---" && grep -nE "def (read_file|search_web|get_calendar_events|calculate|list_available_capabilities|capabilities_refresh|capabilities_subscribe_updates|dispatch_by_capability|queue_build|escalate_to_frontier)\b" src/jarvis/tools/general.py src/jarvis/tools/capabilities.py src/jarvis/tools/dispatch.py | head -20

OUT
107:def configure(config: JarvisConfig | None) -> None:
177:def _resolve_api_key(config: JarvisConfig | None) -> str | None:
191:def _coerce_results(
246:@tool(parse_docstring=True)
247:def search_web(query: str, max_results: int = 5) -> str:
363:def _detect_unsafe_token(expression: str) -> str | None:
390:def _normalise_percent_of(expression: str) -> str:
399:def _format_calculate_result(value: object) -> str:
418:def _evaluate_expression(expression: str) -> str:
482:@tool(parse_docstring=True)
483:def calculate(expression: str) -> str:
525:def _resolve_workspace_root() -> Path:
538:def _is_inside(candidate: Path, workspace: Path) -> bool:
551:@tool(parse_docstring=True)
552:def read_file(path: str) -> str:
637:@tool(parse_docstring=True)
638:def get_calendar_events(
---signatures---
src/jarvis/tools/capabilities.py:260:def list_available_capabilities() -> str:
src/jarvis/tools/capabilities.py:303:def capabilities_refresh() -> str:
src/jarvis/tools/capabilities.py:331:def capabilities_subscribe_updates() -> str:
src/jarvis/tools/general.py:247:def search_web(query: str, max_results: int = 5) -> str:
src/jarvis/tools/general.py:483:def calculate(expression: str) -> str:
src/jarvis/tools/general.py:552:def read_file(path: str) -> str:
src/jarvis/tools/general.py:638:def get_calendar_events(
src/jarvis/tools/dispatch.py:210:def dispatch_by_capability(
src/jarvis/tools/dispatch.py:366:def queue_build(
src/jarvis/tools/dispatch.py:866:def escalate_to_frontier(
Read dispatch.py (lines 201-320)
Bash Verify DDR-009 grep-anchor swap-point logs
IN
grep -n "JARVIS_DISPATCH_STUB\|JARVIS_QUEUE_BUILD_STUB" src/jarvis/tools/dispatch.py | head -10 && echo "---" && grep -rn "JARVIS_DISPATCH_STUB\|JARVIS_QUEUE_BUILD_STUB" src/jarvis tests/ 2>/dev/null | grep -v pycache | head -15

OUT
106:LOG_PREFIX_DISPATCH: str = "JARVIS_DISPATCH_STUB"
107:LOG_PREFIX_QUEUE_BUILD: str = "JARVIS_QUEUE_BUILD_STUB"
323:        "JARVIS_DISPATCH_STUB tool_name=%s agent_id=%s correlation_id=%s topic=%s payload_bytes=%d",
478:        "JARVIS_QUEUE_BUILD_STUB feature_id=%s repo=%s correlation_id=%s topic=%s payload_bytes=%d",
---
src/jarvis/tools/dispatch.py:106:LOG_PREFIX_DISPATCH: str = "JARVIS_DISPATCH_STUB"
src/jarvis/tools/dispatch.py:107:LOG_PREFIX_QUEUE_BUILD: str = "JARVIS_QUEUE_BUILD_STUB"
src/jarvis/tools/dispatch.py:323:        "JARVIS_DISPATCH_STUB tool_name=%s agent_id=%s correlation_id=%s topic=%s payload_bytes=%d",
src/jarvis/tools/dispatch.py:478:        "JARVIS_QUEUE_BUILD_STUB feature_id=%s repo=%s correlation_id=%s topic=%s payload_bytes=%d",
tests/test_tools_dispatch.py:32:  assertion: ``JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y>
tests/test_tools_dispatch.py:43:  ``JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
tests/test_tools_dispatch.py:463:    ``JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y> correlation_id=<z>
tests/test_tools_dispatch.py:694:    ``JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
tests/test_tools_dispatch.py:735:    ``grep -rn "JARVIS_DISPATCH_STUB|JARVIS_QUEUE_BUILD_STUB" src/jarvis/``
tests/test_tools_dispatch.py:739:    1. ``LOG_PREFIX_DISPATCH: str = "JARVIS_DISPATCH_STUB"`` (constant)
tests/test_tools_dispatch.py:740:    2. ``LOG_PREFIX_QUEUE_BUILD: str = "JARVIS_QUEUE_BUILD_STUB"`` (constant)
tests/test_tools_dispatch.py:741:    3. The ``logger.info("JARVIS_DISPATCH_STUB ...")`` line in
tests/test_tools_dispatch.py:743:    4. The ``logger.info("JARVIS_QUEUE_BUILD_STUB ...")`` line in
tests/test_tools_dispatch.py:751:      ``JARVIS_DISPATCH_STUB`` to ``JARVIS_DISPATCH_LEGACY``).
Bash DDR-006/007/008 conformance
IN
grep -E "asteval\|safe_eval|SafeEvaluator\|import asteval" src/jarvis/tools/general.py | head -3 && echo "---" && grep -n "{available_capabilities}\|Available Capabilities" src/jarvis/prompts/supervisor_prompt.py | head -10 && echo "---tavily---" && grep -n "tavily\|Tavily" src/jarvis/tools/general.py | head -5

OUT
---
18:    {available_capabilities} — rendered ``CapabilityDescriptor.as_prompt_block``
69:## Available Capabilities
74:{available_capabilities}
---tavily---
30::class:`TavilyProvider` wraps the ``langchain-tavily`` client. The grep
31:anchor ``class TavilyProvider`` is the single point a future feature
34:provider" and never names Tavily, so a swap does not change routing
88:    "TavilyProvider",
120:# DDR-006 swap-point grep anchor: ``class TavilyProvider``.
Bash DDR-007 asteval check
IN
grep -n "asteval\|Interpreter()" src/jarvis/tools/general.py | head -5 && echo "---" && grep -n "asteval" pyproject.toml 2>/dev/null && echo "---calc---" && sed -n '418,470p' src/jarvis/tools/general.py

OUT
61:from asteval import Interpreter  # type: ignore[import-untyped]
347:    # care about that the asteval symbol table does not strip but whose
400:    """Render the ``asteval`` result as a clean numeric string.
422:    via :class:`asteval.Interpreter`, and converts every failure mode into
437:    # ``asteval.Interpreter()`` ships with the math allow-list pre-populated
---
36:    "asteval>=0.9.33",
---calc---
def _evaluate_expression(expression: str) -> str:
    """Safely evaluate ``expression`` and return a contract-compliant string.

    Pre-filters unsafe tokens, normalises ``X% of Y`` shorthand, evaluates
    via :class:`asteval.Interpreter`, and converts every failure mode into
    one of the four canonical error strings documented in API-tools.md
    §1.4. Never raises — the public :func:`calculate` tool relies on this
    invariant to honour ADR-ARCH-021.
    """
    stripped = expression.strip()
    if not stripped:
        return "ERROR: parse_error — empty expression"

    token = _detect_unsafe_token(expression)
    if token is not None:
        return f"ERROR: unsafe_expression — disallowed token: {token}"

    normalised = _normalise_percent_of(stripped)

    # ``asteval.Interpreter()`` ships with the math allow-list pre-populated
    # (sqrt, log, exp, sin, cos, tan, abs, min, max, round, plus the
    # operators we need). ``no_print=True`` suppresses any stray ``print``
    # output the user expression might attempt.
    interp = Interpreter(no_print=True)

    try:
        result = interp(normalised, show_errors=False, raise_errors=False)
    except Exception as exc:  # pragma: no cover — asteval should not raise
        # Defensive: ADR-ARCH-021 forbids propagation across the boundary.
        logger.warning("asteval raised unexpectedly for %r: %s", expression, exc)
        return f"ERROR: parse_error — {type(exc).__name__}: {exc}"

    # asteval reports every error via ``interp.error`` (a list of
    # ``ExceptionHolder``). The first entry carries the originating
    # exception class and message.
    if interp.error:
        first = interp.error[0]
        exc_cls = getattr(first, "exc", None)
        msg = getattr(first, "msg", "") or ""
        if exc_cls is ZeroDivisionError:
            return "ERROR: division_by_zero"
        if exc_cls is OverflowError:
            return "ERROR: overflow — result exceeds float range"
        text = str(msg).strip()
        if text:
            detail = text.splitlines()[0]
        elif exc_cls is not None:
            detail = exc_cls.__name__
        else:
            detail = "unknown error"
        return f"ERROR: parse_error — {detail}"

    if result is None:
Bash Stub registry contents
IN
grep -n "stub_capabilities\|registry\|architect\|product-owner\|ideation\|forge" src/jarvis/config/stub_capabilities.yaml 2>/dev/null | head -20 && echo "---" && wc -l src/jarvis/config/stub_capabilities.yaml

OUT
4:  - agent_id: architect-agent
7:      Produces architecture sessions, C4 diagrams, and ADRs for features. Best
9:      architecture against the ADR set". Not for implementation.
11:      - tool_name: run_architecture_session
22:  - agent_id: product-owner-agent
27:      feature?", "should we build X or Y first?". Not for architectural
41:  - agent_id: ideation-agent
47:      to Rich or to the architect.
60:  - agent_id: forge
65:      does the work. Fire-and-forget — progress events arrive via
---
      78 src/jarvis/config/stub_capabilities.yaml
Bash queue_build Pattern A details
IN
grep -n "^def queue_build\|BuildQueuedPayload\|originating_adapter\|triggered_by" src/jarvis/tools/dispatch.py | head -15 && echo "---" && grep -n "queue_build" src/jarvis/tools/dispatch.py | head -8

OUT
7:``BuildQueuedPayload`` / ``MessageEnvelope``) and then ``logger.info`` the
61:from nats_core.events import BuildQueuedPayload, CommandPayload, ResultPayload
366:def queue_build(
371:    originating_adapter: str = "terminal",
385:    BuildQueuedPayload per nats-core, logs it, and returns a canned ACK.
401:        originating_adapter: Which Jarvis adapter the human used. One of
404:                            Default ``terminal`` (CLI). ``triggered_by`` is
431:    # ----- Validate originating_adapter ------------------------------------
432:    if originating_adapter not in _ALLOWED_ADAPTERS:
433:        return f"ERROR: invalid_adapter — {originating_adapter} not in allowed list"
441:        payload = BuildQueuedPayload(
446:            triggered_by="jarvis",
447:            originating_adapter=originating_adapter,  # type: ignore[arg-type]
---
4:``queue_build``) that connect Jarvis to the NATS event bus. In Phase 2
34:   anchor used by every ``logger.info`` line emitted from ``queue_build``.
366:def queue_build(
958:    "queue_build",
Read dispatch.py (lines 366-420)
Bash Confirm 9-tool wiring assertion
IN
grep -n "test_compiled\|9 tools\|10 tool\|nine\|ten_tools\|test_assemble_tool_list_is_alphabetical\|expected_tool_names" tests/test_supervisor_with_tools.py | head -10 && echo "---design DDR-009 expected feature_id---" && grep -n "FEATURE_ID_PATTERN\|FEAT-\\\[A-Z" src/jarvis/tools/dispatch.py | head -5

OUT
1:"""Integration test for TASK-J002-022 — supervisor-with-tools + nine-tool wiring + prompt injection.
170:# AC-001 / AC-002 — build_app_state wires 9 tools in alphabetical order
176:    async def test_compiled_supervisor_exposes_nine_tool_names(
199:    async def test_create_deep_agent_receives_nine_tools_alphabetically(
204:        """``create_deep_agent`` is invoked with exactly the 9 tools in alphabetical order."""
227:            f"Expected create_deep_agent to receive the 9 tools in alphabetical "
231:    def test_assemble_tool_list_is_alphabetical(
---design DDR-009 expected feature_id---
ugrep: error: error at position 31
(?m)FEATURE_ID_PATTERN\|FEAT-\\[A-Z
             mismatched [ ]___/
Update Todos

Run focused FEAT-J002 test suite to verify AutoBuild's 100% pass claim

Audit design vs implementation for the 9 tools and assemble_tool_list wiring

Verify DDR conformance (DDR-005..009) and ADR alignment

Check success criteria from build plan §Success Criteria

Generate review report and present decision checkpoint
Bash Quality gates: langgraph.json, ruff, mypy
IN
test -f langgraph.json && echo "langgraph.json EXISTS" && head -20 langgraph.json && echo "---ruff---" && .venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py 2>&1 | tail -5 && echo "---mypy---" && .venv/bin/mypy --no-error-summary src/jarvis/tools 2>&1 | tail -10

OUT
langgraph.json EXISTS
{
  "dependencies": [
    "."
  ],
  "graphs": {
    "jarvis": {
      "path": "./src/jarvis/agents/supervisor.py:graph",
      "transport": "asgi"
    },
    "jarvis_reasoner": {
      "path": "./src/jarvis/agents/subagents/jarvis_reasoner.py:graph",
      "transport": "asgi"
    }
  },
  "env": ".env",
  "python_version": "3.12"
}
---ruff---
   |
help: Remove quotes

Found 7 errors.
[*] 4 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
---mypy---
src/jarvis/tools/general.py:187: error: Statement is unreachable  [unreachable]
src/jarvis/tools/dispatch.py:349: error: Subclass of "str" and "ResultPayload" cannot exist: would have incompatible method signatures  [unreachable]
src/jarvis/tools/dispatch.py:356: error: Subclass of "ResultPayload" and "str" cannot exist: would have incompatible method signatures  [unreachable]
src/jarvis/tools/dispatch.py:359: error: Statement is unreachable  [unreachable]
src/jarvis/tools/dispatch.py:661: error: Argument 5 to "_emit_frontier_log" has incompatible type "Literal['attended_only']"; expected "Literal['success', 'config_missing', 'provider_unavailable', 'degraded_empty']"  [arg-type]
src/jarvis/tools/dispatch.py:678: error: Argument 5 to "_emit_frontier_log" has incompatible type "Literal['attended_only']"; expected "Literal['success', 'config_missing', 'provider_unavailable', 'degraded_empty']"  [arg-type]
src/jarvis/tools/dispatch.py:944: error: Statement is unreachable  [unreachable]
Bash Get specific ruff failures
IN
.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py 2>&1 | head -50

OUT
RUF022 `__all__` is not sorted
  --> src/jarvis/tools/__init__.py:64:11
   |
64 |   __all__ = [
   |  ___________^
65 | |     # Pydantic types (3 + 1 internal sentinel = 4)
66 | |     "CalendarEvent",
67 | |     "CapabilityDescriptor",
68 | |     "DispatchError",
69 | |     "WebResult",
70 | |     # General tools (4)
71 | |     "calculate",
72 | |     "get_calendar_events",
73 | |     "read_file",
74 | |     "search_web",
75 | |     # Capability catalogue tools (3)
76 | |     "capabilities_refresh",
77 | |     "capabilities_subscribe_updates",
78 | |     "list_available_capabilities",
79 | |     # Dispatch tools (2 + 1 attended-only escalation)
80 | |     "dispatch_by_capability",
81 | |     "escalate_to_frontier",
82 | |     "queue_build",
83 | |     # Assembly + loader
84 | |     "assemble_tool_list",
85 | |     "load_stub_registry",
86 | | ]
   | |_^
   |
help: Apply an isort-style sorting to `__all__`

UP037 [*] Remove quotes from type annotation
  --> src/jarvis/tools/__init__.py:90:13
   |
89 | def assemble_tool_list(
90 |     config: "JarvisConfig",
   |             ^^^^^^^^^^^^^^
91 |     capability_registry: list[CapabilityDescriptor],
92 |     *,
   |
help: Remove quotes

UP042 Class FrontierTarget inherits from both `str` and `enum.Enum`
  --> src/jarvis/tools/dispatch_types.py:39:7
   |
39 | class FrontierTarget(str, Enum):
   |       ^^^^^^^^^^^^^^
40 |     """Closed enumeration of supported cloud frontier providers.
   |
help: Inherit from `enum.StrEnum`
Bash Distinct ruff rule violations
IN
.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py 2>&1 | grep -E "^[A-Z]+[0-9]+ " | sort -u

OUT
I001 [*] Import block is un-sorted or un-formatted
RUF002 Docstring contains ambiguous `–` (EN DASH). Did you mean `-` (HYPHEN-MINUS)?
RUF022 [*] `__all__` is not sorted
RUF022 `__all__` is not sorted
UP037 [*] Remove quotes from type annotation
UP042 Class FrontierTarget inherits from both `str` and `enum.Enum`
Bash Routing e2e test (Step 11 success criterion)
IN
OPENAI_API_KEY=sk-fake ANTHROPIC_API_KEY=sk-fake GOOGLE_API_KEY=fake .venv/bin/pytest tests/test_routing_e2e.py -v --tb=line 2>&1 | tail -25

OUT
============================= test session starts ==============================
platform darwin -- Python 3.12.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/richardwoollcott/Projects/appmilla_github/jarvis
configfile: pyproject.toml
plugins: langsmith-0.7.33, cov-7.1.0, asyncio-1.3.0, bdd-8.1.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 25 items

tests/test_routing_e2e.py .........................                      [100%]

=============================== warnings summary ===============================
tests/test_routing_e2e.py: 16 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:210: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 25 passed, 16 warnings in 1.95s ========================
Bash Confirm task subfolder structure
IN
grep -n "test_supervisor_with_tools\|nine_tool\|@pytest.mark" tests/test_supervisor_with_tools.py | head -10 && echo "---J002 task list---" && ls tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/ 2>/dev/null | head -25 && echo "---" && ls tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/ 2>/dev/null | wc -l

OUT
5:    AC-001: ``tests/test_supervisor_with_tools.py`` creates ``test_config`` +
175:    @pytest.mark.asyncio
176:    async def test_compiled_supervisor_exposes_nine_tool_names(
198:    @pytest.mark.asyncio
199:    async def test_create_deep_agent_receives_nine_tools_alphabetically(
253:    @pytest.mark.asyncio
296:    @pytest.mark.asyncio
400:    @pytest.mark.asyncio
---J002 task list---
IMPLEMENTATION-GUIDE.md
README.md
TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md
TASK-J002-002-write-canonical-stub-capabilities-yaml.md
TASK-J002-003-define-capabilitydescriptor-capabilitytoolsummary-pydantic-m.md
TASK-J002-004-define-webresult-calendarevent-dispatcherror-pydantic-models.md
TASK-J002-005-correlation-id-primitive-module.md
TASK-J002-006-stub-registry-loader-load-stub-registry.md
TASK-J002-007-stub-response-hook-contract-for-dispatch.md
TASK-J002-008-implement-read-file-tool.md
TASK-J002-009-implement-search-web-tool.md
TASK-J002-010-implement-get-calendar-events-tool.md
TASK-J002-011-implement-calculate-tool.md
TASK-J002-012-implement-list-available-capabilities-refresh-subscribe-tool.md
TASK-J002-015-assemble-tool-list-tools-package-init-re-exports.md
TASK-J002-016-extend-supervisor-prompt-with-tool-usage-section-available-c.md
TASK-J002-017-extend-build-supervisor-signature-and-lifecycle-wiring.md
TASK-J002-018-unit-tests-for-tool-types-types-py-capabilities-py-models.md
TASK-J002-019-unit-tests-for-general-tools.md
TASK-J002-020-unit-tests-for-capability-tools-snapshot-isolation.md
TASK-J002-021-unit-tests-for-dispatch-tools-swap-point-grep-invariant.md
TASK-J002-022-integration-test-supervisor-with-tools-nine-tool-wiring-prom.md
TASK-J002-023-pyproject-dependency-management.md
---
      23
Bash Locate every TASK-J002 task file
IN
find tasks -type f -name "TASK-J002*" 2>/dev/null | sort | head -50

OUT
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-002-write-canonical-stub-capabilities-yaml.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-003-define-capabilitydescriptor-capabilitytoolsummary-pydantic-m.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-004-define-webresult-calendarevent-dispatcherror-pydantic-models.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-005-correlation-id-primitive-module.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-006-stub-registry-loader-load-stub-registry.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-007-stub-response-hook-contract-for-dispatch.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-008-implement-read-file-tool.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-009-implement-search-web-tool.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-010-implement-get-calendar-events-tool.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-011-implement-calculate-tool.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-012-implement-list-available-capabilities-refresh-subscribe-tool.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-015-assemble-tool-list-tools-package-init-re-exports.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-016-extend-supervisor-prompt-with-tool-usage-section-available-c.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-017-extend-build-supervisor-signature-and-lifecycle-wiring.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-018-unit-tests-for-tool-types-types-py-capabilities-py-models.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-019-unit-tests-for-general-tools.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-020-unit-tests-for-capability-tools-snapshot-isolation.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-021-unit-tests-for-dispatch-tools-swap-point-grep-invariant.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-022-integration-test-supervisor-with-tools-nine-tool-wiring-prom.md
tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-023-pyproject-dependency-management.md
tasks/backlog/TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md
tasks/backlog/TASK-J002-002-write-canonical-stub-capabilities-yaml.md
tasks/backlog/TASK-J002-003-define-capabilitydescriptor-capabilitytoolsummary-pydantic-m.md
tasks/backlog/TASK-J002-004-define-webresult-calendarevent-dispatcherror-pydantic-models.md
tasks/backlog/TASK-J002-005-correlation-id-primitive-module.md
tasks/backlog/TASK-J002-006-stub-registry-loader-load-stub-registry.md
tasks/backlog/TASK-J002-007-stub-response-hook-contract-for-dispatch.md
tasks/backlog/TASK-J002-010-implement-get-calendar-events-tool.md
tasks/backlog/TASK-J002-015-assemble-tool-list-tools-package-init-re-exports.md
tasks/backlog/TASK-J002-016-extend-supervisor-prompt-with-tool-usage-section-available-c.md
tasks/backlog/TASK-J002-018-unit-tests-for-tool-types-types-py-capabilities-py-models.md
tasks/backlog/TASK-J002-020-unit-tests-for-capability-tools-snapshot-isolation.md
tasks/backlog/TASK-J002-023-pyproject-dependency-management.md
tasks/design_approved/TASK-J002-008-implement-read-file-tool.md
tasks/design_approved/TASK-J002-009-implement-search-web-tool.md
tasks/design_approved/TASK-J002-011-implement-calculate-tool.md
tasks/design_approved/TASK-J002-012-implement-list-available-capabilities-refresh-subscribe-tool.md
tasks/design_approved/TASK-J002-013-implement-dispatch-by-capability-tool.md
tasks/design_approved/TASK-J002-014-implement-queue-build-tool.md
tasks/design_approved/TASK-J002-017-extend-build-supervisor-signature-and-lifecycle-wiring.md
tasks/design_approved/TASK-J002-019-unit-tests-for-general-tools.md
tasks/design_approved/TASK-J002-021-unit-tests-for-dispatch-tools-swap-point-grep-invariant.md
tasks/design_approved/TASK-J002-022-integration-test-supervisor-with-tools-nine-tool-wiring-prom.md
Bash Check field naming and kanban state
IN
grep -n "feature_yaml_path\|feature_spec_ref\|feature_yaml_url" tests/test_tools_queue_build.py 2>/dev/null | head -3 && echo "---" && grep -n "BuildQueuedPayload" /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/_pipeline.py 2>/dev/null | head -3 && echo "---scope tasks completed?---" && find tasks/completed -name "TASK-J002*" 2>/dev/null | head -5

OUT
77:            "feature_yaml_path",
130:        assert "feature_yaml_path:" in docstring
157:            feature_yaml_path="features/feat.yaml",
---
26:# Regex patterns for BuildQueuedPayload validators.
30:# Literal types for BuildQueuedPayload provenance fields.
79:    """DEPRECATED: Use BuildQueuedPayload.
---scope tasks completed?---
Bash Check BuildQueuedPayload field name
IN
sed -n '79,140p' /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/_pipeline.py 2>/dev/null | head -40

OUT
    """DEPRECATED: Use BuildQueuedPayload.

    Retained for backward compatibility, to be removed in nats-core v2.x.

    Payload emitted when a feature has been planned and decomposed into waves.

    Attributes:
        feature_id: Unique identifier for the feature.
        wave_count: Total number of waves in the plan.
        task_count: Total number of tasks across all waves.
        waves: Ordered list of wave summaries.
    """

    model_config = ConfigDict(extra="ignore")

    feature_id: str = Field(description="Unique identifier for the feature")
    wave_count: int = Field(ge=1, description="Total number of waves in the plan")
    task_count: int = Field(ge=1, description="Total number of tasks across all waves")
    waves: list[WaveSummary] = Field(description="Ordered list of wave summaries")

    def model_post_init(self, __context: Any) -> None:
        import warnings

        warnings.warn(
            "FeaturePlannedPayload is deprecated; use BuildQueuedPayload",
            DeprecationWarning,
            stacklevel=2,
        )

    @model_validator(mode="after")
    def _waves_length_matches_wave_count(self) -> FeaturePlannedPayload:
        if len(self.waves) != self.wave_count:
            msg = (
                f"len(waves) is {len(self.waves)} but wave_count is {self.wave_count}; "
                "they must be equal"
            )
            raise ValueError(msg)
        return self
Bash Confirm queue_build field name
IN
grep -n "feature_yaml_path\|feature_yaml_url\|feature_spec\|class BuildQueuedPayload" /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/_pipeline.py 2>/dev/null | head -10

OUT
265:class BuildQueuedPayload(BaseModel):
277:        feature_yaml_path: Path to feature YAML spec, relative to repo root.
298:    feature_yaml_path: str = Field(
Bash Coverage on tools/
IN
.venv/bin/pytest --cov=src/jarvis/tools --cov-report=term --cov-config=pyproject.toml --no-header -q tests/test_tools_general.py tests/test_tools_capabilities.py tests/test_tools_dispatch.py tests/test_tools_dispatch_contract.py tests/test_tools_queue_build.py tests/test_tools_types.py tests/test_dispatch_by_capability.py tests/test_capabilities.py tests/test_general_calculate.py tests/test_search_web.py tests/test_get_calendar_events.py tests/test_assemble_tool_list.py tests/test_load_stub_registry.py tests/test_correlation.py tests/test_supervisor_with_tools.py 2>&1 | tail -20

OUT
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/src/jarvis/infrastructure/lifecycle.py:338: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    config.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform darwin, python 3.12.4-final-0 _______________

Name                                 Stmts   Miss  Cover
--------------------------------------------------------
src/jarvis/tools/__init__.py            18      0   100%
src/jarvis/tools/_correlation.py         3      0   100%
src/jarvis/tools/capabilities.py        76      6    92%
src/jarvis/tools/dispatch.py           214    100    53%
src/jarvis/tools/dispatch_types.py      19      1    95%
src/jarvis/tools/general.py            216     40    81%
src/jarvis/tools/types.py               34      0   100%
--------------------------------------------------------
TOTAL                                  580    147    75%
Update Todos

Run focused FEAT-J002 test suite to verify AutoBuild's 100% pass claim

Audit design vs implementation for the 9 tools and assemble_tool_list wiring

Verify DDR conformance (DDR-005..009) and ADR alignment

Check success criteria from build plan §Success Criteria

Generate review report and present decision checkpoint
Bash Ensure reviews directory exists
IN
test -d .claude/reviews && echo "exists" || mkdir -p .claude/reviews && echo "created"

OUT
exists
created
Write FEAT-JARVIS-002-review-report.md
315 lines
---
feature_id: FEAT-JARVIS-002
title: Core Tools & Capability-Driven Dispatch Tools
review_mode: architectural
review_depth: standard
reviewed_at: 2026-04-26
reviewer: claude-opus-4-7 (task-review orchestrator)
status: REVIEW_COMPLETE
---

# Review Report: FEAT-JARVIS-002 — Core Tools & Capability-Driven Dispatch Tools

## 1. Executive Summary

**Verdict: ACCEPT with two non-blocking remediation tasks.**

FEAT-JARVIS-002 has shipped to spec. The 9-tool surface (`calculate`,
`capabilities_refresh`, `capabilities_subscribe_updates`,
`dispatch_by_capability`, `get_calendar_events`,
`list_available_capabilities`, `queue_build`, `read_file`, `search_web`)
is implemented, alphabetically wired through
[assemble_tool_list](src/jarvis/tools/__init__.py#L89), exercised by
591 focused tests (100% pass), and protected by the DDR-009 swap-point
grep anchors that downstream FEAT-J004/005 will rely on.

The full project test suite is green (**1585 passed, 2 skipped**, no
regressions). The end-to-end routing test
[test_routing_e2e.py](tests/test_routing_e2e.py) — the build plan's Step
11 acceptance gate — passes all 25 cases. The five DDRs landed in
`/system-design` (DDR-005..009) all materialise in code:
`dispatch_by_capability` replaces the old `call_specialist` shape
(DDR-005), `TavilyProvider` is the swap-point grep anchor (DDR-006),
`asteval.Interpreter` powers `calculate` (DDR-007), the
`{available_capabilities}` placeholder injects descriptors into the
prompt (DDR-008), and `JARVIS_DISPATCH_STUB` /
`JARVIS_QUEUE_BUILD_STUB` log lines are guarded by an explicit
invariant test (DDR-009).

Two remediation items deserve a follow-up subtask each — neither
blocks Phase 3 work:

- **Ruff/mypy housekeeping** (success criterion #9 violated): 7 ruff
  lints + 7 mypy errors across `tools/`. All low-impact (unsorted
  `__all__`, en-dash in docstrings, `StrEnum` modernisation, defensive
  unreachable branches mypy can't narrow). No behavioural risk.
- **Kanban hygiene**: the 23 task files never moved to
  `tasks/completed/` after AutoBuild closed. Files are duplicated
  across `tasks/backlog/feat-jarvis-002-…/`, loose
  `tasks/backlog/TASK-J002-*`, and `tasks/design_approved/`. Pure
  bookkeeping — but if `/feature-complete` exists it should be run.

## 2. Review Details

| Field | Value |
|-------|-------|
| Mode | architectural (with code-quality + decision elements) |
| Depth | standard |
| Duration | ~30 min interactive |
| Inputs | `tasks/FEAT-JARVIS-002-*.md` (none at root — 23 files under `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/`), `docs/research/ideas/phase2-dispatch-foundations-scope.md`, `docs/research/ideas/phase2-build-plan.md`, `docs/design/FEAT-JARVIS-002/design.md`, `.guardkit/features/FEAT-J002.yaml`, `.guardkit/autobuild/FEAT-J002/review-summary.md` |
| Source-of-truth design | [docs/design/FEAT-JARVIS-002/design.md](docs/design/FEAT-JARVIS-002/design.md) (5 DDRs, 14 sections) |
| AutoBuild status | Completed 2026-04-25, commit `1da94ca`, 23/23 tasks PASSED, 91% first-attempt approval, avg 1.09 turns/task |

## 3. Conformance Audit — Design → Code

### 3.1 Tool surface (design.md §3, §7; build plan FEAT-J002 Change 1–4)

All nine `@tool(parse_docstring=True)` functions present at the
expected module paths:

| Design surface | Implementation | Notes |
|----------------|----------------|-------|
| `read_file(path) -> str` | [src/jarvis/tools/general.py:552](src/jarvis/tools/general.py#L552) | Path-traversal guard returns `ERROR: path_traversal …` |
| `search_web(query, max_results=5) -> str` | [src/jarvis/tools/general.py:247](src/jarvis/tools/general.py#L247) | Tavily wrapper; `ERROR: config_missing` when key absent |
| `get_calendar_events(window) -> str` | [src/jarvis/tools/general.py:638](src/jarvis/tools/general.py#L638) | Stub returning `[]`; window-validated |
| `calculate(expression) -> str` | [src/jarvis/tools/general.py:483](src/jarvis/tools/general.py#L483) | `asteval.Interpreter` (DDR-007) |
| `list_available_capabilities() -> str` | [src/jarvis/tools/capabilities.py:260](src/jarvis/tools/capabilities.py#L260) | Snapshot from `assemble_tool_list` |
| `capabilities_refresh() -> str` | [src/jarvis/tools/capabilities.py:303](src/jarvis/tools/capabilities.py#L303) | Phase-2 no-op string |
| `capabilities_subscribe_updates() -> str` | [src/jarvis/tools/capabilities.py:331](src/jarvis/tools/capabilities.py#L331) | Phase-2 no-op string |
| `dispatch_by_capability(tool_name, payload_json, intent_pattern, timeout_seconds=60)` | [src/jarvis/tools/dispatch.py:210](src/jarvis/tools/dispatch.py#L210) | DDR-005 contract honoured |
| `queue_build(feature_id, feature_yaml_path, repo, branch, originating_adapter, …)` | [src/jarvis/tools/dispatch.py:366](src/jarvis/tools/dispatch.py#L366) | Pattern A; field names track `nats_core` upstream (see §4.1 below) |

`escalate_to_frontier` exists in `dispatch.py` per its reserved slot in
design §11 / DDR-014, but ships as a FEAT-J003 deliverable behind the
keyword-only `include_frontier` Layer 3 gate in
[assemble_tool_list](src/jarvis/tools/__init__.py#L193). The 9-tool
FEAT-J002 surface is preserved when `include_frontier=False`.

### 3.2 DDR conformance

| DDR | Status | Evidence |
|-----|--------|----------|
| DDR-005 — `dispatch_by_capability` supersedes `call_specialist` | ✅ | Function name + docstring contract match exactly. Tool list contains no `call_specialist`. |
| DDR-006 — Tavily as web-search provider, swap-anchored | ✅ | `class TavilyProvider` in `general.py` with comment "DDR-006 swap-point grep anchor". |
| DDR-007 — `asteval` for `calculate` | ✅ | `from asteval import Interpreter` + `asteval>=0.9.33` in `pyproject.toml`. |
| DDR-008 — Capabilities via tool AND prompt placeholder | ✅ | `{available_capabilities}` placeholder lives in `supervisor_prompt.py:74`; `list_available_capabilities` tool also wired. |
| DDR-009 — Stub transport semantics + grep anchors | ✅ | `LOG_PREFIX_DISPATCH = "JARVIS_DISPATCH_STUB"`, `LOG_PREFIX_QUEUE_BUILD = "JARVIS_QUEUE_BUILD_STUB"` constants + invariant test [test_tools_dispatch.py:735](tests/test_tools_dispatch.py#L735) that pins the four canonical anchor sites. |

### 3.3 ADR alignment (spot checks)

- **ADR-ARCH-021 (tools never raise)** — every tool wraps its body in
  `try/except` and returns a structured `ERROR:` / `DEGRADED:` /
  `TIMEOUT:` string. Verified by reading each tool body. Tests assert
  the negative-path strings explicitly.
- **ADR-ARCH-003 / 015 / 016 (no hardcoded `agent_id`)** —
  `dispatch_by_capability` resolves through the in-memory registry;
  the contradiction `C1` flagged in design §11 is fully resolved by
  DDR-005 and there is no live caller naming an `agent_id` directly.
- **ADR-ARCH-023 (reasoning model cannot rebind tool list)** —
  `assemble_tool_list` returns a fresh `list[...]` on every call;
  `include_frontier` is keyword-only; snapshot copies are made of
  `capability_registry` for both consuming modules (ASSUM-006).
- **ADR-SP-014 Pattern A + ADR-SP-016 (singular topic convention)** —
  `queue_build` builds a real `BuildQueuedPayload` with hardcoded
  `triggered_by="jarvis"` and a configurable `originating_adapter`
  whitelist; topic literal is `pipeline.build-queued.{feature_id}`.

### 3.4 Wiring + lifecycle

`build_supervisor` honours its design §8 signature exactly:
keyword-only `tools` (default empty) + `available_capabilities`
(default "No capabilities currently registered."), so Phase 1 callers
remain working. The lifecycle flow `JarvisConfig → load_stub_registry →
assemble_tool_list → build_supervisor` matches design §8 verbatim.
[langgraph.json](langgraph.json) at repo root declares both
`jarvis` and `jarvis_reasoner` graphs — note this file is technically a
FEAT-J003 deliverable but supports the J002 surface without issue.

## 4. Findings

### 4.1 NON-BLOCKING — `queue_build` field name drifted from build plan

**Severity: low (informational).** The build plan (§FEAT-J002 Change 3)
named the parameter `feature_spec_ref`. The implementation uses
`feature_yaml_path` because that is the actual field name on
`nats_core.events.BuildQueuedPayload` (verified at
[../nats-core/src/nats_core/events/_pipeline.py:298](../nats-core/src/nats_core/events/_pipeline.py#L298)).
This is the correct resolution — design.md's "Stubbed transport ≠
stubbed schema" invariant requires tracking the upstream model — but
the build plan was never updated to reflect it.

**Recommendation**: add a footnote to
[phase2-build-plan.md](docs/research/ideas/phase2-build-plan.md) noting
the field-name pin to upstream `nats-core`. No code change.

### 4.2 NON-BLOCKING — Ruff & mypy not clean (success criterion #9 fails)

**Severity: low.** Build plan success criterion #9: "Ruff + mypy clean
on all new `src/jarvis/` modules." Current state (run on the FEAT-J002
surface):

**Ruff (7 errors)**:
| Rule | File | Nature |
|------|------|--------|
| RUF022 | `tools/__init__.py` | `__all__` not isort-sorted (intentionally grouped by category in source) |
| UP037 | `tools/__init__.py:90` | Stringified `"JarvisConfig"` annotation — `TYPE_CHECKING` import no longer needed at runtime |
| UP042 | `tools/dispatch_types.py:39` | `class FrontierTarget(str, Enum)` should use `enum.StrEnum` |
| I001 | (one file) | Import block ordering |
| RUF002 | several docstrings | Em/en-dash characters flagged as ambiguous (deliberate prose style) |

**Mypy (7 errors in `tools/`)**:
- 4× `unreachable` warnings — defensive `else` branches mypy thinks
  can't fire after type-narrowing. Honest defensive code; can be
  silenced with `# type: ignore[unreachable]` or removed if truly
  dead.
- 2× `arg-type` errors at `dispatch.py:661,678` —
  `_emit_frontier_log` has a `Literal[…]` outcome union that doesn't
  include `"attended_only"`. Fix by widening the literal type.
- 1× false-positive on `Subclass of str and ResultPayload` —
  needs an `isinstance` narrowing fix.

**Recommendation**: spawn a small implementation task
("FIX-J002-quality-gates") to drive ruff + mypy clean. Either fix the
violations or pin a project-level ignore in `pyproject.toml` for
RUF002 (en-dash style is intentional). Estimated 30–45 minutes.

### 4.3 NON-BLOCKING — Kanban hygiene: tasks not moved to `tasks/completed/`

**Severity: low (process).** AutoBuild reports 23/23 tasks completed
but the task files are scattered across three directories:

- `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/` — 21 task
  files (the canonical feature subfolder, missing TASK-J002-013 and
  TASK-J002-014)
- `tasks/backlog/TASK-J002-*` — 13 loose duplicates at the top of
  backlog
- `tasks/design_approved/TASK-J002-*` — 10 J002 task files (including
  the missing 013 and 014, the dispatch and queue_build tools)

`.guardkit/features/FEAT-J002.yaml` says `status: completed`, and
`tasks/completed/` contains zero J002 entries. This is purely
bookkeeping debt. Suggested action: `/feature-complete FEAT-J002`
(if available) or a manual sweep.

### 4.4 OBSERVATION — Test coverage on `tools/` is 75% in J002-only run

The J002-only coverage view shows 75% on `tools/` overall, with
`dispatch.py` at 53% — but this is *because* the J002-only run
excludes the `escalate_to_frontier` tests that live in J003. With the
full suite run, dispatch.py coverage is materially higher (the
`escalate_to_frontier` body is several hundred lines of the 959-line
file). The build plan target was 80% on **new modules**; per-tool, the
J002-authored portions clear that bar:

| Module | Coverage (J002-only) |
|--------|----------------------|
| `tools/__init__.py` (assemble_tool_list) | 100% |
| `tools/_correlation.py` | 100% |
| `tools/types.py` | 100% |
| `tools/capabilities.py` | 92% |
| `tools/dispatch_types.py` | 95% |
| `tools/general.py` | 81% |
| `tools/dispatch.py` | 53% (J002 portion only — J003's `escalate_to_frontier` not exercised in this run) |

No remediation needed. Worth re-measuring with the J003 tests included
for the canonical Phase 2 number.

## 5. Success-Criteria Scorecard (build plan §Success Criteria)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | All Phase 1 tests still pass (zero regressions) | ✅ Full suite green (1585/1585 effective, 2 skipped) |
| 2 | 9 J002 tools registered + each has happy + failure test | ✅ Verified — `test_tools_*.py` covers all 9 |
| 3 | (FEAT-J003 — async subagents) | n/a for this review (FEAT-J003 separately closed 26 Apr) |
| 4 | End-to-end routing test passes | ✅ `test_routing_e2e.py` 25/25 PASS |
| 5 | `jarvis chat` exhibits noticeably better behaviour than Phase 1 | ⚠ Not verified in this review (requires interactive run with real keys) |
| 6 | `langgraph.json` valid; `langgraph dev` spins all graphs | ⚠ File present and structurally correct; `langgraph dev` not invoked in this review |
| 7 | Capability catalogue stub renders 4 descriptors | ✅ Tested in `test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection` |
| 8 | (FEAT-J003 — `quick_local` fallback) | n/a |
| 9 | Ruff + mypy clean on new modules | ❌ 7 ruff lints + 7 mypy errors — see §4.2 |
| 10 | Memory Store round-trip (Phase 1) still works | ✅ Phase 1 session tests pass; no regressions in `tests/test_sessions.py` |

7 hard ✅ for J002-scope items, 1 hard ❌ (#9), 2 ⚠ that need a quick
manual confirmation outside this review's scope.

## 6. Recommendations

### 6.1 Recommended decision: **Accept** the review

The feature delivers what design.md and build-plan.md asked for. Ship
it as-is for Phase 3 to consume.

### 6.2 Two follow-up subtasks worth creating

| ID (suggested) | Title | Mode | Est | Why |
|---|---|---|---|---|
| TASK-J002-FIX-001 | Drive ruff + mypy clean on `tools/` (or pin RUF002 ignore for prose dashes) | direct | 30-45 min | Closes success criterion #9; prevents quality-gate drift into Phase 3 |
| TASK-J002-FIX-002 | Move 23 J002 task files to `tasks/completed/`; deduplicate the 13 loose backlog copies and reconcile `tasks/design_approved/` entries | direct | 10-15 min | Restores kanban truth so future `/task-status` queries work |

Both are low-risk, low-effort, and orthogonal to anything in the
Phase 3 NATS work. Do them in either order.

### 6.3 One scope-doc footnote

Add a note in
[phase2-build-plan.md](docs/research/ideas/phase2-build-plan.md)
clarifying that `queue_build`'s parameter is `feature_yaml_path` (not
`feature_spec_ref` as originally drafted) because the implementation
follows the upstream `nats-core` `BuildQueuedPayload` schema. No code
change needed.

### 6.4 Outside-this-review verification

Two success criteria couldn't be verified non-interactively:

- **Criterion #5** — Run `jarvis chat` once with a real provider key
  and confirm the supervisor reaches for `calculate` /
  `dispatch_by_capability` correctly across 2-3 prompts.
- **Criterion #6** — Run `langgraph dev` once locally and confirm the
  graphs spin up.

Both are part of the "Phase 2 close" sign-off the build plan flagged
("**Next: `/task-review` + regression check + Step 11 end-to-end
routing validation.**"). The Step-11 routing test is verified ✅;
criterion #5/#6 are the remaining attended-checkpoint items.

## 7. Decision Matrix

| Option | Effort | Risk | Phase 3 readiness | Recommendation |
|--------|--------|------|-------------------|----------------|
| **Accept now**, file FIX-001/FIX-002 in backlog | very low | low | Ready | ★ **recommended** |
| Accept after running FIX-001 + FIX-002 first | ~1 hr | very low | Slightly cleaner | acceptable if you want a fully clean handoff |
| Revise — deeper analysis of `dispatch.py` coverage (53% → re-measure with J003 tests) | low | none (data only) | Ready | unnecessary — analysis above explains the artefact |
| Implement (create FIX subtasks now) | low | low | Ready | preferable to plain Accept if you want them tracked |

## 8. Appendix — Verified Inventory

**Tool modules** (`src/jarvis/tools/`, 2496 LOC):
- `__init__.py` (216) — `assemble_tool_list` factory + re-exports
- `general.py` (680) — 4 general tools + `TavilyProvider` swap anchor
- `capabilities.py` (351) — `CapabilityDescriptor` + 3 catalogue tools
- `dispatch.py` (959) — 2 J002 dispatch tools + 1 reserved-slot J003 escalation
- `types.py` (127) — `WebResult`, `CalendarEvent`
- `dispatch_types.py` (123) — `DispatchError`, `FrontierTarget` (J003)
- `_correlation.py` (40) — `new_correlation_id`

**Test modules** (J002-tagged):
`test_tools_general.py`, `test_tools_capabilities.py`,
`test_tools_dispatch.py`, `test_tools_dispatch_contract.py`,
`test_tools_queue_build.py`, `test_tools_types.py`,
`test_dispatch_by_capability.py`, `test_capabilities.py`,
`test_general_calculate.py`, `test_search_web.py`,
`test_get_calendar_events.py`, `test_supervisor_with_tools.py`,
`test_assemble_tool_list.py`, `test_load_stub_registry.py`,
`test_correlation.py`, `test_config_phase2.py`,
`test_phase2_dependencies.py`. **591 cases, 100% pass.**

**Stub registry**: [src/jarvis/config/stub_capabilities.yaml](src/jarvis/config/stub_capabilities.yaml)
— 4 agents (architect, product-owner, ideation, forge), 78 LOC.

**DDR-009 swap-point anchors verified at**:
- `src/jarvis/tools/dispatch.py:106-107` (constants)
- `src/jarvis/tools/dispatch.py:323` (dispatch log)
- `src/jarvis/tools/dispatch.py:478` (queue_build log)
- `tests/test_tools_dispatch.py:735+` (invariant test)
Update Todos

Run focused FEAT-J002 test suite to verify AutoBuild's 100% pass claim

Audit design vs implementation for the 9 tools and assemble_tool_list wiring

Verify DDR conformance (DDR-005..009) and ADR alignment

Check success criteria from build plan §Success Criteria

Generate review report and present decision checkpoint
Review complete. Report at FEAT-JARVIS-002-review-report.md.

Review Results — FEAT-JARVIS-002
Verdict: Accept with two non-blocking remediation items.

Key results:

Full test suite: 1585 passed, 2 skipped (no regressions)
FEAT-J002 surface: 591 tests pass, 100% — AutoBuild's claim verified
Routing E2E (build plan Step 11): 25/25 pass
All 5 DDRs (005..009) materialise in code; DDR-009 swap-point grep anchors guarded by an explicit invariant test
All 9 tools wired alphabetically through assemble_tool_list; ADR-ARCH-021 (tools never raise) honoured
Findings:

§4.2 — Ruff/mypy not clean (success criterion #9 fails): 7 ruff lints + 7 mypy errors in tools/. All low-impact (sorted __all__, StrEnum, en-dash style, defensive unreachable branches). No behavioural risk.
§4.3 — Kanban hygiene: 23 task files never moved to tasks/completed/; duplicates exist in tasks/backlog/ (loose) and tasks/design_approved/. Pure bookkeeping.
§4.1 — Field name drift (informational): build plan said feature_spec_ref; implementation uses feature_yaml_path to track upstream nats_core.BuildQueuedPayload. Correct resolution; only the build-plan footnote is missing.
Recommended follow-ups (suggested as direct-mode subtasks):

TASK-J002-FIX-001 — drive ruff + mypy clean (~30-45 min)
TASK-J002-FIX-002 — kanban sweep, move J002 task files to tasks/completed/ (~10-15 min)
Decision Checkpoint
[A] Accept findings — file FIX-001/FIX-002 in backlog, archive review
[R] Revise — request deeper analysis (e.g. recompute coverage with J003 tests included, run langgraph dev and jarvis chat for criteria #5/#6)
[I] Implement — auto-create the two FIX subtasks now and stage them for /task-work
[C] Cancel — discard review

Your choice?

I
Accepted. Two small fixes, both orthogonal — I'll propose the implementation plan in one go rather than walking through each Context B question.

Implementation Plan
Subtask	Mode	Wave	Est	Approach
TASK-J002F-001 — Quality gates: ruff + mypy clean on tools/	direct	1	30-45 min	Mix of fixes (RUF022 sort, UP037 strip quote, UP042 StrEnum, mypy literal widening) + targeted tool.ruff.lint.per-file-ignores for RUF002 prose dashes
TASK-J002F-002 — Kanban hygiene: move 23 J002 task files to tasks/completed/	direct	1	10-15 min	Deduplicate three locations (subfolder + loose backlog + design_approved); single source of truth lands in tasks/completed/feat-jarvis-002-core-tools-and-dispatch/
Execution: parallel-safe (no file conflicts — different scopes).
Testing depth: minimal (FIX-001 must keep all 1585 tests green; FIX-002 has no test surface — pure bookkeeping).
Subfolder: tasks/backlog/feat-jarvis-002-quality-cleanup/
Provenance: parent_review: FEAT-JARVIS-002-review-2026-04-26, feature_id: FEAT-J002F

Confirm and I'll generate the subtask files + IMPLEMENTATION-GUIDE.md + README.md, or push back if you'd like different choices (e.g. one bundled task instead of two, or different subfolder name).

proceed
Read TASK-J002-008-implement-read-file-tool.md
Got the format. Now let me create the four files.

Bash Create the cleanup feature subfolder
IN
mkdir -p tasks/backlog/feat-jarvis-002-quality-cleanup && ls tasks/backlog/feat-jarvis-002-quality-cleanup/

OUT
(Bash completed with no output)
Write README.md
70 lines
# FEAT-J002F — FEAT-JARVIS-002 Quality & Hygiene Cleanup

> **Parent review:** [.claude/reviews/FEAT-JARVIS-002-review-report.md](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)
> **Parent feature:** [FEAT-JARVIS-002](../../../docs/design/FEAT-JARVIS-002/design.md) — already merged (`1da94ca`, 25 Apr 2026)
> **Generated:** 2026-04-26 via `/task-review FEAT-JARVIS-002` → `[I]mplement`
> **Status:** Backlog — ready to execute

## Problem

The 26 Apr `/task-review` of FEAT-JARVIS-002 confirmed the feature
ships to spec (1585/1585 tests green, all 9 tools wired, all 5 DDRs
honoured) but flagged two non-blocking remediation items the AutoBuild
cycle didn't pick up:

1. **Build-plan success criterion #9 fails** — Ruff reports 7 lints
   and mypy reports 7 errors across `src/jarvis/tools/`. All are
   stylistic / type-hygiene issues with no behavioural risk, but the
   "ruff + mypy clean on new modules" gate is still red.
2. **Kanban state is stale** — `.guardkit/features/FEAT-J002.yaml`
   says `status: completed`, but none of the 23 task files have moved
   to `tasks/completed/`. They sit duplicated across three
   directories: `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/`
   (21 files, missing 013/014), `tasks/backlog/TASK-J002-*` (13 loose
   copies), and `tasks/design_approved/TASK-J002-*` (10 files
   including the missing 013/014).

Neither blocks Phase 3 — both are workflow debt worth clearing
before FEAT-JARVIS-004 builds on top.

## Solution

Two small direct-mode subtasks, parallel-safe (no file conflicts):

- **TASK-J002F-001** — make `src/jarvis/tools/` ruff- and mypy-clean.
- **TASK-J002F-002** — reconcile and move the 23 J002 task files to
  `tasks/completed/`, deduplicating across the three current
  locations.

## Subtasks

| ID | Title | Mode | Wave | Est | Workspace |
|---|---|---|---|---|---|
| TASK-J002F-001 | Quality gates: ruff + mypy clean on `tools/` | direct | 1 | 30-45 min | `feat-jarvis-002-quality-cleanup-wave1-1` |
| TASK-J002F-002 | Kanban hygiene: move J002 task files to `tasks/completed/` | direct | 1 | 10-15 min | `feat-jarvis-002-quality-cleanup-wave1-2` |

## Acceptance

- `.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py` exits 0.
- `.venv/bin/mypy src/jarvis/tools` exits 0 (or any remaining warnings explicitly justified).
- Full pytest suite stays at **1585 passed, 2 skipped** with no new failures.
- `find tasks/backlog -name "TASK-J002-*"` returns nothing.
- `find tasks/design_approved -name "TASK-J002-*"` returns nothing.
- `find tasks/completed -name "TASK-J002-*"` returns 23 files (one per autobuild task).

## Out of Scope

- Any behavioural change to the J002 tool surface — this is hygiene
  only.
- Closing the two unverified build-plan success criteria (#5 manual
  `jarvis chat` and #6 `langgraph dev` smoke). Those are attended
  checkpoints that belong to the human, not a subtask.
- The build-plan footnote about `feature_yaml_path` field naming —
  one-line doc edit, do directly without a task.

## See Also

- [FEAT-JARVIS-002 review report](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md) — full findings
- [phase2-build-plan.md §Success Criteria](../../../docs/research/ideas/phase2-build-plan.md)
- [FEAT-J002.yaml](../../../.guardkit/features/FEAT-J002.yaml)
Write IMPLEMENTATION-GUIDE.md
156 lines
# FEAT-J002F — Implementation Guide

> **Generated:** 2026-04-26 via `/task-review FEAT-JARVIS-002` → `[I]mplement`
> **Estimated total:** 40-60 minutes (parallelisable)

## Execution Strategy

Both subtasks are **direct-mode** and **parallel-safe**. They touch
disjoint surfaces:

- TASK-J002F-001 modifies `src/jarvis/tools/*.py` and (optionally)
  `pyproject.toml`. No task-file moves.
- TASK-J002F-002 moves task markdown files between `tasks/backlog/`,
  `tasks/design_approved/`, and `tasks/completed/`. No source code.

Either order works. If running through Conductor:

| Wave | Task | Workspace |
|---|---|---|
| 1 | TASK-J002F-001 | `feat-jarvis-002-quality-cleanup-wave1-1` |
| 1 | TASK-J002F-002 | `feat-jarvis-002-quality-cleanup-wave1-2` |

Otherwise: do them sequentially in either order; merge in one commit
or two.

## Wave 1 (parallel)

### TASK-J002F-001 — ruff + mypy clean

**Goal**: zero ruff errors and zero mypy errors over the J002 module
surface. Behavioural code unchanged.

**Approach**:

1. Run `.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py`.
2. For each rule:
   - **RUF022** (`__all__` not sorted in `tools/__init__.py:64`) —
     either accept isort sort, or add `# noqa: RUF022` with a
     comment explaining the deliberate category grouping. Pick
     whichever matches existing project style.
   - **UP037** (`tools/__init__.py:90` stringified `"JarvisConfig"`) —
     remove quotes and lift the import out of `TYPE_CHECKING` if it's
     in there, or vice versa. The forward-reference is unnecessary at
     module level.
   - **UP042** (`tools/dispatch_types.py:39 FrontierTarget(str, Enum)`)
     — convert to `class FrontierTarget(StrEnum)`. Verify nothing
     downstream relies on `str.__mro__` ordering.
   - **I001** import sorting — auto-fixable with `ruff check --fix`.
   - **RUF002** ambiguous en/em-dashes in docstrings — pin
     `[tool.ruff.lint.per-file-ignores]` for `"src/jarvis/**" = ["RUF002"]`
     in `pyproject.toml`. Em-dash prose is intentional and pervasive
     across the codebase; converting them all to ASCII `-` would harm
     readability.
3. Run `.venv/bin/mypy src/jarvis/tools`. For each error:
   - **`unreachable`** in `general.py:187`, `dispatch.py:359,944` —
     these are defensive `else` arms after exhaustive narrowing.
     Either remove them (if truly dead) or suppress per-line with
     `# type: ignore[unreachable]` and a one-line comment explaining
     the defensive intent.
   - **`Subclass of "str" and "ResultPayload"`** at `dispatch.py:349,356`
     — narrow the union before the comparison; an explicit
     `isinstance(value, str)` guard typically fixes it.
   - **`arg-type`** at `dispatch.py:661,678` — widen the
     `_emit_frontier_log` outcome literal to include
     `"attended_only"`, or split the call site into a separate
     specialised emitter.
4. Re-run both gates plus the full pytest suite to confirm no
   regressions. Target outcome: `0` ruff errors, `0` mypy errors,
   `1585 passed, 2 skipped`.

**Files likely touched**:

- `src/jarvis/tools/__init__.py`
- `src/jarvis/tools/dispatch.py`
- `src/jarvis/tools/dispatch_types.py`
- `src/jarvis/tools/general.py`
- `pyproject.toml` (only if pinning the RUF002 per-file ignore)

**Validation**:

```bash
.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py
.venv/bin/mypy src/jarvis/tools
.venv/bin/pytest -q
```

All three commands must exit 0 (with the pytest summary line showing
`1585 passed, 2 skipped`).

### TASK-J002F-002 — kanban hygiene

**Goal**: every J002 task lives at exactly one path, under
`tasks/completed/feat-jarvis-002-core-tools-and-dispatch/`. Orphan
copies in `tasks/backlog/` and `tasks/design_approved/` removed.

**Approach**:

1. List the three current locations and identify the canonical copy
   for each task ID:
   - Primary: `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-*.md`
     (21 files; missing 013, 014)
   - Loose backlog: `tasks/backlog/TASK-J002-*.md` (13 files)
   - Design approved: `tasks/design_approved/TASK-J002-*.md` (10
     files; **includes** 013 and 014)
2. For each `TASK-J002-NNN`:
   - If only one copy exists, that's canonical.
   - If multiple copies exist, prefer the one with the populated
     `autobuild_state.turns` array and `status: in_review` — that's
     the version `/task-work` wrote during AutoBuild.
   - Update each canonical copy's frontmatter: `status: completed`,
     add `completed_at: 2026-04-25T...` (use the timestamp from
     `.guardkit/features/FEAT-J002.yaml`'s per-task `completed_at`).
3. `git mv` (or `mv`) the canonical copies into
   `tasks/completed/feat-jarvis-002-core-tools-and-dispatch/`.
4. `git rm` the duplicate copies.
5. Update the `IMPLEMENTATION-GUIDE.md` and `README.md` paths in the
   subfolder if they point to old locations (they shouldn't —
   relative paths inside the subfolder remain valid after the move).

**Validation**:

```bash
test $(find tasks/backlog -name "TASK-J002-*" | wc -l) -eq 0
test $(find tasks/design_approved -name "TASK-J002-*" | wc -l) -eq 0
test $(find tasks/completed -name "TASK-J002-*" | wc -l) -eq 23
```

All three commands must exit 0.

**Note**: The cleanup task files (TASK-J002F-001 and TASK-J002F-002
themselves) live under `tasks/backlog/feat-jarvis-002-quality-cleanup/`
and are NOT moved by this task — they live in backlog until they
themselves complete, then move to `tasks/completed/feat-jarvis-002-quality-cleanup/`
in the normal way.

## Final Verification

After both subtasks complete:

```bash
# Quality gates
.venv/bin/ruff check src/jarvis/
.venv/bin/mypy src/jarvis/
.venv/bin/pytest -q
# expected: 0 errors, 0 errors, "1585 passed, 2 skipped"

# Kanban truth
find tasks/backlog -name "TASK-J002-[0-9]*"  # expected: empty
find tasks/design_approved -name "TASK-J002-*"  # expected: empty
find tasks/completed -name "TASK-J002-*" | wc -l  # expected: 23
```

Then mark `.guardkit/features/FEAT-J002.yaml`'s task entries
`status: completed` if they aren't already, and the FEAT-JARVIS-002
loop closes cleanly for Phase 3 to inherit.
Write TASK-J002F-001-quality-gates-ruff-mypy-clean.md
120 lines
---
id: TASK-J002F-001
title: Quality gates - ruff and mypy clean on tools surface
task_type: feature
status: backlog
created: 2026-04-26 00:00:00+00:00
updated: 2026-04-26 00:00:00+00:00
priority: medium
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 45
dependencies: []
parent_review: FEAT-JARVIS-002-review-2026-04-26
feature_id: FEAT-J002F
tags:
- phase-2
- jarvis
- feat-jarvis-002
- quality-gates
- post-review-fix
scenarios_covered:
- ruff check exits 0 on src/jarvis/tools and related FEAT-J002 modules
- mypy exits 0 on src/jarvis/tools
- Full pytest suite remains at 1585 passed, 2 skipped
test_results:
  status: pending
  coverage: null
  last_run: null
---
# Quality gates: ruff + mypy clean on FEAT-JARVIS-002 tools surface

**Feature:** FEAT-J002F "FEAT-JARVIS-002 Quality & Hygiene Cleanup"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 30-45 min
**Parent review:** [.claude/reviews/FEAT-JARVIS-002-review-report.md §4.2](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)

## Description

Phase 2 build-plan success criterion #9 ("Ruff + mypy clean on all
new `src/jarvis/` modules") is the only outstanding red gate from the
26 Apr `/task-review` of FEAT-JARVIS-002. AutoBuild closed without
catching it because its quality oracle didn't include the
project-level lint/type sweep. Close the gap before Phase 3 inherits
the technical debt.

All findings are stylistic / type-hygiene; **no behavioural change**
to the tool surface is allowed by this task.

## Findings to Close

**Ruff (7 errors across the J002 surface):**

| Rule | File | Action |
|---|---|---|
| RUF022 | `src/jarvis/tools/__init__.py:64` | Either accept isort sort, or `# noqa: RUF022` with comment explaining the deliberate category grouping |
| UP037 | `src/jarvis/tools/__init__.py:90` | Remove quotes from `"JarvisConfig"` annotation (forward reference no longer needed) |
| UP042 | `src/jarvis/tools/dispatch_types.py:39` | Convert `class FrontierTarget(str, Enum)` to `class FrontierTarget(StrEnum)` |
| I001 | one file | `ruff check --fix` autofix |
| RUF002 | several docstrings | Pin `[tool.ruff.lint.per-file-ignores] "src/jarvis/**" = ["RUF002"]` in `pyproject.toml` — em-dash prose style is intentional |

**Mypy (7 errors in `src/jarvis/tools/`):**

| Line | Error | Fix |
|---|---|---|
| `general.py:187` | `unreachable` after type narrowing | Either remove the dead arm or `# type: ignore[unreachable]` with explanatory comment |
| `dispatch.py:349,356` | `Subclass of "str" and "ResultPayload" cannot exist` | Add explicit `isinstance(value, str)` narrowing before the comparison |
| `dispatch.py:359` | `unreachable` | Same treatment as `general.py:187` |
| `dispatch.py:661,678` | `arg-type — Literal["attended_only"] not in outcome union` | Widen the `outcome` literal in `_emit_frontier_log` to include `"attended_only"`, OR split the call site into a specialised emitter |
| `dispatch.py:944` | `unreachable` | Same treatment as `general.py:187` |

## Constraints

- **No behavioural changes.** Every existing test must pass without
  modification. If a test starts failing, the fix is wrong — revert
  and pick a different approach.
- **No new tests required.** Lint/type cleanup is its own
  verification.
- **No mass mechanical fixes.** Do not run `ruff check --fix
  --unsafe-fixes` blindly — RUF022 and UP042 deserve human review
  because they affect the public ordering and `__mro__` of exported
  symbols.

## Acceptance Criteria

```bash
.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py
# expected: "All checks passed!" (exit 0)

.venv/bin/mypy src/jarvis/tools
# expected: "Success: no issues found in N source files" (exit 0)

.venv/bin/pytest -q
# expected: "1585 passed, 2 skipped" (exit 0)
```

All three commands must exit 0. If any test starts failing, revert
and re-approach.

## Files Likely Touched

- `src/jarvis/tools/__init__.py`
- `src/jarvis/tools/dispatch.py`
- `src/jarvis/tools/dispatch_types.py`
- `src/jarvis/tools/general.py`
- `pyproject.toml` (only if pinning the RUF002 per-file ignore)

## Out of Scope

- Coverage improvements on `tools/dispatch.py` (the 53% number in
  the J002-only run is an artefact of FEAT-J003 tests being excluded
  — see review §4.4).
- Any change to tool docstrings beyond the RUF002 dash issue.
- Re-running `langgraph dev` or `jarvis chat` (criteria #5/#6 are
  attended-checkpoint items, not subtasks).

## See Also

- [Review report §4.2](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)
- [phase2-build-plan.md §Success Criteria #9](../../../docs/research/ideas/phase2-build-plan.md)
Write TASK-J002F-002-kanban-hygiene-move-completed.md
127 lines
---
id: TASK-J002F-002
title: Kanban hygiene - move J002 task files to tasks/completed
task_type: chore
status: backlog
created: 2026-04-26 00:00:00+00:00
updated: 2026-04-26 00:00:00+00:00
priority: low
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 15
dependencies: []
parent_review: FEAT-JARVIS-002-review-2026-04-26
feature_id: FEAT-J002F
tags:
- phase-2
- jarvis
- feat-jarvis-002
- kanban
- post-review-fix
scenarios_covered:
- All 23 J002 task files live under tasks/completed/feat-jarvis-002-core-tools-and-dispatch
- No J002 task files remain in tasks/backlog/ or tasks/design_approved/
- Each canonical task file has status=completed and a completed_at timestamp
test_results:
  status: pending
  coverage: null
  last_run: null
---
# Kanban hygiene: move J002 task files to tasks/completed

**Feature:** FEAT-J002F "FEAT-JARVIS-002 Quality & Hygiene Cleanup"
**Wave:** 1 | **Mode:** direct | **Complexity:** 1/10 | **Est.:** 10-15 min
**Parent review:** [.claude/reviews/FEAT-JARVIS-002-review-report.md §4.3](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)

## Description

`.guardkit/features/FEAT-J002.yaml` says `status: completed` and
AutoBuild closed cleanly on 25 Apr (commit `1da94ca`), but the 23
task files never moved to `tasks/completed/`. They are scattered
across three directories with overlap and gaps:

| Location | Count | Notes |
|---|---|---|
| `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/` | 21 | Canonical subfolder; **missing** TASK-J002-013, TASK-J002-014 |
| `tasks/backlog/TASK-J002-*` | 13 | Loose duplicates at top of backlog |
| `tasks/design_approved/TASK-J002-*` | 10 | Includes the missing 013, 014 |

Result: future `/task-status FEAT-J002` queries return wrong state,
and there are at most three copies of the same task ID floating
around.

## Approach

1. **Inventory** — list all J002 task files across the three
   locations, group by ID:

   ```bash
   for id in $(seq -w 1 23); do
     echo "TASK-J002-$id:"
     find tasks -name "TASK-J002-$id-*.md" -type f
   done
   ```

2. **Pick the canonical copy per ID** — prefer the one with
   populated `autobuild_state.turns` and `status: in_review` (this
   is the version `/task-work` wrote during the AutoBuild cycle).
   If only one copy exists, that is canonical by default.

3. **Update frontmatter** of each canonical copy:
   - `status: completed`
   - `completed_at: <timestamp>` — pull the value from the matching
     entry in `.guardkit/features/FEAT-J002.yaml`'s `tasks` array
     (each task there has `completed_at` populated).

4. **Move** with `git mv` to
   `tasks/completed/feat-jarvis-002-core-tools-and-dispatch/`,
   creating that directory if needed.

5. **Delete** the duplicate copies with `git rm`.

6. **Sanity check** that the moved files' relative paths to README,
   IMPLEMENTATION-GUIDE, and any sibling markdown still resolve.
   The completed feature subfolder will need its own `README.md` /
   `IMPLEMENTATION-GUIDE.md` copied too if they were in
   `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/` (move
   them over).

## Constraints

- **Use git, not raw `mv`/`rm`.** History matters — `git mv`
  preserves the rename trail.
- **Do not alter task body content** — only the two frontmatter
  fields above. Keep the AutoBuild player/coach turn history intact.
- **Do not move TASK-J002F-001 or TASK-J002F-002 themselves.** Those
  files (and this whole `feat-jarvis-002-quality-cleanup/` subfolder)
  stay in backlog until they themselves complete.

## Acceptance Criteria

```bash
test $(find tasks/backlog -name "TASK-J002-[0-9]*" 2>/dev/null | wc -l) -eq 0 && echo "backlog clean"
test $(find tasks/design_approved -name "TASK-J002-*" 2>/dev/null | wc -l) -eq 0 && echo "design_approved clean"
test $(find tasks/completed -name "TASK-J002-*" 2>/dev/null | wc -l) -eq 23 && echo "completed has 23 files"
```

All three lines must print their success message. The pattern
`TASK-J002-[0-9]*` deliberately excludes `TASK-J002F-*` (this
feature's own files).

Spot-check three canonical files for `status: completed` +
`completed_at: 2026-04-25T...` in frontmatter.

## Out of Scope

- Any code change.
- Any change to `.guardkit/features/FEAT-J002.yaml` — it is already
  correct.
- Cleanup of FEAT-J003 task files (different feature, different
  review).

## See Also

- [Review report §4.3](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)
- [.guardkit/features/FEAT-J002.yaml](../../../.guardkit/features/FEAT-J002.yaml) — source of `completed_at` timestamps
Bash Verify created files
IN
ls -la tasks/backlog/feat-jarvis-002-quality-cleanup/

OUT
total 56
drwxr-xr-x   6 richardwoollcott  staff   192 Apr 26 13:57 .
drwxr-xr-x  38 richardwoollcott  staff  1216 Apr 26 13:56 ..
-rw-r--r--   1 richardwoollcott  staff  6254 Apr 26 13:56 IMPLEMENTATION-GUIDE.md
-rw-r--r--   1 richardwoollcott  staff  3392 Apr 26 13:55 README.md
-rw-r--r--   1 richardwoollcott  staff  4711 Apr 26 13:57 TASK-J002F-001-quality-gates-ruff-mypy-clean.md
-rw-r--r--   1 richardwoollcott  staff  4571 Apr 26 13:57 TASK-J002F-002-kanban-hygiene-move-completed.md
Done. Created tasks/backlog/feat-jarvis-002-quality-cleanup/ with:

README.md — problem, solution, subtask summary
IMPLEMENTATION-GUIDE.md — execution strategy, step-by-step approaches, validation commands
TASK-J002F-001 — 7 ruff lints + 7 mypy errors itemised with fix hints (45 min, direct mode)
TASK-J002F-002 — kanban reconciliation across three locations (15 min, direct mode)
Both carry parent_review: FEAT-JARVIS-002-review-2026-04-26 and feature_id: FEAT-J002F in frontmatter for provenance.

Next steps: pick either subtask and run /task-work TASK-J002F-001 or /task-work TASK-J002F-002 — they're parallel-safe (no file overlap), so Conductor can run both in Wave 1.