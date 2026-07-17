"""Shared engine for jarvis F4 gate scripts.

Ported from api_test/qa/gates/_gatelib.py — the F4 gate-script CONTRACT is kept
VERBATIM, but the HTTP/urllib SPEC engine is REPLACED, not blind-copied: jarvis's
Slack door (`jarvis serve-nats`, src/jarvis/cli/main.py:263) is a host-process
NATS subscriber with NO HTTP endpoint to probe, so this venue's liveness signal
is systemd + journalctl, not GET /health. This module therefore provides
systemd/journalctl probe helpers in place of the api_test urllib SPEC runner,
while preserving the api_test evidence + envelope helpers byte-for-byte in
behaviour.

F4 CONTRACT (guardkit/qa/formats/gate_registry.py): a gate prints a JSON object
carrying an ``assertions`` list on stdout — each assertion ``{id, status,
observed, expected, evidence_ref}`` — and exits 0 iff every assertion passed; a
non-zero exit MUST enumerate its failing assertions. The live-gate executor
parses that envelope verbatim.

stdlib only (subprocess) so a gate runs against the live host-process deployment
with no extra dependencies. A liveness gate reads:
  - ``systemctl --user is-active <unit>``  -> the unit's active-state, and
  - ``journalctl --user -u <unit> -n 1 -o short-unix``  -> the last-log epoch,
from which a freshness age is derived. NO systemctl start/stop/enable and NO
daemon-reload is ever issued here — these are READ-ONLY probes (the same signal
the L1 socket-guard watchdog reads).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EVIDENCE_DIR = Path("qa/gates/evidence")


# ---------------------------------------------------------------------------
# Host-process probes (systemd / journalctl) — READ-ONLY.
# ---------------------------------------------------------------------------
def systemctl_is_active(unit: str, timeout: float = 10.0) -> Tuple[str, Optional[str]]:
    """Run ``systemctl --user is-active <unit>``.

    Returns ``(state, error)`` where ``state`` is the reported active-state
    ("active" / "inactive" / "failed" / "activating" / "unknown", …). ``is-active``
    exits non-zero for any non-active state but still prints the state on stdout,
    so a non-zero return code is NOT an error — only a failure to invoke the tool
    at all is (``error`` set). Never raises.
    """
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as exc:  # systemctl absent / no user bus / timeout
        return "unknown", f"systemctl is-active invocation failed: {exc}"
    state = (proc.stdout or proc.stderr or "").strip().splitlines()
    return (state[0] if state else "unknown"), None


def journal_last_epoch(unit: str, timeout: float = 10.0) -> Tuple[Optional[float], str, Optional[str]]:
    """Read the most recent journal line for ``unit`` and return its epoch.

    Uses ``journalctl --user -u <unit> -n 1 -o short-unix --no-pager``: the
    ``short-unix`` output format prefixes each line with the message's epoch
    seconds (``<epoch> host unit[pid]: …``), so the first whitespace token of the
    last line is the last-log time. Returns ``(epoch_or_None, raw_last_line,
    error)``. Never raises.
    """
    try:
        proc = subprocess.run(
            ["journalctl", "--user", "-u", unit, "-n", "1", "-o", "short-unix", "--no-pager"],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as exc:
        return None, "", f"journalctl invocation failed: {exc}"
    raw = (proc.stdout or "").strip()
    if not raw or raw.startswith("-- No entries"):
        return None, raw, None
    first_token = raw.splitlines()[-1].split(None, 1)[0]
    try:
        return float(first_token), raw, None
    except ValueError:
        # Not the expected short-unix shape — surface the raw line, no epoch.
        return None, raw, None


def journal_age_seconds(unit: str, timeout: float = 10.0) -> Tuple[Optional[float], str, Optional[str]]:
    """Return ``(age_seconds, raw_last_line, error)`` for ``unit``'s last log.

    ``age_seconds`` is ``now - last_log_epoch`` (>= 0). ``None`` when no dated
    entry is available.
    """
    epoch, raw, err = journal_last_epoch(unit, timeout=timeout)
    if err is not None or epoch is None:
        return None, raw, err
    return max(0.0, time.time() - epoch), raw, None


# ---------------------------------------------------------------------------
# F4 envelope helpers (ported VERBATIM in behaviour from api_test/_gatelib.py).
# ---------------------------------------------------------------------------
def _write_evidence(gate_id: str, payload: Dict[str, Any]) -> Optional[str]:
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE_DIR / f"{gate_id}_latest.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _emit_and_exit(assertions: List[Dict[str, Any]]) -> None:
    print(json.dumps({"assertions": assertions}))
    sys.exit(0 if all(a["status"] == "pass" for a in assertions) else 1)
