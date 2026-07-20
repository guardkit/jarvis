#!/usr/bin/env python3
"""jarvis serve-nats staleness watchdog — journalctl → Slack alert (HB-4 L1).

WHAT: the live jarvis Slack door on this box is the ``jarvis serve-nats`` systemd
*user* unit (a NATS subscriber + Slack Socket-Mode client — src/jarvis/cli/main.py).
When its Socket-Mode subscription silently drops and does NOT recover, the door
looks ``active`` to systemd but a James/Rich Slack request goes nowhere. This
watchdog READS the unit's state (``systemctl --user is-active`` + its journal) and
posts a loud alert to Slack when the door has gone quiet in a way that means the
subscription is wedged. It NEVER touches the running service (no start/stop/restart),
never contacts a seat/GPU/keepalive — it is CPU- and journal-only.

WHY NOT "no journal lines in N minutes": the HB-1 liveness prior art
(qa/gates/liveness_gate.py) already showed a HEALTHY-but-idle door is NOT silent,
and reading the real journal (``journalctl --user -u jarvis-serve-nats -n 300``,
2026-07-16..18) confirms it: an idle door still emits
``list_all: KV unavailable, returning empty list`` sporadically, and the Slack
Socket-Mode client rotates its websocket roughly every ~5h, logging
``The old session (...) has been abandoned`` immediately FOLLOWED (within ~1s) by
``A new session (...) has been established``. So a pure no-lines-in-N-minutes rule
would false-alarm on a legitimately quiet door AND on every healthy 5-hourly
rotation. The honest signal is the *shape* of the connection lifecycle, not
mere silence.

STALENESS RULE (the door is STALE → alert iff ANY of):
  1. DOWN — ``systemctl --user is-active <unit>`` is not ``active``
     (inactive / failed / activating / unknown). The door process is not running.
  2. UNRECOVERED DROP — within the scanned journal tail the most recent
     connection-TROUBLE line (reconnecting / session abandoned / already-closed /
     disconnect / websocket error / failed-to-connect) is MORE RECENT than the
     most recent connection-HEALTHY line (``a new session ... has been
     established``). A healthy ~5-hourly rotation ALWAYS logs the trouble line
     immediately followed by an ``established`` line, so rotation never trips this;
     a subscription that dropped and never re-established does. If neither marker
     is present in the window (the establish scrolled past the tail) this signal
     is silent — is-active + the silence backstop carry the verdict, so a long
     healthy-idle stretch is never a false alarm.
  3. SILENCE BACKSTOP — is-active reports ``active`` but the newest journal line
     is older than ``--max-silence-seconds`` (default 21600s = 6h, chosen larger
     than the observed ~5h max gap between guaranteed Socket-Mode rotation log
     events). A door that has logged NOTHING for longer than a full rotation cycle
     is wedged even while the process lingers.

The door is FRESH/QUIET (→ no alert) otherwise: process ``active``, the last
connection event is a healthy ``established`` (or there is no trouble at all in
the window), and a journal line within the silence window.

SLACK CREDS: reused from jarvis's OWN env, at RUNTIME, via the SAME
EnvironmentFile the serve-nats unit sources (``%h/.config/guardkit/jarvis.env``).
No secret is read from or written to the repo. The exact variable names are the
ones jarvis's own Slack notifier uses (src/jarvis/config/settings.py, env_prefix
``JARVIS_``): the bot token ``JARVIS_SLACK_BOT_TOKEN`` and the channel
``JARVIS_SLACK_CHANNEL_ID``. An optional ``JARVIS_WATCHDOG_ALERT_CHANNEL_ID``
overrides the destination channel so alerts can go somewhere other than the main
notification channel without touching jarvis config.

EXIT CODES (distinct outcomes — a broken watchdog must NEVER look like a healthy
door):
  0  = door fresh/quiet — healthy, no alert.
  10 = door STALE — alert dispatched (posted to Slack, or printed under --dry-run).
       Marked a systemd success via ``SuccessExitStatus=10`` on the .service so a
       fired alert does not read as a unit failure; the alert itself is the signal.
  20 = watchdog-internal-error — could not read the journal, could not post to
       Slack, missing token on a real post, bad arguments, etc. NON-ZERO and
       distinct from 0 so systemd marks the unit failed and the operator sees it.

Stdlib only (subprocess for the read-only probes, urllib for chat.postMessage).
Deliberately run under the SYSTEM ``/usr/bin/python3`` (see the .service), not the
jarvis venv, so the watchdog stays independent of the thing it watches.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

DEFAULT_UNIT = "jarvis-serve-nats"
DEFAULT_MAX_SILENCE_SECONDS = 21600.0  # 6h > observed ~5h max healthy rotation gap
DEFAULT_LINES = 300
SLACK_POST_URL = "https://slack.com/api/chat.postMessage"

# Exit codes.
EXIT_FRESH = 0
EXIT_STALE_ALERTED = 10
EXIT_INTERNAL_ERROR = 20

# Env var names — jarvis's OWN Slack creds (src/jarvis/config/settings.py).
ENV_BOT_TOKEN = "JARVIS_SLACK_BOT_TOKEN"
ENV_CHANNEL_ID = "JARVIS_SLACK_CHANNEL_ID"
ENV_ALERT_CHANNEL_OVERRIDE = "JARVIS_WATCHDOG_ALERT_CHANNEL_ID"

# Connection-lifecycle markers (matched case-insensitively on the message text).
# HEALTHY: the definitive "subscription is live again" marker from slack_sdk's
# Socket-Mode client.
HEALTHY_CONN_RE = re.compile(r"has been established", re.IGNORECASE)
# TROUBLE: a drop / reconnect attempt / transport error. "has been abandoned" and
# "Reconnecting" also occur during a HEALTHY rotation, but there they are always
# followed by a newer HEALTHY line, so the last-index comparison never false-fires.
TROUBLE_CONN_RE = re.compile(
    r"reconnect"
    r"|has been abandoned"
    r"|already closed"
    r"|disconnect"
    r"|websocket.*(?:error|closed|closing)"
    r"|connection.*(?:error|closed|lost|refused)"
    r"|failed to (?:send|connect|establish)",
    re.IGNORECASE,
)

# A short-unix journal line: "<epoch.frac> host unit[pid]: message".
_EPOCH_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)?)\s")


class WatchdogError(Exception):
    """A watchdog-internal failure (→ exit 20). Distinct from a stale door."""


@dataclass
class Verdict:
    stale: bool
    reason: str  # human sentence for the alert / log
    is_active: str
    journal_age_seconds: Optional[float]
    last_line: str
    last_healthy_idx: int
    last_trouble_idx: int


# ---------------------------------------------------------------------------
# Pure detection (unit-tested; no subprocess, no network).
# ---------------------------------------------------------------------------
def parse_last_epoch(lines: List[str]) -> Tuple[Optional[float], str]:
    """Return (last_epoch, last_nonblank_line) from short-unix journal lines.

    ``last_epoch`` is the epoch of the most recent line that carries a short-unix
    epoch prefix, or None if none do (e.g. a fixture without epoch prefixes — then
    the silence backstop is skipped rather than mis-firing).
    """
    last_line = ""
    last_epoch: Optional[float] = None
    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        last_line = line
        m = _EPOCH_PREFIX_RE.match(line)
        if m:
            try:
                last_epoch = float(m.group(1))
            except ValueError:
                pass
    return last_epoch, last_line


def classify(
    is_active: str,
    journal_lines: List[str],
    now_epoch: float,
    max_silence_seconds: float = DEFAULT_MAX_SILENCE_SECONDS,
) -> Verdict:
    """Classify door state from probe inputs. Pure — the heart of the watchdog.

    Precedence: DOWN (is-active) → UNRECOVERED DROP → SILENCE BACKSTOP → FRESH.
    """
    last_healthy_idx = -1
    last_trouble_idx = -1
    for idx, raw in enumerate(journal_lines):
        # Order by line position: journalctl prints oldest→newest, so a larger
        # index is a more recent event. HEALTHY is checked first so a line that is
        # itself the establish is never miscounted as trouble.
        if HEALTHY_CONN_RE.search(raw):
            last_healthy_idx = idx
        elif TROUBLE_CONN_RE.search(raw):
            last_trouble_idx = idx

    last_epoch, last_line = parse_last_epoch(journal_lines)
    age = None if last_epoch is None else max(0.0, now_epoch - last_epoch)

    # 1. DOWN.
    if is_active != "active":
        return Verdict(True, f"unit is not active (systemctl reports '{is_active}')",
                       is_active, age, last_line, last_healthy_idx, last_trouble_idx)

    # 2. UNRECOVERED DROP — a trouble line more recent than the last established.
    if last_trouble_idx > last_healthy_idx:
        return Verdict(
            True,
            "Slack Socket-Mode subscription dropped without recovery "
            "(last connection event is a reconnect/abandon with no following "
            "'session established')",
            is_active, age, last_line, last_healthy_idx, last_trouble_idx,
        )

    # 3. SILENCE BACKSTOP — active but silent past a full rotation cycle.
    if age is not None and age > max_silence_seconds:
        return Verdict(
            True,
            f"unit is active but its journal has been silent for {age:.0f}s "
            f"(> {max_silence_seconds:.0f}s backstop) — a wedged, non-logging door",
            is_active, age, last_line, last_healthy_idx, last_trouble_idx,
        )

    return Verdict(False, "door is active and its Slack subscription is live",
                   is_active, age, last_line, last_healthy_idx, last_trouble_idx)


def build_alert_text(unit: str, host: str, v: Verdict) -> str:
    """Human-first Slack alert (plain text; no internal IDs as the headline)."""
    age_str = "unknown" if v.journal_age_seconds is None else f"{v.journal_age_seconds:.0f}s ago"
    return (
        f":rotating_light: jarvis Slack door looks DOWN on {host}\n"
        f"The `{unit}` service — the door that receives your Slack requests — is stale: "
        f"{v.reason}.\n"
        f"systemctl is-active: {v.is_active}. Last log line: {age_str}.\n"
        f"Requests to jarvis in Slack may be going unanswered. "
        f"Check it with: journalctl --user -u {unit} -n 50 --no-pager"
    )


# ---------------------------------------------------------------------------
# Side-effecting edges (probes + Slack post).
# ---------------------------------------------------------------------------
def probe_is_active(unit: str, timeout: float = 10.0) -> str:
    """``systemctl --user is-active <unit>`` → state string. Raises on invoke fail."""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as exc:  # systemctl absent / no user bus / timeout
        raise WatchdogError(f"systemctl --user is-active invocation failed: {exc}") from exc
    state = (proc.stdout or proc.stderr or "").strip().splitlines()
    return state[0] if state else "unknown"


def read_journal(unit: str, lines: int, timeout: float = 20.0) -> List[str]:
    """Read the last ``lines`` journal entries for ``unit`` in short-unix format."""
    try:
        proc = subprocess.run(
            ["journalctl", "--user", "-u", unit, "-n", str(lines),
             "-o", "short-unix", "--no-pager"],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as exc:
        raise WatchdogError(f"journalctl invocation failed: {exc}") from exc
    if proc.returncode != 0:
        raise WatchdogError(
            f"journalctl exited {proc.returncode}: {(proc.stderr or '').strip()}"
        )
    return (proc.stdout or "").splitlines()


def post_to_slack(token: str, channel: str, text: str, timeout: float = 15.0) -> None:
    """POST chat.postMessage (mrkdwn off), mirroring jarvis's notifier call shape.

    Raises WatchdogError on any transport error or a non-ok Slack response — a
    stale door whose alert did not land is a watchdog-internal failure, not a
    silent success.
    """
    body = json.dumps({"channel": channel, "text": text, "mrkdwn": False}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_POST_URL, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise WatchdogError(f"Slack chat.postMessage transport error: {exc}") from exc
    except Exception as exc:
        raise WatchdogError(f"Slack chat.postMessage failed: {exc}") from exc
    if not payload.get("ok"):
        raise WatchdogError(f"Slack chat.postMessage returned not-ok: {payload.get('error')}")


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="jarvis serve-nats staleness watchdog — journalctl → Slack alert.",
    )
    p.add_argument("--unit", default=DEFAULT_UNIT, help=f"user unit (default {DEFAULT_UNIT})")
    p.add_argument("--lines", type=int, default=DEFAULT_LINES,
                   help=f"journal tail length (default {DEFAULT_LINES})")
    p.add_argument("--max-silence-seconds", type=float, default=DEFAULT_MAX_SILENCE_SECONDS,
                   help="silence-backstop window (default 21600 = 6h)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the would-be alert instead of posting to Slack")
    p.add_argument("--channel", default=None,
                   help="override the alert channel id (else env)")
    # Test seams: feed substitute journal/service state without touching the box.
    src = p.add_mutually_exclusive_group()
    src.add_argument("--journal-file", default=None,
                     help="read journal (short-unix) from a file instead of journalctl")
    src.add_argument("--stdin", action="store_true",
                     help="read journal (short-unix) from stdin instead of journalctl")
    p.add_argument("--is-active-override", default=None,
                   help="supply the is-active state instead of calling systemctl")
    p.add_argument("--now-epoch", type=float, default=None,
                   help="override 'now' (epoch seconds) for deterministic silence tests")
    return p.parse_args(argv)


def resolve_channel(args: argparse.Namespace) -> Optional[str]:
    if args.channel:
        return args.channel
    return os.environ.get(ENV_ALERT_CHANNEL_OVERRIDE) or os.environ.get(ENV_CHANNEL_ID)


def run(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    host = socket.gethostname()
    now_epoch = args.now_epoch if args.now_epoch is not None else time.time()

    # Gather state (from overrides for tests, else the live read-only probes).
    if args.is_active_override is not None:
        is_active = args.is_active_override
    else:
        is_active = probe_is_active(args.unit)

    if args.journal_file is not None:
        try:
            with open(args.journal_file, "r", encoding="utf-8") as fh:
                journal_lines = fh.read().splitlines()
        except OSError as exc:
            raise WatchdogError(f"could not read --journal-file: {exc}") from exc
    elif args.stdin:
        journal_lines = sys.stdin.read().splitlines()
    else:
        journal_lines = read_journal(args.unit, args.lines)

    verdict = classify(is_active, journal_lines, now_epoch, args.max_silence_seconds)

    if not verdict.stale:
        print(json.dumps({
            "outcome": "fresh", "unit": args.unit, "host": host,
            "is_active": verdict.is_active, "reason": verdict.reason,
            "journal_age_seconds": verdict.journal_age_seconds,
        }))
        return EXIT_FRESH

    alert = build_alert_text(args.unit, host, verdict)

    if args.dry_run:
        print("=== DRY RUN — would post to Slack ===")
        print(alert)
        print(json.dumps({
            "outcome": "stale", "dry_run": True, "unit": args.unit, "host": host,
            "is_active": verdict.is_active, "reason": verdict.reason,
            "journal_age_seconds": verdict.journal_age_seconds,
        }))
        return EXIT_STALE_ALERTED

    channel = resolve_channel(args)
    token = os.environ.get(ENV_BOT_TOKEN)
    if not token:
        raise WatchdogError(
            f"door is STALE but {ENV_BOT_TOKEN} is unset — cannot post the alert"
        )
    if not channel:
        raise WatchdogError(
            f"door is STALE but no alert channel ({ENV_ALERT_CHANNEL_OVERRIDE} / "
            f"{ENV_CHANNEL_ID}) is set — cannot post the alert"
        )
    post_to_slack(token, channel, alert)
    print(json.dumps({
        "outcome": "stale", "dry_run": False, "unit": args.unit, "host": host,
        "channel": channel, "is_active": verdict.is_active, "reason": verdict.reason,
        "journal_age_seconds": verdict.journal_age_seconds,
    }))
    return EXIT_STALE_ALERTED


def main_with_argv(argv: Optional[List[str]] = None) -> int:
    """run() wrapped so every internal failure becomes a loud, distinct exit 20.

    A broken watchdog must NEVER exit 0 (which would read as a healthy door).
    """
    try:
        return run(argv)
    except WatchdogError as exc:
        print(f"watchdog-internal-error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    except Exception as exc:  # any unexpected failure is also loud, never silent
        print(f"watchdog-internal-error (unexpected): {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def main() -> int:
    return main_with_argv()


if __name__ == "__main__":
    sys.exit(main())
