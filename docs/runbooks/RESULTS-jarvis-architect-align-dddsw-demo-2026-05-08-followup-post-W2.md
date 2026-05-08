# RESULTS: Jarvis → Architect Align — DDD South West Demo (post-W2 follow-up)

**Date:** 2026-05-08 (afternoon — second walkthrough of the day)
**Operator:** Claude Code (non-interactive, stdin-piped REPL driver)
**Machine:** GB10 (`promaxgb10-41b1`) — single-host all-local
**Jarvis HEAD:** `30e4ae4` (post `50704b6` TASK-DSR-003 W2 — live CapabilitiesRegistry wired into dispatch resolver)
**specialist-agent HEAD:** `7345e33` (post `11f0b54` TASK-LLM-0D07 — local provider wired to LOCAL_MODEL)
**Image:** `specialist-agent:latest` (built 2026-05-08 07:06 BST — same image as morning run)
**ADR pair:** Option A — ADR-ARCH-001 vs Opus 4.7 escalation proposal
**Companion file:** [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md) — the morning run, blocked by Gap DISPATCH-STUB-RESOLVER (since closed by TASK-DSR-003 W2)

**Outcome:** ⏸ **STILL BLOCKED, but at a different layer.** The morning's resolver gap is gone — `dispatch_by_capability(tool_name="architect_align")` now resolves to `architect-agent` via the live KV-backed registry (verified by trace `outcome_detail.visited=["architect-agent"]` and a wire-tap envelope on `agents.command.architect-agent`). Three new bugs surfaced behind it; demo path remains red.

**Demo blocking?** YES. The DDD South West demo (2026-05-16) cannot land an `AlignmentJudgment` until **Bug #1 (PubAck race)** is fixed in either jarvis or specialist-agent. Bugs #2 (`on_command` mapping miss) and #3 (`OPENAI_BASE_URL` /v1 suffix) are masked by Bug #1 today but block the next walkthrough.

---

## What's new vs the morning run

| Topic | Morning run (`ca2ba6b`, pre-W2) | This run (`30e4ae4`, post-W2) |
|---|---|---|
| Resolver lookup of `architect_align` | `ERROR: unresolved` (resolver iterated stub yaml) | ✅ resolved → `architect-agent` (resolver reads live KV, TASK-DSR-003 W2) |
| Wire-tap envelopes on `agents.command.architect-agent` | 0 captured | 2 captured (one per dispatch attempt — `architect_align`, `architect_explore`) |
| Wire-tap envelopes on `agents.result.architect-agent` | 0 captured | 3 captured (2 jarvis-driven + 1 from a direct-`nats request` diagnostic) |
| Trace `outcome_type` | `unresolved` | `exhausted` |
| Root cause | Static-stub resolver (closed by W2) | PubAck race + 2 stacked secondary bugs |

The W2 fix did exactly what it claimed. We've moved one layer down the dispatch path.

## Phase × gate summary

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main + clean tree | ⚠️ HEAD past `ca2ba6b` (top: `30e4ae4`); `command_history.md` + first-real-run runbook dirty (doc-only) | `git status -s -uno` |
| 0.2 | specialist-agent main + image freshness | ⚠️ Image dated **2026-05-08 07:06 BST** ✅; `docker-compose.dual-role.yml` + `command-history.md` dirty | `docker images` |
| 0.3 | llama-swap + `architect-agent` model | ✅ `architect-agent`, `qwen36-workhorse`, `gemma4-tutor`, `nomic-embed`, `qwen-graphiti` all listed | `/v1/models` |
| 0.4 | NATS up + APPMILLA creds | ✅ Up 29h healthy; `RICH_NATS_PASSWORD` extracted | — |
| 0.5 | Stub yaml advertises `architect_align` | ✅ — | `stub_capabilities.yaml` |
| 0.6 | ADR pair | Option A | — |
| 1 | NATS provisioning | ✅ all 7 streams + auth checks | `verify-nats.sh` |
| 2.1 | specialist-agent .env | ⚠️ `local`/`LLM_BASE_URL`/`NATS_USER`/`NATS_PASSWORD` set ✅; `OPENAI_BASE_URL` missing ❌ (Bug #3); `OPENAI_API_KEY` is a real cloud key | — |
| 2.2 | Dual-role stack | ✅ Up 8h (re-used; no cycle) | — |
| 2.3 | Container env propagated | ✅ for vars present in compose; `OPENAI_BASE_URL` absent (Bug #3 prerequisite) | — |
| 2.4 | KV registration | ✅ `architect-agent`, `product-owner-agent`, `jarvis` | — |
| 2.5 | Architect tool surface | ✅ tool count 4 incl. `architect_align` | — |
| 3.1 | Boot | ✅ clean — `nats_connect_success`, `capability_registry_loaded count=4`, `capabilities_mode=live` | `evidence/dddsw-demo/chat-2026-05-08.log` |
| 4 (attempt 1) | Dispatch fires + AlignmentJudgment rendered | ❌ supervisor invoked `dispatch_by_capability(tool_name="architect_align")`; trace `outcome_type=exhausted`; reply was `{"stream":"AGENTS","seq":9}` (PubAck — Bug #1); supervisor pivoted to its own analysis | trace `6b04c4c6-…json`, chat log run-1 |
| 4 (attempt 2) | (re-run with corrected wire taps) | ❌ same outcome — second dispatch attempt added `architect_explore` (supervisor exploring the failure space); both got PubAck back | traces `7e7c72e2`, `ff0e19ea`; `wire-{command,result}-2026-05-08.log` |
| 4 (diagnostic 3) | Direct `nats request` with `command="align"` (bypass Bug #2) | ❌ surface error `Command 'align' failed: Error code: 404` (Bug #3) | container log `_handle_align` traceback |
| 5.1 | Wire tap on `agents.command.architect-agent.>` (per runbook) | ❌ 0 envelopes — runbook subject pattern is broken (Bug #4) | empty log |
| 5.1' | Wire tap on `agents.command.>` (corrected) | ✅ 2 envelopes captured (correlation_ids `7e7c72e2`, `ff0e19ea`) | `evidence/dddsw-demo/wire-command-2026-05-08.log` |
| 5.2' | Wire tap on `agents.result.>` (corrected) | ✅ 3 envelopes captured (2 jarvis + 1 diag) — all `success: false` | `evidence/dddsw-demo/wire-result-2026-05-08.log` |
| 5.3 | AlignmentJudgment captured | ⏭ N/A — no successful dispatch | — |
| 7.1 | Chat transcript | ✅ `evidence/dddsw-demo/chat-2026-05-08.log` (run-2 with corrected taps) | — |
| 7.2 | Routing-history offload | ✅ 3 traces written, all `outcome_type=exhausted`, attempts list contains the PubAck-shaped validation error | `evidence/dddsw-demo/trace-*.json` |
| 7.3 | command_history.md entry | ⏳ Pending — after this file | — |
| 7.4 | RESULTS file | ✅ THIS FILE | — |
| 8 | Demo close | ❌ Demo path not green; Phases 0-3 clean; Phase 4 blocked by Bugs #1-#3 | — |

## Bug catalogue (in priority order)

### Bug #1 — PubAck race on JetStream-backed COMMAND subject (DEMO BLOCKER)

**Symptom:** Every jarvis dispatch records this attempt detail in the FRR-003 trace:
```
3 validation errors for ResultPayload
  command: Field required [type=missing, input_value={'stream': 'AGENTS', 'seq': N}, input_type=dict]
  result:  Field required ...
  success: Field required ...
```

**Cause:** `Topics.Agents.COMMAND = "agents.command.{agent_id}"`. The AGENTS JetStream stream filters `agents.>` so this subject is JetStream-stored. Jarvis publishes via `nats_client.request()` (core NATS request/reply, [`dispatch.py:531`](../../src/jarvis/tools/dispatch.py#L531)) — which sets a reply-to inbox. nats-server delivers the JetStream **ingest-ack** (`{"stream":"AGENTS","seq":N}`) to that inbox immediately. The architect's actual reply is published by the `NATSAdapter` to `agents.result.architect-agent` — never to jarvis's request inbox. Jarvis resolves the request future with the PubAck, ResultPayload validation fails, attempt recorded as `specialist_error`, no other candidates → `exhausted`.

**Confirmed by:** All three traces (`7e7c72e2`, `ff0e19ea`, `6b04c4c6`) plus a direct `nats request` diagnostic (rtt **379µs**, reply was `{"stream":"AGENTS","seq":15}`). The architect's *real* reply landed on `agents.result.architect-agent` 2ms after the publish (visible in `wire-result-2026-05-08.log`) — too late for jarvis's already-resolved future.

**Fix options (pick one):**
- **(A) Specialist-agent `NATSAdapter` replies to inbox** in addition to publishing on `agents.result.<agent_id>` — i.e., honour the message's `reply` header. Smallest blast radius; preserves topology semantics.
- **(B) Jarvis dispatch subscribes-and-correlates on `agents.result.<agent_id>`** instead of using `client.request()`. Filter incoming envelopes by `correlation_id`, time out by future. Larger code change in [`dispatch.py:511-616`](../../src/jarvis/tools/dispatch.py#L511) but matches the runbook's conceptual model (`agents.command.*` outbound, `agents.result.*` inbound).
- **(C) Move COMMAND subjects outside the AGENTS JetStream filter.** Cleanest topology fix but loses the "JetStream durable replay of agent commands" property.

**Recommend (A)** — repository scope: specialist-agent.

### Bug #2 — `command_router.on_command` does not consult `tool_to_command` mapping

**Symptom:** When the architect's reply *does* arrive (visible on `agents.result.architect-agent`):
```json
{"error": "Command 'architect_align' is not supported.
  Available commands: ['align', 'explore', 'feasibility', 'greenfield']"}
```

**Cause:** `specialist-agent/src/specialist_agent/adapters/command_router.py` has two entry paths:
- `on_command(envelope)` (line 328): subscribed to `agents.command.{agent_id}`. Reads `command = cmd_payload.command` literally, looks up in `command_map`. **Never consults `self.tool_to_command`.**
- `on_tool_call(envelope, tool_name=…)` (line 397): subscribed to a different subject pattern. **Does** apply `tool_to_command` (line 408).

Jarvis publishes via `Topics.Agents.COMMAND` → hits `on_command` → mapping never fires → architect rejects all four `architect_*` names.

The mapping itself is correctly declared in both host source AND container image of [`roles/architect/__init__.py:37-41`](file:///home/richardwoollcott/Projects/appmilla_github/specialist-agent/src/specialist_agent/roles/architect/__init__.py#L37). The bug is purely in `on_command` not honouring it.

**Fix:** ~5-line patch in `command_router.on_command`:
```python
command = self.tool_to_command.get(cmd_payload.command, cmd_payload.command)
```
plus a regression test that sends `architect_align` via the COMMAND subject and asserts it dispatches `_handle_align`. Repository scope: specialist-agent.

**Important note:** Bug #2 is masked by Bug #1 in current behaviour — fixing #1 alone immediately surfaces #2. Both must land before Phase 4 can succeed.

### Bug #3 — `OPENAI_BASE_URL` missing `/v1` suffix → architect 404

**Symptom:** Direct `nats request` with `command="align"` (bypassing Bug #2) gets:
```
Command 'align' failed: Error code: 404
…
File "langchain_openai/chat_models/base.py", line 1925, in _agenerate
    _handle_openai_api_error(e)
openai.NotFoundError: Error code: 404
During task with name 'model'
```

**Cause:** TASK-LLM-0D07 (commit `11f0b54`) does:
```python
os.environ.setdefault("OPENAI_BASE_URL", LLM_BASE_URL)
```
With `LLM_BASE_URL=http://host.docker.internal:9000`, langchain-openai POSTs to `http://host.docker.internal:9000/chat/completions` → 404 (no `/v1`). The architect container only has `LLM_BASE_URL` (no `OPENAI_BASE_URL` override). Direct urllib POST from inside the container to `http://host.docker.internal:9000/v1/chat/completions` with model `architect-agent` returns **200** — confirming llama-swap and the model alias are fine; the bug is purely the URL path.

**Fix:** Either —
- Append `/v1` if not already present in the setdefault (specialist-agent fix), OR
- Set `OPENAI_BASE_URL=http://host.docker.internal:9000/v1` explicitly in `specialist-agent/.env` AND in `docker-compose.dual-role.yml`'s `environment:` block (env-var fix; recommended — more explicit).

Repository scope: specialist-agent.

### Bug #4 — Runbook §5.1 / §5.2 wire-tap subject pattern is broken (DOCS BUG)

**Symptom:** Following runbook §5.1 verbatim — `nats sub "agents.command.architect-agent.>"` — captures **0** envelopes during a real dispatch.

**Cause:** `Topics.Agents.COMMAND = "agents.command.{agent_id}"` — no correlation_id suffix. NATS `>` wildcard requires ≥1 token after, so `agents.command.architect-agent.>` doesn't match `agents.command.architect-agent`.

**Fix:** Patch runbook §5.1/§5.2 to use `agents.command.>` (or exact `agents.command.architect-agent`) and add a footnote about the wildcard gotcha. This is the runbook's "live wire mirror" stage trick (§5 talk-track) — currently silent on stage. Repository scope: jarvis (this runbook).

---

## What's working — the demo narrative is sound

- **Infrastructure layer green:** NATS, JetStream, llama-swap (incl. `architect-agent` alias serving), dual-role compose, agent-registry KV — all good.
- **Catalogue propagation green:** `architect_align`/`architect_greenfield`/`architect_explore`/`architect_feasibility` correctly published to live KV.
- **W2 wiring (TASK-DSR-003):** **Verified** — the dispatch resolver consults the live KV. The morning's stub-resolver gap is fully closed. Trace `visited=["architect-agent"]` is the proof.
- **Supervisor reasoning:** `qwen36-workhorse` selected `dispatch_by_capability` correctly with the right `tool_name`, surfaced the failure clearly to the user, and pivoted gracefully to its own analysis from the prompt context. (Two of three reasoning loops were spent narrating the architect's "timeout" — the model's framing of `exhausted` as "timing out" is forgivable.)
- **Routing-history + chat-log capture:** FRR-003 path writes traces cleanly to `~/.jarvis/traces/`; INFO log level produced a readable transcript suitable for the talk recap.

The local-first / single-machine / fine-tuned-architect story holds. The dispatch path needs ~30 LOC across two repos before any of it can run end-to-end.

---

## Next steps before 2026-05-16

Eight days remain.

1. **Fix Bug #1 (PubAck race)** — option (A): specialist-agent `NATSAdapter` honours the inbound message's `reply` header. Validate via `scripts/capture-nats-roundtrip.sh`.
2. **Fix Bug #2 (`on_command` mapping miss)** — 5-line patch + regression test in `command_router.on_command`.
3. **Fix Bug #3 (`OPENAI_BASE_URL` /v1 suffix)** — env-var fix in `specialist-agent/.env` + dual-role compose; tighten TASK-LLM-0D07's setdefault as a belt-and-braces.
4. **Patch Bug #4 (runbook subject patterns)** — `agents.command.architect-agent.>` → `agents.command.>` in §5.1/§5.2; footnote the wildcard gotcha so the stage operator doesn't fall into it.
5. **Re-run this runbook end-to-end.** Should green-light Phases 4-8. Save the resulting `AlignmentJudgment` JSON to `evidence/dddsw-demo/<correlation_id>.json` per §5.3 — that's the artefact for the slide.
6. **Dress rehearsal** the day before (2026-05-15). Warm the architect with one throwaway `align` call before going on stage (per runbook §6 last row — even with Bugs #1-#3 fixed, Gemma-4 26B-A4B cold-start latency can flatten the first response).

## Hygiene flags (non-blocking but worth addressing)

- **`OPENAI_API_KEY` in `specialist-agent/.env`** is a real `sk-proj-…` key. The local-first demo doesn't need it; consider rotating + replacing with `not-needed`. The "no cloud LLM in the path" claim reads better when no live cloud key is in env.
- **Two repos with dirty trees** at start of run (jarvis: 2 doc files; specialist-agent: 2 files incl. `docker-compose.dual-role.yml`). Worth committing the compose patch before the talk so the stage env is reproducible from clean main.
- **Runbook §0.1 expected commit `ca2ba6b`** — current top-of-log is `30e4ae4`; consider dropping the specific hash since it'll continue drifting.

## Evidence index

All under [`docs/runbooks/evidence/dddsw-demo/`](evidence/dddsw-demo/):

- `chat-2026-05-08.log` — full INFO-level boot + Phase 4 transcript (run 2, with corrected wire taps)
- `wire-command-2026-05-08.log` — 2 envelopes on `agents.command.architect-agent` (correlation `7e7c72e2`, `ff0e19ea`)
- `wire-result-2026-05-08.log` — 3 envelopes on `agents.result.architect-agent` (2 jarvis-driven + 1 direct-`nats request` diagnostic, all `success: false`)
- `trace-architect_align-7e7c72e2.json` — FRR-003 trace, `outcome_type=exhausted`, attempt detail = PubAck validation error
- `trace-architect_explore-ff0e19ea.json` — same shape; supervisor's second-attempt fallback to a sibling capability hit the same wall
