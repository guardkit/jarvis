---
complexity: 7
consumer_context:
- consumes: APP_STATE
  driver: click>=8
  format_note: CLI commands invoke startup(config) to obtain AppState; version MUST
    NOT load config; health + chat MUST load config; chat REPL MUST NOT read next
    stdin line until prior reply printed (ASSUM-004)
  framework: click CLI + asyncio.run
  task: TASK-J001-005
dependencies:
- TASK-J001-007
- TASK-J001-005
feature_id: FEAT-JARVIS-001
id: TASK-J001-008
implementation_mode: task-work
parent_review: TASK-REV-J001
status: design_approved
tags:
- feature
- cli
- click
- repl
- sigint
- ddr-003
- assum-001
- assum-002
- assum-004
task_type: feature
title: cli/main.py — click group chat/version/health + REPL + SIGINT=130
wave: 5
---

# Task: `src/jarvis/cli/main.py` — click group with chat/version/health + REPL

The only adapter in Phase 1. Three commands — no more, no fewer (DDR-003). REPL serialises turns one-at-a-time (ASSUM-004), refuses blank-line turns silently (ASSUM-001), exits cleanly on `/exit` / EOF / SIGINT (ASSUM-002).

## Context

- [contracts/API-cli.md](../../../docs/design/FEAT-JARVIS-001/contracts/API-cli.md)
- [DDR-003 CLI minimal surface](../../../docs/design/FEAT-JARVIS-001/decisions/DDR-003-cli-minimal-surface.md) (referenced)
- ASSUM-001/002/004/005 — all load-bearing here
- Reference implementation: `../specialist-agent/src/specialist_agent/cli/main.py`

## Scope

**Files (NEW):**

- `src/jarvis/cli/__init__.py`
- `src/jarvis/cli/main.py`:

```python
@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """jarvis — attended DeepAgent surface."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())  # prints command list
        ctx.exit(0)

@main.command()
def version():
    """Print jarvis version."""
    click.echo(VERSION)
    # Exit 0; NO config load (feature file @key-example @smoke)

@main.command()
def health():
    """Print config summary + supervisor build + memory store readiness."""
    # Load config → on pydantic ValidationError exit 1 (ASSUM-005)
    # validate_provider_keys → on ConfigurationError exit 1 naming the missing env var
    # build_supervisor (token-free) → report success
    # Build InMemoryStore → report ready

@main.command()
def chat():
    """Start an interactive REPL."""
    asyncio.run(_chat_loop())

async def _chat_loop() -> None:
    # startup(config) → AppState
    # session = session_manager.start_session(Adapter.CLI, "rich")
    # Install SIGINT handler that calls end_session + sys.exit(130)
    # while True:
    #     line = await aioread stdin
    #     if line is EOF: break
    #     if line.strip() == "": continue               # ASSUM-001 silent skip
    #     if line.strip() == "/exit": break              # ASSUM-002 case-sensitive, whitespace-trimmed
    #     try:
    #         reply = await session_manager.invoke(session, line)
    #         click.echo(reply)                          # ASSUM-004: print BEFORE reading next line
    #     except Exception as e:
    #         click.echo(f"[error] {e}")                 # REPL survives provider errors
    # session_manager.end_session(session.session_id)
    # click.echo("session ended.")
    # sys.exit(0)
```

## Acceptance Criteria

- `jarvis` (no args) prints the command list and exits 0.
- `jarvis version` prints the version on one line, exits 0, does **not** load config.
- `jarvis health` with a valid config prints summary, reports supervisor builds successfully + memory store ready, exits 0.
- `jarvis health` with missing `OPENAI_BASE_URL` (default model) fails with a `ConfigurationError` naming `OPENAI_BASE_URL`, exits 1.
- `jarvis health` with malformed `JARVIS_SUPERVISOR_MODEL` ("jarvis-reasoner" no prefix) fails with `ValidationError` and exits 1 (ASSUM-005).
- `jarvis chat` starts REPL, handles:
  - `/exit` (case-sensitive, whitespace-trimmed) → clean exit with "session ended." banner, code 0
  - EOF / Ctrl-D → clean exit with "session ended." banner, code 0
  - SIGINT / Ctrl-C → session ended, `SessionEnded` event, exit 130
  - empty line → silently skipped, no supervisor call, no event
  - provider error mid-turn → `[error] ...` printed, REPL continues, session not ended
- REPL does not read the next stdin line until the current turn's reply has been printed (ASSUM-004).
- All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

- Coach verifies `version` command does not import `JarvisConfig` or call `startup()`.
- Coach verifies SIGINT handler calls `session_manager.end_session(...)` before `sys.exit(130)`.
- Coach verifies `/exit` matching is **case-sensitive** (`if line.strip() == "/exit"`, not `.lower()`).
- Coach verifies the REPL awaits the reply print before reading next stdin line (no concurrent read task).