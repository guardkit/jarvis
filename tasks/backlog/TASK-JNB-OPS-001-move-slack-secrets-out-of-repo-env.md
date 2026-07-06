---
id: TASK-JNB-OPS-001
title: "Move JARVIS_SLACK_* secrets out of the repo .env into the service EnvironmentFile"
status: backlog
created: 2026-07-04T11:00:00Z
priority: high
task_type: operator_handoff
tags: [security, slack, found-2026-07-04]
complexity: 2
---

# Move Slack secrets out of jarvis/.env

During the FEAT-28FF build (2026-07-03), autobuild Player agents in the
jarvis worktree read the real Slack bot token from the parent repo's
gitignored .env and posted ~a dozen synthetic FEAT-TEST messages to the live
#forge-builds channel. Worktrees do not isolate secrets from SDK-harness
agents; any secret in a repo-adjacent .env is reachable.

> **Amended 2026-07-06:** the canonical, expanded checklist is
> `docs/handoff/jnb-v1.1-remaining-gate-activation-and-ops-2026-07-05.md` §4
> (written after this task was filed). Deltas vs the list below: there are now
> **FIVE** keys (JNB-104 added `JARVIS_SLACK_DECIDED_BY` — set it to `rich`,
> verbatim-equal to forge `ApprovalConfig.expected_approver`; jarvis refuses
> every phone approval while it is unset), token rotation is a **required**
> numbered step (not "consider"), `chmod 600` the env file, and verify via the
> boot-log event table (`slack_reply_socket_mode_started` is the strongest
> signal). This task must land **before any live Slack traffic (TASK-JNB-107)**.
>
> ~~See also (same window, different credential): the fleet-memory relay
> container still holds the pre-rotation `FLEET_MEMORY_PG_DSN`…~~
> **[Resolved 2026-07-06: the relay had already been recreated with the new
> DSN on 07-05 15:12 UTC — verified by container-env vs `.env.deploy` hash
> comparison; the retro's "pending" note was stale (closed, guardkit
> `28587b61`). Nothing extra to fold into this task.]**

## Required operator follow-up

This task is task_type: operator_handoff — AutoBuild will not attempt it.

- Move JARVIS_SLACK_BOT_TOKEN / CHANNEL_ID / APP_TOKEN / OPERATOR_USER_ID
  **/ DECIDED_BY (five keys)** out
  of jarvis/.env into ~/.config/guardkit/jarvis.env on BOTH hosts (Mac + GB10
  — the GB10 unit already loads that file; on the Mac export them per-session
  or mirror the file).
- Confirm pydantic-settings still resolves them (env vars beat .env values,
  so the unit's EnvironmentFile wins by construction).
- **Rotate the bot token** (required — it was live in a worktree
  agents could read).
- Restart jarvis-serve-nats; verify slack_notifier_started is not no-op and
  slack_reply_socket_mode_started appears.
