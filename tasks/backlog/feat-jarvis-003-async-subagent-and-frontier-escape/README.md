# FEAT-JARVIS-003 — Async Subagent for Model Routing + Attended Frontier Escape

**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)
**Review report:** [.claude/reviews/TASK-REV-J003-review-report.md](../../../.claude/reviews/TASK-REV-J003-review-report.md)
**Design:** [docs/design/FEAT-JARVIS-003/design.md](../../../docs/design/FEAT-JARVIS-003/design.md)
**Gherkin spec:** [features/feat-jarvis-003-async-subagent-and-frontier-escape/](../../../features/feat-jarvis-003-async-subagent-and-frontier-escape/) (44 scenarios)
**AutoBuild YAML:** [.guardkit/features/FEAT-J003.yaml](../../../.guardkit/features/FEAT-J003.yaml)

**Approach:** Option B (envelope-first, concurrent fan-out) — review score 12/12.
**Execution:** `/feature-build FEAT-J003` — AutoBuild parallel worktrees per FEAT-J002 precedent.

---

## Wave 1 — Envelope (6 tasks, all parallel)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 001 | [Extend JarvisConfig with FEAT-JARVIS-003 fields](TASK-J003-001-extend-jarvisconfig-with-feat-j003-fields.md) | 2 | direct |
| 002 | [Define RoleName + FrontierTarget closed enums](TASK-J003-002-define-rolename-frontiertarget-closed-enums.md) | 2 | direct |
| 003 | [Define AsyncTaskInput + SwapStatus Pydantic models](TASK-J003-003-define-asynctaskinput-swapstatus-pydantic-models.md) | 2 | direct |
| 004 | [Define FrontierEscalationContext Pydantic model](TASK-J003-004-define-frontierescalationcontext-pydantic-model.md) | 2 | direct |
| 005 | [Role prompt registry module + 3 role prompts](TASK-J003-005-role-prompt-registry-module-and-3-prompts.md) | 3 | direct |
| 006 | [pyproject — provider SDKs + langgraph dev dep](TASK-J003-006-pyproject-provider-sdks-and-langgraph-dep.md) | 2 | direct |

## Wave 2 — Components (5 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 007 | [Implement LlamaSwapAdapter with stubbed health](TASK-J003-007-implement-llamaswap-adapter-with-stubbed-health.md) | 4 | task-work |
| 008 | [Implement jarvis_reasoner subagent graph](TASK-J003-008-implement-jarvis-reasoner-subagent-graph.md) | 6 | task-work (TDD) |
| 009 | [Implement subagent_registry.build_async_subagents](TASK-J003-009-implement-subagent-registry-build-async-subagents.md) | 4 | task-work |
| 010 | [Implement escalate_to_frontier Layer 1](TASK-J003-010-implement-escalate-to-frontier-layer-1-body.md) | 6 | task-work (TDD) |
| 011 | [Implement escalate_to_frontier Layer 2](TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-assertion.md) | 5 | task-work (TDD) |

## Wave 3 — Wiring (4 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 012 | [assemble_tool_list session-aware gating (Layer 3 standalone)](TASK-J003-012-assemble-tool-list-session-aware-layer-3.md) | 4 | task-work |
| 013 | [Extend build_supervisor signature](TASK-J003-013-extend-build-supervisor-signature.md) | 4 | task-work |
| 014 | [Extend supervisor_prompt — Subagent Routing + Frontier Escalation](TASK-J003-014-extend-supervisor-prompt-subagent-routing-and-frontier-escalation.md) | 3 | direct |
| 015 | [Extend lifecycle.startup — async subagents + ambient factory + LlamaSwapAdapter](TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambient-factory.md) | 5 | task-work (TDD) |

## Wave 4 — Deployment + Unit Tests (4 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 016 | [langgraph.json at repo root](TASK-J003-016-langgraph-json-at-repo-root.md) | 3 | direct |
| 017 | [Unit tests — subagent layer](TASK-J003-017-unit-tests-subagent-layer.md) | 5 | task-work |
| 018 | [Unit tests — escalate_to_frontier (three layers)](TASK-J003-018-unit-tests-escalate-to-frontier.md) | 6 | task-work (TDD) |
| 019 | [Unit tests — LlamaSwapAdapter + voice-ack](TASK-J003-019-unit-tests-llamaswap-adapter-and-voice-ack.md) | 5 | task-work |

## Wave 5 — Integration + Regression + Acceptance (5 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 020 | [Regression test — no retired-roster strings](TASK-J003-020-regression-test-no-retired-roster-strings.md) | 3 | direct |
| 021 | [Integration test — supervisor_with_subagents](TASK-J003-021-integration-test-supervisor-with-subagents.md) | 5 | task-work |
| 022 | [Integration test — role propagation](TASK-J003-022-integration-test-role-propagation.md) | 5 | task-work |
| 023 | [Acceptance test — test_routing_e2e (7 prompts)](TASK-J003-023-acceptance-test-routing-e2e.md) | 6 | task-work (TDD) |
| 024 | [langgraph.json smoke validation](TASK-J003-024-langgraph-json-smoke-validation.md) | 2 | direct |

---

## Context-A concern traceability

| Concern | Addressed by |
|---|---|
| Layer 3 standalone task | TASK-J003-012 |
| LlamaSwapAdapter stub shape stable for FEAT-J004 | TASK-J003-007 + TASK-J003-019 (Contract 3 in §4) |
| Zero retired-roster strings | TASK-J003-009 (description invariants) + TASK-J003-020 (regression grep) |
| Role-propagation integration test | TASK-J003-022 |
| Tight granularity vs Coach-Player stall | Max complexity 6; escalate gate split L1/L2/L3; 24 tasks averaging 3.8 complexity |

## Key design references

- **DDR-010** single `jarvis-reasoner` AsyncSubAgent → TASK-J003-008, -009
- **DDR-011** RoleName closed enum → TASK-J003-002, -005, -017
- **DDR-012** module-import compilation → TASK-J003-008
- **DDR-013** langgraph.json at repo root + ASGI → TASK-J003-016, -024
- **DDR-014** escalate_to_frontier three-layer belt+braces → TASK-J003-010, -011, -012, -018
- **DDR-015** LlamaSwapAdapter stubbed health → TASK-J003-007, -019

## Next steps

1. `cd /Users/richardwoollcott/Projects/appmilla_github/jarvis`
2. Review [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) (Mermaid data flow + contract sequence + dependency graph + §4 Integration Contracts)
3. `/feature-build FEAT-J003` — AutoBuild cycle over the 24 subtasks

After AutoBuild lands:
- Phase 2 close regression: `uv run pytest tests/ --cov=src/jarvis`
- Manual acceptance: `jarvis chat` with the three canned role prompts (design §13 item 6)
- `langgraph dev` smoke (real server, not harness)
