# Review Report: TASK-REV-22CF — Plan: NATS Fleet Registration and Specialist Dispatch

- **Review mode**: decision
- **Depth**: standard
- **Date**: 2026-04-27
- **Feature**: FEAT-JARVIS-004
- **Clarification**: focus=all, tradeoff=balanced, concerns=[ASSUM-009, ASSUM-008, contract-enforcement, test-strategy-gaps]
- **Inputs**: design.md (14 §, 7 DDRs), 3 contract docs, DM-routing-history (20+ field schema), 36 Gherkin scenarios, 12 assumptions, phase3-build-plan.md (commit-order Step 7)

## Executive Summary

The FEAT-JARVIS-004 design is exceptionally well-specified. Seven DDRs, three contract documents, an authoritative routing-history schema (DDR-018), 36 acceptance scenarios with 12 assumptions resolved (10 high / 1 medium / 1 low), and a clear C4 L3 component map. The job of `/feature-plan` is **not** to redesign — it is to slice this corpus into a dependency-aware AutoBuild task graph with all cross-task hand-offs pinned as Integration Contracts.

**Score**: 88/100 (the 12 deductions are actionable in this plan; see "Findings" §3 below — none are blockers).

The recommended implementation strategy is **wave-based parallel fan-out** along the design's existing module boundaries (`infrastructure/nats_client.py`, `fleet_registration.py`, `dispatch_semaphore.py`, `capabilities_registry.py`, `routing_history.py`, then `tools/dispatch.py` swap + `lifecycle.py` wiring). The design's clean ADR-ARCH-006 five-group layout makes Wave 2's five infrastructure modules genuinely parallel-safe (separate files, contracts pinned by API-internal.md). Approach 1 (strict sequential per build-plan §Step 7) is conservative but underuses available parallelism; Approach 3 (vertical slice) is tempting but the dispatch-by-capability transport cannot light up until the registry, semaphore, NATS client, and routing-history schema are all in place — so the natural seam is module-first, not feature-first.

All four user-flagged concerns resolve to concrete recommendations (DDR promotion for ASSUM-008 and ASSUM-009; dedicated contract-test task with grep invariant for envelope source_id and Topics formatter; explicit shutdown-ordering test).

---

## 1. Approaches considered

| # | Approach | Wall-clock | Parallelism | Rework risk | Recommended? |
|---|---|---|---|---|---|
| 1 | **Sequential, build-plan §Step 7 ordering** — 9 tasks, one per Change in build-plan | High (single-thread) | None | Lowest | No — wastes available parallelism |
| 2 | **Wave-based parallel fan-out along module boundaries** | Lowest | High (Waves 1, 2, 4, 5 fan out) | Low — contracts are pinned in API-internal.md | **Yes — Recommended** |
| 3 | **Vertical slice (walking skeleton first)** | Medium | Medium | Higher — requires foundational types to be re-shaped mid-flight when retry-with-redirect or large-trace offload land | No — design is already module-decomposed |

### Approach 1 — Sequential build-plan §Step 7 ordering

Mirrors phase3-build-plan §Step 7 verbatim: config → nats_client → fleet_registration → routing_history → capabilities → dispatch swap → lifecycle → fallback tests → contract tests. Each step waits on the previous. Easiest to debug (one boundary at a time). Wall-clock is roughly the sum of every step's effort. Doesn't honour the design's clean module decomposition.

**When it wins**: when contracts are unstable (they are not — API-internal.md pins them).

### Approach 2 — Wave-based parallel fan-out (Recommended)

Five waves:

- **Wave 1 — Foundations** (5 tasks, parallel-safe): config extensions, pyproject extras, schema-only (Pydantic models), DDR promotions for ASSUM-008/009, schema-conformance test.
- **Wave 2 — Infrastructure modules** (5 tasks, parallel-safe — different files): `nats_client.py`, `fleet_registration.py`, `dispatch_semaphore.py`, `capabilities_registry.py` (Live + Stub + Protocol), `routing_history.py` (writer methods).
- **Wave 3 — Tool surface swap + lifecycle** (3 tasks, mostly sequential — touch shared modules): `tools/dispatch.py`, `tools/capabilities.py`, `infrastructure/lifecycle.py`.
- **Wave 4 — Integration & soft-fail tests** (5 tasks, parallel-safe — separate test files): dispatch round-trip + retry, capabilities-real + fleet-registration integration, soft-fail trio, slot-release Scenario Outline regression, shutdown-ordering invariant.
- **Wave 5 — Contract tests + Phase 2 retirement** (2 tasks, parallel-safe): `test_contract_nats_core.py`, retire LOG_PREFIX_DISPATCH grep + update routing-e2e.

**Why this wins**:

- ADR-ARCH-006 five-group layout already enforces module boundaries — the parallel work doesn't fight the layout.
- API-internal.md pins every cross-module Python contract (NATSClient, RoutingHistoryWriter, CapabilitiesRegistry Protocol, DispatchSemaphore, AppState extensions). Wave 2 modules can be implemented independently because their *consumers* in Wave 3 read from the pinned API.
- Test files in Waves 4–5 are file-disjoint — true parallel-safe.
- Wave 3's three sequential tasks are the only true bottleneck and they are short (each touches one module).

**When it loses**: when integration boundaries are fuzzy. Here they are not — the contracts are tight.

### Approach 3 — Vertical slice (walking skeleton)

Slice 1: minimal happy-path dispatch (NATS connect → fleet.register → resolve → request/reply → inline trace write). Slice 2: retry-with-redirect + visited-set. Slice 3: 16KB filesystem offload + redaction. Slice 4: NATS-soft-fail + Graphiti-soft-fail. Slice 5: contract tests + ASSUM-008/009 DDRs.

**Why it loses here**: the schema (`JarvisRoutingHistoryEntry`) is authoritative-from-v1 per DDR-018 — getting it wrong in Slice 1 and reshaping it in Slice 3 multiplies refactor cost on the 36 scenario fixtures. Approach 3 wins when the design is uncertain; here the design is locked.

---

## 2. Recommendation

**Approach 2 — Wave-based parallel fan-out**, with the following implementation breakdown:

### Wave 1 — Foundations (5 tasks, parallel-safe)

| ID | Task | task_type | Complexity | Notes |
|---|---|---|---|---|
| TASK-J004-001 | DDR-023 (ASSUM-009 → trace-file collision = WARN+preserve) + DDR-024 (ASSUM-008 → degraded eligible v1) | documentation | 2 | Promotes both flagged assumptions to append-only DDRs; retires the "low" / "medium" confidence tags |
| TASK-J004-002 | `pyproject.toml` — add nats-py + graphiti-core to provider extras | scaffolding | 2 | Per LCOI policy from `.claude/CLAUDE.md`; both go under `[project.optional-dependencies]` |
| TASK-J004-003 | `config/settings.py` — extend JarvisConfig with NATS + Graphiti + dispatch fields | declarative | 3 | Per API-internal.md §8; 9 new typed fields with validators |
| TASK-J004-004 | `infrastructure/routing_history.py` — Pydantic schema only (`JarvisRoutingHistoryEntry`, `DispatchOutcome`, `RedirectAttempt`, helper types) — no writer logic yet | declarative | 4 | Per DM-routing-history.md; `frozen=True`, `extra="ignore"` |
| TASK-J004-005 | `tests/test_routing_history_schema.py` — schema-conformance gate (full-shape, frozen, extra=ignore, redaction-at-write-boundary skeleton) | testing | 3 | DDR-018 invariant test |

### Wave 2 — Infrastructure modules (5 tasks, parallel-safe — different files; depend on Wave 1)

| ID | Task | task_type | Complexity | Depends on |
|---|---|---|---|---|
| TASK-J004-006 | `infrastructure/nats_client.py` (connect/drain/request) + `tests/test_nats_client.py` | feature | 5 | TASK-J004-002, TASK-J004-003 |
| TASK-J004-007 | `infrastructure/fleet_registration.py` (`build_jarvis_manifest`, `register_on_fleet`, `heartbeat_loop`, `deregister_from_fleet`) + `tests/test_fleet_registration.py` | feature | 4 | TASK-J004-003 |
| TASK-J004-008 | `infrastructure/dispatch_semaphore.py` (DispatchSemaphore wrapper) + `tests/test_dispatch_semaphore.py` | feature | 3 | TASK-J004-003 |
| TASK-J004-009 | `infrastructure/capabilities_registry.py` (Protocol + LiveCapabilitiesRegistry + StubCapabilitiesRegistry) + `tests/test_capabilities_registry_unit.py` | feature | 6 | TASK-J004-003, TASK-J004-006 |
| TASK-J004-010 | `infrastructure/routing_history.py` writer methods (`write_specialist_dispatch` + 16KB filesystem offload + structlog redaction at write boundary + `flush`) + `tests/test_routing_history_writer.py` | feature | 7 | TASK-J004-004 |

### Wave 3 — Tool surface swap + lifecycle (3 tasks; depend on Wave 2)

| ID | Task | task_type | Complexity | Depends on |
|---|---|---|---|---|
| TASK-J004-011 | `tools/dispatch.py` — real `dispatch_by_capability` body: round-trip + retry-with-redirect + visited-set + DEGRADED strings + delete `LOG_PREFIX_DISPATCH` + `_stub_response_hook` + Phase 2 paragraph from docstring | feature | 7 | TASK-J004-006, TASK-J004-008, TASK-J004-009, TASK-J004-010 |
| TASK-J004-012 | `tools/capabilities.py` — `list_available_capabilities` reads `CapabilitiesRegistry.snapshot()`; real `capabilities_refresh` + `capabilities_subscribe_updates` bodies; docstring deltas | feature | 4 | TASK-J004-009 |
| TASK-J004-013 | `infrastructure/lifecycle.py` — startup ordering (NATS → Graphiti → register → heartbeat → semaphore) + shutdown drain (cancel heartbeat → deregister → close registry → flush writer → drain NATS → close Graphiti) + `AppState` extensions | feature | 6 | TASK-J004-006, TASK-J004-007, TASK-J004-008, TASK-J004-009, TASK-J004-010 |

### Wave 4 — Integration & soft-fail tests (5 tasks, parallel-safe; depend on Wave 3)

| ID | Task | task_type | Complexity | Depends on |
|---|---|---|---|---|
| TASK-J004-014 | `tests/test_fleet_registration_integration.py` + `tests/test_capabilities_real.py` — register / heartbeat / deregister + KV-watch invalidation | testing | 5 | TASK-J004-013 |
| TASK-J004-015 | `tests/test_dispatch_by_capability_integration.py` — round-trip happy / timeout-exhausted / redirect-success / redirect-exhausted / specialist-error-redirect / semaphore-overflow | testing | 6 | TASK-J004-013 |
| TASK-J004-016 | `tests/test_nats_unavailable.py` + `tests/test_graphiti_unavailable.py` + `tests/test_lifecycle_partial_failure.py` (NATS-up/Graphiti-down, NATS-down/Graphiti-up, both-down) | testing | 5 | TASK-J004-013 |
| TASK-J004-017 | `tests/test_dispatch_slot_release.py` — Scenario Outline 5-row regression (DDR-020): success / timeout / specialist_error / transport_unavailable / unresolved | testing | 4 | TASK-J004-013 |
| TASK-J004-018 | `tests/test_lifecycle_shutdown_order.py` — drain-on-shutdown ordering invariant (heartbeat → deregister → registry close → writer flush → NATS drain → Graphiti close) | testing | 4 | TASK-J004-013 |

### Wave 5 — Contract tests + Phase 2 retirement (2 tasks, parallel-safe; depend on Wave 4)

| ID | Task | task_type | Complexity | Depends on |
|---|---|---|---|---|
| TASK-J004-019 | `tests/test_contract_nats_core.py` — 5 contract tests (manifest round-trip, CommandPayload/ResultPayload deserialise, source_id="jarvis" audit, Topics-formatter grep invariant) | testing | 4 | TASK-J004-015 |
| TASK-J004-020 | Update `tests/test_routing_e2e.py` for real-NATS path; retire TASK-J002-021 LOG_PREFIX_DISPATCH grep test | refactor | 3 | TASK-J004-015 |

**20 tasks across 5 waves.** Aggregate complexity: 88/200. Estimated wall-clock: 6–8 working days under solo execution; 4–5 days with Wave 2 fan-out.

---

## 3. Findings on user-flagged concerns

### ASSUM-009 (low confidence) — trace-file collision policy

**Current state**: `.feature` line 377 pins write-failure semantics: existing trace file at the per-decision path → log `WARN routing_history_write_failed`, preserve original, do not overwrite. Confidence is "low" because the design pins 1:1 decision-id→file mapping but does not explicitly state collision behaviour.

**Recommendation**: **Promote to DDR-023** ("trace-file collision = WARN-and-preserve"). Rationale:

- `decision_id` is UUIDv4; collision implies UUID re-use, which is itself an error condition worth flagging
- Preserving the original retains audit-trail evidence of the first dispatch (the second is the bug)
- Aligns with `frozen=True` invariant — the second write would be a mutation
- Operator-visible WARN gives observability without false-alarm escalation

**Alternative considered**: overwrite-with-warning. Rejected because it silently loses the original audit trail; the rare collision case is more likely to be a UUID-generation bug than a real second decision.

**Action**: TASK-J004-001 produces DDR-023. Confidence promotes to "high".

### ASSUM-008 (medium confidence) — degraded specialist dispatch eligibility

**Current state**: v1 keeps `manifest.status="degraded"` specialists dispatch-eligible; redirect-with-retry handles their failures. Confidence is "medium" because the AgentManifest enum permits "degraded" but no DDR forbids dispatching to one.

**Recommendation**: **Promote to DDR-024** ("degraded specialists remain eligible at resolution-time in v1"). Rationale:

- The redirect-with-retry policy (DDR-017) already provides graceful degradation for slow / failing specialists — adding a second exclusion mechanism at resolution-time would be belt-and-braces
- Suppression at resolution-time is `jarvis.learning` (FEAT-J008, v1.5) territory and lands as an append-only DDR there
- Already covered by scenario at line 388 (degraded specialist still eligible, status captured in trace)
- Capturing status in routing-history (already in spec) gives `jarvis.learning` the data to suppress later if patterns emerge

**Action**: TASK-J004-001 produces DDR-024 (combined commit with DDR-023). Confidence promotes to "high".

### Contract enforcement

**Current state**: design §9 lists 6 contract tests in `test_contract_nats_core.py`. ADR-ARCH-029 redaction is covered. AgentManifest kebab-case is covered by the model itself (`agent_id: str = Field(pattern=...)`).

**Findings**:

1. **Strong**: The 5 listed contract tests (manifest round-trip, CommandPayload deserialise, ResultPayload deserialise, source_id audit, Topics-formatter usage) cover the cross-repo nats-core handshake.
2. **Gap**: No grep invariant for hard-coded subject strings. The FEAT-J002 pattern (TASK-J002-021 LOG_PREFIX_DISPATCH) shows grep-invariants work — recommend adding one for `agents.command.`, `agents.result.`, `fleet.register` literals in `src/jarvis/`.
3. **Gap**: The `source_id="jarvis"` audit invariant is one assertion in one test — recommend hoisting to a separate parametrised test that walks every emitted MessageEnvelope construction site.
4. **Strength**: Redaction is covered at the write boundary (TASK-J004-005, TASK-J004-010) per ADR-ARCH-029 — not at Pydantic validation, which would be too early.

**Recommendation**: TASK-J004-019 explicitly includes the Topics-formatter grep invariant and a parametrised source_id test. The FEAT-J002 invariant pattern is the template.

### Test strategy gaps

**Findings**:

1. **Strong**: 5-row Scenario Outline at line 352 ("slot released on every outcome") is the canonical regression for DDR-020 — already in spec. TASK-J004-017 owns this.
2. **Gap (small)**: filesystem-offload edge cases:
   - Pre-existing trace file (covered, line 377; ASSUM-009 → DDR-023)
   - Inline (line 132) and offload (line 140) thresholds (covered)
   - **Missing**: directory creation on first write — TASK-J004-010 should assert `~/.jarvis/traces/{date}/` is created lazily with mode 0700 per DDR-018
   - **Already covered**: redaction-after-offload — line 312 covers, asserts file content is also redacted
3. **Gap (filled)**: NATS connect-then-disconnect mid-session not in the 36 scenarios. Existing `test_nats_client.py` covers reconnect logging. **Recommendation**: leave as-is — the supervisor-side dispatch path treats mid-session disconnect as `NATSConnectionError → transport_unavailable`, which is covered by line 252 (mid-dispatch NATS failure surfaces transport_unavailable without redirect).
4. **Gap (filled)**: drain-on-shutdown ordering — TASK-J004-018 owns the explicit invariant test (heartbeat → deregister → registry close → writer flush → NATS drain → Graphiti close).

---

## 4. Cross-task Integration Contracts (preview for IMPLEMENTATION-GUIDE.md §4)

The following cross-task data hand-offs MUST appear as Integration Contracts in IMPLEMENTATION-GUIDE.md §4:

1. **`JarvisConfig` extensions** — Producer: TASK-J004-003. Consumers: every Wave 2 + Wave 3 task. Format: typed Pydantic v2 fields per API-internal.md §8.
2. **`JarvisRoutingHistoryEntry` schema** — Producer: TASK-J004-004. Consumers: TASK-J004-005 (schema test), TASK-J004-010 (writer methods), TASK-J004-011 (dispatch tool builds entries).
3. **`NATSClient` API** — Producer: TASK-J004-006. Consumers: TASK-J004-009 (capabilities), TASK-J004-011 (dispatch), TASK-J004-013 (lifecycle).
4. **`CapabilitiesRegistry` Protocol** — Producer: TASK-J004-009. Consumers: TASK-J004-011 (dispatch resolution), TASK-J004-012 (capabilities tools), TASK-J004-013 (lifecycle wiring).
5. **`DispatchSemaphore` API** — Producer: TASK-J004-008. Consumers: TASK-J004-011 (dispatch), TASK-J004-013 (lifecycle armament).
6. **`RoutingHistoryWriter` API** — Producer: TASK-J004-010. Consumers: TASK-J004-011 (dispatch), TASK-J004-013 (lifecycle flush).
7. **NATS subject formatters (singular convention)** — Producer: external (`nats_core.Topics`). Consumers: TASK-J004-007 (`fleet.register`), TASK-J004-011 (`agents.command.{agent_id}` / `agents.result.{agent_id}`), TASK-J004-009 ($KV.agent-registry.>). Format constraint: subjects produced via `nats_core.Topics.*` formatters; never hard-coded literals. Validation: TASK-J004-019 grep invariant.
8. **`source_id="jarvis"` envelope audit** — Producer: TASK-J004-011 (every emitted MessageEnvelope). Consumer: TASK-J004-019 (parametrised assertion across all emit sites).

---

## 5. Risk register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Wave 2 modules drift from API-internal.md while implemented in parallel | Low | Medium | Each Wave 2 task includes a contract test against the API-internal.md spec; Coach validates the file matches the contract at gate |
| 16KB offload threshold misjudged in real workloads | Low | Low | DDR-018 alternatives explicitly considered 4KB / 16KB / 64KB; if WARN frequency >1% over 24h, append-only DDR raises threshold |
| `NATSKVManifestRegistry` watch callback shape differs from Forge convention | Medium | Low | ASSUM-NATS-KV-WATCH carried forward; thin adapter in TASK-J004-009 isolates the divergence |
| Graphiti latency exceeds dispatch wall-clock budget | Low | Medium | DDR-019 fire-and-forget; `asyncio.create_task` at the boundary; writer flush bounded at 5s on shutdown |
| Phase 2 stub-path tests fail to retire cleanly | Low | Low | TASK-J004-020 owns the cleanup; LOG_PREFIX_DISPATCH grep invariant flips to "must NOT be present" |
| Redaction missed at write boundary → secret in `~/.jarvis/traces/...` | Low | High | TASK-J004-010 + TASK-J004-005 assert structlog redact-processor runs on the offload-file content, not just the inline path |

---

## 6. Decision artefacts produced by this review

1. This review report — `.claude/reviews/TASK-REV-22CF-review-report.md`
2. **Pending on [I]mplement**: feature folder `tasks/backlog/feat-jarvis-004-fleet-registration-and-specialist-dispatch/` with 20 task files, IMPLEMENTATION-GUIDE.md (with mandatory data-flow diagram, sequence diagram, dependency graph, §4 Integration Contracts), README.md
3. **Pending on [I]mplement**: structured YAML at `.guardkit/features/FEAT-J004-XXXX.yaml` for AutoBuild
4. **Pending on [I]mplement**: BDD scenario tagging via `bdd-linker` subagent (Step 11) — expect tags to cluster around the 5 wave themes

---

## Decision options

- **[A]ccept** — save findings, do not generate implementation tasks yet
- **[R]evise** — explore an alternative (e.g. compress to fewer/larger tasks; promote ASSUM-009 to overwrite-with-warning instead of write-failure)
- **[I]mplement** — generate the 20-task feature structure, IMPLEMENTATION-GUIDE.md (with mandatory diagrams + §4 Integration Contracts), structured FEAT-J004-XXXX.yaml, run pre-flight validation, and run Step 11 BDD linker
- **[C]ancel** — discard this plan
