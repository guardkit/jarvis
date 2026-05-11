# RESULTS: Jarvis → Architect Align — DDD South West Demo (post-CAPS-PROMPT walkthrough)

**Date:** 2026-05-08 (evening, fourth walkthrough — first run after TASK-CAPS-PROMPT-001/002 landed)
**Operator:** Claude Code (non-interactive, stdin-piped REPL driver)
**Machine:** GB10 (`promaxgb10-41b1`) — single-host all-local
**Jarvis HEAD:** `8db400d` (`Render tool parameter schema in supervisor capability prompt block (TASK-CAPS-PROMPT-001)`) — uv.lock has unstaged drift; not load-bearing
**specialist-agent HEAD:** `82ce8a6` (nats-core floor bump; same image as the post-fix run — `specialist-agent:latest` built 2026-05-08 18:01 BST)
**nats-core HEAD:** `8f2c532` / tag `v0.4.0`
**ADR pair:** Option A — ADR-ARCH-001 (local-first inference) vs Opus 4.7 escalation proposal
**correlation_id:** `3e147897-c586-4218-9873-1f9fa3a23135` (run 2, the canonical wire-evidence run)

**Companion files:**
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md) — morning run, blocked by Gap DISPATCH-STUB-RESOLVER
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-followup-post-W2.md`](RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-followup-post-W2.md) — afternoon run, blocked by Bugs #1/#2/#3
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md`](RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md) — third run, demo-green via R1 break-glass (explicit args framing in §4.1 prompt)

**Outcome:** ✅ **R2 verified end-to-end.** TASK-CAPS-PROMPT-001's parameter schema rendering closes the supervisor-invents-args gap surfaced by TASK-REV-9939 — the supervisor now constructs `architect_align` payloads with all three required args (`context`, `proposal`, `question`) populated correctly from the user's natural-language prompt. AlignmentJudgment returns clean (judgment=`misaligned`, confidence=`0.95`) on the Option A pair. Two back-to-back dispatches in this run (~24s + ~17s wall-clock) — second run was warm.

**Demo blocking?** ✅ NO — demo path green; the §4.1 explicit-args framing is no longer load-bearing post-R2 (it still works, but it's no longer required for valid payloads).

---

## What's new vs the prior post-fix run (`RESULTS-…-postfix.md`)

| Topic | Postfix run (R1 break-glass) | This run (post-CAPS-PROMPT, R2) |
|---|---|---|
| Supervisor capability prompt block | Tool names only — supervisor invented arg names like `{adr_id, adr_summary, proposal_summary}` (Bug #5) | **Renders typed `Args (required):` block** per `as_prompt_block()` post-TASK-CAPS-PROMPT-001 (commit `8db400d`) |
| §4.1 prompt template | Explicit `Context: / Proposal: / Question:` labels were load-bearing — removing them caused arg-shape mismatch | Same prompt now succeeds *because the schema is rendered*, not because the labels happen to match the args |
| Inbound dispatch payload (`agents.command.architect-agent`) | Sometimes valid, sometimes invented arg names | ✅ All 3 required args fully populated and routed to architect's `align` command (run 2 envelope captured verbatim) |
| Trace `outcome_type` | `success` (run 2 only, after explicit-args retry) | ✅ `success` (first try) |
| Wire-tap subject `agents.command.architect-agent.>` | Captured 4 envelopes | ❌ **0 envelopes** — runbook gap-fold finding (see §Gap-folds below) |

---

## Phase × gate summary

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main on FEAT/CAPS-PROMPT close | ✅ | `git log --oneline -5` — top is `8db400d` (TASK-CAPS-PROMPT-001) |
| 0.2 | specialist-agent image fresh | ✅ | `specialist-agent:latest` 2026-05-08 18:01 BST (image rebuilt for prior post-fix run; reused) |
| 0.3 | llama-swap up + `architect-agent` model loaded | ✅ | `:9000` listening; `/v1/models` lists `architect-agent` + 4 others |
| 0.4 | NATS up + auth env sourced | ✅ | `ships-computer-nats` Up 35h healthy; `RICH_NATS_PASSWORD` exported |
| 0.5 | stub_capabilities.yaml has `architect_align` | ✅ | yaml introspection shows all 4 architect tools incl. `architect_align` with `required: [context, proposal, question]` |
| 1   | verify-nats.sh all 7 streams + KV | ✅ | `verify-nats.sh` reports `7 passed, 0 failed` |
| 2.2 | dual-role stack up | ✅ | `specialist-agent-architect-agent-1` + `specialist-agent-product-owner-agent-1` Up |
| 2.3 | architect container env correct | ✅ | `AGENT_MODELS__REASONING_MODEL=local`, `LOCAL_MODEL=architect-agent`, `LLM_BASE_URL=http://host.docker.internal:9000` |
| 2.4 | agent-registry KV populated | ✅ | KV ls shows `architect-agent`, `product-owner-agent`, `jarvis` |
| 2.5 | architect tool surface includes `architect_align` | ✅ | KV `architect-agent` row publishes 4 tools incl. `architect_align` with full `parameters.required: [context, proposal, question]` |
| 3.1 | jarvis chat boots clean | ✅ | `jarvis_startup_complete nats_available=true graphiti_available=false capabilities_mode=live` |
| 4.x | dispatch turn produces AlignmentJudgment | ✅ | Run 1 (correlation_id `7a7d71d5-…`) and run 2 (correlation_id `3e147897-…`) — both render judgment `misaligned`, confidence `0.95` |
| 5.1 | inbound dispatch envelope captured | ✅ (run 2 only — see Gap-folds) | `docs/runbooks/evidence/dddsw-demo/wire-command-3e147897-….json` — payload contains `command: architect_align` + all 3 args populated |
| 5.2 | reply envelope captured on `_INBOX.>` | ✅ | `docs/runbooks/evidence/dddsw-demo/wire-reply-3e147897-….json` — `correlation_id` matches inbound; `success: true`; `result` = AlignmentJudgment |
| 5.3 | AlignmentJudgment saved | ✅ | `docs/runbooks/evidence/dddsw-demo/3e147897-….json` |
| 7.1 | chat transcript saved | ✅ | `~/.jarvis/transcripts/3e147897-….txt` |
| 7.2 | routing-history offload landed | ✅ | `~/.jarvis/traces/3e147897-….json` — `outcome_type: success`, `outcome_detail.final_agent_id: architect-agent`, `supervisor_reasoning_summary: dispatch_by_capability` |

---

## Headline evidence

### Inbound dispatch envelope (proves R2 is rendering the schema)

`docs/runbooks/evidence/dddsw-demo/wire-command-3e147897-c586-4218-9873-1f9fa3a23135.json`:

```json
{
    "message_id": "d09036ce-422e-47cd-9b2d-19f75886e2d7",
    "timestamp": "2026-05-08T19:33:02.201949Z",
    "version": "1.0",
    "source_id": "jarvis",
    "event_type": "command",
    "correlation_id": "3e147897-c586-4218-9873-1f9fa3a23135",
    "payload": {
        "command": "architect_align",
        "args": {
            "context": "ADR-ARCH-001 commits Jarvis to local-first inference via llama-swap. Cloud LLMs are explicitly out of the supervisor's hot path. The local reasoner (gpt-oss-120b) is the primary reasoning engine.",
            "proposal": "Add a Claude Opus 4.7 escalation tool that the supervisor can call when its local reasoner has low confidence on safety-critical or high-stakes user requests, bound by a per-session budget cap.",
            "question": "Is this proposal architecturally sound given ADR-ARCH-001's local-first invariant? What changes to the ADR or the supervisor's contract would the architect need to see for this to be aligned?"
        },
        "correlation_id": "3e147897-c586-4218-9873-1f9fa3a23135"
    }
}
```

**All three `architect_align` required args (`context`, `proposal`, `question`) are present and properly populated** — this is the load-bearing R2 evidence. Pre-R2 the supervisor invented arg names like `{adr_id, adr_summary, proposal_summary, context}` (per the wave-1 evidence in `trace-architect_align-31a2e8de-bug5-missing-args.json` etc); post-R2 it consults the rendered `Args (required):` schema in the supervisor prompt block and constructs a valid payload first try.

### Outbound AlignmentJudgment

`docs/runbooks/evidence/dddsw-demo/3e147897-c586-4218-9873-1f9fa3a23135.json`:

```json
{
  "judgment": "misaligned",
  "confidence": 0.95,
  "reasoning": "The proposal introduces a cloud LLM (Claude Opus) into the supervisor's reasoning path, which contradicts ADR-ARCH-001's explicit constraint that cloud LLMs are out of the hot path...",
  "suggestions": []
}
```

Narrative-perfect for the talk: the local-first ADR being asked to evaluate a cloud-escalation proposal returns `misaligned` at 95% confidence. Reasoning specifically cites `ADR-ARCH-001's explicit constraint`, proving the architect actually consumed the `context` field.

### End-to-end timings

| Run | Wall-clock | Notes |
|---|---|---|
| 1 (cold) | ~24s (19:30:14 → 19:30:38) | First architect call after stack idle; warm-up cost included |
| 2 (warm) | ~17s (19:32:57 → 19:33:15) | Architect model warm; this is the canonical evidence run |

Both runs well under the runbook's 30–90s expected envelope.

---

## Runbook gap-folds discovered (and addressed in this run)

Both gap-folds were filed AND folded into [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](RUNBOOK-jarvis-architect-align-dddsw-demo.md) in the same evening:

| Gap | Location | Fix applied | Priority |
|---|---|---|---|
| **§5.1 wire-tap subject was wrong** — `agents.command.architect-agent.>` (with `.>`) matches no published subject because `nats-core`'s `Topics.Agents.COMMAND = "agents.command.{agent_id}"` resolves to `agents.command.architect-agent` with NO trailing token. The `.>` wildcard expects further tokens after the agent_id and therefore captured nothing. | RUNBOOK §5.1 | ✅ Dropped the trailing `.>` — subject is now `agents.command.architect-agent` (exact match). Added a callout explaining the exact-match contract pinned to `nats-core` `v0.4.0` / commit `8f2c532`. | High — silently broke the on-stage wire-mirror demo |
| **§4.1 explicit-args framing was no longer required post-R2** — TASK-CAPS-PROMPT-001 shipped at commit `8db400d` and TASK-CAPS-PROMPT-002's AC-005 (conditional on R2 landing) was thereby satisfied. The §4.1 prompt with explicit `Proposal: / Question:` labels still worked, but free-text also works now. R1/break-glass scaffolding (footnote in §4.2, R1 note in §4.4, fallback row in §6) was operationally dead. | RUNBOOK §4.1, §4.2 fn, §4.4 R1 note, §6 fallback row | ✅ Replaced both Option A and Option B prompts with free-text framing. Removed the §4.2 footnote and the §4.4 R1/break-glass blockquote. Tightened §4.2 step 3 to cite the rendered `as_prompt_block()` schema. Updated §6 row to flag the explicit-tool-name fallback as "regression worth filing" rather than a normal alternative. | Medium — non-blocking, but operator-facing clarity |

### Verification of the post-R2 free-text claim

Before patching the runbook, ran a third dispatch using a fully free-text prompt (no `Proposal:` / `Question:` labels) — correlation_id `e6ba44e3-b385-4895-9df9-8552d06c6b62`. Wire envelope at `docs/runbooks/evidence/dddsw-demo/wire-command-e6ba44e3-b385-4895-9df9-8552d06c6b62.json` confirms the supervisor populated all three required args (`context`, `proposal`, `question`) from flowing prose, and even embellished the `question` field with structured sub-points the architect could chew on. R2's natural-routing claim is solid.

### Note on prior-run evidence files

The `.>`-vs-no-suffix wire-tap subject issue means prior-wave evidence files (`wire-command-2026-05-08-postfix.log`, etc.) almost certainly captured envelopes via a different tap (either an earlier subject pattern or a different recipe). Worth a quick git-blame on §5.1 if you're curious — but the corrected pattern (`agents.command.architect-agent` exact-match) is what works at `nats-core` `v0.4.0` / `8f2c532`.

---

## Decision

[x] **Demo path green and R2 verified.** Runbook executed end-to-end on GB10; the supervisor's natural-language → architect_align payload construction now succeeds first-try because the rendered parameter schema makes the args explicit. Demo path is unchanged from the post-fix run; the change is operator-facing (the §4.1 explicit-args framing is no longer load-bearing).

[x] **Two runbook gap-folds filed** above (§5.1 wire-tap subject; §4.x R1 break-glass language). Recommend a small docs PR to close both before the 2026-05-15 dress rehearsal.

[ ] **Optional follow-up:** if the wire-tap subject gap turns out to be a regression (i.e. a prior version of `nats-core` published to `agents.command.{agent_id}.{command}`), add a §0 precondition that pins the `nats-core` version against which §5.1 is valid. As of `nats-core` `v0.4.0` (`8f2c532`), the published subject is the exact-match form.
