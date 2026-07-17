#!/usr/bin/env python3
"""Local live-gate driver — supplies the F16 seam that `guardkit qa live-gate`
leaves unwired in v1.

WHY THIS EXISTS: guardkit's pre-flight (guardkit/orchestrator/live_gate/
preflight.py) ALWAYS consults an F16 perishable-prereq checklist provider, but
the `guardkit qa live-gate` CLI injects none — so the plain CLI short-circuits
to verdict `environment_fail` (exit 4) BEFORE any gate script runs, on every
repo, regardless of how healthy the deployment is. (The F16 schema is WS5-owned;
only guardkit's own tests inject a provider.) That is a guardkit-side v1 gap,
not a jarvis authoring gap — the registered gate script itself passes on a live
door. This driver is modelled on api_test/qa/gates/local_live_gate.py and its
proven study-tutor port, adapted for a HOST-PROCESS (systemd) target.

WHAT THIS DOES: constructs the SAME, UNMODIFIED guardkit LiveGateRunner but wires
a minimal HONEST F16 provider for jarvis's Slack door. jarvis `serve-nats` has NO
HTTP endpoint (src/jarvis/cli/main.py:263), so the F16 probe is NOT a GET
/healthz — it is a READ-ONLY host-process liveness check:
`systemctl --user is-active <unit>` (the same signal the L1 socket-guard reads).
When the unit is `active`, the real runner executes the registered F4 gate
(serve-nats-liveness) against the live box and emits the genuine results envelope
(+ qa/gates/history/<run_id>.json and the evidence dir). Identical envelope
shape, verdict, and exit-code semantics as the CLI.

THE NATS-DOWN LAW (honesty): `serve-nats` refuses to start without a live NATS
broker (src/jarvis/cli/main.py:354 → SystemExit(1)). So a down/unreachable broker
makes the unit inactive/failed. The F16 probe reports that as ok=False, which the
pre-flight classifies as **environment_fail** — an honest "no live door to verify
against", NEVER a product fail. This driver issues ZERO systemctl start/stop/
enable and NO daemon-reload — it only READS unit state.

    python3 qa/gates/local_live_gate.py --feature <id> --target local [--gates serve-nats-liveness]

RUN ENVIRONMENT + CWD FOOTGUN (read this): guardkit is a sibling repo
(../guardkit) and is NOT a dependency of jarvis's own venv, so this driver runs
under guardkit's env. AND — like the api_test/study-tutor precedent — the runner
resolves the gate registry (qa/gates/registry.yaml) and every gate's evidence dir
(qa/gates/evidence/) CWD-RELATIVE. So it MUST be launched FROM THE JARVIS REPO
ROOT:

    cd /home/richardwoollcott/Projects/appmilla_github/jarvis
    uv run --no-sync --project ../guardkit \
      python qa/gates/local_live_gate.py --feature HB-1-SERVE-NATS-LIVENESS \
      --target local --repo .

Optional env (both have honest defaults): JARVIS_SERVE_NATS_UNIT (default
jarvis-serve-nats) names the target unit; the gate subprocess inherits it.

If/when guardkit gains a CLI hook for the F16 provider (or a real WS5 F16
source), this driver retires in favour of `guardkit qa live-gate`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from guardkit.orchestrator.live_gate.preflight import F16ChecklistProvider, SeamResult
from guardkit.orchestrator.live_gate.runner import LiveGateRunner

_VERDICT_EXIT = {"pass": 0, "fail": 1, "instrument_fail": 3, "environment_fail": 4}

DEFAULT_UNIT = "jarvis-serve-nats"


class ServeNatsLivenessF16(F16ChecklistProvider):
    """Honest F16 for jarvis's host-process Slack door: the perishable prereq we
    assert is 'the serve-nats unit is up', proven by a READ-ONLY
    `systemctl --user is-active <unit>` probe (NOT a GET /healthz — serve-nats has
    no HTTP endpoint). serve-nats requires a live NATS broker to start
    (cli/main.py:354), so an inactive unit means the broker is down → ok=False →
    environment_fail, the honest 'no live door to verify' verdict."""

    def __init__(self, unit: str) -> None:
        self.unit = unit

    def checklist(self):
        try:
            proc = subprocess.run(
                ["systemctl", "--user", "is-active", self.unit],
                capture_output=True, text=True, timeout=10,
            )
        except Exception as exc:
            return [SeamResult(
                ok=False,
                detail=(f"F16 perishable readiness: `systemctl --user is-active "
                        f"{self.unit}` could not be invoked: {exc} → environment_fail"),
            )]
        state = (proc.stdout or proc.stderr or "").strip().splitlines()
        state = state[0] if state else "unknown"
        ok = state == "active"
        detail = (
            f"F16 perishable readiness: `systemctl --user is-active {self.unit}` "
            f"-> {state}"
        )
        if not ok:
            detail += (
                " (serve-nats requires a live NATS broker to start, "
                "cli/main.py:354; a down broker => inactive unit => environment_fail, "
                "not a product fail)"
            )
        return [SeamResult(ok=ok, detail=detail)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--feature", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--gates", default=None, help="comma-separated gate id subset")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()

    unit = os.environ.get("JARVIS_SERVE_NATS_UNIT") or DEFAULT_UNIT
    runner = LiveGateRunner(Path(args.repo), f16_provider=ServeNatsLivenessF16(unit))
    requested = [g.strip() for g in args.gates.split(",") if g.strip()] if args.gates else None

    envelope = runner.run(args.feature, args.target, requested_gate_ids=requested)
    print(json.dumps(envelope.model_dump(mode="json"), indent=2))
    sys.exit(_VERDICT_EXIT.get(envelope.verdict, 1))


if __name__ == "__main__":
    main()
