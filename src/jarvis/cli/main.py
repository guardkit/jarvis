"""Jarvis CLI entry-point.

Provides the ``jarvis`` console script with ``chat``, ``version``,
and ``health`` sub-commands (DDR-003: exactly three, no more).

The REPL serialises turns one-at-a-time (ASSUM-004), refuses blank-line
turns silently (ASSUM-001), and exits cleanly on ``/exit`` / EOF / SIGINT
(ASSUM-002).

Logging is configured at CLI entry so that configuration-load failures
(``pydantic.ValidationError`` at ``JarvisConfig()``) are emitted as
structured events rather than bare ``click.echo`` writes.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import TYPE_CHECKING

import click
import structlog

from jarvis.agents import build_supervisor
from jarvis.infrastructure.logging import configure
from jarvis.shared.constants import VERSION, Adapter
from jarvis.shared.exceptions import ConfigurationError

if TYPE_CHECKING:
    from jarvis.infrastructure.lifecycle import AppState


def _configure_default_logging() -> None:
    """Configure structlog at the default level before any config load.

    ``JARVIS_LOG_LEVEL`` overrides the ``INFO`` default.  ``configure()`` is
    idempotent so a later call from ``build_app_state(config)`` with the
    user-specified level simply re-applies.
    """
    default_level = os.environ.get("JARVIS_LOG_LEVEL", "INFO")
    configure(default_level)


async def _create_app_state() -> AppState:
    """Load config and build the fully-wired :class:`AppState`.

    Logging is configured before :class:`JarvisConfig` is instantiated so
    that a ``pydantic.ValidationError`` raised during config load is
    captured as a structured event (via the caller's ``except`` handler)
    rather than surfacing through an un-configured logger.

    Returns:
        A fully wired :class:`AppState` with supervisor and session_manager.

    Raises:
        ConfigurationError: If provider key validation fails.
        pydantic.ValidationError: If config fields are invalid.
    """
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.lifecycle import build_app_state

    _configure_default_logging()
    config = JarvisConfig()
    return await build_app_state(config)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Jarvis — attended DeepAgent surface."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


@main.command()
def version() -> None:
    """Print the Jarvis version and exit."""
    click.echo(f"jarvis {VERSION}")


@main.command()
def health() -> None:
    """Print config summary, supervisor build status and memory store readiness."""
    from pydantic import ValidationError

    from jarvis.config.settings import JarvisConfig

    # Configure logging before any validation so that errors are emitted as
    # structured events (F4 from FEAT-JARVIS-001 review).
    _configure_default_logging()
    log = structlog.get_logger(__name__)

    # 1. Load config — ValidationError on malformed fields → structured log + exit 1
    try:
        config = JarvisConfig()
    except ValidationError as exc:
        log.error("jarvis_config_invalid", error=str(exc))
        raise SystemExit(1) from exc

    # 2. Validate provider keys — ConfigurationError → structured log + exit 1
    try:
        config.validate_provider_keys()
    except ConfigurationError as exc:
        log.error("jarvis_provider_key_missing", error=str(exc))
        raise SystemExit(1) from exc

    # 3. Build supervisor (token-free) — report success
    try:
        build_supervisor(config)
        click.echo("supervisor: ok")
    except Exception as exc:
        log.error("jarvis_supervisor_build_failed", error=str(exc))
        raise SystemExit(1) from exc

    # 4. Memory store readiness (Phase 1: InMemoryStore always succeeds)
    from langgraph.store.memory import InMemoryStore

    InMemoryStore()
    click.echo("memory store: ready")


@main.command()
def chat() -> None:
    """Start an interactive REPL."""
    asyncio.run(_chat_loop())


async def _chat_loop() -> None:
    """Run the interactive REPL loop.

    Sequence:
        1. Bootstrap application state (config → build_app_state → AppState).
        2. Start a CLI session via the session manager.
        3. Install SIGINT handler for clean exit (code 130).
        4. Loop: read stdin → skip blanks → handle /exit → invoke → print reply.
    """
    from pydantic import ValidationError

    # 1. Bootstrap — _create_app_state wires supervisor + session_manager
    try:
        state = await _create_app_state()
    except ValidationError as exc:
        log = structlog.get_logger(__name__)
        log.error("jarvis_config_invalid", error=str(exc))
        raise SystemExit(1) from exc
    except ConfigurationError as exc:
        log = structlog.get_logger(__name__)
        log.error("jarvis_provider_key_missing", error=str(exc))
        raise SystemExit(1) from exc
    except Exception as exc:
        log = structlog.get_logger(__name__)
        log.error("jarvis_startup_failed", error=str(exc))
        raise SystemExit(1) from exc

    session_manager = state.session_manager

    # 2. Start session
    session = session_manager.start_session(Adapter.CLI, "cli-user")

    # 3. Install SIGINT handler — calls end_session then sys.exit(130)
    def _sigint_handler(signum: int, frame: object) -> None:
        session_manager.end_session(session.session_id)
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)

    # 4. REPL loop — sequential turns (ASSUM-004)
    try:
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            except EOFError:
                break

            # EOF: readline returns ""
            if not line:
                break

            stripped = line.strip()

            # ASSUM-001: skip blank lines silently
            if stripped == "":
                continue

            # ASSUM-002: /exit is case-sensitive, whitespace-trimmed
            if stripped == "/exit":
                break

            # Invoke supervisor and print reply BEFORE reading next line (ASSUM-004)
            try:
                reply = await session_manager.invoke(session, stripped)
                click.echo(reply)
            except KeyboardInterrupt:
                # SIGINT during invoke
                session_manager.end_session(session.session_id)
                sys.exit(130)
            except Exception as exc:
                # Provider error — REPL survives
                click.echo(f"[error] {exc}")

    except KeyboardInterrupt:
        session_manager.end_session(session.session_id)
        sys.exit(130)

    # Clean exit
    session_manager.end_session(session.session_id)
    click.echo("session ended.")


if __name__ == "__main__":
    main()
