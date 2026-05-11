---
id: TASK-REV-JV06
title: "Plan: NATS Chat Gateway (FEAT-JARVIS-006)"
task_type: review
status: backlog
priority: high
created: 2026-05-11T00:00:00Z
updated: 2026-05-11T00:00:00Z
complexity: 5
tags: [planning, nats, chat-gateway, demo-critical]
feature_id: FEAT-JARVIS-006
clarification:
  context_a:
    timestamp: 2026-05-11T00:00:00Z
    decisions:
      focus: all
      tradeoff: speed
      concerns:
        - risk_5_double_registration_appstate
        - risk_3_forge_notification_drain
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: NATS Chat Gateway (FEAT-JARVIS-006)

## Description

Plan the implementation of the NATS Chat Gateway for Jarvis (`jarvis serve-nats`) that
subscribes to `agents.command.jarvis`, feeds inbound chat requests into the existing
`session_manager.invoke()` pipeline, and dual-publishes the supervisor's reply on
both the requester's reply inbox (Bug #1) and the canonical `agents.result.jarvis`
envelope topic.

**DEMO-CRITICAL** — deadline 12 May 2026 (before DDD dry runs); estimated 3–4 hours.

## Context Files

- `features/feat-jarvis-006-nats-chat-gateway/feat-jarvis-006-nats-chat-gateway_summary.md`
- `features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md`
- `features/feat-jarvis-006-nats-chat-gateway/feat-jarvis-006-nats-chat-gateway.feature` (26 BDD scenarios)
- `features/feat-jarvis-006-nats-chat-gateway/feat-jarvis-006-nats-chat-gateway_assumptions.yaml`

## Review Scope (Context A)

- **Focus**: all aspects (technical, architecture, performance, security, demo-readiness)
- **Trade-off**: speed of delivery (DEMO-CRITICAL — copy proven patterns over abstraction)
- **Specific concerns**:
  - Risk #5 — AppState already registers on NATS; the gateway must add ONLY command
    subscription + drain to the existing `AppState.nats_client`, not clone a full
    NATSAdapter
  - Risk #3 — Forge notification drain behavior; stage-complete notifications queued
    during a chat turn are appended to the same reply that closes the turn

## Acceptance Criteria

- [ ] Technical options analysed with explicit reference to study-tutor and
      specialist-agent templates (proven 8–11 May 2026)
- [ ] Module boundaries identified: where does the new subscription wire-up live
      (`infrastructure/nats_serve.py` vs `nats_client.py` extension)?
- [ ] Risk #5 mitigation: explicit decision on AppState integration (extend existing
      client vs new NATSAdapter)
- [ ] Risk #3 mitigation: forge notification drain pattern documented
- [ ] Bug #1 dual-publish pattern wired (reply_to inbox + `agents.result.jarvis`)
- [ ] Bug #4 flat-subject discipline confirmed (`agents.command.jarvis` exactly)
- [ ] Signal handling + graceful shutdown ordering specified (study-tutor `_serve_adapter` pattern)
- [ ] Task breakdown sized for 3–4 hour total implementation budget
- [ ] Integration contract diagram included if cross-task data dependencies exist
- [ ] Data flow diagram showing write/read paths (read = supervisor reply → reply_to + canonical topic)

## Test Requirements

This is a planning/review task. No code tests are produced here; the review's
outputs are the structured feature YAML and the IMPLEMENTATION-GUIDE.md.

## Implementation Notes

This task is the planning analysis for FEAT-JARVIS-006. Outputs will be:

1. `tasks/backlog/feat-jarvis-006-nats-chat-gateway/` — subtask folder
2. `tasks/backlog/feat-jarvis-006-nats-chat-gateway/IMPLEMENTATION-GUIDE.md` with
   mandatory Mermaid diagrams (data flow, integration contracts, task dependency)
3. `.guardkit/features/FEAT-JARVIS-006.yaml` — structured AutoBuild feature file
4. Subtask markdown files with `task_type` and `parent_review: TASK-REV-JV06` provenance
