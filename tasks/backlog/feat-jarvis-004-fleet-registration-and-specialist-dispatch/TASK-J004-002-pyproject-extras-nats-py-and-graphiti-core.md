---
id: TASK-J004-002
title: "pyproject.toml \u2014 add nats-py and graphiti-core to provider extras"
task_type: scaffolding
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
priority: high
tags:
- pyproject
- dependencies
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
  started_at: '2026-04-27T16:42:59.616031'
  last_updated: '2026-04-27T16:50:03.111753'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-27T16:42:59.616031'
    player_summary: "Added two focused optional-extras groups to pyproject.toml \u2014\
      \ `[nats]` (nats-py>=2.0,<3) and `[graphiti]` (graphiti-core>=0.9,<1.0) \u2014\
      \ and re-exported both into the `[providers]` umbrella so a single `pip install\
      \ .[providers]` still installs everything (LCOI policy \u2014 TASK-REV-LES1\
      \ / LES1 \xA73). Pin rationale: nats-py lower bound matches the sibling `nats-core/pyproject.toml`\
      \ convention (`nats-py>=2.0`) and caps at the next major (`<3`); graphiti-core\
      \ lower bound `>=0.9` is the first line that ships "
    player_success: true
    coach_success: true
---

# TASK-J004-002 — pyproject.toml: add nats-py and graphiti-core to provider extras

## Description

Add the two FEAT-JARVIS-004 third-party dependencies — `nats-py` for the
real NATS transport and `graphiti-core` for the routing-history writer —
to `pyproject.toml`'s `[project.optional-dependencies]` block.

Per `.claude/CLAUDE.md` LCOI policy (TASK-REV-LES1 / LES1 §3): every
provider/integration this template can be configured to use must be
declared. `[providers]` already covers LangChain integrations
(openai, google-genai); FEAT-JARVIS-004 adds two new optional groups:

- `[nats]` → `nats-py>=2.x,<3.0` (pinned to whatever `nats-core` repo
  pyproject already resolves — confirm at task-work time).
- `[graphiti]` → `graphiti-core>=0.x` (pinned to a minor version line).

Both are added to `[providers]` umbrella so a single `pip install .[providers]`
still installs everything.

## Acceptance Criteria

- [ ] `pyproject.toml` `[project.optional-dependencies]` gains `nats` and `graphiti` groups.
- [ ] `[providers]` umbrella includes both new groups.
- [ ] `uv sync` succeeds against the updated pyproject.
- [ ] `uv run python -c "import nats; import graphiti_core"` succeeds after `uv sync --extra providers`.
- [ ] Version pins explicitly bound: lower bound is the nats-core / forge convention; upper bound is the next major.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] N/A — scaffolding task. Acceptance via successful `uv sync` + import smoke check above.

## Implementation Notes

Confirm the exact `nats-py` version that `nats-core` (sibling repo at
`../nats-core/pyproject.toml`) pins; match it. Mismatched majors between
Jarvis and nats-core are the FEAT-J004 #1 likely contract-test failure
mode.

`graphiti-core` is local-FalkorDB-friendly per `.guardkit/graphiti.yaml`
which already configures `graph_store: falkordb`.

## Test Execution Log

(Populated by /task-work.)
