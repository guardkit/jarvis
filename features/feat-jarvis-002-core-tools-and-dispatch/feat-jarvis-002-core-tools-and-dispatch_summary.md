# Feature Spec Summary: Core Tools & Capability-Driven Dispatch Tools

**Stack**: python
**Generated**: 2026-04-23T00:00:00Z
**Scenarios**: 42 total (7 smoke, 0 regression)
**Assumptions**: 6 total (1 high / 4 medium / 1 low confidence)
**Review required**: Yes

## Scope

Gherkin specification for FEAT-JARVIS-002 — the nine `@tool` functions the Jarvis
supervisor gains in Phase 2: four general tools (`read_file`, `search_web`,
`get_calendar_events`, `calculate`), three capability-catalogue tools
(`list_available_capabilities`, `capabilities_refresh`,
`capabilities_subscribe_updates`), and two dispatch tools
(`dispatch_by_capability`, `queue_build`). Covers happy-path behaviour, bounded
parameter ranges, structured-error failure modes per ADR-ARCH-021, stubbed-but-
schema-honest NATS payload construction (DDR-009), and security/concurrency
edge cases.

Aligned to the authoritative design at
[docs/design/FEAT-JARVIS-002/design.md](../../docs/design/FEAT-JARVIS-002/design.md)
and its contracts/models. The `dispatch_by_capability` naming supersedes the
original scope-doc `call_specialist` per [DDR-005](../../docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md).

## Scenario Counts by Category

| Category                        | Count |
|---------------------------------|-------|
| Key examples (@key-example)     | 9     |
| Boundary conditions (@boundary) | 8     |
| Negative cases (@negative)      | 17    |
| Edge cases (@edge-case)         | 14    |
| Smoke (@smoke)                  | 7     |

Some scenarios carry multiple tags (e.g. `@boundary @negative`, `@edge-case @negative`),
so category counts overlap intentionally.

## Deferred Items

None — all five proposed groups were accepted.

## Open Assumptions (low confidence)

- **ASSUM-006** — `list_available_capabilities` / `capabilities_refresh` snapshot-isolation
  semantics. Phase 2 refresh is a no-op so the scenario holds trivially; the commitment
  is forward-looking for Phase 3. Revisit when FEAT-JARVIS-004 wires
  `NATSKVManifestRegistry` with real refresh semantics.

## Medium-confidence Assumptions To Verify At Implementation Time

- **ASSUM-001** Correlation-id scheme (UUID4 per dispatch vs alternative).
- **ASSUM-002** Symlink rejection behaviour (depends on DeepAgents built-in filesystem
  implementation choice).
- **ASSUM-003** Null-byte rejection lands under `path_traversal` error category rather
  than a new category.
- **ASSUM-004** `search_web` returning hostile snippet text verbatim without attempting
  sanitisation at the tool layer.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Core Tools & Capability-Driven Dispatch Tools" \
      --context features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_summary.md \
      --context features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature \
      --context features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_assumptions.yaml \
      --context docs/design/FEAT-JARVIS-002/design.md \
      --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
      --context docs/research/ideas/phase2-build-plan.md \
      --context .guardkit/context-manifest.yaml
