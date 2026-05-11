---
id: TASK-J006-001
title: Manifest factory for jarvis (one ToolCapability + one IntentCapability)
task_type: declarative
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 1
implementation_mode: direct
complexity: 3
priority: high
status: backlog
dependencies: []
created: 2026-05-11T00:00:00Z
updated: 2026-05-11T00:00:00Z
tags: [nats, manifest, declarative]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Manifest factory for jarvis

## Description

Create `src/jarvis/infrastructure/manifest.py` exposing a factory that returns an
`AgentManifest` describing jarvis on the NATS bus. Jarvis exposes exactly one
`ToolCapability` (`chat`) and one `IntentCapability` (`general.*`).

This is the declarative schema half of FEAT-JARVIS-006 — no business logic, no NATS
calls. The factory is consumed by `chat_handler` (TASK-J006-003) and the
`serve_nats` CLI command (TASK-J006-004).

## Acceptance Criteria

- [ ] Module `src/jarvis/infrastructure/manifest.py` exports `build_manifest(config: JarvisConfig) -> AgentManifest`
- [ ] Returned manifest carries `agent_id = "jarvis"` (matches existing `fleet.register`)
- [ ] One `ToolCapability` entry: `name="chat"`, parameter schema documents `message` (required, str), `conversation_history` (optional, list), `adapter` (optional, str)
- [ ] One `IntentCapability` entry: `name="general"`, signals describe natural-language chat routing (non-empty, per Bug #5 guard from study-tutor template)
- [ ] Manifest version field matches existing fleet-register convention
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

- [ ] Unit test: `tests/unit/infrastructure/test_manifest.py` — builds manifest, asserts agent_id, asserts exactly one tool with name="chat", asserts non-empty intents (Bug #5 guard)
- [ ] Unit test: parameter schema for `chat` tool includes `message` as required string

## Implementation Notes

Use `nats_core.manifest.AgentManifest`, `ToolCapability`, `IntentCapability` directly
(see scope doc §"Shared contracts" and study-tutor's `adapters/manifest.py` for the
template). Do not introduce wrapper types.

Reference: `study-tutor/src/study_tutor/adapters/manifest.py` (proven 11 May 2026).

## Coach Validation

- Module imports cleanly
- Unit tests pass
- Lint zero-errors
- No NATS imports beyond `nats-core` types
