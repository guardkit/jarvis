---
id: TASK-JNB-110
title: "Truthful decided_by: publish the actual clicker's Slack member ID (one identity scheme fleet-wide)"
status: backlog
created: 2026-07-06T21:00:00Z
updated: 2026-07-06T21:00:00Z
priority: high
task_type: implementation
repo: jarvis
complexity: 4
dependencies: []
blocks: [forge TASK-MP-010 AC-3, forge TASK-JNB-107 live round-trip]
tags: [jnb, approval-loop, identity, decided-2026-07-06]
---

# Task: Truthful decided_by — Slack member IDs as the fleet identity scheme

## Decision (Rich, 2026-07-06 — TASK-MP-012 decisions session)

`decided_by` must be a **factual claim about who clicked**, not a config
constant. Jarvis currently publishes `decided_by = settings.slack_decided_by`
("rich") for EVERY approval click regardless of the actual clicker, with the
real access control living in `slack_operator_user_id`. This breaks Mode P's
per-run approver pinning entirely (forge pins `expected_approver` to the
originator's Slack member ID `U…`, so verbatim equality can never hold —
even Rich approving his own planning run fails), and makes the audit trail
fictional.

**Chosen option:** jarvis sends the clicker's real Slack member ID; forge's
build-gate `approval.expected_approver` config is updated to Rich's member ID
in the same change. One identity scheme (Slack member IDs) fleet-wide.
Rejected: static alias for planning (deletes originator-first routing);
identity-mapping directory (drift-prone new surface, YAGNI for a 2-person
fleet — member IDs already ARE stable canonical identities).

## Acceptance criteria

- [ ] `slack_reply` publishes `decided_by = <interaction payload user id>`
      (the actual clicker), for ALL approval responses (build + planning).
      `JARVIS_SLACK_DECIDED_BY` is removed or demoted to a fallback with a
      deprecation warning.
- [ ] Authorization stays separate from identity: `slack_operator_user_id`
      becomes a small allowlist (`slack_operator_user_ids`) of member IDs
      permitted to click at all — identity says who DID, the allowlist says
      who MAY. (Needed anyway before James approves planning runs.)
- [ ] Coordinated forge config change documented: GB10 `forge.yaml`
      `approval.expected_approver` → Rich's Slack member ID (config-only;
      the code default "rich" is untouched). Note in the deploy record.
- [ ] Pinned contract test on the jarvis side: response payload's
      `decided_by` equals the interaction user id verbatim (JNB-107
      contract v2).
- [ ] Sequencing: land BEFORE the JNB-107 / TASK-MP-010 live round-trips so
      the final identity contract is validated once (both validations assert
      member-ID equality, not "rich").
- [ ] Doc sweep (added 2026-07-06 post-OPS-001): the literal `rich` contract is
      pinned in several places that must move to the member-ID scheme in the
      same change — jarvis `.env.example` (JARVIS_SLACK_DECIDED_BY comment
      block), `docs/handoff/jnb-v1.1-remaining-gate-activation-and-ops-2026-07-05.md`
      §1/§4, TASK-JNB-107 + TASK-JNB-OPS-001 task files (both refreshed today
      to say `=rich`), and forge's NATS approval protocol contract + FORGE-008
      runbook (JNB-101 documented the verbatim-'rich' pairing there). The
      operator's live `~/.config/guardkit/jarvis.env` (set to `rich` during
      OPS-001 2026-07-06) also needs its value swapped — or the key removed if
      the env var is deleted outright.

## Cross-repo references

- forge per-run pinning loci: `src/forge/planning/checkpoint.py`
  (`_dispatch_approval_response` vs RUN ROW `expected_approver`) and the
  per-run `ApprovalSubscriber` construction in
  `src/forge/cli/_serve_planning.py`.
- forge decision record: `docs/state/TASK-MP-012/review-findings-resolution.md`
  + `tasks/in_review/TASK-MP-012-*.md` "Design questions".
- ASSUM-003 (originator may approve own origination) is the policy this
  mechanism serves — unchanged by this task.
