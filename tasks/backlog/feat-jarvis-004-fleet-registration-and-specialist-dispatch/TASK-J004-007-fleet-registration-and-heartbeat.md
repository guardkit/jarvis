---
id: TASK-J004-007
title: "infrastructure/fleet_registration.py — manifest, register, heartbeat, deregister"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 2
implementation_mode: task-work
complexity: 4
dependencies: [TASK-J004-003]
priority: high
tags: [infrastructure, fleet, registration, heartbeat, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-007 — Fleet registration: manifest, register, heartbeat, deregister

## Description

Land `src/jarvis/infrastructure/fleet_registration.py` with four functions
per [API-internal.md §2](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md):

- `build_jarvis_manifest(config) -> AgentManifest` — pure function, no
  I/O. Produces a `nats_core.AgentManifest` with `agent_id="jarvis"`,
  `template="general_purpose_agent"`, four `IntentCapability` entries
  (`conversational.gpa`, `dispatch.by_capability`, `meta.dispatch`,
  `memory.recall`), `tools=[]`, `max_concurrent=1`, `status="ready"`,
  `trust_tier="core"`, version from `config.jarvis_agent_version`.
- `register_on_fleet(client, manifest)` — publishes via
  `NATSKVManifestRegistry.register(manifest)`. Idempotent.
- `heartbeat_loop(client, manifest, config)` — periodic republish at
  `config.heartbeat_interval_seconds`. DEBUG on success, WARN on
  failure, loop continues; cancellation is the normal shutdown path.
- `deregister_from_fleet(client, agent_id="jarvis")` — clean shutdown,
  idempotent, WARN on failure (does not raise).

Plus `tests/test_fleet_registration.py` — manifest validation +
register / heartbeat / deregister contract tests against an in-process
NATS test server.

## Acceptance Criteria

- [ ] `build_jarvis_manifest(config)` is **pure** — no network, no filesystem; output is fully determined by `config`.
- [ ] Manifest validates against `nats_core.AgentManifest` (kebab-case `agent_id`, semver `version`, valid `trust_tier` enum).
- [ ] `metadata` dict on manifest is JSON-serializable; ≤64KB encoded (validator-enforced by `nats_core.AgentManifest`).
- [ ] `register_on_fleet` is idempotent — registering a second time replaces the prior entry, no exception.
- [ ] `heartbeat_loop` cancels cleanly on `asyncio.CancelledError` (no traceback, INFO log line).
- [ ] `heartbeat_loop` survives a single failed publish (WARN log, next tick succeeds).
- [ ] `deregister_from_fleet` does not raise even if the registry has no entry for `agent_id`.
- [ ] `tests/test_fleet_registration.py` covers: manifest shape, register-then-query, heartbeat fires at interval (use `freezegun` or `asyncio.sleep` mocking), heartbeat survives one publish failure, deregister removes the entry, deregister of missing entry is silent.
- [ ] `uv run mypy src/jarvis/infrastructure/fleet_registration.py` strict-clean.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Subjects produced via `nats_core.Topics.*` formatters — never hard-coded literals.
- [ ] In-process NATS test server fixture used for register/deregister/heartbeat integration tests.

## Implementation Notes

Every NATS subject string MUST come from `nats_core.Topics` per
ADR-SP-016 singular convention; hard-coded literals will fail
TASK-J004-019's grep invariant test.

`container_id` falls back to `os.environ.get("HOSTNAME") or None` per
API-internal.md §2 spec — not the reverse.

## Test Execution Log

(Populated by /task-work.)
