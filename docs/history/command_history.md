/system-arch "Jarvis: General Purpose DeepAgent with dispatch tools — attended surface of the three-surface fleet" \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-build-plan-conversation-starter.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/general-purpose-agent.md \
  --context docs/research/ideas/reachy-mini-integration.md \
  --context docs/research/ideas/nemoclaw-assessment.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context .guardkit/context-manifest.yaml


  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ARCHITECTURE DOCUMENTATION CREATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

docs/architecture/
  ├── ARCHITECTURE.md              (index + summary)
  ├── domain-model.md              (7 bounded contexts, DDD context map, aggregates, events)
  ├── system-context.md            (C4 Level 1 Mermaid)
  ├── container.md                 (C4 Level 2 Mermaid)
  ├── assumptions.yaml             (15 ASSUM entries)
  └── decisions/
      ├── ADR-ARCH-001-local-first-inference-via-llama-swap.md   [FOUNDATIONAL]
      ├── ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md
      ├── ADR-ARCH-003-jarvis-is-the-gpa.md
      ├── ADR-ARCH-004-jarvis-registers-on-fleet-register.md
      ├── ADR-ARCH-005-seven-bounded-contexts.md
      ├── ADR-ARCH-006-five-group-module-layout.md
      ├── ADR-ARCH-007-adapter-services-as-separate-containers.md
      ├── ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md
      ├── ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md
      ├── ADR-ARCH-010-python-312-and-deepagents-pin.md
      ├── ADR-ARCH-011-single-jarvis-reasoner-subagent.md
      ├── ADR-ARCH-012-swap-aware-voice-latency-policy.md
      ├── ADR-ARCH-013-pattern-b-watcher-ceiling.md
      ├── ADR-ARCH-014-docker-on-gb10-deployment.md
      ├── ADR-ARCH-015-ci-ruff-mypy-pytest.md
      ├── ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md
      ├── ADR-ARCH-017-static-skill-declaration-v1.md
      ├── ADR-ARCH-018-calibration-approvals-cli-only-v1.md
      ├── ADR-ARCH-019-dashboard-read-only-live-trace-viewport.md
      ├── ADR-ARCH-020-trace-richness-by-default.md
      ├── ADR-ARCH-021-tools-return-structured-errors.md
      ├── ADR-ARCH-022-constitutional-rules-belt-and-braces.md
      ├── ADR-ARCH-023-permissions-constitutional-not-reasoning-adjustable.md
      ├── ADR-ARCH-024-pattern-b-watcher-failure-policy.md
      ├── ADR-ARCH-025-deepagents-0-6-upgrade-gated.md
      ├── ADR-ARCH-026-no-horizontal-scaling.md
      ├── ADR-ARCH-027-attended-only-cloud-escape-hatch.md
      ├── ADR-ARCH-028-watcher-durability.md
      ├── ADR-ARCH-029-personal-use-compliance-posture.md
      └── ADR-ARCH-030-budget-envelope.md

Graphiti seeding (5 background jobs):
  • bwgcwcf4v — ADR directory → architecture_decisions (30 ADRs)
  • bigrp6dhx — ARCHITECTURE.md → project overview
  • b2jriowe9 — domain-model.md → full_doc
  • bfzf5yvcy — system-context.md → full_doc
  • bxhdbfm6o — container.md → full_doc

Open questions resolved in-session: JA2, JA3, JA4, JA5, JA6, JA7, JA8
Deferred to /system-design: JA1 (jarvis_routing_history Pydantic schema)

Next steps:
  1. Review: docs/architecture/ARCHITECTURE.md
  2. Check seeding progress: BashOutput for the five bg jobs above
  3. Design APIs / schemas: /system-design "Jarvis"
  4. Plan features: /system-plan "feature description"
Session summary
Captured 30 ADRs + C4 diagrams across 6 categories. Mid-session you corrected my cloud-LLM blind spot — that forced the foundational ADR-ARCH-001 (local-first inference via llama-swap) and a re-take of the subagent roster (single jarvis-reasoner on gpt-oss-120b instead of four cloud models) plus the cloud escape hatch (ADR-ARCH-027, constitutionally attended-only). Preference saved to memory so the mistake won't recur.

Graphiti seeding runs locally via GB10 vLLM — I'll be notified when the five background jobs finish. Meanwhile, the markdown artefacts are ready for review regardless of seeding state.





/system-design FEAT-JARVIS-001 \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/architecture/decisions/ADR-J-004-supervisor-model-default.md \
  --context docs/architecture/decisions/ADR-J-005-memory-store-backend.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../specialist-agent/pyproject.toml \
  --context ../forge/pyproject.toml \
  --context .guardkit/context-manifest.yaml

Summary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SYSTEM DESIGN — FEAT-JARVIS-001
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Created: docs/design/FEAT-JARVIS-001/
├── design.md                                   ← top-level consolidated doc
├── contracts/
│   ├── API-cli.md                              (3 subcommands, env vars, exit codes)
│   └── API-internal.md                         (module boundaries, public APIs, stability)
├── models/
│   ├── DM-jarvis-reasoning.md                  (Session, Adapter, AppState, exceptions)
│   └── DM-config.md                            (JarvisConfig BaseSettings)
├── diagrams/
│   └── supervisor-container-l3.md              ⚠ AWAITING APPROVAL
└── decisions/
    ├── DDR-001 — no network protocols Phase 1
    ├── DDR-002 — Memory Store keyed by user_id
    ├── DDR-003 — CLI = chat/version/health only
    └── DDR-004 — thread_id == session_id 1:1

Protocols NOT generated (by design — see DDR-001):
  openapi.yaml | mcp-tools.json | a2a-schemas.yaml

Contradictions with 30 existing ADRs: 0
Graphiti: 9 seeding commands ready, awaiting [Y/N]

Pending gates:
  1. C4 L3 diagram approval → [A/R/R]
  2. Graphiti seeding → [Y/N]

Next in pipeline (per phase1-build-plan.md Steps 3–5):
  /feature-spec FEAT-JARVIS-001 --context docs/design/FEAT-JARVIS-001/design.md ...
  /feature-plan FEAT-JARVIS-001
  AutoBuild
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Committed as b259206 — 12 files, 3211 insertions. Branch is now 3 commits ahead of origin/main; nothing pushed. C4 L3 approval and Graphiti seeding are still outstanding whenever you want to revisit.

Pending gates:
  1. C4 L3 diagram approval → [A]pprove
  2. Graphiti seeding → [Y]

  Graphiti seeding succeeded — all 9 artefacts ingested across 42 episodes total.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ GRAPHITI SEEDING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

contracts/API-cli.md                  →  1 episode
contracts/API-internal.md             → 11 episodes (chunked — large)
models/DM-jarvis-reasoning.md         → 10 episodes (chunked — large)
models/DM-config.md                   →  1 episode
decisions/DDR-001..004.md             →  4 episodes (1 each, --type adr)
design.md                             → 14 episodes (chunked — large)
─────────────────────────────────────────────
Total: 9 files, 42 episodes → FalkorDB @ whitestocks:6379
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Warnings were just benign "document too large, auto-chunking" notes — no failures.

/system-design FEAT-JARVIS-001 is complete. Design artefacts + approval + Graphiti seeding all landed. Branch is 4 commits ahead of origin/main, nothing pushed. Next per phase1-build-plan.md Step 3: /feature-spec FEAT-JARVIS-001 --context docs/design/FEAT-JARVIS-001/design.md ...