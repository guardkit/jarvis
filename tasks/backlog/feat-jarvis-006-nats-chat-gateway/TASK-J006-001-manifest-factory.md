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
status: in_review
dependencies: []
created: 2026-05-11 00:00:00+00:00
updated: 2026-05-11 00:00:00+00:00
tags:
- nats
- manifest
- declarative
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-006
  base_branch: main
  started_at: '2026-05-11T22:34:56.827905'
  last_updated: '2026-05-11T22:48:03.034797'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-05-11T22:34:56.827905'
    player_summary: 'Added a new declarative manifest factory at src/jarvis/infrastructure/manifest.py
      exposing build_manifest(config: JarvisConfig) -> AgentManifest. The factory
      composes the manifest from two private helpers (_build_chat_tool, _build_general_intent)
      so each shape can be reviewed in isolation. ToolCapability `chat` documents
      a JSON-Schema parameter object with `message` required (string), `conversation_history`
      optional (array of objects), and `adapter` optional (string), matching CommandPayload.arg'
    player_success: true
    coach_success: true
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
