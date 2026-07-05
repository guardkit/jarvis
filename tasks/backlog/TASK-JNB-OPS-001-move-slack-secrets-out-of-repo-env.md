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

## Required operator follow-up

This task is task_type: operator_handoff — AutoBuild will not attempt it.

- Move JARVIS_SLACK_BOT_TOKEN / CHANNEL_ID / APP_TOKEN / OPERATOR_USER_ID out
  of jarvis/.env into ~/.config/guardkit/jarvis.env on BOTH hosts (Mac + GB10
  — the GB10 unit already loads that file; on the Mac export them per-session
  or mirror the file).
- Confirm pydantic-settings still resolves them (env vars beat .env values,
  so the unit's EnvironmentFile wins by construction).
- Consider rotating the bot token afterwards (it was live in a worktree
  agents could read).
- Restart jarvis-serve-nats; verify slack_notifier_started is not no-op.
