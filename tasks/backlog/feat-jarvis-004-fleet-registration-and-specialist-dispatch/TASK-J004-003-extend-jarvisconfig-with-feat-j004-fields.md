---
id: TASK-J004-003
title: Extend JarvisConfig with FEAT-JARVIS-004 fields
task_type: declarative
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
priority: high
tags:
- config
- settings
- FEAT-JARVIS-004
status: in_review
created: 2026-04-27 15:30:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J004-702C
  base_branch: main
  started_at: '2026-04-27T16:42:59.619623'
  last_updated: '2026-04-27T16:47:11.102008'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-27T16:42:59.619623'
    player_summary: 'Added the nine FEAT-JARVIS-004 fields to JarvisConfig under a
      clearly delimited block, immediately after the FEAT-J003 attended_adapter_ids
      field and before model_config: nats_url (str default ''nats://localhost:4222''),
      nats_credentials_path (Path|None=None), heartbeat_interval_seconds (int Field
      default=30 ge=5 le=300 per DDR-021/heartbeat), graphiti_endpoint (str|None=None
      for DDR-019 soft-fail), graphiti_api_key (SecretStr|None=None), jarvis_traces_dir
      (Path default ~/.jarvis/traces), speciali'
    player_success: true
    coach_success: true
---

# TASK-J004-003 — Extend JarvisConfig with FEAT-JARVIS-004 fields

## Description

Extend `src/jarvis/config/settings.py` with the nine new typed Pydantic
v2 fields specified by [API-internal.md §8](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md):

```python
# ── NATS ────────────────────────────────────────────
nats_url: str = "nats://localhost:4222"
nats_credentials_path: Path | None = None
heartbeat_interval_seconds: int = Field(default=30, ge=5, le=300)

# ── Graphiti ────────────────────────────────────────
graphiti_endpoint: str | None = None
graphiti_api_key: SecretStr | None = None
jarvis_traces_dir: Path = Path.home() / ".jarvis" / "traces"

# ── Dispatch ────────────────────────────────────────
specialist_dispatch_timeout_seconds: int = Field(default=60, ge=5, le=600)
dispatch_concurrent_cap: int = Field(default=8, ge=1, le=64)

# ── Fleet ───────────────────────────────────────────
jarvis_agent_version: str = Field(
    default="0.4.0",
    pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$",
)
```

All fields resolve from env via the existing `env_prefix="JARVIS_"`
(so `JARVIS_NATS_URL`, `JARVIS_GRAPHITI_ENDPOINT`, etc.). Defaults are
chosen so a zero-env developer still gets a working config:
`graphiti_endpoint=None` triggers DDR-019 soft-fail; localhost NATS
covers the in-process integration test pattern.

## Acceptance Criteria

- [ ] Nine fields added to `JarvisConfig` with the exact validators above.
- [ ] `Field(ge=, le=)` constraints applied per DDR-016 (timeout 5..600), DDR-020 (cap 1..64), DDR-021/heartbeat (5..300).
- [ ] `jarvis_agent_version` defaults to `"0.4.0"` with semver regex validator.
- [ ] `.env.example` (if present) updated with stub entries for each `JARVIS_*` env var, marked optional.
- [ ] `tests/test_config_settings.py` (new or extended) covers: out-of-range rejection (timeout=4 → ValidationError; cap=0 → ValidationError; heartbeat=4 → ValidationError); env-prefix resolution (`JARVIS_NATS_URL` → `nats_url`); default values applied when env vars absent.
- [ ] No `nats-py` or `graphiti-core` import inside `settings.py` — keep this module dependency-free.
- [ ] `uv run mypy src/jarvis/config/` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Validator boundary tests for every `Field(ge=, le=)` constraint.
- [ ] Env-var override smoke test (set `JARVIS_NATS_URL=nats://test:4222` → loaded value).
- [ ] Defaults applied when env unset.

## Implementation Notes

This is a **declarative** task per `.claude/rules/code-style.md` —
Pydantic field definitions only, no business logic. CoachValidator runs
the `declarative` profile for this task.

`Path | None` and `SecretStr | None` are deliberate — the soft-fail
chain depends on `None` being a first-class signal (per DDR-019,
DDR-021).

## Test Execution Log

(Populated by /task-work.)
