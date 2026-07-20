"""Tests for the serve-nats staleness watchdog (HB-4 L1, ops/systemd).

The watchdog lives under ``ops/systemd/serve_nats_watchdog.py`` (a stdlib-only
operational script run by a systemd user timer), not under ``src/``, so it is
loaded here by file path. These tests exercise the PURE detection/parsing logic
and the CLI orchestration with FAKE journal fixtures — no subprocess to the real
journalctl/systemctl, no network. The Slack poster is monkeypatched/captured so
the "would-be alert" is asserted without touching Slack.

Coverage:
  - classify(): FRESH (healthy rotation), the three STALE paths (DOWN /
    unrecovered-drop / silence backstop), and the no-false-alarm cases (idle-but-
    healthy quiet door, establish-scrolled-past-window).
  - parse_last_epoch(): short-unix prefix parsing + graceful no-epoch fixtures.
  - run(): exit codes 0 / 10 / 20, dry-run prints instead of posting, real post
    path calls the (mocked) Slack poster, missing-token on a real stale post is a
    loud internal error.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the ops-tree script by path (it is not an importable package).
# ---------------------------------------------------------------------------
_WATCHDOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "ops" / "systemd" / "serve_nats_watchdog.py"
)
_spec = importlib.util.spec_from_file_location("serve_nats_watchdog", _WATCHDOG_PATH)
assert _spec and _spec.loader
wd = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass can resolve the module via sys.modules.
sys.modules[_spec.name] = wd
_spec.loader.exec_module(wd)


NOW = 1_784_554_100.0


def _line(epoch: float, msg: str) -> str:
    return f'{epoch:.6f} promaxgb10-41b1 jarvis[2903526]: {{"event": "{msg}"}}'


# A healthy Socket-Mode rotation: abandon immediately FOLLOWED by established.
FRESH_ROTATION = [
    _line(NOW - 4000, "list_all: KV unavailable, returning empty list"),
    _line(NOW - 1100, "The old session (s_A) has been abandoned"),
    _line(NOW - 1099, "A new session (s_B) has been established"),
    _line(NOW - 100, "list_all: KV unavailable, returning empty list"),
]

# A wedge: reconnect/abandon is the LAST connection event, no following established.
STALE_DROP = [
    _line(NOW - 4000, "A new session (s_A) has been established"),
    _line(NOW - 2000, "list_all: KV unavailable, returning empty list"),
    _line(NOW - 600, "The session (s_A) seems to be already closed. Reconnecting..."),
    _line(NOW - 599, "The old session (s_A) has been abandoned"),
]

# Idle-but-healthy: only benign activity, no connection lifecycle lines at all
# (the last establish scrolled out of the 300-line window).
IDLE_HEALTHY = [
    _line(NOW - 3000, "list_all: KV unavailable, returning empty list"),
    _line(NOW - 200, "list_all: KV unavailable, returning empty list"),
]


# ---------------------------------------------------------------------------
# parse_last_epoch
# ---------------------------------------------------------------------------
class TestParseLastEpoch:
    def test_reads_last_short_unix_epoch(self) -> None:
        epoch, last = wd.parse_last_epoch(FRESH_ROTATION)
        assert epoch == pytest.approx(NOW - 100)
        assert "list_all" in last

    def test_no_epoch_prefix_returns_none_epoch(self) -> None:
        epoch, last = wd.parse_last_epoch([
            "Jul 18 11:55:13 host jarvis[1]: no epoch here",
        ])
        assert epoch is None
        assert last.endswith("no epoch here")

    def test_blank_lines_ignored(self) -> None:
        epoch, last = wd.parse_last_epoch(["", _line(NOW, "hello"), "  "])
        assert epoch == pytest.approx(NOW)
        assert "hello" in last

    def test_empty_input(self) -> None:
        assert wd.parse_last_epoch([]) == (None, "")


# ---------------------------------------------------------------------------
# classify — the staleness rule
# ---------------------------------------------------------------------------
class TestClassifyFresh:
    def test_healthy_rotation_is_fresh(self) -> None:
        v = wd.classify("active", FRESH_ROTATION, NOW)
        assert v.stale is False
        # abandon (trouble) is FOLLOWED by established (healthy) → not a drop.
        assert v.last_healthy_idx > v.last_trouble_idx

    def test_idle_healthy_no_conn_lines_is_fresh(self) -> None:
        # No establish/trouble markers in the window must NOT false-alarm.
        v = wd.classify("active", IDLE_HEALTHY, NOW)
        assert v.stale is False
        assert v.last_healthy_idx == -1 and v.last_trouble_idx == -1

    def test_quiet_within_backstop_is_fresh(self) -> None:
        # 5h of silence (< 6h backstop) on an active door is still fresh.
        v = wd.classify("active", IDLE_HEALTHY, NOW - 200 + 5 * 3600)
        assert v.stale is False


class TestClassifyStale:
    def test_down_unit_is_stale(self) -> None:
        v = wd.classify("failed", FRESH_ROTATION, NOW)
        assert v.stale is True
        assert "not active" in v.reason and "failed" in v.reason

    def test_inactive_unit_is_stale(self) -> None:
        assert wd.classify("inactive", FRESH_ROTATION, NOW).stale is True

    def test_unrecovered_drop_is_stale(self) -> None:
        v = wd.classify("active", STALE_DROP, NOW)
        assert v.stale is True
        assert "without recovery" in v.reason
        assert v.last_trouble_idx > v.last_healthy_idx

    def test_silence_backstop_trips_when_active_but_silent(self) -> None:
        # 7h since the last line, unit still 'active' → wedged non-logging door.
        v = wd.classify("active", IDLE_HEALTHY, NOW - 200 + 7 * 3600)
        assert v.stale is True
        assert "silent" in v.reason

    def test_down_takes_precedence_over_drop(self) -> None:
        # A down unit reports the DOWN reason even if the journal also shows a drop.
        v = wd.classify("inactive", STALE_DROP, NOW)
        assert v.stale is True
        assert "not active" in v.reason

    def test_silence_not_checked_without_epoch(self) -> None:
        # No parseable epoch → silence backstop is skipped (not a false alarm).
        no_epoch = ["Jul 18 host jarvis[1]: A new session has been established"]
        v = wd.classify("active", no_epoch, NOW + 10 * 86400)
        assert v.stale is False


# ---------------------------------------------------------------------------
# build_alert_text
# ---------------------------------------------------------------------------
class TestAlertText:
    def test_alert_names_door_and_unit_in_human_terms(self) -> None:
        v = wd.classify("failed", FRESH_ROTATION, NOW)
        text = wd.build_alert_text("jarvis-serve-nats", "myhost", v)
        assert "jarvis-serve-nats" in text
        assert "myhost" in text
        assert "Slack" in text
        # human-first: mentions requests going unanswered, not an internal id.
        assert "unanswered" in text


# ---------------------------------------------------------------------------
# run() — CLI orchestration, exit codes, dry-run vs post
# ---------------------------------------------------------------------------
def _write(tmp_path: Path, lines: list[str]) -> str:
    p = tmp_path / "journal.log"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


class TestRunExitCodes:
    def test_fresh_returns_0_and_does_not_post(self, tmp_path, capsys, monkeypatch) -> None:
        called = {}
        monkeypatch.setattr(wd, "post_to_slack",
                            lambda *a, **k: called.setdefault("posted", True))
        rc = wd.run([
            "--is-active-override", "active",
            "--journal-file", _write(tmp_path, FRESH_ROTATION),
            "--now-epoch", str(NOW),
        ])
        assert rc == wd.EXIT_FRESH
        assert "posted" not in called
        assert json.loads(capsys.readouterr().out)["outcome"] == "fresh"

    def test_stale_dry_run_returns_10_and_prints_not_posts(
        self, tmp_path, capsys, monkeypatch
    ) -> None:
        called = {}
        monkeypatch.setattr(wd, "post_to_slack",
                            lambda *a, **k: called.setdefault("posted", True))
        rc = wd.run([
            "--dry-run",
            "--is-active-override", "active",
            "--journal-file", _write(tmp_path, STALE_DROP),
            "--now-epoch", str(NOW),
        ])
        assert rc == wd.EXIT_STALE_ALERTED
        assert "posted" not in called  # dry-run never posts
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "without recovery" in out

    def test_stale_real_post_calls_slack_with_env_creds(
        self, tmp_path, capsys, monkeypatch
    ) -> None:
        captured = {}

        def fake_post(token, channel, text, timeout=15.0):
            captured.update(token=token, channel=channel, text=text)

        monkeypatch.setattr(wd, "post_to_slack", fake_post)
        monkeypatch.setenv(wd.ENV_BOT_TOKEN, "xoxb-fake")
        monkeypatch.setenv(wd.ENV_CHANNEL_ID, "C_DEFAULT")
        rc = wd.run([
            "--is-active-override", "failed",
            "--journal-file", _write(tmp_path, FRESH_ROTATION),
            "--now-epoch", str(NOW),
        ])
        assert rc == wd.EXIT_STALE_ALERTED
        assert captured["token"] == "xoxb-fake"
        assert captured["channel"] == "C_DEFAULT"
        assert "DOWN" in captured["text"]

    def test_alert_channel_override_env_wins(self, tmp_path, monkeypatch) -> None:
        captured = {}
        monkeypatch.setattr(wd, "post_to_slack",
                            lambda t, c, x, timeout=15.0: captured.update(channel=c))
        monkeypatch.setenv(wd.ENV_BOT_TOKEN, "xoxb-fake")
        monkeypatch.setenv(wd.ENV_CHANNEL_ID, "C_DEFAULT")
        monkeypatch.setenv(wd.ENV_ALERT_CHANNEL_OVERRIDE, "C_ALERTS")
        wd.run([
            "--is-active-override", "failed",
            "--journal-file", _write(tmp_path, FRESH_ROTATION),
            "--now-epoch", str(NOW),
        ])
        assert captured["channel"] == "C_ALERTS"

    def test_missing_token_on_real_stale_is_internal_error(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        monkeypatch.delenv(wd.ENV_BOT_TOKEN, raising=False)
        rc = wd.main_with_argv([
            "--is-active-override", "failed",
            "--journal-file", _write(tmp_path, FRESH_ROTATION),
            "--now-epoch", str(NOW),
        ])
        assert rc == wd.EXIT_INTERNAL_ERROR
        assert "watchdog-internal-error" in capsys.readouterr().err

    def test_missing_journal_file_is_internal_error(self, monkeypatch, capsys) -> None:
        rc = wd.main_with_argv([
            "--is-active-override", "active",
            "--journal-file", "/no/such/file.log",
            "--now-epoch", str(NOW),
        ])
        assert rc == wd.EXIT_INTERNAL_ERROR
        assert "watchdog-internal-error" in capsys.readouterr().err
