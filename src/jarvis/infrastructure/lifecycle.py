"""Application lifecycle management — startup and shutdown.

Provides :func:`build_app_state` and :func:`shutdown` for bootstrapping and
tearing down the Jarvis runtime, plus the frozen :class:`AppState`
dataclass that holds all runtime dependencies.

``build_app_state()`` configures structured logging **before** any validation
so that configuration errors are emitted as structured events.  It returns a
fully populated ``AppState`` — supervisor and session manager are always
wired.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

import structlog

from jarvis.agents import build_supervisor
from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.logging import configure
from jarvis.sessions.manager import SessionManager
from jarvis.shared.exceptions import ConfigurationError

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.store.base import BaseStore

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class AppState:
    """Immutable container for fully-wired runtime dependencies.

    Attributes:
        config: Validated application configuration.
        supervisor: The compiled LangGraph supervisor graph.
        store: The LangGraph memory store instance.
        session_manager: The session manager wired over supervisor + store.
    """

    config: JarvisConfig
    supervisor: CompiledStateGraph[Any, Any, Any, Any]
    store: BaseStore
    session_manager: SessionManager


async def build_app_state(config: JarvisConfig) -> AppState:
    """Bootstrap the Jarvis application into a fully-wired :class:`AppState`.

    Sequence:
        1. (Re-)configure structured logging at ``config.log_level``.
        2. Validate provider keys — raises :class:`ConfigurationError`
           if the selected provider's credentials are missing.
        3. Build the memory store (``InMemoryStore`` for Phase 1).
        4. Build the supervisor compiled graph.
        5. Wire a :class:`SessionManager` over supervisor + store.
        6. Return an :class:`AppState` with every field populated.

    ``configure()`` is idempotent, so callers are free to configure logging
    themselves at process entry (so that ``pydantic.ValidationError`` at
    ``JarvisConfig()`` load is emitted as a structured event) — this call
    will simply re-apply the user-configured level over that default.

    Args:
        config: A validated :class:`JarvisConfig` instance.

    Returns:
        A fully wired :class:`AppState`.

    Raises:
        ConfigurationError: If provider key validation fails.
    """
    # 1. Re-apply logging config at the user-selected level (idempotent).
    configure(config.log_level)

    log = structlog.get_logger(__name__)
    log.info("jarvis_startup_begin", supervisor_model=config.supervisor_model)

    # 2. Validate provider keys — may raise ConfigurationError.
    try:
        config.validate_provider_keys()
    except ConfigurationError:
        log.error(
            "jarvis_startup_failed",
            reason="provider_key_validation_failed",
            supervisor_model=config.supervisor_model,
        )
        raise

    # 3. Build memory store (Phase 1: in_memory only).
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    log.info("jarvis_store_ready", backend=config.memory_store_backend)

    # 4. Build supervisor and wire the session manager in a single step so
    #    AppState is fully populated on return.
    supervisor = build_supervisor(config)
    session_manager = SessionManager(supervisor=supervisor, store=store)

    state = AppState(
        config=config,
        supervisor=supervisor,
        store=store,
        session_manager=session_manager,
    )

    log.info("jarvis_startup_complete")
    return state


# Backwards-compatible alias — earlier phases imported ``startup`` by name.
startup = build_app_state


async def shutdown(state: AppState) -> None:
    """Gracefully shut down the Jarvis application.

    Idempotent — calling this multiple times on the same state does
    not raise.  Logs a structured shutdown event on completion.

    Args:
        state: The :class:`AppState` to tear down.
    """
    log = structlog.get_logger(__name__)

    try:
        if hasattr(state.store, "close"):
            try:
                state.store.close()
            except Exception:
                log.warning("jarvis_store_close_warning", exc_info=True)

        log.info("jarvis_shutdown_complete")
    except Exception:
        # Idempotent — swallow any error on repeated calls.
        log.warning("jarvis_shutdown_warning", exc_info=True)
