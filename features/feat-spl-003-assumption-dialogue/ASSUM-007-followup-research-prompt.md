# Follow-up research prompt — ASSUM-007 override premise

**Filed:** 2026-07-07 (decision-queue curation session, Rich).
**Why this exists:** ASSUM-007 was **overridden** from a durable notification
consumer to an **ephemeral NEW** one. The override's load-bearing premise is
that a missed build/planning notification is *recoverable by asking Jarvis for
current status*. If that capability does not actually exist, restart-window
gaps become unrecoverable and ASSUM-007 should be revisited (back to durable).
This prompt verifies the premise.

---

## Research prompt

> **Question: Does Jarvis today expose a way for a human in Slack to query the
> current status of a forge planning run / build, on demand?**
>
> Investigate the `jarvis` repo (and its contracts with `forge` over NATS) and
> answer concretely:
>
> 1. **Is there any inbound command/intent path** — a slash command, an
>    app-mention handler, a Socket Mode interaction, or a natural-language
>    intent — by which a human can ask Jarvis "what is the status of planning
>    run X / build Y?" and get an answer in Slack? Cite the handler
>    (file:symbol) if so.
> 2. **If yes:** what is the data source behind that answer — does Jarvis query
>    forge (which subject / request-reply contract, or which SQLite/state read),
>    or does it only reflect state it has locally cached? Does it work for a run
>    whose notifications were *missed* (i.e. is the status pull independent of
>    the push notifications that ASSUM-007 governs)?
> 3. **If no such path exists:** what is the closest existing surface, and how
>    much work would a minimal "status of run X" query be (new consumer? new
>    forge request-reply subject? new intent)? Is forge's `planning_runs` /
>    `planning_run_events` state queryable over NATS today, or only via direct
>    DB access?
> 4. **Coverage check:** does any answer path cover the specific messages
>    ASSUM-007 is about — Mode P planning notifications on
>    `jarvis.notification.slack` (handoffs, checkpoint transitions, escalations)
>    — or only build/task status?
>
> **Deliverable:** a short finding — PREMISE HOLDS / PREMISE PARTIAL / PREMISE
> DOES NOT HOLD — with the evidence (file:symbol, subject names, contracts), and
> if PARTIAL/DOES-NOT-HOLD, the smallest change that would make on-demand status
> query real. This feeds the ASSUM-007 revisit decision (ephemeral vs durable
> notification consumer).

---

## Decision hook

- **PREMISE HOLDS** → ASSUM-007 override (ephemeral) stands; close this trigger.
- **PREMISE PARTIAL / DOES NOT HOLD** → re-open ASSUM-007; weigh reverting to a
  durable consumer vs building the status-query path as the recovery mechanism.
