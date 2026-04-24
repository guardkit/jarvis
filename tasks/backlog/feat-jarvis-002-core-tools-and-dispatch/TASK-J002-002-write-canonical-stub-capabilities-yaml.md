---
id: TASK-J002-002
title: "Write canonical stub_capabilities.yaml"
task_type: declarative
status: backlog
created: 2026-04-24T06:55:00Z
updated: 2026-04-24T06:55:00Z
priority: high
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 20
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags: [phase-2, jarvis, feat-jarvis-002]
scenarios_covered:
  - "Listing available capabilities returns the current stub registry"
swap_point_note: "DELETED in FEAT-JARVIS-004 when NATSKVManifestRegistry wires live reads. Grep anchor: `stub_capabilities.yaml`."
test_results:
  status: pending
  coverage: null
  last_run: null
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
