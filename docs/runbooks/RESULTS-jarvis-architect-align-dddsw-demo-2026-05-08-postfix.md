# RESULTS: Jarvis → Architect Align — DDD South West Demo (post-fix walkthrough)

**Date:** 2026-05-08 (evening — third walkthrough; first run after specialist-agent Bug #1/#2/#3 fixes landed)
**Operator:** Claude Code (non-interactive, stdin-piped REPL driver)
**Machine:** GB10 (`promaxgb10-41b1`) — single-host all-local
**Jarvis HEAD:** `4c53e6c` (runbook results) — same as morning run
**specialist-agent HEAD:** `82ce8a6` (post `1979aa8` Bug #1 + `08a95fe` Bug #2 + `4d80bd3` Bug #3 + `82ce8a6` nats-core floor bump)
**nats-core HEAD:** `8f2c532` / tag `v0.4.0` (subscribe_with_reply + publish_raw — required by Bug #1 fix)
**Image:** `specialist-agent:latest` rebuilt 2026-05-08 18:01 BST (image id `dc8d9e75d0da`) — contains all three bug fixes
**ADR pair:** Option A — ADR-ARCH-001 vs Opus 4.7 escalation proposal
**Companion files:**
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md) — morning run, blocked by Gap DISPATCH-STUB-RESOLVER
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-followup-post-W2.md`](RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-followup-post-W2.md) — afternoon run, blocked by Bugs #1/#2/#3

**Outcome:** ✅ **DEMO PATH GREEN.** AlignmentJudgment lands end-to-end. Bugs #1/#2/#3 verified closed by both wire-level evidence and a direct `nats request` round-trip (rtt 3.6s). Architect's fine-tuned Gemma 4 26B-A4B serving via llama-swap returns a structured `AlignmentJudgment{judgment: misaligned, confidence: 0.95, reasoning: …}` for the Option A pair — narrative-perfect for the talk.

**Demo blocking?** ✅ NO — for the runbook's intended scope (one ADR/proposal pair, dispatched, judgment rendered). One residual issue (Bug #5, supervisor hallucinating arg names because the parameter schema isn't in the prompt-block) is **non-blocking with a tightened prompt** but should be fixed-forward before the talk so the operator doesn't have to over-engineer the on-stage prompt.

---

## What's new vs the prior runs

| Topic | Morning (`ca2ba6b`, pre-W2) | Afternoon (`30e4ae4`, post-W2) | This run (`4c53e6c` jarvis + `82ce8a6` specialist + image rebuilt) |
|---|---|---|---|
| Resolver lookup of `architect_align` | ❌ `ERROR: unresolved` | ✅ resolved → `architect-agent` | ✅ resolved → `architect-agent` |
| `agents.command.architect-agent` envelopes | 0 | 2 (jarvis-driven) | 4 (3 from run-1 prompt-shape mismatch + 1 from run-2 explicit-shape success) |
| `agents.result.architect-agent` envelopes | 0 | 3 (jarvis + diag) — all `success: false` | **0 — by design** (Bug #1 fix routes replies via `msg.reply` inbox, bypassing the JetStream-stored result subject) |
| Architect reply mechanism | n/a | publish to `agents.result.<agent_id>` (raced with PubAck) | reply to `msg.reply` inbox via `publish_raw` (Bug #1 closed) |
| Architect `align` command dispatch | n/a | ❌ rejected — `Command 'architect_align' not supported` (Bug #2) | ✅ dispatched (Bug #2 closed by `tool_to_command` mapping in `_dispatch_command`) |
| Architect llama-swap call | n/a | ❌ 404 — missing `/v1` suffix (Bug #3) | ✅ 200 — `/v1` normalised in `_resolve_agent_model("local")` (Bug #3 closed) |
| Trace `outcome_type` | `unresolved` | `exhausted` | `success` (run 2) |
| Architect response time | n/a | n/a | **3.6s** (warm Gemma 4 26B-A4B on Blackwell) — direct `nats request` round-trip |
| AlignmentJudgment captured | ❌ | ❌ | ✅ `judgment: misaligned, confidence: 0.95` |

The three bug fixes did exactly what they claimed. Demo path is green.

---

## Phase × gate summary

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main + clean tree | ✅ HEAD `4c53e6c`, clean tree | `git status` |
| 0.2 | specialist-agent main + image freshness | ⚠️ → ✅ image dated `2026-05-08 07:06 BST` was **stale** (pre Bug #1/#2/#3 commits at 16:33–16:36 BST). Rebuilt to `2026-05-08 18:01 BST` / image id `dc8d9e75d0da` per user instruction. | `docker images` |
| 0.2a | nats-core sibling at v0.4.0 | ⚠️ tag `v0.4.0` exists at HEAD `8f2c532` but `pyproject.toml` was unbumped (still `0.3.0`) — **blocked the rebuild** with `ERROR: Could not find a version that satisfies the requirement nats-core>=0.4`. **Fixed** by bumping `nats-core/pyproject.toml` to `0.4.0` (one-line edit, with user approval). | rebuild log |
| 0.3 | llama-swap + `architect-agent` model | ✅ port 9000 listening; models incl. `architect-agent`, `qwen36-workhorse`, `gemma4-tutor`, `nomic-embed`, `qwen-graphiti` | `/v1/models` |
| 0.4 | NATS up + APPMILLA creds | ✅ `ships-computer-nats` Up 32h healthy; `RICH_NATS_PASSWORD` extracted (16 chars) | — |
| 0.5 | Stub yaml advisory | ✅ `architect_align` present in `architect-agent.capability_list` of `stub_capabilities.yaml`. **Runbook docs bug:** the yaml uses top-level key `capabilities:`, not `agents:` — the python one-liner in §0.5 returns empty. | `head stub_capabilities.yaml` |
| 0.6 | ADR pair | Option A | — |
| 1 | NATS provisioning | ✅ all 7 streams + auth checks via `verify-nats.sh` (PASSED 7/7) | — |
| 2.1 | specialist-agent .env | ✅ `local`/`LLM_BASE_URL=http://promaxgb10-41b1:9000`/`NATS_USER=rich`/`NATS_PASSWORD=<set>`. `OPENAI_BASE_URL` and `*_LOCAL_MODEL` absent from `.env` but provided by `docker-compose.dual-role.yml` defaults — Bug #3 fix normalises `/v1` in code (`_resolve_agent_model("local")`), so operator-facing `.env` stays clean. | `.env` grep |
| 2.2 | Dual-role stack up with new image | ✅ both containers `Up` after `down + up -d`; image id `dc8d9e75d0da` confirmed | `docker ps`, `docker inspect` |
| 2.3 | Container env propagated | ✅ `AGENT_MODELS__REASONING_MODEL=local`, `LOCAL_MODEL=architect-agent`, `LLM_BASE_URL=http://host.docker.internal:9000`, `NATS_USER=rich`, `NATS_PASSWORD set (17 chars incl trailing newline)` | `docker exec printenv` |
| 2.4 | KV registration | ✅ `architect-agent`, `product-owner-agent`, `jarvis` all present | `nats kv ls` |
| 2.5 | Architect tool surface | ✅ tool count 4, includes `architect_align` | `nats kv get` |
| 3.1 | jarvis chat boot | ✅ clean — `nats_connect_success`, `capability_registry_loaded count=4`, `capabilities_mode=live`, `forge_notifications_subscribed`, `jarvis_startup_complete` | `evidence/dddsw-demo/chat-2026-05-08-postfix-run1.log` |
| 4 (run 1) | Dispatch fires + judgment rendered | ❌ **Bug #5 surfaced** — supervisor (`qwen36-workhorse`) invented arg names `{adr_id, adr_summary, proposal_summary, context}` instead of the manifest-required `{context, proposal, question}`. Architect rejected: *"Missing required arguments for 'align': proposal, question"* in 6ms. Trace `outcome_type=exhausted`, but **Bugs #1/#2/#3 all proven fixed** by the round-trip happening at all (architect reached, mapping applied, model called would have happened if args were valid). Supervisor pivoted to its own analysis. | trace `31a2e8de`, `232ec2e0`, fallback `architect_explore` `368f9149` |
| 4 (run 2) | Dispatch fires + judgment rendered | ✅ With prompt explicitly listing the three required arg names, supervisor constructed the right payload. Architect dispatched, replied with `AlignmentJudgment{judgment: "misaligned", confidence: 0.95, reasoning: <one paragraph>, suggestions: []}`. Trace `outcome_type=success`, wall-clock 5.3s. Supervisor rendered judgment to chat. | trace `8df345b4`, `evidence/dddsw-demo/chat-2026-05-08-postfix-run2.log` |
| 4 (diagnostic) | Direct `nats request` round-trip | ✅ rtt 3.6s. Reply landed via `msg.reply` inbox (NOT on `agents.result.<agent_id>`) — Bug #1 fix verified at the wire level. Body: well-formed `ResultPayload{command: "align", result: AlignmentJudgment{...}, success: true}` — Bug #2 verified (would have rejected `architect_align` if mapping miss); Bug #3 verified (model call returned 200, not 404). | `/tmp/dddsw-slide-raw.txt`, captured to `evidence/.../slide-002` |
| 5.1 | Wire tap on `agents.command.architect-agent` (corrected post-Bug #4) | ✅ 4 envelopes captured (3 run-1 + 1 run-2 success) | `evidence/dddsw-demo/wire-command-2026-05-08-postfix.log` |
| 5.2 | Wire tap on `agents.result.architect-agent` | ✅ **0 envelopes — by design.** Bug #1 fix replies via `msg.reply` inbox; the `agents.result.<agent_id>` subject is no longer used for request/reply. **Runbook §5.2 should be updated** — the on-stage operator should not expect this tap to fill (it'll mislead the audience into thinking the architect didn't reply). The inbox tap (e.g. `_INBOX.>`) is the new "live wire mirror" if one is wanted. | `evidence/dddsw-demo/wire-result-2026-05-08-postfix.log` (empty by design) |
| 5.3 | AlignmentJudgment captured to slide artefact | ✅ `evidence/dddsw-demo/8df345b4-7b47-4214-8ae3-959aac5252e4.json` — clean JSON with judgment / confidence / reasoning / suggestions populated | — |
| 7.1 | Chat transcript | ✅ `~/.jarvis/transcripts/8df345b4-7b47-4214-8ae3-959aac5252e4.txt` + repo-tracked `evidence/dddsw-demo/chat-2026-05-08-postfix-run{1,2}.log` | — |
| 7.2 | Routing-history offload | ✅ `~/.jarvis/traces/8df345b4-7b47-4214-8ae3-959aac5252e4.json` — `outcome_type=success`, `chosen_specialist_id=architect-agent`, `wall_clock_ms=5354`, `subagent_final_state=success`. Run-1 traces also captured for reference. | — |
| 7.3 | command_history.md entry | ⏳ Pending — to follow this file | — |
| 7.4 | RESULTS file | ✅ THIS FILE | — |
| 8 | Demo close | ✅ Phases 0-5+7 all green; Bugs #1/#2/#3 closed with evidence; one residual non-blocker (Bug #5) noted for fix-forward | — |

---

## What's now working — talk narrative confirmed

- **Bug #1 (PubAck race) → CLOSED.** Architect's `NATSAdapter` honours the inbound message's `reply` header (`subscribe_with_reply` + `publish_raw` in `nats-core` v0.4.0). Verified: direct `nats request` returns the `AlignmentJudgment` ResultPayload in 3.6s — not a 32-byte PubAck. Jarvis's `client.request(...)` future now resolves with the architect's actual reply.
- **Bug #2 (`on_command` mapping miss) → CLOSED.** `_dispatch_command` consults `self.tool_to_command` so `architect_align` → `align`. The architect dispatched the request without the previous "Command 'architect_align' not supported" rejection. Verified by trace `8df345b4`.
- **Bug #3 (`OPENAI_BASE_URL` /v1 suffix) → CLOSED.** `_resolve_agent_model("local")` appends `/v1` to `LLM_BASE_URL` before mirroring into `OPENAI_BASE_URL` via `setdefault`. Verified by the architect successfully invoking the `architect-agent` Gemma 4 model (no 404). Idempotent on `/v1`-suffixed inputs.
- **Bug #4 (runbook wire-tap subject pattern) → DOCS-PATCH STILL PENDING.** This run used the corrected pattern (`agents.command.architect-agent` exact, no trailing `.>`). Runbook still needs a quick patch.

The local-first / single-machine / fine-tuned-architect story holds end-to-end. **Marginal cost per dispatch: $0.00. Architect inference: 3.6s warm.** This is the demo.

---

## Newly surfaced (Bug #5) — non-blocker for the talk if the operator's prompt is explicit

**Symptom:** With a naturally phrased prompt ("I want the architect to align this proposal against ADR-ARCH-001…"), the supervisor invents arg names like `{adr_id, adr_summary, proposal_summary, context}` rather than the manifest-required `{context, proposal, question}`. The architect correctly rejects with *"Missing required arguments for 'align': proposal, question"* in 6ms. Three traces captured this in run 1.

**Cause:** `CapabilityDescriptor.as_prompt_block()` in `jarvis/src/jarvis/tools/capabilities.py:135-164` formats the catalogue as `tool_name (risk_level) — description` with **no parameter schema**. The supervisor sees only the tool name + description; the manifest's `parameters: {properties, required}` is in the live KV but never reaches the prompt. The supervisor has to guess the JSON shape.

**Workaround used in this run:** Run 2 prompt explicitly listed the three required arg names and provided values. Worked first try (trace `8df345b4`, success in 5.3s).

**Fix-forward (recommended before the talk):** Extend `as_prompt_block()` to render `parameters.properties` keys + `parameters.required` for each `tool_name`. Roughly:

```
- architect_align (read_only) — Align an existing design against the ADR set; emit an AlignmentJudgment.
    Args (required): context (string), proposal (string), question (string)
```

Repository scope: jarvis (`src/jarvis/tools/capabilities.py`). ~10 LOC + a snapshot test. Without it, the on-stage prompt has to be over-engineered to pre-list the args, which dents the "look how naturally it routes" demo claim.

**Important note:** Bug #5 is **wholly orthogonal** to Bugs #1-#3. It was masked previously by the wire-level failures — once the wire round-trip works, the supervisor's payload-construction quality becomes the next hop's bottleneck.

## Other surfaced docs gaps in the runbook (DOCS-only)

- **§0.5 yaml introspection one-liner** uses `d.get('agents', [])` but the file's top-level key is `capabilities:` — silently returns empty. Suggested fix: `d.get('capabilities', [])`.
- **§4.3 `judgment` Literal values** lists `"needs_clarification" | "aligned" | "not_aligned"` — actual schema (`specialist_agent/generation/types.py:147`) is `Literal["aligned", "misaligned", "needs_clarification"]`. The model returned `"misaligned"`, which is in-schema. Runbook should be aligned to the actual Literal.
- **§5.2 "wire tap on `agents.result.<agent_id>`"** is now a misleading expectation — Bug #1 fix routes replies via `msg.reply` inbox, so this subject is **not** used for request/reply traffic in the demo path. Either drop §5.2 or replace with an `_INBOX.>` tap (or a directed log of jarvis's `nats_request_received` event).
- **§0.1 expected commit `ca2ba6b`** is several commits stale — top-of-log moved to `4c53e6c`. Suggest dropping the specific hash (the runbook is otherwise version-agnostic).

## Hygiene flags (still applicable, non-blocking)

- **`OPENAI_API_KEY` in `specialist-agent/.env`** is still a real `sk-proj-…` key — not used by the local-first path but reads off-narrative. Rotate + replace with `not-needed` before the talk.
- **`nats-core/pyproject.toml` had `version = "0.3.0"`** despite the `v0.4.0` git tag and the consuming `nats-core>=0.4` floor in `specialist-agent/pyproject.toml`. **Bumped to `0.4.0` during this run** (one-line edit with user approval) to unblock the docker rebuild. Worth committing the bump in `nats-core` so the next rebuild doesn't trip the same trap.

## Next steps before 2026-05-16 (8 days)

1. **(Recommended)** Patch `as_prompt_block()` to expose `parameters.properties` + `parameters.required` so the supervisor stops inventing arg names. ~10 LOC in jarvis + snapshot test. Closes Bug #5.
2. **Patch the runbook** — Bug #4 (wire-tap subject), §0.5 yaml key, §4.3 judgment Literal, §5.2 inbox-routing note. ~15 line edits.
3. **Commit `nats-core/pyproject.toml` v0.4.0 bump** so future rebuilds don't trip the unbumped-version trap.
4. **Dress rehearsal** the day before (2026-05-15). Warm the architect with one throwaway `align` call before going on stage so the first audience-facing call is on the warm path.
5. *(Optional)* Save a second run with Option B (drift-rich pair: ADR-ARCH-008 vs forge SQLite drift) to hold in reserve for Q&A.

---

## Evidence index

All under [`docs/runbooks/evidence/dddsw-demo/`](evidence/dddsw-demo/):

- `chat-2026-05-08-postfix-run1.log` — INFO-level boot + Phase 4 transcript (run 1, Bug #5 reproduction)
- `chat-2026-05-08-postfix-run2.log` — INFO-level boot + Phase 4 transcript (run 2, success with explicit args)
- `wire-command-2026-05-08-postfix.log` — 4 envelopes on `agents.command.architect-agent` (3 run-1 misshape + 1 run-2 success)
- `wire-result-2026-05-08-postfix.log` — **0 envelopes by design** (Bug #1 fix routes replies via `msg.reply` inbox)
- `trace-architect_align-8df345b4-success.json` — FRR-003 trace, `outcome_type=success`, `wall_clock_ms=5354`
- `trace-architect_align-31a2e8de-bug5-missing-args.json` — Bug #5 evidence (one of three)
- `trace-architect_align-232ec2e0-bug5-missing-args.json` — Bug #5 evidence
- `trace-architect_explore-368f9149-bug5-fallback.json` — supervisor's sibling-capability fallback after `architect_align` rejected
- `8df345b4-7b47-4214-8ae3-959aac5252e4.json` — **the slide artefact** (clean `AlignmentJudgment` JSON)

Live transcript also at `~/.jarvis/transcripts/8df345b4-7b47-4214-8ae3-959aac5252e4.txt` (per LES1 §8 / runbook §7.1).
