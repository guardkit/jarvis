# Feature Spec Summary: Project Scaffolding, Supervisor Skeleton & Session Lifecycle

**Feature ID**: FEAT-JARVIS-001
**Stack**: python (Python 3.12 + DeepAgents >=0.5.3,<0.6)
**Generated**: 2026-04-21T14:00:00Z
**Scenarios**: 35 total (6 @smoke, 3 @regression)
**Assumptions**: 6 total (0 high / 4 medium / 2 low confidence — all explicitly confirmed)
**Review required**: No (low-confidence items re-reviewed and signed off by Rich on 2026-04-21)

## Scope

The Phase 1 foundation feature: a runnable Python scaffold (`pyproject.toml` with the `deepagents>=0.5.3,<0.6` pin plus the five-group `src/jarvis/` layer structure), a `build_supervisor(config)` factory that returns a DeepAgents `CompiledStateGraph` with built-ins only, a thread-per-session `SessionManager` with a user-keyed LangGraph Memory Store, and a `jarvis` CLI exposing exactly three commands (`chat`, `version`, `health`). The specification pins the day-1 success criterion — Rich can hold a useful conversation on the CLI, and a fact stated in one session is recalled in a later session for the same user.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 8 |
| Boundary conditions (@boundary) | 7 |
| Negative cases (@negative) | 8 |
| Edge cases (@edge-case) | 12 |
| — of which @security | 3 |
| — of which @concurrency | 2 |
| — of which @integration | 2 |
| Smoke (@smoke) | 6 |
| Regression (@regression) | 3 |

## Deferred Items

None. All four initial groups and all three edge-case-expansion sub-groups were accepted without deferral.

## Open Assumptions (low confidence — confirmed, no longer gating)

Two assumptions were classified as low confidence because their basis was not pinned in any contract. Both have since been explicitly re-reviewed and confirmed by Rich (2026-04-21); no further human gate is required before AutoBuild.

- **ASSUM-002** — `/exit` command matching semantics (case sensitivity + whitespace trimming). *Accepted*: case-sensitive exact match for lowercase "/exit", with leading/trailing whitespace trimmed. If a future adapter needs case-insensitive or i18n variants, revisit here.
- **ASSUM-003** — Concurrent `invoke` on the same session. *Accepted*: refuse the second call with a clear error rather than silently serialise. Documented as a Phase 1 constraint; FEAT-JARVIS-006 Telegram will revisit when real concurrency arrives.

Four further assumptions are medium-confidence (ASSUM-001, 004, 005, 006) and should still be sanity-checked by the Coach before AutoBuild lands the corresponding scenarios, but do not gate the specification.

## Cross-references

- Design: [docs/design/FEAT-JARVIS-001/design.md](../../docs/design/FEAT-JARVIS-001/design.md)
- CLI contract: [docs/design/FEAT-JARVIS-001/contracts/API-cli.md](../../docs/design/FEAT-JARVIS-001/contracts/API-cli.md)
- Internal API contract: [docs/design/FEAT-JARVIS-001/contracts/API-internal.md](../../docs/design/FEAT-JARVIS-001/contracts/API-internal.md)
- Session data model: [docs/design/FEAT-JARVIS-001/models/DM-jarvis-reasoning.md](../../docs/design/FEAT-JARVIS-001/models/DM-jarvis-reasoning.md)
- Config data model: [docs/design/FEAT-JARVIS-001/models/DM-config.md](../../docs/design/FEAT-JARVIS-001/models/DM-config.md)
- Key ADRs: ADR-ARCH-002 (clean/hexagonal in DeepAgents supervisor), ADR-ARCH-006 (five-group module layout), ADR-ARCH-009 (thread-per-session + Memory Store), ADR-ARCH-010 (Python 3.12 + DeepAgents pin), ADR-ARCH-020 (trace-richness by default), ADR-ARCH-021 (tools return structured errors)
- Design DDRs: DDR-001 (in-process only), DDR-002 (Memory Store keyed by user_id), DDR-003 (CLI minimal surface), DDR-004 (session/thread 1:1)

## Integration with /feature-plan

This summary is the primary context for the next step in the build plan:

    /feature-plan "Project Scaffolding, Supervisor Skeleton & Session Lifecycle" \
      --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md \
      --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature \
      --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml \
      --context docs/design/FEAT-JARVIS-001/design.md \
      --context docs/research/ideas/phase1-build-plan.md
