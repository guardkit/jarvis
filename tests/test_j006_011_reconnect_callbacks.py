"""Hermetic broker-bounce tests for TASK-J006-011.

TASK-J006-010 bounded the *initial* connect at boot; it did nothing for a
steady-state broker bounce during a live ``serve-nats`` run. Before this
task the three transport lifecycle callbacks were log-only stubs, so a
mid-session bounce staled the ``agent-registry`` KV entry and the gateway
sat wedged in a ``fleet_heartbeat_failed`` loop, silently off the fleet.

These tests exercise the bound-callback machinery with ``unittest.mock`` in
place of a live broker (Phase-3 hermetic floor — no NATS server, no network):

  AC-J006-011-01  ``connect`` accepts ``lifecycle_callbacks`` and merges the
                  override key-wise; unspecified keys keep the module stubs.
  AC-J006-011-02  the bound ``reconnected_cb`` re-publishes the manifest via
                  ``register_on_fleet``.
  AC-J006-011-03  the bound ``reconnected_cb`` respawns the heartbeat task
                  when the prior task has died.
  AC-J006-011-04  the bound ``closed_cb`` sets ``terminal_close_event``.
  AC-J006-011-06  the new callbacks stay inert during a *boot* connect
                  failure (the TASK-J006-010 hard-fail is unchanged).

AC-J006-011-05 (the serve-adapter terminal-close → ``SystemExit(1)`` race)
lives in ``test_serve_nats_cli.py`` beside the serve-adapter fixtures.
AC-J006-011-07/08 are GB10 operator probes (documented in the task file);
they require a live broker and are out of scope for the hermetic suite.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import pytest
import structlog

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import fleet_registration
from jarvis.infrastructure import nats_client as nats_client_module
from jarvis.infrastructure.fleet_registration import build_jarvis_manifest
from jarvis.infrastructure.nats_client import (
    NATSClient,
    ReconnectContext,
    build_lifecycle_callbacks,
)
from jarvis.shared.exceptions import BrokerUnreachableError, NATSConnectionError

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _capture_structlog() -> Any:
    """Render structlog events to stdout so ``capsys`` can grep them."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.KeyValueRenderer(
                key_order=["event", "level"],
                sort_keys=False,
            ),
        ],
        wrapper_class=structlog.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    yield
    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> JarvisConfig:
    """A hermetic JarvisConfig (``_env_file=None`` blocks the .env loader)."""
    base: dict[str, Any] = {
        "nats_url": "nats://localhost:4222",
        "nats_credentials_path": None,
    }
    base.update(overrides)
    return JarvisConfig(_env_file=None, **base)  # type: ignore[arg-type]


def _make_ctx(config: JarvisConfig | None = None) -> ReconnectContext:
    """Build a ReconnectContext over a real manifest and an empty holder."""
    cfg = config or _make_config()
    return ReconnectContext(
        manifest=build_jarvis_manifest(cfg),
        config=cfg,
        heartbeat_task_holder=[None],
        terminal_close_event=asyncio.Event(),
    )


# ===========================================================================
# AC-J006-011-01 — connect accepts and merges lifecycle_callbacks
# ===========================================================================


class TestConnectLifecycleCallbacksOverride:
    @pytest.fixture
    def patched_connect(self) -> Any:
        fake_client = mock.MagicMock()
        fake_client.is_connected = True
        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(return_value=fake_client),
        ) as patched:
            yield patched

    async def test_override_replaces_named_callbacks_keywise(
        self, patched_connect: mock.AsyncMock
    ) -> None:
        """AC-01: supplied keys win; unspecified keys keep the stub."""
        override = {
            "reconnected_cb": mock.AsyncMock(name="bound_reconnect"),
            "closed_cb": mock.AsyncMock(name="bound_closed"),
        }
        await NATSClient.connect(_make_config(), lifecycle_callbacks=override)

        kwargs = patched_connect.call_args.kwargs
        assert kwargs["reconnected_cb"] is override["reconnected_cb"]
        assert kwargs["closed_cb"] is override["closed_cb"]
        # A key absent from the override retains the module-level stub.
        assert kwargs["disconnected_cb"] is nats_client_module._on_disconnect

    async def test_default_wires_module_stubs(self, patched_connect: mock.AsyncMock) -> None:
        """AC-01: no override → the log-only stubs are wired (test-path stability)."""
        await NATSClient.connect(_make_config())

        kwargs = patched_connect.call_args.kwargs
        assert kwargs["reconnected_cb"] is nats_client_module._on_reconnect
        assert kwargs["disconnected_cb"] is nats_client_module._on_disconnect
        assert kwargs["closed_cb"] is nats_client_module._on_closed


# ===========================================================================
# AC-J006-011-02 / -03 — bound reconnect callback
# ===========================================================================


class TestBoundReconnect:
    async def test_reconnect_republishes_manifest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-02: reconnect re-publishes the manifest via register_on_fleet."""
        register = mock.AsyncMock(name="register_on_fleet")
        monkeypatch.setattr(fleet_registration, "register_on_fleet", register)

        ctx = _make_ctx()
        ctx.nats_client = mock.MagicMock(name="wrapper")
        # A live (not-done) heartbeat task → no respawn this cycle so the
        # test isolates the re-register hop.
        live_task = mock.MagicMock()
        live_task.done.return_value = False
        ctx.heartbeat_task_holder[0] = live_task

        callbacks = build_lifecycle_callbacks(ctx)
        await callbacks["reconnected_cb"]()

        register.assert_awaited_once_with(ctx.nats_client, ctx.manifest)
        # The live task was left untouched.
        assert ctx.heartbeat_task_holder[0] is live_task

    async def test_reconnect_noop_when_client_not_yet_bound(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-06-adjacent: a reconnect that races the initial connect (the
        wrapper not yet late-bound) does not attempt a register."""
        register = mock.AsyncMock(name="register_on_fleet")
        monkeypatch.setattr(fleet_registration, "register_on_fleet", register)

        ctx = _make_ctx()
        assert ctx.nats_client is None  # boot window — not yet bound

        callbacks = build_lifecycle_callbacks(ctx)
        await callbacks["reconnected_cb"]()

        register.assert_not_awaited()

    async def test_reconnect_survives_register_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reconnect that immediately re-drops must not raise out of the callback."""
        register = mock.AsyncMock(
            name="register_on_fleet",
            side_effect=NATSConnectionError("broker dropped again"),
        )
        monkeypatch.setattr(fleet_registration, "register_on_fleet", register)

        ctx = _make_ctx()
        ctx.nats_client = mock.MagicMock(name="wrapper")
        live_task = mock.MagicMock()
        live_task.done.return_value = False
        ctx.heartbeat_task_holder[0] = live_task

        callbacks = build_lifecycle_callbacks(ctx)
        # No exception propagates.
        await callbacks["reconnected_cb"]()
        register.assert_awaited_once()

    @pytest.mark.parametrize("prior", ["dead", "none"])
    async def test_reconnect_respawns_heartbeat_when_dead(
        self, monkeypatch: pytest.MonkeyPatch, prior: str
    ) -> None:
        """AC-03: reconnect spawns a fresh heartbeat when the prior task is
        done (or was never started)."""
        monkeypatch.setattr(fleet_registration, "register_on_fleet", mock.AsyncMock())

        loop_invocations: list[tuple[Any, Any, Any]] = []

        async def _fake_heartbeat(client: Any, manifest: Any, config: Any) -> None:
            loop_invocations.append((client, manifest, config))

        monkeypatch.setattr(fleet_registration, "heartbeat_loop", _fake_heartbeat)

        ctx = _make_ctx()
        ctx.nats_client = mock.MagicMock(name="wrapper")
        if prior == "dead":
            dead_task = mock.MagicMock()
            dead_task.done.return_value = True
            ctx.heartbeat_task_holder[0] = dead_task
        else:
            ctx.heartbeat_task_holder[0] = None

        callbacks = build_lifecycle_callbacks(ctx)
        await callbacks["reconnected_cb"]()

        new_task = ctx.heartbeat_task_holder[0]
        assert isinstance(new_task, asyncio.Task)
        await new_task  # let the fake loop run to completion
        assert loop_invocations == [(ctx.nats_client, ctx.manifest, ctx.config)]

    async def test_reconnect_does_not_respawn_live_heartbeat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-03: a still-running heartbeat is left in place (no duplicate)."""
        monkeypatch.setattr(fleet_registration, "register_on_fleet", mock.AsyncMock())
        spawn = mock.MagicMock(name="heartbeat_loop")
        monkeypatch.setattr(fleet_registration, "heartbeat_loop", spawn)

        ctx = _make_ctx()
        ctx.nats_client = mock.MagicMock(name="wrapper")
        live_task = mock.MagicMock()
        live_task.done.return_value = False
        ctx.heartbeat_task_holder[0] = live_task

        callbacks = build_lifecycle_callbacks(ctx)
        await callbacks["reconnected_cb"]()

        spawn.assert_not_called()
        assert ctx.heartbeat_task_holder[0] is live_task


# ===========================================================================
# AC-J006-011-04 — bound closed callback sets terminal_close_event
# ===========================================================================


class TestBoundClosedAndDisconnect:
    async def test_closed_sets_terminal_event(self) -> None:
        """AC-04: the terminal close fires the event the CLI races on."""
        ctx = _make_ctx()
        assert not ctx.terminal_close_event.is_set()

        callbacks = build_lifecycle_callbacks(ctx)
        await callbacks["closed_cb"]()

        assert ctx.terminal_close_event.is_set()

    async def test_disconnect_does_not_set_terminal_event(self) -> None:
        """A transient disconnect is not terminal — the event stays clear."""
        ctx = _make_ctx()
        callbacks = build_lifecycle_callbacks(ctx)

        await callbacks["disconnected_cb"]()

        assert not ctx.terminal_close_event.is_set()

    async def test_error_cb_is_the_module_logger(self) -> None:
        """The override reuses the structured module-level error logger."""
        ctx = _make_ctx()
        callbacks = build_lifecycle_callbacks(ctx)
        assert callbacks["error_cb"] is nats_client_module._on_error


# ===========================================================================
# AC-J006-011-06 — boot-path hard-fail unchanged; callbacks inert at boot
# ===========================================================================


class TestBootPathRegression:
    async def test_boot_hard_fail_still_raises_with_bound_callbacks(self) -> None:
        """AC-06: a boot ConnectionRefused still hard-fails even when the
        bound lifecycle callbacks are supplied — the callbacks never fire
        during a boot connect failure because ``connect`` raises before the
        wrapper (and thus the late-bound client) exists."""
        ctx = _make_ctx()
        callbacks = build_lifecycle_callbacks(ctx)

        with (
            mock.patch.object(
                nats_client_module,
                "_nats_connect",
                new=mock.AsyncMock(side_effect=ConnectionRefusedError("no broker")),
            ),
            pytest.raises(BrokerUnreachableError),
        ):
            await NATSClient.connect(_make_config(), lifecycle_callbacks=callbacks)

        # The boot failure did not signal a terminal close (the context's
        # client was never bound; the CLI must not exit on a boot-path
        # failure via this event).
        assert not ctx.terminal_close_event.is_set()
        assert ctx.nats_client is None
