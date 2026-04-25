---
id: TASK-J002-001
title: Extend JarvisConfig with Phase 2 fields
task_type: declarative
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 30
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Searching the web without a configured Tavily key returns a configuration error
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:18:47.035348'
  last_updated: '2026-04-25T16:21:49.541881'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:18:47.035348'
    player_summary: 'Extended JarvisConfig (src/jarvis/config/settings.py) with four
      Phase 2 fields placed in a new ''-- Phase 2: web search + workspace settings
      --'' block: web_search_provider: Literal[''tavily'',''none'']=''tavily'', tavily_api_key:
      SecretStr|None=None, stub_capabilities_path: Path=Path(''src/jarvis/config/stub_capabilities.yaml''),
      workspace_root: Path=Path(''.'').resolve(). The existing SettingsConfigDict(env_prefix=''JARVIS_'',
      case_sensitive=False) already maps these to JARVIS_WEB_SEARCH_PROVIDER, JARVIS_TA'
    player_success: true
    coach_success: true
---
# Extend JarvisConfig with Phase 2 fields

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 30 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Add four Phase-2 fields to JarvisConfig: web_search_provider, tavily_api_key, stub_capabilities_path, workspace_root. All respect the JARVIS_ env-var prefix. validate_provider_keys() emits a warning (not an error) when Tavily is selected without a key — startup should not fail merely because the provider is unconfigured.

## Acceptance Criteria

- [ ] `JarvisConfig` gains four fields: `web_search_provider: Literal["tavily","none"] = "tavily"`, `tavily_api_key: SecretStr | None = None`, `stub_capabilities_path: Path = Path("src/jarvis/config/stub_capabilities.yaml")`, `workspace_root: Path = Path(".").resolve()`.
- [ ] Env var names respect the `JARVIS_` prefix (JARVIS_WEB_SEARCH_PROVIDER, JARVIS_TAVILY_API_KEY, JARVIS_STUB_CAPABILITIES_PATH, JARVIS_WORKSPACE_ROOT).
- [ ] `validate_provider_keys()` emits a warning (not a ConfigurationError) when `web_search_provider == "tavily"` and `tavily_api_key is None`.
- [ ] Phase 1 config tests in `tests/test_config.py` still pass unchanged.

## Scenarios Covered

- Searching the web without a configured Tavily key returns a configuration error

## Test Execution Log

_Populated by `/task-work` during implementation._
