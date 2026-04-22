---
id: TASK-J001-006
title: "agents/supervisor.py \u2014 build_supervisor(config) factory (DeepAgents built-ins\
  \ only, token-free)"
task_type: feature
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 3
implementation_mode: task-work
complexity: 7
dependencies:
- TASK-J001-003
- TASK-J001-004
status: in_review
tags:
- feature
- supervisor
- deepagents
- create_deep_agent
- adr-arch-010
- adr-arch-011
consumer_context:
- task: TASK-J001-003
  consumes: SUPERVISOR_MODEL_ENDPOINT
  framework: DeepAgents create_deep_agent via langchain.chat_models.init_chat_model
  driver: 'langchain-openai (for openai: prefix routing to llama-swap)'
  format_note: 'supervisor_model must be provider-prefixed (e.g. ''openai:jarvis-reasoner'');
    openai: prefix routes to llama-swap via OPENAI_BASE_URL; factory MUST NOT mutate
    the string or issue a test token call'
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T22:50:54.324023'
  last_updated: '2026-04-21T22:59:20.115490'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-21T22:50:54.324023'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: `src/jarvis/agents/supervisor.py` — `build_supervisor(config: JarvisConfig) -> CompiledStateGraph`

The single public factory every later feature composes against. DeepAgents built-ins only; no subagents (FEAT-003), no custom tools (FEAT-002), no LLM call at build time.

## Context

- [ADR-ARCH-010 deepagents pin](../../../docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md)
- [ADR-ARCH-011 single Jarvis reasoner subagent](../../../docs/architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md)
- [ADR-ARCH-002 clean hexagonal in DeepAgents supervisor](../../../docs/architecture/decisions/ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md)
- [contracts/API-internal.md §2 `build_supervisor`](../../../docs/design/FEAT-JARVIS-001/contracts/API-internal.md)
- Feature file @edge-case @integration @regression: "build_supervisor does not invoke the language model"

## Scope

**Files (NEW):**

- `src/jarvis/agents/__init__.py`
- `src/jarvis/agents/supervisor.py`:

```python
def build_supervisor(config: JarvisConfig) -> CompiledStateGraph:
    """Compose and return the Jarvis supervisor compiled graph.

    Phase 1: DeepAgents built-ins only. No LLM traffic.
    """
    model = init_chat_model(config.supervisor_model)  # provider-prefixed
    return create_deep_agent(
        model=model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        # Built-ins: write_todos, virtual filesystem, task — on by default
        # execute: disabled (no shell in Phase 1)
        tools=[],          # FEAT-002
        subagents=[],      # FEAT-003
        # Memory Store wired in SessionManager, not here
    )
```

- Honour the DeepAgents 0.5.3 API shape (factory may be `create_deep_agent` or `create_agent` — ADR-ARCH-010 settled on `create_deep_agent`; if the SDK preview drifts, adjust here only).
- Disable `execute` tool explicitly (pass `tools=[]` + any `disable_builtins=["execute"]` flag the SDK exposes, or construct without it if that's the default).
- **No LLM call at build time** — `init_chat_model` returns a chat model object without issuing traffic; the factory must not "test" it with a throwaway ping.

## Acceptance Criteria

- `build_supervisor(test_config)` returns a `CompiledStateGraph` without issuing any network request (verified by mock of the chat model's transport layer).
- Structural assertions pass: `write_todos`, virtual filesystem, and `task` tools appear in the compiled graph's tool inventory; `execute` does not; no custom tools; no subagents.
- `jarvis health` can call `build_supervisor(config)` without consuming any provider tokens.
- Factory is **idempotent-safe**: calling it twice with the same config yields two independent graphs (no hidden global state).
- All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

- Coach greps `agents/supervisor.py` for `.invoke(`, `.ainvoke(`, `.stream(`, `.astream(` on any model object — none must appear.
- Coach verifies the `system_prompt` argument is imported from `jarvis.prompts.supervisor_prompt` (not hard-coded inline).
- Coach verifies `tools=[]` and `subagents=[]` (or equivalent empty sequences) are explicitly passed — not defaulted — to document Phase 1 intent.

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify SUPERVISOR_MODEL_ENDPOINT contract from TASK-J001-003."""
import pytest
from jarvis.config.settings import JarvisConfig


@pytest.mark.seam
@pytest.mark.integration_contract("SUPERVISOR_MODEL_ENDPOINT")
def test_supervisor_model_endpoint_format(monkeypatch):
    """Verify supervisor_model is provider-prefixed and openai: → OPENAI_BASE_URL is required.

    Contract: supervisor_model must be provider-prefixed (e.g. 'openai:jarvis-reasoner');
    openai: prefix routes to llama-swap via OPENAI_BASE_URL.
    Producer: TASK-J001-003
    """
    # Producer side: load config with openai: prefix (default)
    monkeypatch.setenv("JARVIS_OPENAI_BASE_URL", "http://promaxgb10-41b1:9000/v1")
    config = JarvisConfig()

    # Consumer side: verify format matches contract
    assert ":" in config.supervisor_model, (
        f"supervisor_model must be provider-prefixed, got: {config.supervisor_model!r}"
    )
    provider, _, model_name = config.supervisor_model.partition(":")
    assert provider in {"openai", "anthropic", "google_genai"}, (
        f"Unknown provider prefix {provider!r} in {config.supervisor_model!r}"
    )
    if provider == "openai":
        assert config.openai_base_url, (
            "openai: prefix requires OPENAI_BASE_URL to route via llama-swap"
        )
```
