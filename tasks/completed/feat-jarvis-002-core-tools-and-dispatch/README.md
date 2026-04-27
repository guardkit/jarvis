# FEAT-JARVIS-002 — Core Tools & Capability-Driven Dispatch Tools

**Feature ID:** FEAT-J002
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)
**Spec:** [features/feat-jarvis-002-core-tools-and-dispatch/](../../../features/feat-jarvis-002-core-tools-and-dispatch/)
**Implementation guide:** [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md)

---

## Problem

Phase 1 landed an empty Jarvis supervisor with zero `@tool` bindings. Phase 2
must populate `src/jarvis/tools/` with nine LangChain tools — four general-purpose
tools, three capability-catalogue tools, and two dispatch tools — and wire them
into the DeepAgents supervisor.

The dispatch tools must construct **real** `nats-core` envelope payloads *before*
logging, so the schema is frozen from day one. FEAT-JARVIS-004/005 will later
swap two `logger.info` lines for `nats.request(...)` / `js.publish(...)` without
touching any tool docstring or return shape. That swap-point invariant is
DDR-009 and is the single biggest risk the plan must protect.

## Solution (Option B — Envelope-first, concurrent fan-out)

Five waves, 23 tasks:

1. **Wave 1 — Foundation** (7 tasks, parallel): config fields, stub YAML,
   Pydantic models (`CapabilityDescriptor`, `CapabilityToolSummary`, `WebResult`,
   `CalendarEvent`, `DispatchError`), `new_correlation_id` helper, stub-response-hook
   contract, `pyproject` deps.
2. **Wave 2 — Tools** (9 tasks, parallel): `read_file`, `search_web`, `calculate`,
   `get_calendar_events`, `list_available_capabilities` / `capabilities_refresh` /
   `capabilities_subscribe_updates`, `dispatch_by_capability`, `queue_build`,
   `load_stub_registry`, and the supervisor prompt extension.
3. **Wave 3 — Wiring** (2 tasks): `assemble_tool_list` + package `__init__`;
   `build_supervisor` signature extension + lifecycle wiring.
4. **Wave 4 — Unit tests** (4 tasks, parallel): types, general tools, capability
   tools (+ snapshot-isolation concurrency test), dispatch tools (+ **grep-invariant
   test** that guards DDR-009 swap points).
5. **Wave 5 — Integration** (1 task): supervisor-with-9-tools end-to-end.

## Subtask summary

| ID | Wave | Title | Type | Complexity | Mode | Est. |
|---|---|---|---|---|---|---|
| [TASK-J002-001](./TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md) | 1 | Extend JarvisConfig with Phase 2 fields | declarative | 2 | direct | 30m |
| [TASK-J002-002](./TASK-J002-002-write-canonical-stub-capabilities-yaml.md) | 1 | Write canonical stub_capabilities.yaml | declarative | 1 | direct | 20m |
| [TASK-J002-003](./TASK-J002-003-define-capabilitydescriptor-capabilitytoolsummary-pydantic-m.md) | 1 | Define CapabilityDescriptor + CapabilityToolSummary | declarative | 2 | direct | 40m |
| [TASK-J002-004](./TASK-J002-004-define-webresult-calendarevent-dispatcherror-pydantic-models.md) | 1 | Define WebResult, CalendarEvent, DispatchError | declarative | 2 | direct | 40m |
| [TASK-J002-005](./TASK-J002-005-correlation-id-primitive-module.md) | 1 | Correlation-ID primitive module | feature | 2 | direct | 30m |
| [TASK-J002-007](./TASK-J002-007-stub-response-hook-contract-for-dispatch.md) | 1 | Stub-response-hook contract for dispatch | scaffolding | 2 | direct | 30m |
| [TASK-J002-023](./TASK-J002-023-pyproject-dependency-management.md) | 1 | pyproject + dependency management | scaffolding | 2 | direct | 25m |
| [TASK-J002-006](./TASK-J002-006-stub-registry-loader-load-stub-registry.md) | 2 | Stub registry loader | feature | 3 | direct | 45m |
| [TASK-J002-008](./TASK-J002-008-implement-read-file-tool.md) | 2 | Implement read_file tool | feature | 4 | task-work | 60m |
| [TASK-J002-009](./TASK-J002-009-implement-search-web-tool.md) | 2 | Implement search_web tool | feature | 5 | task-work | 75m |
| [TASK-J002-010](./TASK-J002-010-implement-get-calendar-events-tool.md) | 2 | Implement get_calendar_events tool | feature | 2 | direct | 40m |
| [TASK-J002-011](./TASK-J002-011-implement-calculate-tool.md) | 2 | Implement calculate tool | feature | 4 | task-work | 60m |
| [TASK-J002-012](./TASK-J002-012-implement-list-available-capabilities-refresh-subscribe-tool.md) | 2 | Capability catalogue tools (3) | feature | 3 | task-work | 50m |
| [TASK-J002-013](./TASK-J002-013-implement-dispatch-by-capability-tool.md) | 2 | **dispatch_by_capability ★** | feature | 7 | task-work | 110m |
| [TASK-J002-014](./TASK-J002-014-implement-queue-build-tool.md) | 2 | **queue_build ★** | feature | 6 | task-work | 90m |
| [TASK-J002-016](./TASK-J002-016-extend-supervisor-prompt-with-tool-usage-section-available-c.md) | 2 | Extend supervisor_prompt | feature | 3 | direct | 45m |
| [TASK-J002-015](./TASK-J002-015-assemble-tool-list-tools-package-init-re-exports.md) | 3 | assemble_tool_list + package __init__ | scaffolding | 3 | direct | 40m |
| [TASK-J002-017](./TASK-J002-017-extend-build-supervisor-signature-and-lifecycle-wiring.md) | 3 | build_supervisor + lifecycle wiring | feature | 4 | task-work | 70m |
| [TASK-J002-018](./TASK-J002-018-unit-tests-for-tool-types-types-py-capabilities-py-models.md) | 4 | Unit tests: tool types | testing | 3 | direct | 45m |
| [TASK-J002-019](./TASK-J002-019-unit-tests-for-general-tools.md) | 4 | Unit tests: general tools | testing | 5 | task-work | 90m |
| [TASK-J002-020](./TASK-J002-020-unit-tests-for-capability-tools-snapshot-isolation.md) | 4 | Unit tests: capability tools + snapshot isolation | testing | 4 | direct | 70m |
| [TASK-J002-021](./TASK-J002-021-unit-tests-for-dispatch-tools-swap-point-grep-invariant.md) | 4 | Unit tests: dispatch + grep invariant | testing | 6 | task-work | 110m |
| [TASK-J002-022](./TASK-J002-022-integration-test-supervisor-with-tools-nine-tool-wiring-prom.md) | 5 | Integration test: supervisor-with-9-tools | testing | 5 | task-work | 80m |

★ = PRIMARY DDR-009 swap points. See [IMPLEMENTATION-GUIDE.md §4](./IMPLEMENTATION-GUIDE.md#4-§4-integration-contracts).

## Coverage

All **40 Scenario/Scenario-Outline** blocks in
[feat-jarvis-002-core-tools-and-dispatch.feature](../../../features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature)
map to at least one task's `scenarios_covered:` list.

## Context

- **Review decisions (Context A):** focus=all, depth=standard, tradeoff=**maintainability**, concerns=[swap-point safety, envelope evolution, correlation-id, task ordering]
- **Implementation decisions (Context B):** approach=**B**, execution=**parallel**, testing=**standard**, constraints=none
- **Assumptions confirmed:** ASSUM-001..006 (see [assumptions.yaml](../../../features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_assumptions.yaml))

## Next steps

1. Read [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md)
2. Start Wave 1 (7 parallel tasks, no deps)
3. `/feature-build FEAT-J002` for AutoBuild execution, or run `/task-work TASK-J002-XXX` per task
