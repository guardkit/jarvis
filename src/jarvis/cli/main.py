"""Jarvis CLI entry-point.

Provides the ``jarvis`` console script with ``chat``, ``version``,
``health``, and ``serve-nats`` sub-commands. The ``serve-nats`` command
(FEAT-JARVIS-006) supersedes DDR-003's three-command constraint by adding
the canonical fleet gateway entry-point.

The REPL serialises turns one-at-a-time (ASSUM-004), refuses blank-line
turns silently (ASSUM-001), and exits cleanly on ``/exit`` / EOF / SIGINT
(ASSUM-002).

The ``serve-nats`` command bootstraps :func:`_create_app_state` exactly
once (Risk #5 — :func:`build_app_state` already owns
``register_on_fleet`` + ``heartbeat_loop``), subscribes
:func:`jarvis.infrastructure.chat_handler.handle_chat_command` to
``agents.command.jarvis`` via
:meth:`NATSClient.subscribe_with_reply`, and installs SIGINT/SIGTERM
handlers that share a single :class:`asyncio.Event` to drive graceful
shutdown (unsubscribe → drain in-flight → cancel heartbeat → deregister →
disconnect).

Logging is configured at CLI entry so that configuration-load failures
(``pydantic.ValidationError`` at ``JarvisConfig()``) are emitted as
structured events rather than bare ``click.echo`` writes.
"""

from __future__ import annotations

import asyncio
import functools
import os
import signal
import sys
from typing import TYPE_CHECKING

import click
import structlog
from dotenv import load_dotenv
from nats_core.topics import Topics

from jarvis.agents import build_supervisor
from jarvis.infrastructure.chat_handler import handle_chat_command
from jarvis.infrastructure.fleet_registration import (
    JARVIS_AGENT_ID,
    deregister_from_fleet,
)
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
    # Seed os.environ from .env so downstream consumers that read the process
    # environment directly (langchain's OpenAI client reads OPENAI_API_KEY,
    # langchain_anthropic reads ANTHROPIC_API_KEY, etc.) see the values the
    # user put in .env. pydantic-settings populates JarvisConfig from .env but
    # does NOT export to os.environ, so without this bridge the langchain
    # clients would fail with "api_key option must be set" even when the key
    # is present in .env. override=False so shell exports win over .env.
    load_dotenv(override=False)

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
            # TASK-J005-007 / DDR-030: drain & render any Forge notifications
            # that arrived since the previous iteration BEFORE reading the next
            # user line, so the rendered lines appear above the input cursor
            # and never mid-turn (design.md §8 CLI render sequence). The drain
            # is atomic (per TASK-J005-006 AC-003); SIGINT during the readline
            # below leaves any *new* notifications safe in the queue for the
            # next iteration. Empty list → no echo, no blank line.
            for notification in session_manager.pending_notifications(session.session_id):
                click.echo(notification.render_line())

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


# ---------------------------------------------------------------------------
# FEAT-JARVIS-006: serve-nats command
# ---------------------------------------------------------------------------
# Default budget for draining in-flight ``subscribe_with_reply`` handlers
# during graceful shutdown. Mirrors the AC of TASK-J006-004 (30s) and the
# study-tutor reference implementation. Exposed as a module constant so
# unit tests can monkey-patch it down to milliseconds without touching
# the function signature.
_SERVE_NATS_DRAIN_TIMEOUT: float = 30.0


@main.command("serve-nats")
@click.option(
    "--nats",
    "nats_url",
    default=None,
    help="NATS broker URL (overrides JARVIS_NATS_URL).",
)
@click.option(
    "--agent-id",
    "agent_id",
    default=JARVIS_AGENT_ID,
    show_default=True,
    help="Fleet agent identifier — resolves the subscription subject.",
)
@click.option(
    "--log-level",
    "log_level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default=None,
    help="Structured-log level (overrides JARVIS_LOG_LEVEL).",
)
def serve_nats(nats_url: str | None, agent_id: str, log_level: str | None) -> None:
    """Serve the Jarvis chat gateway over NATS.

    Bootstraps the full supervisor via :func:`_create_app_state`, then
    subscribes the chat handler to ``agents.command.{agent_id}`` and
    waits for a SIGINT/SIGTERM-driven shutdown event before tearing down
    the subscription and the broker connection in the order:

    unsubscribe → drain in-flight (30s) → cancel heartbeat → deregister →
    disconnect.

    Broker-as-hard-dependency: when ``_create_app_state`` returns an
    ``AppState`` whose ``nats_client`` is ``None`` (DDR-021 soft-fail),
    this command refuses to start and exits non-zero with a clear error
    message — diverging from ``jarvis chat`` which tolerates broker
    absence.
    """
    if log_level is not None:
        os.environ["JARVIS_LOG_LEVEL"] = log_level
    if nats_url is not None:
        os.environ["JARVIS_NATS_URL"] = nats_url

    asyncio.run(_run_serve_nats(agent_id=agent_id))


async def _run_serve_nats(*, agent_id: str) -> None:
    """Bootstrap :class:`AppState` and hand off to :func:`_serve_adapter`.

    Separated from the click handler so ``asyncio.run`` owns the loop
    lifetime and the inner coroutine is exercisable from unit tests
    without re-entering click.

    Raises:
        SystemExit: With code ``1`` when the NATS broker is unreachable
            (``state.nats_client is None``) or the configuration fails to
            load. Exit code propagates through ``asyncio.run`` to the
            click runtime.
    """
    from pydantic import ValidationError

    log = structlog.get_logger(__name__)

    try:
        state = await _create_app_state()
    except ValidationError as exc:
        log.error("jarvis_serve_nats_config_invalid", error=str(exc))
        click.echo(f"[error] invalid configuration: {exc}", err=True)
        raise SystemExit(1) from exc
    except ConfigurationError as exc:
        log.error("jarvis_serve_nats_provider_key_missing", error=str(exc))
        click.echo(f"[error] {exc}", err=True)
        raise SystemExit(1) from exc
    except Exception as exc:
        log.error("jarvis_serve_nats_startup_failed", error=str(exc))
        click.echo(f"[error] startup failed: {exc}", err=True)
        raise SystemExit(1) from exc

    if state.nats_client is None:
        # Broker-as-hard-dependency posture (AC-003). The chat command
        # tolerates ``nats_client=None`` (REPL works without the broker),
        # but the gateway has nothing to subscribe to so we refuse to
        # start and exit non-zero with a diagnostic.
        nats_url = getattr(state.config, "nats_url", "<unset>")
        log.error(
            "jarvis_serve_nats_broker_unreachable",
            nats_url=nats_url,
            agent_id=agent_id,
        )
        click.echo(
            f"[error] NATS broker unreachable at {nats_url}; "
            "serve-nats requires a live broker (DDR-021 soft-fail is the chat REPL posture only).",
            err=True,
        )
        raise SystemExit(1)

    await _serve_adapter(state, agent_id=agent_id)


async def _serve_adapter(
    state: AppState,
    *,
    agent_id: str = JARVIS_AGENT_ID,
    drain_timeout: float | None = None,
) -> None:
    """Run the NATS chat gateway against ``state`` until shutdown.

    Step-by-step (mirrors the AC ordering of TASK-J006-004):

    1. ``session_manager.start_session(Adapter.NATS, "nats-shared")`` —
       Phase 1 single shared session for the gateway. Concurrent
       requests serialise (per the scope doc trade-off).
    2. Bind :func:`handle_chat_command` against the session via
       :func:`functools.partial` and register it on
       ``agents.command.{agent_id}`` via :meth:`NATSClient.subscribe_with_reply`.
    3. Install SIGINT and SIGTERM signal handlers that set a shared
       :class:`asyncio.Event`.
    4. Await the event.
    5. On wake-up, perform graceful shutdown:

       a. ``subscription.unsubscribe()`` — stop accepting new commands.
       b. Wait up to ``drain_timeout`` seconds for in-flight handler
          invocations (``nats_client.in_flight``) to reach zero.
       c. Cancel ``state.fleet_heartbeat_task`` (if running).
       d. ``deregister_from_fleet`` — remove the agent from the
          ``agent-registry`` KV bucket.
       e. ``nats_client.drain(timeout=5.0)`` — close the underlying
          broker connection (idempotent).

    The function deliberately does **not** call
    :func:`register_on_fleet` (Risk #5 — :func:`build_app_state` already
    owns the single registration call).

    Args:
        state: The fully-wired :class:`AppState` returned by
            :func:`_create_app_state`. Must have ``nats_client``
            populated — the caller (``_run_serve_nats``) validates this
            before delegating.
        agent_id: The agent identifier used to resolve the subscription
            subject (``agents.command.{agent_id}``) and the deregister
            target. Defaults to :data:`JARVIS_AGENT_ID`.
        drain_timeout: Maximum seconds to wait for in-flight handlers
            during shutdown. Defaults to :data:`_SERVE_NATS_DRAIN_TIMEOUT`
            (30.0s). Tests override to keep wall-clock low.
    """
    log = structlog.get_logger(__name__)
    nats_client = state.nats_client
    if nats_client is None:
        # Defensive — ``_run_serve_nats`` is responsible for refusing the
        # broker-unreachable case before invoking ``_serve_adapter``. We
        # raise rather than ``assert`` so the contract is enforced even
        # when Python is run with ``-O`` (which strips assertions).
        raise RuntimeError(
            "_serve_adapter requires state.nats_client; "
            "_run_serve_nats must enforce this invariant before delegating."
        )

    if drain_timeout is None:
        drain_timeout = _SERVE_NATS_DRAIN_TIMEOUT

    # ------------------------------------------------------------------
    # 1. Bootstrap a single shared session for the gateway (Adapter.NATS)
    # ------------------------------------------------------------------
    session = state.session_manager.start_session(Adapter.NATS, "nats-shared")
    log.info(
        "jarvis_serve_nats_session_started",
        session_id=session.session_id,
        agent_id=agent_id,
    )

    # ------------------------------------------------------------------
    # 2. Bind handler + subscribe via subscribe_with_reply
    # ------------------------------------------------------------------
    # ``functools.partial`` (not a closure over local names) so the
    # subscriber's callback signature stays inspectable in unit tests —
    # the bound kwargs are accessible via ``handler.keywords``.
    bound_handler = functools.partial(
        handle_chat_command,
        session_manager=state.session_manager,
        session=session,
        nats_client=nats_client,
        agent_id=agent_id,
    )

    subject = Topics.resolve(Topics.Agents.COMMAND, agent_id=agent_id)
    subscription = await nats_client.subscribe_with_reply(subject, bound_handler)
    log.info(
        "jarvis_serve_nats_subscribed",
        subject=subject,
        agent_id=agent_id,
    )

    # ------------------------------------------------------------------
    # 3. Install signal handlers — shared shutdown event
    # ------------------------------------------------------------------
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_shutdown(signame: str) -> None:
        log.info("jarvis_serve_nats_signal_received", signal=signame)
        shutdown_event.set()

    # ``add_signal_handler`` is not implemented on Windows asyncio loops;
    # fall back to ``signal.signal`` so the command at least exits on
    # SIGINT there too. Tests that exercise the signal-set seam patch
    # this whole helper out via ``shutdown_event.set()``.
    for sig, name in ((signal.SIGINT, "SIGINT"), (signal.SIGTERM, "SIGTERM")):
        try:
            loop.add_signal_handler(sig, _request_shutdown, name)
        except (NotImplementedError, RuntimeError):
            # Windows or non-main-thread asyncio: degrade to the
            # synchronous signal handler — still flips the asyncio Event
            # via ``loop.call_soon_threadsafe``.
            def _sync_handler(signum: int, _frame: object, _signame: str = name) -> None:
                loop.call_soon_threadsafe(_request_shutdown, _signame)

            signal.signal(sig, _sync_handler)

    log.info(
        "jarvis_serve_nats_ready",
        subject=subject,
        agent_id=agent_id,
        session_id=session.session_id,
    )

    # ------------------------------------------------------------------
    # 4. Await shutdown signal OR a terminal broker close (TASK-J006-011)
    # ------------------------------------------------------------------
    # A steady-state broker outage that exhausts nats-py's reconnect loop
    # fires the bound ``closed_cb``, which sets ``terminal_close_event``.
    # Racing it against the signal-driven ``shutdown_event`` means a
    # prolonged outage exits the process non-zero (recoverable by a
    # process/container restart) instead of the pre-J006-011 behaviour where
    # the gateway sat wedged in a ``fleet_heartbeat_failed`` loop, silently
    # off the fleet.
    terminal_close_event = state.terminal_close_event
    wait_tasks = [asyncio.create_task(shutdown_event.wait())]
    if terminal_close_event is not None:
        wait_tasks.append(asyncio.create_task(terminal_close_event.wait()))
    _, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    terminal_close = terminal_close_event is not None and terminal_close_event.is_set()

    # ------------------------------------------------------------------
    # 5. Graceful shutdown — strict ordering per TASK-J006-004 AC-005
    # ------------------------------------------------------------------
    log.info(
        "jarvis_serve_nats_shutdown_begin",
        agent_id=agent_id,
        terminal_close=terminal_close,
    )

    # 5a. Unsubscribe — stop accepting new commands.
    try:
        await subscription.unsubscribe()
    except Exception as exc:
        log.warning(
            "jarvis_serve_nats_unsubscribe_warning",
            error_class=type(exc).__name__,
            error=str(exc),
        )

    # 5b. Drain in-flight handlers (bounded by ``drain_timeout``). We
    # cannot use ``nats_client.drain()`` here because that also closes
    # the underlying connection — and we still need an open connection
    # for the deregister write below. Poll ``in_flight`` directly with
    # the same 10ms cadence the wrapper uses internally.
    deadline = loop.time() + drain_timeout
    while nats_client.in_flight > 0:
        if loop.time() >= deadline:
            log.warning(
                "jarvis_serve_nats_drain_timeout",
                in_flight=nats_client.in_flight,
                drain_timeout=drain_timeout,
            )
            break
        await asyncio.sleep(0.01)

    # 5c. Cancel the heartbeat task BEFORE the deregister hop so the
    # next heartbeat tick cannot race-resurrect the manifest after we
    # deregister it. TASK-J006-011: read the *current* task from the
    # reconnect holder so a reconnect-respawned heartbeat is cancelled,
    # not the stale boot task.
    heartbeat_task = state.active_heartbeat_task()
    if heartbeat_task is not None and not heartbeat_task.done():
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.warning(
                "jarvis_serve_nats_heartbeat_cancel_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 5d. Deregister — best-effort; the helper already swallows
    # broker-level failures.
    try:
        await deregister_from_fleet(nats_client, agent_id)
    except Exception as exc:
        log.warning(
            "jarvis_serve_nats_deregister_warning",
            agent_id=agent_id,
            error_class=type(exc).__name__,
            error=str(exc),
        )

    # 5e. Disconnect — drain the underlying nats-py client. Bounded at
    # 5s; the wrapper is idempotent so a subsequent lifecycle.shutdown
    # call (if any) is a no-op.
    try:
        await nats_client.drain(timeout=5.0)
    except Exception as exc:
        log.warning(
            "jarvis_serve_nats_drain_warning",
            error_class=type(exc).__name__,
            error=str(exc),
        )

    log.info("jarvis_serve_nats_shutdown_complete", agent_id=agent_id)

    # 5f. TASK-J006-011 — a terminal broker close is NOT a graceful exit.
    # Exit non-zero AFTER the best-effort graceful teardown so an external
    # supervisor (Docker restart policy, systemd) recovers the process with
    # a fresh registration. A signal-driven shutdown falls through to the
    # normal zero exit.
    if terminal_close:
        log.error("jarvis_serve_nats_terminal_close_exit", agent_id=agent_id)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
