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

## serve-nats + staleness watchdog (HB-4 L1)

`jarvis-serve-nats.service` is the **live Slack door** on this box — the
`jarvis serve-nats` NATS subscriber + Slack Socket-Mode client that actually
receives James/Rich requests (src/jarvis/cli/main.py). It is **already installed,
enabled and running**; the copy here is a **byte-faithful version of the on-box
unit** (`~/.config/systemd/user/jarvis-serve-nats.service`) so the real door is
under version control. **Installing this pass does NOT restart it.**

`jarvis-serve-nats-watchdog.service` (+ `.timer`) is a read-only supervisor: every
15 minutes it checks `systemctl --user is-active jarvis-serve-nats` **and** reads
the unit's journal, and posts a Slack alert when the door is stale — the process
is down, **or** its Socket-Mode subscription dropped without re-establishing, **or**
the journal has been silent past a 6h backstop. The staleness rule (and why a
plain no-lines-in-N-minutes rule would false-alarm on a healthy idle/rotating
door) is documented in the script header, `serve_nats_watchdog.py`.
Known cap (honest): a subscription that dies **without logging any trouble line**
while the door's independent KV-poll keeps the journal non-silent evades both
journal signals — the observed Socket-Mode drop class does log its marker; the
truly-silent death is a register residue (cure = an end-to-end probe, not more
journal grammar).

- The watchdog **never** starts/stops/restarts serve-nats and touches no
  seat/GPU/keepalive — it is CPU- and journal-only.
- The Slack alert **reuses jarvis's own credentials**: the watchdog `.service`
  sources the **same** `EnvironmentFile=%h/.config/guardkit/jarvis.env` the door
  uses, and posts with `JARVIS_SLACK_BOT_TOKEN` to `JARVIS_SLACK_CHANNEL_ID`
  (override the destination with `JARVIS_WATCHDOG_ALERT_CHANNEL_ID`). No secret
  lives in the repo; no new secret path is introduced.
- Prove it without touching the live door — dry-run against a simulated journal:
  ```bash
  # ALERTS on a wedged door (reconnect with no following 'established'):
  .venv/bin/python -c 'pass'   # (venv not required; watchdog is stdlib-only)
  printf '%s\n' \
    "$(date +%s).0 host jarvis[1]: {\"event\": \"A new session has been established\"}" \
    "$(date +%s).1 host jarvis[1]: {\"event\": \"seems to be already closed. Reconnecting...\"}" \
  | /usr/bin/python3 ops/systemd/serve_nats_watchdog.py --dry-run --stdin \
      --is-active-override active                       # prints the alert, exits 10
  # QUIET on the real, healthy door (read-only):
  journalctl --user -u jarvis-serve-nats -n 300 -o short-unix --no-pager \
  | /usr/bin/python3 ops/systemd/serve_nats_watchdog.py --dry-run --stdin  # exits 0
  ```
  Exit codes: `0` fresh/quiet · `10` stale-alert-dispatched · `20`
  watchdog-internal-error (a broken watchdog is loud, never a silent green).

### Install (coordinator, jarvis box)

The serve-nats door is **ALREADY LIVE** — do **NOT** restart it. Installing this
pass versions the door unit on-box (idempotent, byte-identical) and enables the
**timer only**; the watchdog `.service` stays inert until the timer fires it.

```bash
mkdir -p ~/.config/systemd/user
# byte-identical to the running unit — a no-op copy, the door is NOT restarted:
cp ops/systemd/jarvis-serve-nats.service ~/.config/systemd/user/
cp ops/systemd/jarvis-serve-nats-watchdog.service ~/.config/systemd/user/
cp ops/systemd/jarvis-serve-nats-watchdog.timer ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger "$USER"          # user units survive logout / start at boot
# enable the TIMER ONLY (never `enable --now` the serve-nats service — it is live):
systemctl --user enable --now jarvis-serve-nats-watchdog.timer
systemctl --user list-timers | grep serve-nats-watchdog
# one-off manual check (dry-run, no Slack post):
systemctl --user start jarvis-serve-nats-watchdog.service   # or run the script --dry-run
journalctl --user -u jarvis-serve-nats-watchdog.service -n 20 --no-pager
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
