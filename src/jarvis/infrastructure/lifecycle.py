"""Application lifecycle management — startup and shutdown.

Provides :func:`startup` and :func:`shutdown` for bootstrapping and
tearing down the Jarvis runtime, plus the frozen :class:`AppState`
dataclass that holds all runtime dependencies.

``startup()`` configures structured logging **before** any validation
so that configuration errors are emitted as structured events.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import structlog

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.logging import configure
from jarvis.shared.exceptions import ConfigurationError

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class AppState:
    """Immutable container for runtime dependencies.

    Attributes:
        config: Validated application configuration.
        supervisor: The LangGraph supervisor agent (``None`` until
            TASK-J001-006 wires it up).
        store: The LangGraph memory store instance.
        session_manager: Session manager (``None`` until TASK-J001-007).
    """

    config: JarvisConfig
    supervisor: Any  # CompiledStateGraph — not yet available
    store: Any  # InMemoryStore (or future backend)
    session_manager: Any  # SessionManager — not yet available


async def startup(config: JarvisConfig) -> AppState:
    """Bootstrap the Jarvis application.

    Sequence:
        1. Configure structured logging (must be first).
        2. Validate provider keys — raises :class:`ConfigurationError`
           if the selected provider's credentials are missing.
        3. Build the memory store (``InMemoryStore`` for Phase 1).
        4. Return :class:`AppState` with all runtime dependencies.

    Args:
        config: A validated :class:`JarvisConfig` instance.

    Returns:
        An :class:`AppState` with all dependencies wired.

    Raises:
        ConfigurationError: If provider key validation fails.
    """
    # 1. Logging MUST be configured before anything else
    configure(config.log_level)

    log = structlog.get_logger(__name__)
    log.info("jarvis_startup_begin", supervisor_model=config.supervisor_model)

    # 2. Validate provider keys — may raise ConfigurationError
    try:
        config.validate_provider_keys()
    except ConfigurationError:
        log.error(
            "jarvis_startup_failed",
            reason="provider_key_validation_failed",
            supervisor_model=config.supervisor_model,
        )
        raise

    # 3. Build memory store (Phase 1: in_memory only)
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    log.info("jarvis_store_ready", backend=config.memory_store_backend)

    # 4. Compose AppState (supervisor and session_manager deferred to later tasks)
    state = AppState(
        config=config,
        supervisor=None,
        store=store,
        session_manager=None,
    )

    log.info("jarvis_startup_complete")
    return state


async def shutdown(state: AppState) -> None:
    """Gracefully shut down the Jarvis application.

    Idempotent — calling this multiple times on the same state does
    not raise.  Logs a structured shutdown event on completion.

    Args:
        state: The :class:`AppState` to tear down.
    """
    log = structlog.get_logger(__name__)

    try:
        # Future: cancel active sessions via state.session_manager
        # Future: flush/close store if it has a close method
        if state.store is not None and hasattr(state.store, "close"):
            try:
                state.store.close()
            except Exception:
                log.warning("jarvis_store_close_warning", exc_info=True)

        log.info("jarvis_shutdown_complete")
    except Exception:
        # Idempotent — swallow any error on repeated calls
        log.warning("jarvis_shutdown_warning", exc_info=True)
