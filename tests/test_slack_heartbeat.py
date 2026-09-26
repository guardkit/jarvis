"""The gateway's Slack heartbeat file (E3-j2) — the writer and the wrapper.

WHAT IS BEING PINNED. Two things, in two halves of this file:

* the writer — an atomic rewrite (no reader ever sees a half-written file),
  the three state words, and a failure that is swallowed rather than taking
  the door down with it;
* the Socket Mode wrapper — that a connect, a disconnect, an inbound
  envelope, a session close and a transport error each rewrite the file, and
  that a close does NOT record a drop when the SDK has already reconnected,
  because a healthy session rotates roughly every five hours and calling
  each rotation a failure is the precise false alarm the retired host
  watchdog was written to avoid.

No Slack anywhere in this file: the SDK client is a stand-in and every token
is nonsense.

Rollout step 1, build item E3-j2, 26 September 2026.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.infrastructure.slack_heartbeat import (
    STATE_CONNECTED,
    STATE_CONNECTING,
    STATE_DISCONNECTED,
    SlackHeartbeatWriter,
    create_slack_heartbeat_writer,
)
from jarvis.infrastructure.slack_reply import SlackSocketModeReplyClient


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# The writer
# ===========================================================================


class TestTheWriterSaysWhatItSees:
    def test_the_three_words_and_the_two_times(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        writer = SlackHeartbeatWriter(path)

        writer.record(STATE_CONNECTING, kind="connect_started")
        first = _read(path)
        assert first["state"] == "connecting"
        assert first["last_event_kind"] == "connect_started"
        assert first["last_event_at"] == first["last_state_change_at"]

        writer.record(STATE_CONNECTED, kind="connect")
        second = _read(path)
        assert second["state"] == "connected"
        # The state changed, so the change time moved with the event time.
        assert second["last_state_change_at"] == second["last_event_at"]
        assert second["last_state_change_at"] > first["last_state_change_at"]

    def test_an_event_in_the_same_state_moves_only_the_event_time(self, tmp_path: Path) -> None:
        """An idle door's frames keep the file fresh without a state change."""
        path = tmp_path / "slack-heartbeat.json"
        writer = SlackHeartbeatWriter(path)
        writer.record(STATE_CONNECTED, kind="connect")
        changed_at = _read(path)["last_state_change_at"]

        writer.record(STATE_CONNECTED, kind="slack_frame")
        after = _read(path)
        assert after["last_state_change_at"] == changed_at
        assert after["last_event_at"] > changed_at
        assert after["last_event_kind"] == "slack_frame"

    def test_every_write_is_whole_and_leaves_nothing_behind(self, tmp_path: Path) -> None:
        """Atomic: one file at the end, no temporary files in the volume."""
        path = tmp_path / "slack-heartbeat.json"
        writer = SlackHeartbeatWriter(path)
        for _ in range(5):
            writer.record(STATE_CONNECTED, kind="slack_frame")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["slack-heartbeat.json"]
        assert _read(path)["state"] == "connected"

    def test_the_rename_is_what_puts_the_file_there(self, tmp_path: Path) -> None:
        """The proof it is write-then-rename and not write-in-place.

        The real file is never opened for writing: it only ever appears by
        ``os.replace``. A reader on a timer therefore sees the previous whole
        file or the new whole file, never a half of either.
        """
        path = tmp_path / "slack-heartbeat.json"
        writer = SlackHeartbeatWriter(path)
        writer.record(STATE_CONNECTED, kind="connect")

        renames: list[tuple[str, str]] = []
        real_replace = os.replace

        def spy(src: Any, dst: Any, *args: Any, **kwargs: Any) -> None:
            renames.append((str(src), str(dst)))
            real_replace(src, dst, *args, **kwargs)

        with patch("jarvis.infrastructure.slack_heartbeat.os.replace", spy):
            writer.record(STATE_DISCONNECTED, kind="disconnect")

        assert len(renames) == 1
        source, destination = renames[0]
        assert destination == str(path)
        assert source != str(path)
        assert Path(source).parent == path.parent  # same filesystem
        assert _read(path)["state"] == "disconnected"

    def test_it_makes_its_own_directory(self, tmp_path: Path) -> None:
        path = tmp_path / "not-there-yet" / "slack-heartbeat.json"
        SlackHeartbeatWriter(path).record(STATE_CONNECTED, kind="connect")
        assert _read(path)["state"] == "connected"

    def test_a_write_that_cannot_happen_does_not_raise(self, tmp_path: Path) -> None:
        """A door whose health file fails is a door, not a failure.

        The gateway carries Rich's Slack traffic. A volume it cannot write
        must leave the watch saying 'unknown' — never take the door down.
        """
        blocked = tmp_path / "a-file-not-a-directory"
        blocked.write_text("in the way", encoding="utf-8")
        writer = SlackHeartbeatWriter(blocked / "slack-heartbeat.json")
        writer.record(STATE_CONNECTED, kind="connect")  # must not raise
        assert writer.state == "connected"

    def test_the_file_is_readable_by_the_watch(self, tmp_path: Path) -> None:
        """The watch is another container's user and mounts this read-only."""
        path = tmp_path / "slack-heartbeat.json"
        SlackHeartbeatWriter(path).record(STATE_CONNECTED, kind="connect")
        assert path.stat().st_mode & 0o044 == 0o044


class TestNoPathMeansNoFile:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_unset_or_blank_writes_nothing(self, value: Any) -> None:
        assert create_slack_heartbeat_writer(value) is None

    def test_a_path_gives_a_writer_for_that_path(self, tmp_path: Path) -> None:
        writer = create_slack_heartbeat_writer(tmp_path / "h.json")
        assert writer is not None
        assert writer.path == tmp_path / "h.json"


# ===========================================================================
# The Socket Mode wrapper writes it
# ===========================================================================


def _stand_in_sdk_client(*, connected: bool = True) -> MagicMock:
    """A stand-in for slack-sdk's Socket Mode client. No Slack, no sockets."""
    client = MagicMock()
    client.socket_mode_request_listeners = []
    client.on_close_listeners = []
    client.on_error_listeners = []
    client.on_message_listeners = []
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.is_connected = AsyncMock(return_value=connected)
    client.send_socket_mode_response = AsyncMock()
    return client


class TestTheWrapperRecordsItsSession:
    @pytest.mark.asyncio
    async def test_connect_then_disconnect(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client()
        states: list[str] = []

        async def _record_state_at_connect() -> None:
            states.append(_read(path)["state"])

        sdk.connect = AsyncMock(side_effect=_record_state_at_connect)

        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()
            assert _read(path)["state"] == "connected"
            await wrapper.stop()

        # 'connecting' was on disk BEFORE the connect was attempted, so a
        # gateway wedged in its own start-up says so rather than being silent.
        assert states == ["connecting"]
        assert _read(path)["state"] == "disconnected"
        assert _read(path)["last_event_kind"] == "disconnect"

    @pytest.mark.asyncio
    async def test_a_connect_that_fails_records_a_lost_session(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client()
        sdk.connect = AsyncMock(side_effect=RuntimeError("no Slack here"))

        with (
            patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk),
            pytest.raises(RuntimeError),
        ):
            await wrapper.start()

        # Not left saying 'connecting' for ever: this process is not going to
        # connect, and the watch must be able to call the session lost.
        assert _read(path)["state"] == "disconnected"
        assert _read(path)["last_event_kind"] == "connect_failed"

    @pytest.mark.asyncio
    async def test_an_inbound_envelope_refreshes_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client()
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()
        before = _read(path)["last_event_at"]

        await wrapper._on_request(
            sdk, SimpleNamespace(type="events_api", envelope_id="env-1", payload={})
        )
        after = _read(path)
        assert after["state"] == "connected"
        assert after["last_event_kind"] == "inbound_request"
        assert after["last_event_at"] > before

    @pytest.mark.asyncio
    async def test_the_three_lifecycle_listeners_are_registered_once(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client()
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()
            await wrapper.start()  # idempotent
        assert len(sdk.on_close_listeners) == 1
        assert len(sdk.on_error_listeners) == 1
        assert len(sdk.on_message_listeners) == 1
        assert len(sdk.socket_mode_request_listeners) == 1

    @pytest.mark.asyncio
    async def test_no_heartbeat_configured_registers_no_lifecycle_listeners(
        self,
    ) -> None:
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
        )
        sdk = _stand_in_sdk_client()
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()
        assert sdk.on_close_listeners == []
        assert sdk.on_error_listeners == []
        assert sdk.on_message_listeners == []


class TestARotationIsNotADrop:
    """The false alarm this design had to avoid, pinned as a test.

    slack-sdk answers a CLOSE frame by connecting to a new endpoint and only
    THEN running its close listeners, so by the time the wrapper is called a
    healthy rotation has already recovered. The file must say 'connected'.
    """

    @pytest.mark.asyncio
    async def test_a_close_after_a_successful_reconnect_stays_connected(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client(connected=True)
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()

        await sdk.on_close_listeners[0](MagicMock())
        after = _read(path)
        assert after["state"] == "connected"
        assert after["last_event_kind"] == "session_closed"

    @pytest.mark.asyncio
    async def test_a_close_with_no_reconnect_is_a_drop(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client(connected=True)
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()

        sdk.is_connected = AsyncMock(return_value=False)
        await sdk.on_close_listeners[0](MagicMock())
        assert _read(path)["state"] == "disconnected"

    @pytest.mark.asyncio
    async def test_a_transport_error_with_no_reconnect_is_a_drop(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client(connected=False)
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()

        await sdk.on_error_listeners[0](MagicMock())
        after = _read(path)
        assert after["state"] == "disconnected"
        assert after["last_event_kind"] == "session_error"

    @pytest.mark.asyncio
    async def test_a_frame_from_slack_keeps_an_idle_door_fresh(self, tmp_path: Path) -> None:
        path = tmp_path / "slack-heartbeat.json"
        wrapper = SlackSocketModeReplyClient(
            app_token="xapp-nonsense",
            handler=None,
            web_client=AsyncMock(),
            events_handler=MagicMock(),
            heartbeat=SlackHeartbeatWriter(path),
        )
        sdk = _stand_in_sdk_client()
        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient", return_value=sdk):
            await wrapper.start()
        before = _read(path)["last_event_at"]

        await sdk.on_message_listeners[0](MagicMock())
        after = _read(path)
        assert after["state"] == "connected"
        assert after["last_event_kind"] == "slack_frame"
        assert after["last_event_at"] > before


class TestTheSettingIsWhatTurnsItOn:
    """``JARVIS_SLACK_HEARTBEAT_PATH`` and nothing else."""

    def test_the_library_really_has_the_three_listener_lists(self) -> None:
        """Confirmed against the installed slack-sdk, not assumed."""
        from slack_sdk.socket_mode.aiohttp import SocketModeClient

        annotations = SocketModeClient.__annotations__
        assert "on_close_listeners" in annotations
        assert "on_error_listeners" in annotations
        assert "on_message_listeners" in annotations
