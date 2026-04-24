# Feature Spec Summary: Async Subagent for Model Routing + Attended Frontier Escape

**Stack**: python
**Generated**: 2026-04-24T00:00:00Z
**Scenarios**: 44 total (11 smoke, 1 regression)
**Assumptions**: 6 total (0 high / 5 medium / 1 low confidence)
**Review required**: Yes

## Scope

Gherkin specification for FEAT-JARVIS-003 — the surface that turns
*"one reasoning model that knows which reasoning model to use"* from aspiration
into observable behaviour. The feature ships:

1. A single `jarvis-reasoner` `AsyncSubAgent` (per
   [DDR-010](../../docs/design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md)
   / [ADR-ARCH-011](../../docs/architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md))
   with a closed-enum `role` kwarg (`critic` / `researcher` / `planner` per
   [DDR-011](../../docs/design/FEAT-JARVIS-003/decisions/DDR-011-role-enum-closed-v1.md)),
   compiled at module import time
   ([DDR-012](../../docs/design/FEAT-JARVIS-003/decisions/DDR-012-subagent-module-import-compilation.md)),
   exposed via repo-root `langgraph.json` with ASGI transport
   ([DDR-013](../../docs/design/FEAT-JARVIS-003/decisions/DDR-013-langgraph-json-at-repo-root.md)).

2. The five `AsyncSubAgentMiddleware` operational tools auto-injected by
   wiring `async_subagents=...` into `create_deep_agent`.

3. An attended-only `escalate_to_frontier` tool in `jarvis.tools.dispatch`
   ([DDR-014](../../docs/design/FEAT-JARVIS-003/decisions/DDR-014-escalate-to-frontier-in-dispatch-tool-module.md))
   with belt+braces gating across three layers — docstring + executor
   assertion (adapter + caller-frame) + ambient-tool-list registration absence.

4. A swap-aware `LlamaSwapAdapter` with stubbed health
   ([DDR-015](../../docs/design/FEAT-JARVIS-003/decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md))
   so the supervisor can honour ADR-ARCH-012's voice-latency policy without
   live llama-swap reads in Phase 2.

Aligned to the authoritative design at
[docs/design/FEAT-JARVIS-003/design.md](../../docs/design/FEAT-JARVIS-003/design.md)
and its contracts/models. The originating `/feature-spec` command named the
retired four-cloud-subagent roster (`deep_reasoner` / `adversarial_critic` /
`long_research` / `quick_local`) and the JA6 cloud-fallback hook; both are
superseded by ADR-ARCH-001 / -011 / -012 / -027 and the spec follows the
reframed design.

## Scenario Counts by Category

| Category                             | Count |
|--------------------------------------|-------|
| Key examples (`@key-example`)        | 10    |
| Boundary conditions (`@boundary`)    | 6     |
| Negative cases (`@negative`)         | 17    |
| Edge cases (`@edge-case`)            | 18    |
| Smoke (`@smoke`)                     | 11    |
| Regression (`@regression`)           | 1     |
| Security expansion (`@security`)     | 3     |
| Concurrency expansion (`@concurrency`)| 1    |
| Integrity expansion (`@integrity`)   | 1     |
| Integration expansion (`@integration`)| 2    |

Some scenarios carry multiple tags (e.g. `@boundary @negative`,
`@edge-case @negative @security`), so category counts overlap intentionally.

## Deferred Items

None — all five proposed groups (A/B/C/D/E) were accepted in full.

## Open Assumptions (low confidence)

- **ASSUM-004** — Empty-string `role` value (`""`) is treated as
  `unknown_role` rather than `missing_field`. `RoleName("")` raises
  `ValueError` at enum lookup which the subagent maps to the `unknown_role`
  path. Inference from Python enum semantics; the design does not
  literally specify which side of the boundary `""` falls on. Verify
  at implementation time and adjust the `unknown_role` example row if
  `missing_field` semantics are preferred for empty strings.

## Medium-confidence Assumptions To Verify At Implementation Time

- **ASSUM-001** — Empty body from the frontier provider maps to
  `DEGRADED: provider_unavailable` (rather than `ERROR: empty_response`).
- **ASSUM-002** — A cancelled async task surfaces as
  `status="cancelled"` via `check_async_task` (the design enumerates
  `complete` / `running` / `error` only).
- **ASSUM-003** — An unknown `task_id` returns a structured no-such-task
  result (e.g. `ERROR: unknown_task_id`) per ADR-ARCH-021 generalisation.
- **ASSUM-005** — Out-of-enum `FrontierTarget` is rejected at the
  `@tool` argument-coercion boundary before any provider is contacted.
- **ASSUM-006** — The attended-only structured error string does not echo
  the instruction body — extending DM-subagent-types §6's log-field
  redaction posture to error returns.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Async Subagent for Model Routing + Attended Frontier Escape" \
      --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md \
      --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature \
      --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml \
      --context docs/design/FEAT-JARVIS-003/design.md \
      --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
      --context docs/research/ideas/phase2-build-plan.md \
      --context .guardkit/context-manifest.yaml
