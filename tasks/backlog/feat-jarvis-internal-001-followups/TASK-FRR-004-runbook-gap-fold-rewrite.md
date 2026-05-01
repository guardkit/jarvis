---
complexity: 3
created: 2026-05-01 00:00:00+00:00
dependencies: []
discovered_on_machine: GB10 (promaxgb10-41b1)
discovered_on_date: 2026-05-01
discovered_via_correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
estimated_minutes: 90
feature_id: FEAT-JARVIS-INTERNAL-001-FRR
forward_references:
- TASK-FRR-001
- TASK-FRR-002
id: TASK-FRR-004
implementation_mode: direct
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md
priority: medium
status: backlog
tags:
- jarvis
- feat-jarvis-internal-001-followups
- documentation
- runbook
- gap-fold
task_type: documentation
title: Runbook gap-fold rewrite — fold all 13 RESULTS gaps so a fresh operator can copy-paste end-to-end
updated: 2026-05-01 00:00:00+00:00
wave: 1
---

# Runbook gap-fold rewrite

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Wave:** 1 | **Mode:** direct | **Complexity:** 3/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — entire "Operator-side gaps in the runbook (gap-fold candidates)" table; recommended follow-up #7
**Forward references:** TASK-FRR-001 (NATS subscriptions), TASK-FRR-002 (`JARVIS_OPENAI_BASE_URL` rename)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-01, correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`

## Description

The 2026-05-01 first real run on the GB10 produced a "Partial — closed with gap-folds" decision. The wire-level path was proved end-to-end (publish → JetStream → forge consume+ack), but the operator manually adjusted around **13 distinct gap-folds** during execution. Without those adjustments captured in the runbook itself, the next operator (in particular the planned MacBook-over-Tailscale follow-up walkthrough) would re-derive every adjustment from scratch — defeating the runbook's purpose.

This task folds all 13 gaps from the RESULTS file's "Operator-side gaps in the runbook" table into [`docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) so a fresh operator can copy-paste the runbook end-to-end on the GB10 verbatim (or near-verbatim — only env-pointing differences for the MacBook-over-Tailscale variant) without manual adjustments.

## Headlines (the 13 gaps)

These are pulled verbatim or paraphrased from the source RESULTS table; the task must fold every row in that table, not just the ones listed here.

1. **Phase 0.4 NATS auth** — Phase 0.4 should require `JARVIS_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222` (or `JARVIS_NATS_CREDENTIALS_PATH`). Current §0.4 list omits NATS auth; the running NATS server uses multi-account auth (APPMILLA / FINPROXY / SYS).
2. **Phase 1.2 `verify-nats.sh` auth sourcing** — Phase 1.2 should `source nats-infrastructure/.env` and export `NATS_URL` with creds before running `verify-nats.sh`. Without auth, the script reports all streams as `[MISSING]` even when they exist (it silently swallows `nats stream ls` errors and treats absence-due-to-auth as absence-of-stream).
3. **Phase 2.1 `scripts/build-image.sh` cwd** — Either fix `scripts/build-image.sh` (covered by the forge-side follow-up) or change Phase 2.1 to invoke `docker buildx build` directly from inside `forge/`. Note the forge-side fix when it lands; for now, the runbook should document the workaround and forward-reference the forge follow-up.
4. **Phase 2.2 `FORGE_NATS_URL`** — Use `FORGE_NATS_URL` (not `NATS_URL`) and document the `FORGE_HEALTHZ_PORT=8088` override (open-webui holds 8080 host-network on this box).
5. **Phase 4 graphiti probe** — Phase 4 should hit the actual Graphiti HTTP endpoint, not llama-swap's `/v1/embeddings` on `:9000`. Add a graphiti-mcp prerequisite check (and acknowledge that on the GB10, `graphiti-mcp` reports unhealthy).
6. **Phase 5.1 / 6.1 `--log-level INFO` flag** — Drop the `--log-level INFO` flag from the `jarvis chat` invocations; no such flag exists. Only `JARVIS_LOG_LEVEL` env var works.
7. **Phase 6.2 feature_id** — Replace the literal `FEAT-JARVIS-INTERNAL-001` feature_id with the on-disk internal id (`FEAT-43DE`) and the YAML path with `.guardkit/archive/FEAT-43DE/feature_state.yaml`. `queue_build`'s validation regex `^FEAT-[A-Z0-9]{3,12}$` rejects the brand-name form. Either parameterize the §6.2 example or pin it to a known-good internal id.
8. **Phase 6.3 stream-state probe** — Replace `nats stream view --subject=…` (TTY-required, can't be tee'd, and workqueue retention removes the message before any view command can see it anyway) with `nats stream info -j` + `nats consumer info PIPELINE forge-serve -j`. Both produce the same evidence and survive `tee`.
9. **Phase 7.1 close criterion narrowing** — Either narrow the close criterion to "forge consumed and acked" OR add an explicit forge precondition that `dispatch_payload` is wired to the real autobuild orchestrator + stage-complete publish path. Currently structurally unsatisfiable against `forge:732408f`. Forward-reference the forge follow-up.
10. **command-history filename** — `command_history.md` (underscore), not `command-history.md` (hyphen). Either pick one and rename, or fix the runbook references throughout. The on-disk file uses underscore; recommendation is to fix the runbook.
11. **§0.4 `JARVIS_OPENAI_BASE_URL` discussion** — Update to reflect local-only mandate (covered by [TASK-FRR-002](TASK-FRR-002-drop-misleading-jarvis-openai-base-url-field.md)) and provide the llama-swap-served model list (`gemma4-tutor`, `qwen36-workhorse`, `qwen-graphiti`, `nomic-embed`). Note that the `.env.example` default `JARVIS_SUPERVISOR_MODEL=openai:jarvis-reasoner` is stale — llama-swap doesn't serve a `jarvis-reasoner` model.
12. **NATS subscription failures at startup** — Document the three startup-time NATS errors (fleet register, KV bind, forge_subscriber attach) as known issues with forward-reference to [TASK-FRR-001](TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md). Until that lands, jarvis cannot subscribe to stage-complete events at all (DDR-030 between-prompt notification path is dead).
13. **Non-interactive REPL invocation** — Document the `printf | jarvis chat` non-interactive REPL invocation pattern that this run used to drive the chat from a non-TTY harness. Add a "non-interactive mode" example to §6.1 (or wherever the chat invocation lives).

## Acceptance Criteria

- [ ] Every row of the source RESULTS file's "Operator-side gaps in the runbook (gap-fold candidates)" table is folded into `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — either as an applied fix in the runbook OR as an explicit forward-reference to a tracked follow-up task (with task ID, e.g. "see TASK-FRR-001"). No row is silently dropped.
- [ ] A second operator (or the MacBook-over-Tailscale follow-up walkthrough) can execute the runbook from cold with **no manual gap-fold during execution**, only env-pointing differences (e.g. `JARVIS_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@<tailscale-host>:4222`).
- [ ] §0.4 explicitly requires NATS auth (`JARVIS_NATS_URL` with creds OR `JARVIS_NATS_CREDENTIALS_PATH`) and explicitly states that the supervisor always routes through llama-swap (cite ADR-ARCH-001; forward-reference TASK-FRR-002).
- [ ] §1.2 sources `nats-infrastructure/.env` (or equivalent) and exports `NATS_URL` with creds before `verify-nats.sh` runs.
- [ ] §2.1 either invokes `docker buildx build` from inside `forge/` directly OR forward-references the forge follow-up to fix `scripts/build-image.sh`.
- [ ] §2.2 uses `FORGE_NATS_URL` (not `NATS_URL`) and documents `FORGE_HEALTHZ_PORT=8088` and the open-webui port-conflict caveat.
- [ ] §4 hits the actual Graphiti HTTP endpoint, with a separate llama-swap embeddings probe if relevant (clearly distinguished as different services).
- [ ] §5.1 and §6.1 use `JARVIS_LOG_LEVEL` env var, not the non-existent `--log-level` flag.
- [ ] §6.2 uses the internal `FEAT-43DE` id (or whichever real-feature internal id is available at the time) and the `.guardkit/archive/FEAT-43DE/feature_state.yaml` YAML path. The `^FEAT-[A-Z0-9]{3,12}$` regex constraint is documented inline.
- [ ] §6.3 uses `nats stream info -j` + `nats consumer info PIPELINE forge-serve -j` instead of `nats stream view`.
- [ ] §7.1 either narrows the close criterion to "forge consumed and acked" OR forward-references the forge follow-up that will wire `dispatch_payload` to the real orchestrator. The expectation as written must not be structurally unsatisfiable against the current `forge:732408f` shape.
- [ ] Filename references throughout the runbook use `command_history.md` (underscore) consistently — match the on-disk file.
- [ ] §6.1 (or equivalent) includes a "non-interactive mode" example showing `printf "..." | jarvis chat` for runbook automation.
- [ ] A new "Known issues / forward-references" section near the top of the runbook lists every forward-referenced follow-up task by ID with a one-line summary, so the operator knows what's deferred and where to find the fix when it lands.
- [ ] No source code is modified by this task — pure documentation. Runbook scripts (e.g. helper bash blocks) are allowed to change so long as they are inline in the runbook markdown, not in `src/` or `scripts/`.

## Files Expected to Change

- `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — the full gap-fold rewrite. This is the only file expected to change.

## Out of Scope

- Source-code changes implied by some of the gaps (e.g. NATS subscription reconciliation, `JARVIS_OPENAI_BASE_URL` rename, trace-offload autocreate). Those are tracked as TASK-FRR-001 / TASK-FRR-002 / TASK-FRR-003. This task documents them as forward-references; it does not implement them.
- Forge-side gaps (`scripts/build-image.sh`, `FORGE_LOG_LEVEL` no-op, `dispatch_payload` stub). Those are tracked in the forge repo and are forward-referenced from the runbook but not fixed here.
- The MacBook-over-Tailscale walkthrough itself. That's the next runbook execution; this task makes that execution feasible without re-deriving the gap-folds.

## References

- **Parent runbook results:** [`docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
  - All 13 rows of the "Operator-side gaps in the runbook (gap-fold candidates)" table.
  - Per-phase outcomes table (rows 0.4, 1.2, 2.1, 2.2, 4.1/4.2, 5.1, 6.2, 6.3, 7.1, 8.4 — every row that produced a "with workaround" or "with caveat" notes a gap that this task must fold).
  - Cross-machine state observed section (notes the open-webui port conflict and the stale `jarvis-reasoner` model default).
  - Recommended follow-up #7.
- **Target file:** [`docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md).
- **Forward-referenced follow-ups (jarvis):**
  - [TASK-FRR-001](TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md) — fixes gap row 12 (NATS subscription failures) at the source.
  - [TASK-FRR-002](TASK-FRR-002-drop-misleading-jarvis-openai-base-url-field.md) — fixes gap row 11 (`JARVIS_OPENAI_BASE_URL`) at the source.
  - [TASK-FRR-003](TASK-FRR-003-ddr-019-trace-offload-autocreate-and-non-silent-drop.md) — fixes the silent-trace-drop issue (per-phase row 8.3).
- **Forward-referenced follow-ups (forge):** wire `dispatch_payload` to real orchestrator (forge follow-up #1); `logging.basicConfig` in `serve.py` (forge follow-up #2); `scripts/build-image.sh` cwd fix (forge follow-up #3). Tracked in the forge repo.
- **Reference internal feature id:** `FEAT-43DE` (= FEAT-JARVIS-INTERNAL-001), archived per `47ec4e5` at `.guardkit/archive/FEAT-43DE/feature_state.yaml`.
- **llama-swap model list:** `gemma4-tutor`, `qwen36-workhorse`, `qwen-graphiti`, `nomic-embed` (no `jarvis-reasoner`; `.env.example` default is stale).
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-01.
- **correlation_id:** `a58ec9a7-27c6-485a-beac-e18675639a10`.

## Notes

- This is documentation-only; no source code, no test files, no settings. The /task-create contract for this task is "rewrite one markdown file"; verify with `git diff` that only the runbook changes.
- The forward-reference pattern (rather than blocking on FRR-001 / FRR-002 to land first) is deliberate. The runbook should be a useful artefact today, with the known-issues section flagging what's still in flight. When FRR-001 / FRR-002 / FRR-003 land, a one-paragraph follow-up edit folds the forward-references into applied fixes.
- The "no manual gap-fold during execution" acceptance criterion is the load-bearing one. Validation strategy: dry-run the rewritten runbook on the GB10 (operator) and time-box the test — if the operator hits any manual gap-fold during execution, that's a failure; cycle back and add it.
- The MacBook-over-Tailscale walkthrough (recommended follow-up #8 in the RESULTS file) is the natural next execution after this task lands. It's deferred until the forge `dispatch_payload` wiring lands, but the runbook gap-fold can land today regardless.
