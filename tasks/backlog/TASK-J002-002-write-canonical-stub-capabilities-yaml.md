---
id: TASK-J002-002
title: Write canonical stub_capabilities.yaml
task_type: declarative
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 20
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Listing available capabilities returns the current stub registry
swap_point_note: 'DELETED in FEAT-JARVIS-004 when NATSKVManifestRegistry wires live
  reads. Grep anchor: `stub_capabilities.yaml`.'
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:32:25.716038'
  last_updated: '2026-04-24T20:37:12.758989'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-24T20:32:25.716038'
    player_summary: "Created src/jarvis/config/stub_capabilities.yaml with the canonical\
      \ 4-entry Phase 2 stub registry (architect-agent, product-owner-agent, ideation-agent,\
      \ forge), copied byte-for-byte from the ```yaml block under '## Canonical Phase\
      \ 2 content' in docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md. Wrote\
      \ tests/test_stub_capabilities_yaml.py organised by acceptance criterion (one\
      \ TestACxxx class each). The AC-002 byte-for-byte test does not hard-code the\
      \ canonical content in the test \u2014 it extrac"
    player_success: true
    coach_success: true
---
# Write canonical stub_capabilities.yaml

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 1/10 | **Est.:** 20 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Create the canonical 4-entry stub_capabilities.yaml fixture that Phase 2 uses in place of a real NATS KV manifest registry. Deleted in FEAT-JARVIS-004.

## Acceptance Criteria

- [ ] File exists at `src/jarvis/config/stub_capabilities.yaml` containing exactly four capabilities: `architect-agent`, `product-owner-agent`, `ideation-agent`, `forge`.
- [ ] Content matches byte-for-byte the canonical YAML in DM-stub-registry.md §"Canonical Phase 2 content".
- [ ] All `agent_id` values are kebab-case; all `tool_name` values are snake_case; all `trust_tier` values are one of `core|specialist|extension`.
- [ ] `forge` entry carries a `build_feature` capability so the reasoning model sees Forge alongside specialists in the catalogue.

## Scenarios Covered

- Listing available capabilities returns the current stub registry

## Swap-Point Note

DELETED in FEAT-JARVIS-004 when NATSKVManifestRegistry wires live reads. Grep anchor: `stub_capabilities.yaml`.

## Test Execution Log

_Populated by `/task-work` during implementation._
