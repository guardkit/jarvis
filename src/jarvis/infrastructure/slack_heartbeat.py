"""The Slack gateway's heartbeat file — how its Socket Mode session is.

WHY THIS EXISTS (26 September 2026, rollout step 1, build item E3-j2).
Nothing outside this process could tell whether the gateway's Slack
connection was alive. The gateway publishes no port and answers nobody on
purpose: it dials out to Slack over a WebSocket and out to the bus, and
both are outbound. So the only two things anything outside could ask were
"is its container running" and "does the bus hold a connection from its
account" — and neither of those says a word about Slack. The gateway can
hold the bus open, be perfectly subscribed, and answer nothing at all from
Slack, which is exactly the failure the retired host watchdog was written
for (``ops/systemd/serve_nats_watchdog.py``).

So the gateway writes down how its Slack session is, and the estate's watch
reads that file. A FILE AND NOT A ROUTE, deliberately: a route would mean
this process listening on a port, which it does not do and should not start
doing to be health-checked. The shape is the one the memory relay already
uses and the estate already knows how to read — a small file inside a
volume of the writer's own, mounted read-only by the reader.

WHAT IT SAYS

    {"state": "connected",
     "last_event_at": "2026-09-26T16:40:00.123456+00:00",
     "last_event_kind": "inbound_request",
     "last_state_change_at": "2026-09-26T12:01:11.902003+00:00",
     "written_at": "2026-09-26T16:40:00.124881+00:00"}

``state`` is one of ``connecting``, ``connected`` and ``disconnected``.
``last_event_at`` is the clock time of the last thing that happened on the
Socket Mode session — a connect, a disconnect, a frame from Slack, or an
inbound request — which is the one number a reader can hold a freshness
rule against. ``last_state_change_at`` is when ``state`` last became
something else. ``written_at`` is when this file was last rewritten, and
equals ``last_event_at`` except when the state was rewritten without a new
event.

WHY FRESHNESS NEEDS A LONG WINDOW, and it is the retired watchdog's own
reason. A healthy but idle door receives no Slack envelopes for hours, so
"no envelope recently" is not evidence of anything. What a healthy session
does do is rotate: slack-sdk's client is given a new WebSocket roughly
every five hours, and the rotation is a close and a fresh connect, both of
which rewrite this file — as do Slack's own control frames on the session.
So a reader's window has to be longer than a full rotation, which is why
the retired watchdog chose six hours and why the estate's watch defaults to
the same. Anything shorter turns a quiet Friday into an alarm.

IT NEVER RAISES AND IT NEVER BLOCKS THE DOOR. A gateway that cannot write
its heartbeat is a gateway whose health is unknown, not a gateway that
should fall over: every failure here is logged once per kind and swallowed.
An absent or unreadable file is what the estate's watch reports as
``unknown``, which is never read as healthy.

THE WRITE IS ATOMIC — a temporary file beside the real one, flushed, then
renamed over it. A reader on the fifteen-minute timer must never catch a
half-written file and call it unparseable; ``os.replace`` on the same
filesystem is atomic, so a reader sees either the previous complete file or
the new complete one.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import structlog

logger = structlog.get_logger(__name__)

#: The three words ``state`` may carry. ``connecting`` is written before the
#: first connect is attempted, so a gateway wedged in its own start-up says
#: so rather than leaving no file at all.
STATE_CONNECTING: Final = "connecting"
STATE_CONNECTED: Final = "connected"
STATE_DISCONNECTED: Final = "disconnected"

__all__ = [
    "STATE_CONNECTED",
    "STATE_CONNECTING",
    "STATE_DISCONNECTED",
    "SlackHeartbeatWriter",
    "create_slack_heartbeat_writer",
]


def _now() -> str:
    """The clock, as a plain ISO-8601 instant with its offset."""
    return datetime.now(UTC).isoformat()


class SlackHeartbeatWriter:
    """Writes the gateway's Socket Mode state to one small file.

    One instance per process, held by the Socket Mode wrapper. Every method
    rewrites the whole file: it is a few hundred bytes and a partial update
    of a health file is a worse thing than a rewrite.

    Args:
        path: Where the file goes. Its parent directory is created if it is
            missing — in the estate that is the mount point of a named
            volume, which exists already.
    """

    __slots__ = ("_last_event_at", "_last_event_kind", "_last_state_change_at", "_path", "_state")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._state: str | None = None
        self._last_state_change_at: str | None = None
        self._last_event_at: str | None = None
        self._last_event_kind: str | None = None

    @property
    def path(self) -> Path:
        """The file this writer keeps."""
        return self._path

    @property
    def state(self) -> str | None:
        """The state last written, or ``None`` before the first write."""
        return self._state

    def record(self, state: str, *, kind: str) -> None:
        """Write the file, with ``state`` and this moment as the last event.

        Args:
            state: One of the three module-level state words.
            kind: A short, plain word for what happened — ``connect``,
                ``disconnect``, ``inbound_request``, ``slack_frame``,
                ``session_closed``, ``session_error``. It is written into
                the file so a person reading it by hand can tell a rotation
                from an envelope.
        """
        now = _now()
        if state != self._state:
            self._state = state
            self._last_state_change_at = now
        self._last_event_at = now
        self._last_event_kind = kind
        self._write(
            {
                "state": self._state,
                "last_event_at": self._last_event_at,
                "last_event_kind": self._last_event_kind,
                "last_state_change_at": self._last_state_change_at,
                "written_at": now,
            }
        )

    def _write(self, document: dict[str, Any]) -> None:
        """Write ``document`` atomically. Never raises.

        The temporary file is made in the SAME directory as the real one, so
        the rename is within one filesystem and is therefore atomic. A
        temporary file left behind by a crash is removed here rather than
        accumulating in the volume.
        """
        body = json.dumps(document, indent=2, sort_keys=True) + "\n"
        tmp_path: str | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handle_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._path.parent),
                prefix=f".{self._path.name}.",
                suffix=".tmp",
            )
            with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            # World-readable: the watch runs as a different user in a
            # different container and mounts this volume read-only. There is
            # nothing secret in it — three times and a word.
            os.chmod(tmp_path, 0o644)
            os.replace(tmp_path, self._path)
            tmp_path = None
        except OSError as exc:
            logger.warning(
                "slack_heartbeat_write_failed",
                path=str(self._path),
                error_class=type(exc).__name__,
                error=str(exc),
                detail=(
                    "the Slack gateway could not write its heartbeat file, so anything "
                    "watching it will report the Slack session as unknown rather than "
                    "healthy. The door itself is unaffected."
                ),
            )
        finally:
            if tmp_path is not None:
                # Best-effort tidy-up: a temporary file left in the volume by
                # a failed write is litter, not a second failure.
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)


def create_slack_heartbeat_writer(path: Path | str | None) -> SlackHeartbeatWriter | None:
    """Build the writer, or ``None`` when no path is configured.

    ``JARVIS_SLACK_HEARTBEAT_PATH`` unset — and a blank value — means no
    heartbeat is written, which is what every jarvis process did until
    today. The estate sets it for the gateway; nothing else has to.
    """
    if path is None:
        return None
    text = str(path).strip()
    if not text:
        return None
    return SlackHeartbeatWriter(Path(text))
