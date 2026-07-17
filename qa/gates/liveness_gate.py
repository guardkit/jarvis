#!/usr/bin/env python3
"""F4 SERVE-NATS-LIVENESS gate — the jarvis Slack door is alive on this box.

Registered in qa/gates/registry.yaml as gate id ``serve-nats-liveness``. jarvis's
real Slack ingress on-box is the ``jarvis serve-nats`` systemd *user* unit (a NATS
subscriber with NO HTTP endpoint — src/jarvis/cli/main.py:263), so its liveness
CANNOT be study-tutor's GET /healthz. Instead this gate READS two host-process
signals (never mutating the box):

  1. ``systemctl --user is-active <unit>``  -> the unit reports ``active``.
  2. ``journalctl --user -u <unit>``        -> the door has a dated log entry
     within a freshness window (a totally-silent unit is a wedged door).

Because ``serve-nats`` refuses to start without a live NATS broker
(src/jarvis/cli/main.py:354), a down broker makes the unit inactive/failed — that
is an ENVIRONMENT condition, not a product defect. This gate honestly reports the
observed red; the ENVIRONMENT-vs-product attribution is the live-gate driver's
job (qa/gates/local_live_gate.py's F16 probe short-circuits to environment_fail
BEFORE this gate runs when the door is down).

Config (env, both optional):
  JARVIS_SERVE_NATS_UNIT         unit name (default: jarvis-serve-nats)
  JARVIS_SERVE_NATS_MAX_LOG_AGE_S  freshness window in seconds (default: 86400).
      Deliberately generous: the primary liveness signal is is-active; the
      freshness read only catches a unit that has gone entirely silent, never an
      idle-but-healthy door.

F4 contract via _gatelib: exit 0 = pass; non-zero enumerates failures in the JSON
results envelope.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _gatelib  # noqa: E402

GATE_ID = "serve-nats-liveness"
DEFAULT_UNIT = "jarvis-serve-nats"
DEFAULT_MAX_LOG_AGE_S = 86400.0


def main() -> None:
    unit = os.environ.get("JARVIS_SERVE_NATS_UNIT") or DEFAULT_UNIT
    try:
        max_age = float(os.environ.get("JARVIS_SERVE_NATS_MAX_LOG_AGE_S") or DEFAULT_MAX_LOG_AGE_S)
    except ValueError:
        max_age = DEFAULT_MAX_LOG_AGE_S

    state, state_err = _gatelib.systemctl_is_active(unit)
    age, raw_last, journal_err = _gatelib.journal_age_seconds(unit)

    evidence = _gatelib._write_evidence(GATE_ID, {
        "unit": unit,
        "is_active": state,
        "is_active_error": state_err,
        "journal_last_line": raw_last,
        "journal_age_seconds": age,
        "journal_error": journal_err,
        "max_log_age_seconds": max_age,
    })

    assertions: List[Dict[str, Any]] = []

    # 1. is-active. If systemctl itself could not be invoked, that is an honest
    #    red observed by the probe (the driver's F16 attributes environment).
    if state_err is not None:
        assertions.append({
            "id": f"{GATE_ID}::is_active", "status": "fail",
            "observed": f"probe error: {state_err}",
            "expected": f"`systemctl --user is-active {unit}` == active",
            "evidence_ref": evidence,
        })
    else:
        assertions.append({
            "id": f"{GATE_ID}::is_active",
            "status": "pass" if state == "active" else "fail",
            "observed": state,
            "expected": f"`systemctl --user is-active {unit}` == active",
            "evidence_ref": evidence,
        })

    # 2. journal freshness — a dated entry within the window (catches a silent
    #    / wedged door). age is None when no dated entry is readable.
    if journal_err is not None:
        assertions.append({
            "id": f"{GATE_ID}::journal_fresh", "status": "fail",
            "observed": f"journal probe error: {journal_err}",
            "expected": f"a journal entry for {unit} within {max_age:.0f}s",
            "evidence_ref": evidence,
        })
    elif age is None:
        assertions.append({
            "id": f"{GATE_ID}::journal_fresh", "status": "fail",
            "observed": "no dated journal entry",
            "expected": f"a journal entry for {unit} within {max_age:.0f}s",
            "evidence_ref": evidence,
        })
    else:
        assertions.append({
            "id": f"{GATE_ID}::journal_fresh",
            "status": "pass" if age <= max_age else "fail",
            "observed": f"last log {age:.0f}s ago",
            "expected": f"a journal entry for {unit} within {max_age:.0f}s",
            "evidence_ref": evidence,
        })

    _gatelib._emit_and_exit(assertions)


if __name__ == "__main__":
    main()
