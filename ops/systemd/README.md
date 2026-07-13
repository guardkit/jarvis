# jarvis ops/systemd — supervised Slack front door (O-30, Phase E2-S3)

`jarvis-frontdoor.service` supervises the jarvis Slack **front door** so it
auto-recovers on a crash and on host reboot. Today the front door is a bare
`uv run python -m langgraph dev` (README §Quickstart step 6) with **no
supervisor** — on an overnight power blip / kernel-update reboot it silently does
not come back, and a James/Rich Slack request goes nowhere (gap O-30).

This unit is **authored + `systemd-analyze verify`-clean, NOT installed/enabled**
by this pass — installing/enabling on the live box is a coordinator step.

## What it runs

- `Type=exec`, `WorkingDirectory=%h/Projects/appmilla_github/jarvis` (so
  `langgraph.json` + `.env` resolve).
- `ExecStart=%h/.local/bin/uv run python -m langgraph dev --no-browser` — the
  README's canonical runtime command through `uv run` (binds the pinned 3.12
  venv); `--no-browser` because a supervised headless service must never open a
  browser. Boots both the `jarvis` and `jarvis_reasoner` graphs.
- `EnvironmentFile=-%h/Projects/appmilla_github/jarvis/.env` — belt-and-suspenders
  env sourcing (langgraph also loads the `.env` named in `langgraph.json`); the
  `-` makes a missing file non-fatal.
- `Restart=on-failure`, `RestartSec=5` — auto-recover a crash; a clean operator
  `systemctl --user stop` stays stopped.

## Install (coordinator, jarvis box)

```bash
mkdir -p ~/.config/systemd/user
cp ops/systemd/jarvis-frontdoor.service ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger "$USER"          # user units survive logout / start at boot
# free the port first — kill any bare `langgraph dev` currently holding :2024
systemctl --user enable --now jarvis-frontdoor.service
systemctl --user status jarvis-frontdoor.service
journalctl --user -u jarvis-frontdoor.service -f   # watch both graphs boot
```

## Boot order

The front door is **LAST** in the factory boot chain (it needs the NATS bus,
forge-prod, and the specialists up before it can serve). The full chain — nats →
forge sidecar → forge-prod → specialists → **jarvis front door** — and why the
restart policies make it safe even if the order is violated, is documented once,
canonically, in **`forge/ops/README.md` §Boot order**.

## Demonstration

The systemd supervised-restart mechanism this unit relies on is demonstrated on a
throwaway transient user unit (same `Restart=on-failure` policy) in
`../receipts/DEMO-systemd-user-unit-supervised-restart.md` — kill the process,
journalctl shows `status=9/KILL` → `Scheduled restart` → `Started`.
