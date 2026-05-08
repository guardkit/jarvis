---
complexity: 3
completed: 2026-05-08T00:00:00Z
created: 2026-05-08 00:00:00+00:00
dependencies: []
discovered_on_machine: GB10 (promaxgb10-41b1)
discovered_on_date: 2026-05-08
discovered_via_correlation_id: af772739-9ebf-473b-b8b7-32c234ccdb73
estimated_minutes: 75
feature_id: FEAT-JARVIS-INTERNAL-001-FRR
forward_references:
- TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A
- TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B
id: TASK-FRR-RUNBOOK-002
implementation_mode: direct
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md
priority: medium
status: completed
completion_notes: |
  All six in-scope wave-2 topology gap-folds landed in
  docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
  and committed via 30e4ae4 "reviews, history tasks":
    1. §2.0 langgraph-runner sidecar section (line 224)
    2. §2.2 --config <path> requirement + minimal forge.yaml schema (line 320, 332)
    3. §2.2 FORGE_AUTOBUILD_RUNNER_URL mandate (line 322, 366)
    4. §2.2 host DB mount /home/forge/.forge with uid 1000 chown (line 324, 349, 368)
    5. §6.2 markdown-bullet shape (replaces JSON-shape match; line 575-590)
    6. §4.2 graphiti probe Content-Type guard against open-webui :8080 collision (line 458-468) + §5.1 stale-warnings retirement
  Wave-3 successor [TASK-FRR-RUNBOOK-003] (in_review) folds W3-A/B/C cosmetic polish on top.
  Note: ~32 lines of additional in-flight wave-2 polish (Pre-flight 1 langgraph-dev kill,
  Queue stats verification, §6.x symptom-check callout — operator's "W3-4 fold" per
  command_history) is layered on the runbook in the working tree but is NOT part of -002's
  in-scope six gap-folds; tracked informally in command_history, not by a dedicated task.
  Closing -002 on its in-scope work; the polish commits independently.
tags:
- jarvis
- feat-jarvis-internal-001-followups
- review
- assessment
- runbook
- gap-fold
- post-pebr-wireup
task_type: review
decision_required: true
title: Review the six post-PEBR-WIREUP runbook gaps and apply the agreed gap-folds (v2)
updated: 2026-05-08 00:00:00+00:00
wave: 2
---

# Review: post-PEBR-WIREUP runbook gaps and proposed gap-folds (v2)

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Wave:** 2 | **Type:** review (`task_type: review`, `decision_required: true`) | **Complexity:** 3/10
**Workflow:** `/task-review` → findings + decision checkpoint → if [I]mplement, fold the six edits into the runbook in this same task
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md) — entire "Runbook gaps discovered (gap-fold candidates)" table; recommended follow-up #3
**Forward references:** TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A (missing migration), TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B (bridge↔runner state-update contract)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-08, correlation_ids `af772739-9ebf-473b-b8b7-32c234ccdb73` and `7657ed5a-8d24-4c78-b615-aef7bf835b74`
**Predecessor:** [TASK-FRR-004](../../completed/feat-jarvis-internal-001-followups/TASK-FRR-004-runbook-gap-fold-rewrite.md) — wave-1 13-gap fold (2026-05-01 baseline). This task is the wave-2 review for the topology that landed between 2026-05-01 and 2026-05-08.

## Description

This is a **review-then-implement** task. The 2026-05-08 post-PEBR-WIREUP runbook execution on the GB10 surfaced six operator-facing topology gaps (catalogued in the RESULTS file's "Runbook gaps discovered (gap-fold candidates)" table) plus two wire-level failures (Gap A migration drift, Gap B bridge↔runner contract). The wire-level failures are forge territory and tracked as FOLLOWUP-A / -B in the forge repo. What lands here is the *runbook-facing review*: examine the six topology gaps, validate each proposed fold against the actual on-disk state, decide which folds are correct and which need re-scoping, then — at the `/task-review` decision checkpoint — choose [A]ccept / [I]mplement / [R]evise / [C]ancel. On [I]mplement, the agreed folds are applied to [`docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) so the next operator (Tailscale walkthrough or greenfield) can execute through Phase 6 without manual adjustment, with the wire-level failure mode forward-referenced.

The review framing is deliberate even though the six folds read like a prescribed plan: each fold has a non-obvious decision attached (e.g. for §6.2, do we adapt the runbook to the markdown bullet shape, or is the right fix to tighten the supervisor prompt? for §4.2, Content-Type guard or docker-internal probe?). The review pass commits to a specific shape per fold before any markdown is edited.

## Review Questions (decision checkpoint)

The `/task-review` analysis pass should produce explicit answers to each of the following before the [I]mplement step touches the runbook. The "proposed fold" column in the Headlines section below is the working hypothesis; the review may adjust any of them.

1. **Gap #1 (`--config <path>`):** Is the minimal `forge.yaml` schema documented in this task body still accurate against `forge:1b82236`? Specifically — does `permissions.filesystem.allowlist` remain the only required block, or has the schema grown since 2026-05-08? Verify by reading `forge/src/forge/cli/_serve_production.py` config-loader code.
2. **Gap #2 (langgraph-runner sidecar):** Is the stripped-`langgraph.json` workaround (orchestrator graph excluded due to `No module named 'agents'` import failure) still the right fold, or has the forge `orchestrator` graph been fixed since 2026-05-08? If fixed, drop the workaround; if not, confirm the forge follow-up is filed and the runbook should forward-reference it.
3. **Gap #3 (host DB mount):** Is `/home/forge/.forge/forge.db` still the persistence location, or has the forge daemon's DB path changed? Confirm the uid 1000 chown step is still correct for the operator's host (vs. the forge container's runtime uid).
4. **Gap #4 (`queue_build` markdown vs JSON):** This is the one with two architecturally distinct fixes. Decide: **(a)** adapt §6.2 to match the markdown bullet shape the supervisor renders (cheap, scope stays in this task), or **(b)** tighten the supervisor prompt template so the raw JSON from [`dispatch.py:1239`](../../../src/jarvis/tools/dispatch.py#L1239) passes through unchanged (changes the contract the runbook depends on; spawn separate task). Default proposal: (a) for this task, file (b) as an optional follow-up. The review must commit to one.
5. **Gap #5 (stale §5.1 expected-warnings):** Confirm by re-reading the 2026-05-08 boot log evidence (`/tmp/jarvis-runbook-evidence/phase5-boot.log` per the RESULTS index) that **none** of the documented warnings reproduce — TASK-FRR-001's reconciliation must have landed cleanly, not just for the three subscriptions named but for any other `nats_*` startup warning. If any warning still reproduces, retain that row in the §5.1 table; only retire the rows that are demonstrably resolved.
6. **Gap #6 (graphiti probe collision with open-webui :8080):** Decide: **(a)** Content-Type / first-line guard inline in §4.2 (cheap, host-portable, false-negatives possible if open-webui ever serves JSON), or **(b)** target `graphiti-mcp` over the docker-internal network via `docker exec` (requires the container name to be stable across hosts, less host-portable). Default proposal: (a) with the docker-internal-only reality of `graphiti-mcp` on GB10 documented as an operator hazard. Review must commit.
7. **Phase 7 forward-reference framing:** Is the runbook's §7.1 close criterion currently written to expect the FOLLOWUP-A symptom, or does it still claim Phase 7 should pass against the current forge HEAD? Confirm the forward-reference language is unambiguous so the operator does not interpret the FAIL as their own setup mistake.
8. **Scope check — anything omitted?** Re-read the RESULTS file's "Runbook gaps discovered (gap-fold candidates)" table and confirm all six rows are represented in the Headlines below. Also re-read the per-phase outcomes table — any "with caveat" / FAIL row that produced an operator-side adjustment but is **not** listed as a gap-fold candidate is a wave-3 candidate; flag if found.

The review output should be a one-paragraph-per-question findings note, then the decision: [A]ccept (proposals stand, ready to implement) / [I]mplement (proceed to fold the six edits) / [R]evise (deeper analysis needed on a specific question) / [C]ancel (re-scope or drop).

## Headlines (the six gaps and proposed folds)

Pulled verbatim from the source RESULTS table; the task must fold every row, not just the summaries below.

1. **§2.2 `forge serve` now requires `--config <path>`.** The container ships without a default `forge.yaml`; the runbook's bare `forge:latest serve` invocation crashes with `Error: forge serve requires a forge.yaml — pass --config <path>...`. §2.2 must mount `~/forge-state/forge.yaml` (or equivalent) and invoke `forge:latest --config /var/forge/forge.yaml serve`. The minimal `forge.yaml` schema (one required block: `permissions.filesystem.allowlist` with absolute paths) must be documented inline.
2. **New §2.0 — start the langgraph-runner sidecar.** `bind_production_serve` now requires `FORGE_AUTOBUILD_RUNNER_URL` (TASK-FORGE-FRR-F010I/J). With it unset, boot raises `ValueError: bind_production_serve: 'autobuild_runner_url' is required but missing/empty`. The deployment topology is now: forge-serve container + langgraph-runner sidecar (typically `langgraph dev` against the forge repo). Add a new §2.0 "Start the langgraph-runner sidecar" with `langgraph dev --host 127.0.0.1 --port 8124 --no-browser` from the forge repo root, and update §2.2 to set `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124`. **Caveat to document:** the canonical `forge/langgraph.json` declares an `orchestrator` graph that fails to import (`No module named 'agents'`), so the sidecar must be started with a stripped config containing only `autobuild_runner` — flag this as a forge follow-up in the known-issues section.
3. **§2.2 host DB mount.** The forge daemon now persists its DB at `/home/forge/.forge/forge.db` inside the container's writable layer, **not** in the existing `~/forge-state` volume mounted at `/var/forge`. Without an additional `-v ~/forge-prod-state/.forge:/home/forge/.forge` mount, every container restart is a fresh DB and any operator-applied migrations are lost (this is exactly how Gap A was hot-fixable on 2026-05-08). §2.2's docker run command must add `-v ~/forge-prod-state/.forge:/home/forge/.forge`, with a precondition step to pre-create the host directory and `chown 1000:1000 ~/forge-prod-state/.forge`.
4. **§6.2 `queue_build` output shape.** The runbook expects `queue_build` to return a JSON payload starting with `status: queued / feature_id: ... / correlation_id: ...`. The supervisor's actual rendered output is a markdown bullet list (`- **Correlation ID:** ...`). The tool itself returns raw JSON via `json.dumps(ack)` ([`src/jarvis/tools/dispatch.py:1239`](../../../src/jarvis/tools/dispatch.py#L1239)) — the markdown rendering happens in the supervisor's tool-result presentation, not in `dispatch.py`. Fold §6.2 to accept the markdown bullet shape, key off `Correlation ID:` and `Publish target:` lines, and document explicitly that the underlying tool returns raw JSON but the chat surface re-renders it. **Out-of-scope but flag:** if a future task tightens the supervisor prompt to pass through the raw JSON unchanged, §6.2 should be re-tightened then; do not change `dispatch.py` from this task.
5. **§5.1 expected-warnings table is stale.** The "expected boot warnings until TASK-FRR-001 lands" no longer reproduce — the JARVIS stream / agent-registry / forge_subscriber subscriptions now bind cleanly (TASK-FRR-001 has landed; 2026-05-08 boot log shows `jarvis_startup_complete` with `nats_available=true, capabilities_mode=live` and zero warnings). Move TASK-FRR-001 from the §"Known issues" / §5.1 expected-warnings tables to a "✅ resolved 2026-05-08" footnote, and remove the boot-warning expectation entirely from §5.1 so the next operator does not waste time looking for warnings that won't appear.
6. **§4.2 graphiti probe collides with open-webui on :8080.** Phase 4 says "Probe the actual Graphiti HTTP endpoint" with `curl http://localhost:8080/healthz`. On GB10, port 8080 is held by `open-webui` (host-network). The probe returns open-webui's HTML splash, which **looks like** a 200 reply but is not Graphiti — false-positive that hid a real issue on the 2026-05-08 run. §4.2 must either (a) detect the response body's `Content-Type` / first line and reject HTML responses (cheap inline shell check), or (b) update the probe to use the actual `graphiti-mcp` exposed port (which on GB10 is **not** mapped to host — `graphiti-mcp` lives on the docker-internal network only, so the probe needs to run inside the docker network, e.g. via `docker exec`). Recommend (a) as the immediate fold and document the docker-internal-only reality of `graphiti-mcp` on GB10 as a known operator hazard.

## Acceptance Criteria

- [ ] Every row of the source RESULTS file's "Runbook gaps discovered (gap-fold candidates)" table is folded into `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — either as an applied fix in the runbook OR as an explicit forward-reference to a tracked follow-up task. No row is silently dropped.
- [ ] §2.2 documents the `--config <path>` requirement, ships a minimal `forge.yaml` schema example inline (`permissions.filesystem.allowlist` block at minimum), and the docker run command in §2.2 mounts the operator's `forge.yaml` and passes `--config /var/forge/forge.yaml`.
- [ ] A new **§2.0 "Start the langgraph-runner sidecar"** is added before §2.1, with the `langgraph dev --host 127.0.0.1 --port 8124 --no-browser` invocation, the stripped `langgraph.json` workaround for the failing `orchestrator` graph (with forward-reference to the forge follow-up), and explicit verification that the sidecar is up before §2.2's `forge serve` boots.
- [ ] §2.2's docker run command adds `-v ~/forge-prod-state/.forge:/home/forge/.forge`, the precondition step pre-creates and chowns the host directory (uid 1000), and §2.2 explicitly states that without this mount every container restart is a fresh DB.
- [ ] §2.2 sets `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124` (matching the §2.0 sidecar port) and documents that this var is now mandatory.
- [ ] §6.2 accepts the markdown bullet output shape (matching on `Correlation ID:` and `Publish target:` lines) and documents inline that the underlying `dispatch.queue_build` returns raw JSON via `json.dumps(ack)` but the supervisor chat surface re-renders. The `^FEAT-[A-Z0-9]{3,12}$` constraint and the `FEAT-43DE` worked example from wave-1 are preserved.
- [ ] §5.1's expected-warnings table no longer lists TASK-FRR-001 boot-time NATS errors. TASK-FRR-001 is moved to a "✅ resolved 2026-05-08" footnote in the Known Issues / Forward References section. The expectation that the operator should see clean `jarvis_startup_complete` (no warnings) is documented positively.
- [ ] §4.2's graphiti probe either (a) checks `Content-Type` / first-line and rejects HTML responses, or (b) targets `graphiti-mcp` over the docker-internal network via `docker exec`. The open-webui port-conflict caveat is documented inline as a known operator hazard on GB10.
- [ ] The "Known issues / forward-references" section near the top of the runbook is updated to:
  - List FOLLOWUP-A (missing `lifecycle_bridge_registry` migration) — Phase 7 will FAIL until this lands, with the specific symptom (`register_ack_handle raised (no such table: lifecycle_bridge_registry)`) so the operator recognises it on sight.
  - List FOLLOWUP-B (bridge↔autobuild_runner state-update contract) — even with FOLLOWUP-A applied, no `pipeline.build-started.*` envelope appears on the wire until B lands.
  - Resolve TASK-FRR-001 to a "✅ resolved 2026-05-08" footnote.
  - Resolve TASK-FRR-002 and TASK-FRR-003 to "✅ resolved" footnotes alongside FRR-001 (both already in `tasks/completed/` — wave-1 forward-references are now stale).
  - **Replace** the obsolete `forge-followup-1` row (today's "wire `dispatch_payload` to the real `pipeline_consumer` orchestrator + stage-complete publish path; today's default is a receipt-only stub") — PEBR-WIREUP at forge HEAD `1b82236` has effectively done this work; the row is no longer accurate. The new gating constraints are FOLLOWUP-A and FOLLOWUP-B (added per the bullets above).
  - Keep `forge-followup-2` (`FORGE_LOG_LEVEL` no-op `basicConfig`) and `forge-followup-3` (`build-image.sh` cwd) as-is for wave-2; they are not directly invalidated by 2026-05-08 evidence and remain defensible until verified against the current image.
  - Mark the "✅ resolved 2026-05-08" milestone explicitly so future readers know the wave-2 fold is the current state.
- [ ] §7's framing is **re-anchored** against the FOLLOWUP-A / FOLLOWUP-B reality, not just augmented with a forward-reference. Specifically:
  - The §7 opening prose is rewritten to anchor on PEBR-WIREUP merged + FOLLOWUP-A/-B pending (replacing the historical FEAT-FORGE-010 framing).
  - §7.1's "Hard rejects" list is rewritten so the FOLLOWUP-A symptom signature (`register_ack_handle raised (no such table: lifecycle_bridge_registry)`) and the FOLLOWUP-B symptom (bridge attaches cleanly per its own logs, SSE GET 200, but zero outbound envelopes for >5 minutes) are the **expected FAIL signatures today**, not regressions. The references to the abandoned FRR-001 design (synthetic single-envelope `stage_label="dispatch"`) and to FEAT-FORGE-010 are removed or demoted to a historical footnote.
  - §7.3's failure-mode table gains two new top rows: (1) the FOLLOWUP-A signature → cause: FOLLOWUP-A not landed → action: **expected FAIL today, do NOT treat as operator setup mistake**, rerun after FOLLOWUP-A lands; (2) the FOLLOWUP-B signature → cause: FOLLOWUP-B not landed → action: same. The historical F009 / FEAT-FORGE-010 / synthetic-dispatch rows are removed or demoted.
- [ ] §4.1 graphiti-mcp health caveat is refreshed: the existing 2026-05-01 "reports unhealthy" line is updated to note that the 2026-05-08 baseline shows the container Up healthy, while keeping the soft-fail offload guidance intact (the runbook still tolerates either state).
- [ ] The "Cross-repo state preconditions (verified 2026-05-01)" table's `forge` row is refreshed to reference forge HEAD `1b82236` (PEBR-WIREUP) as the relevant baseline, with FOLLOWUP-A/-B noted as the contemporary gating-for-Phase-7 dependencies in place of the now-superseded FEAT-FORGE-010 wording.
- [ ] A second operator on a clean GB10 (or near-clone over Tailscale) can execute the runbook from cold through Phase 6 with **no manual gap-fold**, only env-pointing differences. Phase 7 is expected to FAIL with the FOLLOWUP-A symptom until that task lands; the runbook makes this expectation explicit.
- [ ] No source code is modified by this task — pure documentation. The only file expected to change is the runbook itself. The `command_history.md` filename convention from wave-1 is preserved (underscore).

## Files Expected to Change

- `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — the wave-2 gap-fold rewrite. This is the only file expected to change.

## Out of Scope

- **The actual Phase 7 wire-level failure.** Gap A (`lifecycle_bridge_registry` migration not applied at boot) and Gap B (bridge attaches but never publishes `build-started`) are tracked as TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A and -FOLLOWUP-B in the forge repo. This task forward-references them; it does not fix them. AC-11 of TASK-FORGE-FRR-PEBR-WIREUP cannot be met by this task — only by FOLLOWUP-A landing, then a rerun confirming `pipeline.build-started.FEAT-*` on the wire. The forge task should not be moved to `completed/` until that rerun succeeds.
- **Tightening the supervisor prompt to pass through `queue_build`'s raw JSON unchanged.** The current rendering is markdown-bullet because of how the supervisor presents tool results, not because `dispatch.py` returns markdown. If a future task tightens the prompt template, §6.2 can be re-tightened then. For wave-2, the runbook adapts to the rendered shape; `dispatch.py` is not touched.
- **The forge `langgraph.json` `orchestrator` graph import failure (`No module named 'agents'`).** Tracked as a forge follow-up; documented in §2.0 as a known caveat with the stripped-config workaround. Not fixed here.
- **MacBook-over-Tailscale walkthrough.** The natural next runbook execution after this task lands and FOLLOWUP-A lands, but is its own runbook event, not a deliverable of this task.

## References

- **Parent runbook results:** [`docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md`](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md)
  - All six rows of the "Runbook gaps discovered (gap-fold candidates)" table.
  - Per-phase outcomes table (rows 2.2, 4.2, 5.1, 6.2, 7.1, 7.2, 7.3 — every row that produced a "with caveat" / FAIL notes a gap that this task must fold or forward-reference).
  - "The two gaps in detail" section (Gap A + Gap B; both forward-referenced, neither fixed here).
  - Recommended follow-up #3.
- **Target file:** [`docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md).
- **Predecessor task:** [`TASK-FRR-004`](../../completed/feat-jarvis-internal-001-followups/TASK-FRR-004-runbook-gap-fold-rewrite.md) — wave-1 13-gap fold (2026-05-01 baseline). This task continues the same pattern at wave-2 for the post-PEBR-WIREUP topology.
- **Forward-referenced follow-ups (forge — not in this repo):**
  - `TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A` — wire `lifecycle_bridge_registry.apply()` into `bind_production_serve`. ~5-line patch in `forge/src/forge/cli/_serve_production.py` Step 3.5b. AC-11 catch.
  - `TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B` — investigate why the bridge attaches but never publishes `build-started`. Hypothesis from RESULTS: autobuild_runner subagent doesn't drive the `_update_state` transitions the bridge translates to NATS publishes. Recommend structured logging in `bridge.translator` + rerun of `tests/integration/test_lifecycle_bridge_sidecar_e2e.py`.
  - `forge/langgraph.json` `orchestrator` graph fails to import (`No module named 'agents'`) — separate forge follow-up.
- **Resolved (no longer forward-reference):**
  - [`TASK-FRR-001`](../../completed/feat-jarvis-internal-001-followups/TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md) — landed; 2026-05-08 boot is clean. Demote to "✅ resolved" footnote in the runbook.
- **Reference internal feature id:** `FEAT-43DE` (= FEAT-JARVIS-INTERNAL-001) — same as wave-1.
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-08.
- **correlation_ids:** `af772739-9ebf-473b-b8b7-32c234ccdb73`, `7657ed5a-8d24-4c78-b615-aef7bf835b74`.
- **Forge HEAD at discovery:** `1b82236` (PEBR-WIREUP).
- **Jarvis HEAD at discovery:** `60cee6b`.

## Notes

- This is documentation-only; no source code, no test files, no settings. The only file expected to change is the runbook. Verify with `git diff` that only `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` changed.
- The `queue_build` markdown-vs-JSON gap (#4) is **deliberately scoped to docs only**. The tool returns raw JSON; the markdown re-rendering is happening in the supervisor's tool-result presentation. Tightening the supervisor prompt to pass through the raw JSON is a separate, optional follow-up — not part of this task. The runbook adapts to the rendered shape so the operator's eyeballs match what's on screen.
- The forward-reference pattern (rather than blocking on FOLLOWUP-A / -B to land first) is deliberate, mirroring wave-1. The runbook should be a useful artefact today through Phase 6, with the known-issues section flagging that Phase 7 will FAIL with a specific signature until FOLLOWUP-A lands. When FOLLOWUP-A and -B land, a one-paragraph follow-up edit folds the forward-references into "✅ resolved" footnotes (same demotion pattern this task applies to TASK-FRR-001).
- Validation strategy: dry-run the rewritten runbook on the GB10 — operator should reach the end of Phase 6 with no manual gap-folds, and Phase 7 should fail with the exact symptom (`register_ack_handle raised (no such table: lifecycle_bridge_registry)`) the runbook now anticipates. If the operator hits any unanticipated gap, that's a wave-3 candidate; cycle back.
- AC-11 of TASK-FORGE-FRR-PEBR-WIREUP is **NOT** met by this task. The forge task should remain in `in_progress/` (or wherever it currently lives) until FOLLOWUP-A lands and a rerun captures `pipeline.build-started.FEAT-*` on the wire. This task only addresses the operator-facing runbook; the substantive wire-level fix is forge territory.
