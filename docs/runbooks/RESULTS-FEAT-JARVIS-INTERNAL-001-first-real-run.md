# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run

**Date:** 2026-05-01
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident first walkthrough (host = `127.0.0.1` per `/etc/hosts`)
**correlation_id:** `a58ec9a7-27c6-485a-beac-e18675639a10`
**Outcome:** ⏸ Partial — wire e2e proven up to forge consume+ack, but the runbook needs gap-folds before re-run; Phase 7 (stage-complete back-flow) is not satisfiable against the FEAT-FORGE-009 surface as shipped.

## Summary in one paragraph

`queue_build` succeeded end-to-end on the wire: a `BuildQueuedPayload` was published to JetStream subject `pipeline.build-queued.FEAT-43DE`, the `forge-serve` durable consumer dequeued and acked it (`delivered: 1, acked: 1`), and the chat REPL reported the queue ack with the correlation_id back to the operator. The Phase 3 close criterion as the runbook frames it (stage-complete events flowing back into the chat) **was not met**, because (a) `forge serve`'s default `dispatch_payload` is a receipt-only stub that logs and returns — it does not run an autobuild and does not publish stage-complete back; and (b) Jarvis's own `forge_subscriber` failed to attach to the workqueue PIPELINE stream during startup ("consumer must be deliver all on workqueue stream"), so even if forge had emitted stage-complete events Jarvis would not have rendered them. Both of those are real follow-up work, not test operator error. The single real-feature id used was **`FEAT-43DE`** (the internal id of FEAT-JARVIS-INTERNAL-001 per `.guardkit/archive/FEAT-43DE/feature_state.yaml`); the runbook's literal `FEAT-JARVIS-INTERNAL-001` string fails `queue_build`'s `^FEAT-[A-Z0-9]{3,12}$` regex.

## Per-phase outcomes

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | `git log -5` top is `8ec9d39` (runbook update) atop `2864173` (FEAT close); working tree clean |
| 0.2 | GB10 reachable | ✅ (we are GB10) | `uname -a` → `Linux promaxgb10-41b1`; `/etc/hosts` → `127.0.0.1 promaxgb10-41b1` |
| 0.3 | forge nats-core symlink | ✅ | `.guardkit/worktrees/nats-core -> ../../../nats-core` resolves; `pyproject.toml` readable |
| 0.4 | provider keys set | ✅ with notes | `JARVIS_OPENAI_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `FALKORDB_HOST=whitestocks` set; `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `JARVIS_NATS_URL`, `JARVIS_GRAPHITI_ENDPOINT` not set in `.env`. Local-only ethos (no cloud APIs) means we route through llama-swap on `:9000`; cloud keys are not required for this run |
| 1.1 | NATS container up | ✅ | `ships-computer-nats` Up 20 hours (healthy); `0.0.0.0:4222`, `0.0.0.0:8222` bound |
| 1.2 | 7 streams + 4 KV buckets | ✅ | All 7 canonical streams (PIPELINE, AGENTS, JARVIS, NOTIFICATIONS, SYSTEM, FLEET, FINPROXY) present and current; all 4 KV buckets (agent-status, agent-registry, pipeline-state, jarvis-session) present. (Three leftover test streams from 2026-04-16 — PERSISTENCE_TEST, RETRIEVAL_TEST, SURVIVAL_TEST — are unrelated drift; not blocking.) Provisioning required NATS auth via `nats://rich:${RICH_NATS_PASSWORD}@localhost:4222` — `verify-nats.sh` without auth misreports streams as `[MISSING]` when in fact they exist; LES1 §7 fresh-volume note misleads here |
| 1.3 | `pipeline.build-queued.>` bound | ✅ | `nats stream info PIPELINE -j` → `subjects=["pipeline.>"]` (covers `pipeline.build-queued.*`) |
| 2.1 | forge image built | ✅ with workaround | `forge:production-validation` (430MB, retagged `forge:latest` for runbook compat). `scripts/build-image.sh` is broken on this layout: it cd's to forge's parent and runs `--build-context nats-core=../nats-core`, which from the parent resolves to `~/Projects/nats-core` (does not exist). Worked around by running `docker buildx build --build-context nats-core=../nats-core -t forge:production-validation -f Dockerfile .` directly from inside `forge/`. Forge runbook gap-fold candidate, not jarvis |
| 2.2 | forge serve running | ✅ with workaround | `forge-prod` Up (healthy). The runbook's `-e NATS_URL=...` is wrong; forge reads `FORGE_NATS_URL`. Runbook also assumed port 8088 free for healthz; the daemon defaults to 8080 which is held by `open-webui` host-network — set `FORGE_HEALTHZ_PORT=8088`. Started with `-e FORGE_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222 -e FORGE_HEALTHZ_PORT=8088 -e FORGE_LOG_LEVEL=info` |
| 2.3 | /healthz green | ✅ | `curl http://localhost:8088/healthz` → `{"status":"healthy"}` (per `_serve_healthz.py:80` contract — 200 healthy iff JetStream subscription is live). `forge-serve` durable consumer attached on PIPELINE |
| 3.1 | architect container up | ⚠️ skipped | No `specialist-agent-architect` containers running on this host. Per runbook: "technically optional for the close criterion" because FEAT-JARVIS-INTERNAL-001 is documentation-only and dispatches no PO/architect work. Not blocking |
| 3.2 | architect ping | ⚠️ skipped | n/a |
| 4.1 | graphiti/falkordb up | ⚠️ partial | `graphiti-mcp` Up 2 days but **unhealthy**; no local `falkordb` container (`FALKORDB_HOST=whitestocks` in `.env` points off-machine) |
| 4.2 | embeddings reachable | ✅ (different surface) | `curl :9000/v1/embeddings` with `nomic-embed` returned 768-dim vector — but this is **llama-swap**, not Graphiti. Distinct surface; not the right gate. With no `JARVIS_GRAPHITI_ENDPOINT` set, jarvis uses the DDR-019 soft-fail path |
| 5.1 | jarvis chat boots | ✅ with caveat | `.venv` bootstrapped from scratch (Python 3.12 host venv; nats-core editable from sibling, jarvis editable). Supervisor builds, NATS connect succeeds, fleet/forge subscriber subscriptions fail with workqueue config errors (DDR drift — see Gaps table) |
| 5.2 | tool inventory smoke | ✅ | Reasoner enumerated `queue_build`, `dispatch_by_capability`, plus 8 other tools without prompting (transcript: `phase5.2-toolinv.log`) |
| 6.2 | `queue_build` returns success | ✅ | `correlation_id=a58ec9a7-27c6-485a-beac-e18675639a10`; `publish_target=pipeline.build-queued.FEAT-43DE`; `queued_at=2026-05-01T15:12:09 UTC`. Required substituting `FEAT-43DE` for the runbook's literal `FEAT-JARVIS-INTERNAL-001` to pass `^FEAT-[A-Z0-9]{3,12}$` |
| 6.3 | message visible on PIPELINE stream | ✅ via state | PIPELINE `state.last_seq=1` (one publish), `state.messages=0` because workqueue retention removed the message after ack. The runbook's `nats stream view --headers` requires a TTY and cannot be teed; replaced with `stream info -j` and `consumer info -j` |
| 7.1 | between-prompt notifications render | ❌ as expected | No notification lines drained. Two independent reasons: (a) `forge serve`'s default `dispatch_payload` (`_serve_daemon.py:146-180`) is a receipt-only stub — logs and returns, no autobuild, no publish-back; (b) jarvis's `forge_subscriber` failed to attach during startup with `BadRequestError code=10101 description='consumer must be deliver all on workqueue stream'` — even a real stage-complete publish would not be received. Neither is operator error |
| 7.2 | forge logs show consume + publish-back | ⚠️ via consumer state | `forge-serve` consumer info: `delivered=1, acked=1, num_pending=0, num_redelivered=0` proves forge dequeued and acked. Container `docker logs` is empty: `forge serve` parses `FORGE_LOG_LEVEL` into `ServeConfig.log_level` but does not call `logging.basicConfig()` or attach a handler, so `_default_dispatch`'s `logger.info` calls go nowhere. Forge gap-fold |
| 8.1 | chat transcript saved | ✅ | `~/.jarvis/transcripts/a58ec9a7-27c6-485a-beac-e18675639a10.txt` |
| 8.2 | Graphiti routing-history dump | ⚠️ skipped | No `JARVIS_GRAPHITI_ENDPOINT` configured |
| 8.3 | local trace offload | ⚠️ none written | Chat log shows `routing_history_write_failed` but no file landed in `~/.jarvis/traces/` (directory does not exist). The DDR-019 soft-fail path appears to drop on the floor when both `graphiti_endpoint` is `None` AND no traces dir is provisioned, rather than autocreating the default `~/.jarvis/traces/`. Jarvis gap-fold candidate |
| 8.4 | command-history entry | ✅ | Appended to `docs/history/command_history.md` (existing filename uses underscore not hyphen — runbook §8.4 references `command-history.md`, also a gap-fold) |

## Operator-side gaps in the runbook (gap-fold candidates)

| What needed manual adjustment | Suggested runbook fix |
|---|---|
| `verify-nats.sh` reported all streams `[MISSING]` because no auth credentials were sourced; the script silently swallows `nats stream ls` errors and treats absence-due-to-auth as absence-of-stream | Phase 1.2 should source `nats-infrastructure/.env` and export `NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222` before running `verify-nats.sh`; or `verify-nats.sh` itself should detect auth failure and report it distinctly from "stream missing" |
| Phase 0.4 doesn't acknowledge that `JARVIS_NATS_URL` must contain credentials (the running NATS server uses multi-account auth — APPMILLA/FINPROXY/SYS) | Phase 0.4 should require `JARVIS_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222` or `JARVIS_NATS_CREDENTIALS_PATH` set, not just any of the listed cloud keys. The current §0.4 list omits NATS auth |
| Phase 2.1 says `bash scripts/build-image.sh`; the script is broken on the canonical layout (cd's to forge's parent, then `../nats-core` from there resolves to `~/Projects/nats-core` which doesn't exist) | Either fix the script to invoke buildx from inside `forge/` (so `../nats-core` resolves to the sibling), or change Phase 2.1 to invoke buildx directly. Forge-side gap |
| Phase 2.2 uses `-e NATS_URL=…` and `-e FORGE_LOG_LEVEL=info` — the daemon reads `FORGE_NATS_URL`, not `NATS_URL`, and there's no logging handler attached so `FORGE_LOG_LEVEL` has no observable effect | Use `FORGE_NATS_URL` and add a forge follow-up to wire `logging.basicConfig(level=config.log_level)` in `serve.py` so `FORGE_LOG_LEVEL` actually does something |
| Phase 2.3 uses `:8088` for healthz; the daemon defaults to `:8080`, and 8080 is held by `open-webui` host-network on this box | Document the `FORGE_HEALTHZ_PORT` override and the open-webui port-conflict caveat |
| Phase 4.2 hits llama-swap's `/v1/embeddings` on `:9000` and treats success as proof Graphiti is reachable; these are different services | Phase 4 should hit the actual Graphiti HTTP endpoint, with a separate llama-swap embeddings probe if relevant |
| Phase 6.2 prompt uses `FEAT-JARVIS-INTERNAL-001` as the feature_id; this is the brand name but `queue_build`'s validation regex is `^FEAT-[A-Z0-9]{3,12}$` so brand-name-with-hyphens fails — the *internal* id is `FEAT-43DE` | Phase 6.2 prompt template should use the internal `.guardkit/features/`-resident id, not the brand name. Also the on-disk YAML lives at `.guardkit/archive/FEAT-43DE/feature_state.yaml` (already merged/archived per `47ec4e5`), not the `.guardkit/features/FEAT-JARVIS-INTERNAL-001.yaml` path the runbook hard-codes — the operator-decision note already calls this out as "wire test against an already-merged feature" but doesn't update the path |
| Phase 6.3 uses `nats stream view --subject=…` which requires a TTY and cannot be `tee`'d non-interactively; the workqueue retention removes the message before any view command can see it anyway | Use `nats stream info -j` to read `last_seq`, plus `nats consumer info PIPELINE forge-serve -j` to read `delivered`/`acked`/`num_pending`. Both produce the same evidence and survive `tee` |
| Phase 7.1 expects stage-complete notifications to render, but FEAT-FORGE-009's `forge serve` ships only the receipt scaffold; its default `dispatch_payload` is a stub | The runbook's preconditions table claims "FEAT-FORGE-009 production image + `forge serve` daemon merged" is sufficient; it isn't. Either narrow the close criterion to "forge consumed and acked" (which we did prove), or add a forge precondition that `dispatch_payload` is wired to the real autobuild orchestrator + stage-complete publish path. The current Phase 7 expectation is structurally unsatisfiable against `forge:732408f` |
| Phase 5.1 `--log-level INFO` flag does not exist on `jarvis chat`; only `JARVIS_LOG_LEVEL` env works | Drop the `--log-level` flag from §5.1 and §6.1 |
| `JARVIS_OPENAI_BASE_URL=https://api.openai.com/v1` is misleading — `lifecycle.py:569-570` unconditionally sets `os.environ["OPENAI_BASE_URL"]=<llama_swap_base_url>/v1`, so the cloud OpenAI URL never wins | Either Phase 0.4 should explicitly state "the supervisor always routes through llama-swap; pick a model llama-swap actually serves" and provide a list (`gemma4-tutor`, `qwen36-workhorse`, etc.), or jarvis should respect `JARVIS_OPENAI_BASE_URL` when it's explicitly set rather than always clobbering. Project-direction matters here per user feedback (local-only ethos = llama-swap is mandatory; the .env's cloud URL is the actual bug) |
| Jarvis fleet register, KV bind, and forge_subscriber attach all fail at startup against canonical NATS provisioning: `stream name already in use with a different configuration` (KV) and `consumer must be deliver all on workqueue stream` (forge_subscriber) | Either jarvis lifecycle code or the canonical stream/KV definitions need to converge — the JARVIS stream / agent-registry KV / PIPELINE consumer config jarvis tries to set up does not match what `nats-infrastructure` provisions. Cross-repo gap. Until reconciled, jarvis cannot subscribe to stage-complete events at all (DDR-030 between-prompt notification path is dead) |
| Runbook says "every shell block executed verbatim" appended to `docs/history/command-history.md`; the existing file is `command_history.md` (underscore) | Pick one and stick to it; references throughout the runbook drift |
| `jarvis chat` REPL is interactive only — there is no `--prompt` flag or non-interactive-with-stdin documented mode for runbook automation. Piping stdin works (REPL uses `sys.stdin.readline`) but is undocumented | Add a "non-interactive mode" example to the REPL doc + runbook §6.1 |

## Cross-machine state observed

- **NATS** (`ships-computer-nats`, container, host-network): up, healthy, 4222/8222 bound, 7 streams + 4 KV buckets canonical, plus 3 leftover test streams from April 16 (`PERSISTENCE_TEST`, `RETRIEVAL_TEST`, `SURVIVAL_TEST`).
- **forge-prod** (host-network, `forge:latest` = `forge:production-validation`): up, healthy, durable consumer `forge-serve` attached on PIPELINE.
- **graphiti-mcp**: up (2 days), reports unhealthy. Not used in this run; `JARVIS_GRAPHITI_ENDPOINT` unset.
- **open-webui**: up (host-network on 8080); reason for the `FORGE_HEALTHZ_PORT=8088` override.
- **llama-swap**: up via systemd, serving on `:9000` with `gemma4-tutor`, `nomic-embed`, `qwen-graphiti`, `qwen36-workhorse`. **No `jarvis-reasoner`** model — `.env.example` default `JARVIS_SUPERVISOR_MODEL=openai:jarvis-reasoner` is stale.

## Decision

- [ ] Phase 3 closed canonical
- [x] **Phase 3 closed with gap-folds** — wire e2e proven (publish → JetStream → forge consume+ack); runbook needs the fixes in the gaps table above before MacBook walkthrough; the FEAT-FORGE-009 receipt-only `dispatch_payload` is the headline architecture-vs-runbook gap and a follow-up forge feature is needed before a true stage-complete round-trip can be claimed
- [ ] Partial — single-phase failure with follow-up task

## Recommended follow-up tasks

1. **forge**: wire `dispatch_payload` to the real `pipeline_consumer` orchestrator + stage-complete publish path (the comment in `_default_dispatch` explicitly defers this).
2. **forge**: add `logging.basicConfig(level=config.log_level)` in `serve.py` so `FORGE_LOG_LEVEL` produces visible logs.
3. **forge**: fix `scripts/build-image.sh` invocation path (run buildx from inside `forge/` not its parent).
4. **jarvis**: reconcile `JARVIS` stream / `agent-registry` KV / forge_subscriber consumer config with canonical `nats-infrastructure` definitions — three independent NATS-side mismatches at startup.
5. **jarvis**: make `lifecycle.py:569-570` honor an explicit `JARVIS_OPENAI_BASE_URL` (or rename the field to remove the cloud-OpenAI implication).
6. **jarvis**: have the DDR-019 soft-fail trace-offload path autocreate `~/.jarvis/traces/` when graphiti_endpoint is unset, so the offload actually lands instead of disappearing silently.
7. **runbook**: fold all gaps in the table above + retire the literal `FEAT-JARVIS-INTERNAL-001` feature_id in §6.2 in favor of the real internal id (`FEAT-43DE` for this feature).
8. **MacBook over Tailscale walkthrough**: not run. Defer until forge stage-complete wiring lands; without it, the MacBook walkthrough would only re-prove publish→consume.

## Evidence files

All under `/tmp/runbook-evidence/`:
- `phase1.1-compose-ps.log`, `phase1.2-verify-nats.log`, `phase1.2-provision-streams.log`, `phase1.2-provision-kv.log`, `phase1.3-pipeline-info.json`
- `phase2.1-build-image.log`, `phase2.1-images.log`, `phase2.2-forge-logs.log`, `phase2.3-healthz.json`, `phase2.3-consumers.log`
- `phase3.1-specialist.log` (empty — no containers)
- `phase4.1-graphiti.log`, `phase4.2-embeddings.log`
- `phase5.0-health.log`, `phase5.2-toolinv.log`
- `phase6-7-chat.log` (first attempt — gpt-4o-mini failed at llama-swap), `phase6-7-chat-v2.log` (qwen36-workhorse + FEAT-43DE — successful queue), `phase6.3-stream-state.json`, `phase7.2-consumer-info.json`, `phase7.2-forge-logs.log` (empty)
- Transcript: `~/.jarvis/transcripts/a58ec9a7-27c6-485a-beac-e18675639a10.txt`
