# FEAT-BF39 v1.1 — remaining steps after JNB-105 (forge gate-activation + OPS-001)

**Written**: 2026-07-05 (jarvis Opus session, after TASK-JNB-105 landed
`af11a42`). Companion to `jnb-live-roundtrip-handoff-2026-07-05.md` — read that
first for the full loop and contracts; this doc is the two remaining
non-live pieces plus the model/effort guidance for the forge session.

> **⚠️ ANNOTATION 2026-07-06 — §2 and §3 are DONE; do NOT paste the §3 kickoff prompt.**
> The forge gate-activation shipped as **TASK-GATE-D659** (forge `75e0c5c`, all 3
> waves + review-hardened fix pass; in_review, pushed): `gate_check` now has its
> first production caller (`maybe_gate_build` in the daemon dispatch flow), SQLite
> GateRepository/StateMachine adapters, `reconcile_on_boot` binding, and the C1
> `mark_resume_pending` mechanism **removed** (dead-and-broken — do not look for
> it; approve resumes via the subscriber resume-emit seam). DF-007 filed +
> accepted 2026-07-05. **Remaining from this doc: §1 (still load-bearing) and §4
> (OPS-001) → then TASK-JNB-107.** Pre-flight additions found by the 2026-07-06
> audit: verify the GB10 PIPELINE durable `ack_wait=1h` via `nats consumer info`
> (no runtime artifact exists), and assess forge TASK-FWD-002/003/004
> (`forge/tasks/backlog/forge-wire-dispatch-fixes/`) — open defects on the exact
> dispatch path the gated toy build traverses.

## Where the whole loop stands (2026-07-05)

Both **code** halves of the v1.1 approve/reject loop are done and in_review:

| Piece | State |
|---|---|
| jarvis JNB-103/104/105 — buttons + Socket Mode reply path + v1.1 reply-path scenario tests | ✅ in_review on jarvis main (`0b2d1bf`, `51305d7`+`8f52775`, `af11a42`) |
| forge JNB-101/102/106 — ApprovalSubscriber production wiring + build-cancelled + scenario tests | ✅ in_review on forge main, **pushed** (`e003201`, `bc1366d`, `3fc6d41`+`ff2489c`) |
| **forge gate-activation** (§2/§3) — ~~the load-bearing blocker~~ | ✅ **DONE 2026-07-05/06 — TASK-GATE-D659** (forge `75e0c5c`; see the 2026-07-06 annotation above) |
| **TASK-JNB-OPS-001** (§4) — secrets out of repo `.env` | ⛔ operator, **now the sole remaining prerequisite** |
| **TASK-JNB-107** — live round-trip → SPL Gate G1 PASS | gated on OPS-001 only (code blockers all cleared) |

**The blocker (why JNB-107 can't run yet):** `gate_check` has **no production
caller** — nothing in the live forge daemon pauses a build (the autobuild runner
graph never enters `awaiting_approval`; verified by JNB-101's 5-reader sweep). The
JNB tasks built and injected the seam per their deliberately-minimal scope, but a
"gated toy build" needs a **gate-activation step first**.

The forge gate-activation work and OPS-001 are **independent** and can run in
parallel; JNB-107 needs both complete.

---

## 1. Alignment value that silently breaks everything

forge `ApprovalConfig.expected_approver` was pinned to **`rich`** by JNB-101
(`e003201`). jarvis publishes `decided_by = JARVIS_SLACK_DECIDED_BY` untouched;
forge compares it to `expected_approver` by **exact string equality**. So
`JARVIS_SLACK_DECIDED_BY` must be **`rich` verbatim** (NOT the earlier suggested
`rich-slack-operator`). Mismatch ⇒ Approve does nothing: jarvis logs
`slack_reply_decision_published`, forge logs `unrecognised responder … NOT
resuming`, the build stays paused. Re-confirm against live forge config before the
run (`rich` is only the *default*).

---

## 2. Model / effort for the forge gate-activation session

- **Model: Fable 5.** This is the *highest-uncertainty* piece of the loop
  (JNB-101's own plan calls the gating stack "the highest-uncertainty task"),
  design-sensitive production code, and the sole remaining code blocker for the
  live demo — a good use of the Fable window, and it fits the "resumable genre"
  rule (spec/plan/partial waves survive if access ends).
- **Effort: high, with the design/arch-review phase given the most scrutiny
  (xhigh/max if per-phase is available).** The crux is *where* to activate the
  gate in the runner graph and how `emit_resumed` fires on daemon restart —
  JNB-101's arch review **killed the `mark_resume_pending` adapter path** as a
  confirmed bug, so the replacement design is genuinely unsettled. Mechanical
  SQLite-adapter code is fine at high. Don't go below high — it's state-machine +
  persistence + boot-recovery code gating a live run.
- **Shape:** design-first. `/task-work … --design-only` to approve the
  activation-point design before implementing, or `/feature-plan` if it splits
  into waves.

---

## 3. Forge gate-activation kickoff prompt

Paste into a fresh session opened in `~/Projects/appmilla_github/forge`
(one-repo-per-session rule):

```text
FEAT-BF39 v1.1 — forge "gate-activation" work. This is the sole remaining CODE
blocker before the JNB-107 live approve/reject round-trip. Session opened in the
forge repo (one-repo-per-session rule).

WHERE THINGS STAND (2026-07-05):
- Both code halves of the v1.1 loop are done and in_review:
  jarvis JNB-103/104/105 (buttons + Socket Mode reply path + reply-path scenario
  tests) and forge JNB-101/102/106 (ApprovalSubscriber production wiring +
  build-cancelled + scenario tests, pushed to forge main).
- BUT the gate seam is unwired: nothing in the live forge daemon pauses a build.
  gate_check / GateCheckDeps (src/forge/gating/wrappers.py:366,408) have ZERO
  production call sites; the autobuild runner graph
  (src/forge/subagents/autobuild_runner.py:1584-1604) never enters
  awaiting_approval. So a "gated toy build" for JNB-107 cannot exist yet.

READ FIRST (authoritative — do not re-derive):
  docs/state/TASK-JNB-101/implementation_plan.md
  — §"Ground truth discovered before planning" (the 5-reader sweep), the C1/C2
    architectural findings (the mark_resume_pending adapter path was KILLED as a
    confirmed bug — do not resurrect it), and §"Follow-ups (documented, out of
    scope)". Also read ../ai-transition/docs/decisions/REGISTER.md before any
    architectural change (CLAUDE.md rule).

THE WORK (the four documented follow-ups — one cohesive vertical slice = "make a
real build pause, round-trip, and recover"):
  1. gate_check ACTIVATION POINT in the dispatch/runner flow — the design crux.
     Where in the runner graph does a build actually enter awaiting_approval and
     call gate_check? (autobuild_runner.py:1584-1604 graph; wrappers.py gate_check.)
  2. Production SQLite adapters for the GateRepository and StateMachine protocols
     (only in-memory fakes exist today: tests/integration/conftest.py:226,299).
  3. reconcile_on_boot binding at the serve.py:148 recovery seam — boot re-emit of
     ApprovalRequestPayload for PAUSED builds (handoff §6 assumes it exists).
  4. The C1 guard bug in LifecycleEmitterAdapter.mark_resume_pending
     (autobuild_runner.py:559-605) — JNB-101 explicitly assigned this fix to THIS
     (runner-side pause activation) task; emit_resumed silently never fires on a
     fresh adapter (the daemon-restart case it exists for).

APPROACH: start design-first. There is no forge task filed yet — begin with
/task-create (or /task-review) for a single "gate-activation" task, then
/task-work --design-only to get the activation-point design approved BEFORE
implementing (the activation point + the killed-adapter replacement are the real
uncertainty). Split into waves via /feature-plan if the design shows it's >1 task.

ACCEPTANCE (what "done" unblocks JNB-107):
  A real forge build reaching a gate → enters awaiting_approval → publishes
  ApprovalRequestPayload on agents.approval.forge.{build_id} (the pre-existing
  _atomic_pause_and_publish; do NOT add a daemon-side build-paused emit — C4 was
  dissolved) → jarvis posts phone buttons → APPROVE resumes the build (emit_resumed
  fires, incl. the daemon-restart case) → REJECT cancels (JNB-102's build-cancelled)
  → and reconcile_on_boot re-emits approval requests for PAUSED builds after a
  daemon restart. Prove with scenario tests over the production wiring.

ALIGNMENT (load-bearing for the eventual live run — don't change casually):
  forge ApprovalConfig.expected_approver was pinned to "rich" by JNB-101
  (e003201). jarvis JARVIS_SLACK_DECIDED_BY must string-equal it VERBATIM or every
  phone approval silently no-ops. Keep it "rich" unless you deliberately re-pin it
  (and tell the operator so OPS-001 matches).

PROCESS CONSTRAINTS (learned this window):
  - WORKING-TREE CAUTION: there is an UNCOMMITTED operator revert in
    src/forge/subagents/autobuild_runner.py (coach-model routing removal) — this
    task touches that file (C1 fix + activation). Do NOT clobber the revert; inspect
    `git diff` before editing and never `git add -A`/`git stash` blindly.
  - Forge suite baseline: 5048 green (only pre-existing infra failures; verify any
    suspect failure exists identically on HEAD via the git-stash trick before
    attributing it to your diff).
  - Give review/verify agents that mutate code isolation:'worktree'; run
    `git worktree list` + prune before staging.
  - `git checkout` any lockfile you don't own before committing. Commit immediately
    after writing — uncommitted files don't survive repo syncs. Push (forge main is
    the integration branch for these in_review tasks; JNB-101/102/106 were pushed).
  - Model Fable 5 at high effort; give the arch-review/design phase the most
    scrutiny (xhigh/max if available) — the activation point is the crux.
```

---

## 4. TASK-JNB-OPS-001 — operator checklist (secrets out of repo `.env`)

**Why:** during FEAT-28FF (2026-07-03), autobuild worktree agents read the live
bot token from the repo-adjacent gitignored `jarvis/.env` and posted ~a dozen
synthetic messages to `#forge-builds`. Worktrees do not isolate secrets. Must land
**before any live Slack traffic (JNB-107)**. `task_type: operator_handoff` —
AutoBuild will not attempt it. **Do this on BOTH hosts — Mac + GB10.** Task file:
`tasks/backlog/TASK-JNB-OPS-001-move-slack-secrets-out-of-repo-env.md`.

**1. Create the out-of-repo secrets file** `~/.config/guardkit/jarvis.env` with
all five keys (note the **new** `DECIDED_BY = rich`):

```bash
mkdir -p ~/.config/guardkit
cat > ~/.config/guardkit/jarvis.env <<'EOF'
JARVIS_SLACK_BOT_TOKEN=xoxb-...            # the ROTATED token (step 3)
JARVIS_SLACK_CHANNEL_ID=C...               # #forge-builds
JARVIS_SLACK_APP_TOKEN=xapp-...            # Socket Mode app token
JARVIS_SLACK_OPERATOR_USER_ID=U...         # your Slack member id
JARVIS_SLACK_DECIDED_BY=rich               # MUST string-equal forge expected_approver VERBATIM
EOF
chmod 600 ~/.config/guardkit/jarvis.env
```

**2. Remove the `JARVIS_SLACK_*` lines from `jarvis/.env`** on both hosts. *This is
the actual security fix* — real env vars already beat `.env` by pydantic-settings
precedence, so the point is that the secrets no longer sit in the repo-adjacent
file where a worktree agent can read them.

**3. Rotate the bot token** in Slack (regenerate the `xoxb-` bot token — the old
one was readable by worktree agents), then put the new value in
`~/.config/guardkit/jarvis.env` on both hosts. *(Worth rotating the `xapp-` app
token too while you're there.)*

**4. Wire the file into the service:**
- **GB10:** the systemd unit `jarvis-serve-nats` already loads it via
  `EnvironmentFile=…/jarvis.env` → confirm the unit's `EnvironmentFile=` actually
  points at `~/.config/guardkit/jarvis.env` (the one host-specific detail to
  verify against the real unit file), then `systemctl --user daemon-reload` if you
  edited the unit.
- **Mac:** export per session before launching:
  `set -a; source ~/.config/guardkit/jarvis.env; set +a`, then run the `serve-nats`
  entrypoint (`src/jarvis/cli/main.py` → `@main.command("serve-nats")`).

**5. Restart the service** — GB10: `systemctl --user restart jarvis-serve-nats`;
Mac: relaunch `serve-nats`.

**6. Verify from the boot logs** (`journalctl --user -u jarvis-serve-nats -n 200`
on GB10, or stdout on Mac):

| Must SEE (live) | Must NOT see (degraded no-op) |
|---|---|
| `slack_notifier_started` (+ `jarvis_notification_sink_started`) | `slack_sink_no_op` |
| `jarvis_approval_subscriber_started` | — |
| `jarvis_slack_reply_started` **and** `slack_reply_socket_mode_started` | `slack_reply_no_op` |

The reply-path started event is the strongest signal — it proves **all four**
reply-path vars (`BOT_TOKEN`, `APP_TOKEN`, `OPERATOR_USER_ID`, and NATS) resolved.

**7. Confirm the alignment (§1):** `JARVIS_SLACK_DECIDED_BY` == forge
`expected_approver` == `rich`, verbatim.

**Also re-verify these perishable prereqs before the JNB-107 run:** the bot is
still **invited to `#forge-builds`**, and the `ships-computer-nats` broker is
healthy on both hosts.

---

## 5. Key references

| Thing | Path |
|---|---|
| Full loop + contracts (read first) | `docs/handoff/jnb-live-roundtrip-handoff-2026-07-05.md` |
| Forge gate-activation follow-ups (authoritative) | `../forge/docs/state/TASK-JNB-101/implementation_plan.md` (§Ground truth, §C1/C2, §Follow-ups) |
| Live validation script | `tasks/backlog/jarvis-notification-bridge/TASK-JNB-107-*.md` (jarvis-side) |
| OPS-001 task | `tasks/backlog/TASK-JNB-OPS-001-move-slack-secrets-out-of-repo-env.md` |
| JNB-105 (this session) | `tests/test_slack_reply_scenarios_jnb105.py`, `docs/state/TASK-JNB-105/implementation_plan.md` |
| Fleet status tracker | `../ai-transition/docs/fable-window-execution-plan-2026-07-04.md` (updated `542aeec`) |
| Env keys | `.env.example` (JARVIS_SLACK_* incl. `JARVIS_SLACK_DECIDED_BY`) |
