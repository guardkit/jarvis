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

