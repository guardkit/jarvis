---
task_id: TASK-FRR-RUNBOOK-002
review_mode: decision
review_depth: standard
reviewer: claude-opus-4-7 (interactive /task-review)
review_date: 2026-05-08
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md
target_runbook: docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
forge_head: 1b82236
jarvis_head: 60cee6b
---

# Review Report: TASK-FRR-RUNBOOK-002

## Executive Summary

The six proposed gap-folds in the task body are all **valid and ready to apply**, with **two scope additions** discovered during the review pass that the wave-2 fold should also absorb. The fold shape proposed for each of the two architecturally-ambiguous gaps (#4 markdown-vs-JSON, #6 graphiti probe) is the right call: option (a) in both cases — docs-only adaptation, with the alternative tightening logged as an out-of-scope follow-up. Phase 7 framing needs a deeper rewrite than "add a forward-reference" — the existing §7.1 + §7.3 failure-mode table is written against the abandoned FEAT-FORGE-010 / original-FRR-001 design and must be re-anchored against the FOLLOWUP-A symptom signature so the operator does not chase the wrong rejection branch.

**Decision recommendation: [I]mplement** — fold the six edits + the two scope additions in this same task. No re-scoping needed.

## Review Details

- **Mode**: decision (per `task_type: review`, `decision_required: true` in task frontmatter)
- **Depth**: standard
- **Complexity gating**: 3/10 → Context A clarification skipped (default behaviour for low-complexity reviews)
- **Graphiti context**: queried via CLI fallback; 0 nodes/facts returned for this scope (project graph empty for the runbook-fold topic) — review proceeded from codebase + evidence files alone.
- **Evidence sources verified during review**:
  - `forge/src/forge/config/models.py` (HEAD `1b82236`) — `ForgeConfig` schema for `forge.yaml`
  - `forge/src/forge/cli/_serve_config.py` (HEAD `1b82236`) — `ServeConfig` env-var schema (`FORGE_AUTOBUILD_RUNNER_URL`, `DEFAULT_DB_PATH`)
  - `forge/src/forge/cli/_serve_production.py` (HEAD `1b82236`) — `bind_production_serve` config-loader + fail-fast paths
  - `forge/langgraph.json` + `forge/src/forge/agent.py` (HEAD `1b82236`) — orchestrator graph import status
  - `src/jarvis/tools/dispatch.py:1230-1239` — `queue_build` ack JSON shape
  - `/tmp/jarvis-runbook-evidence/phase5-boot.log` — clean boot evidence
  - `/tmp/jarvis-runbook-evidence/phase6-chat.log:28-33` — actual rendered `queue_build` markdown shape
  - `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — current runbook §2.0 (absent), §2.2, §4.1, §4.2, §5.1, §6.2, §7.1, §7.2, §7.3, "Known issues" table

## Findings — answers to the review questions

### Q1. Gap #1 (`--config <path>`) — fold proposal correct as written

The minimal `forge.yaml` schema is **unchanged** at forge HEAD `1b82236`. `ForgeConfig` (in `forge/src/forge/config/models.py:309-330`) declares `permissions` as the only required block (`Field(...)` with no default), with `permissions.filesystem.allowlist: list[Path]` (required, absolute paths only — validator at `models.py:228-243` rejects relatives). All other top-level blocks (`fleet`, `pipeline`, `approval`, `queue`) ship `default_factory=...` defaults. The fail-fast message in `_serve_production.py:406-408` confirms operator-facing language: *"reads approved_originators and the filesystem allowlist from it. Pass --config <path> to forge serve or run from a directory containing ./forge.yaml."*

**Fold this gap as proposed.** The minimal `forge.yaml` example documented inline should be exactly:

```yaml
permissions:
  filesystem:
    allowlist:
      - /home/forge/build-workspace
      # Add any other absolute paths the operator wants the daemon to be allowed to write
```

(One required block, absolute paths only.)

### Q2. Gap #2 (langgraph-runner sidecar) — workaround still required

Confirmed: forge HEAD is still `1b82236` (no commits since the 2026-05-08 run). `forge/langgraph.json` still declares both `orchestrator: ./src/forge/agent.py:agent` and `autobuild_runner: ./src/forge/subagents/autobuild_runner.py:graph`. `forge/src/forge/agent.py:23` still does `from agents import create_orchestrator` — and there is no `agents` Python package on the forge import path. The `langgraph dev` boot will still fail to load the `orchestrator` graph, so the stripped-config workaround (autobuild_runner-only) is **still required**. The forge follow-up to fix this graph (or remove it from `langgraph.json`) should be filed as a forge-side follow-up; the runbook's §2.0 known-issues line should forward-reference it.

**Fold this gap as proposed.**

### Q3. Gap #3 (host DB mount + uid 1000 chown) — correct

`ServeConfig.db_path` defaults to `~/.forge/forge.db` (`_serve_config.py:125-127`, `expanduser()` lazy on instantiation). Inside the forge container, the runtime user is `forge` (uid 1000) per the Dockerfile and the RESULTS file's hot-fix evidence (`docker exec forge-prod python -c ...sqlite3.connect('/home/forge/.forge/forge.db')...` succeeded against the running container, proving the path resolves there at runtime). The proposed `-v ~/forge-prod-state/.forge:/home/forge/.forge` bind-mount is correct, and the `chown 1000:1000 ~/forge-prod-state/.forge` precondition matches the container's runtime uid (not just the host's invoking user, which on GB10 happens to also be 1000 — the runbook should be written for the container uid, since the forge user inside the container is not necessarily the host operator's user).

**Fold this gap as proposed.** Document explicitly that the chown is for the **container's** forge user (uid 1000), not the host operator's uid — this matters for Tailscale-walkthrough hosts where the operator might not be uid 1000.

### Q4. Gap #4 (`queue_build` markdown vs JSON) — DECISION: fold (a) docs-only

The actual runbook evidence (`/tmp/jarvis-runbook-evidence/phase6-chat.log:28-33`) shows the supervisor renders `queue_build`'s tool result as:

```
FEAT-43DE has been queued for build.

- **Correlation ID:** `af772739-9ebf-473b-b8b7-32c234ccdb73`
- **Publish target:** `pipeline.build-queued.FEAT-43DE`

Forge will pick it up from the JetStream topic. ...
```

The underlying tool returns raw JSON via `json.dumps(ack)` at [`src/jarvis/tools/dispatch.py:1238`](../../src/jarvis/tools/dispatch.py#L1238) — the `ack` dict has `feature_id`, `correlation_id`, `queued_at`, `publish_target`, `status: "queued"`. The markdown re-rendering happens in the supervisor's tool-result presentation layer (system prompt + reasoner narration), not in `dispatch.py`.

**Decision: fold (a)** — adapt §6.2 to the markdown bullet shape, key the operator's pass-criteria off the `Correlation ID:` and `Publish target:` lines, and document inline that the tool returns raw JSON but the chat surface re-renders. The `^FEAT-[A-Z0-9]{3,12}$` regex constraint and the `FEAT-43DE` worked example (preserved from wave-1) stay.

Rationale: option (b) — tightening the supervisor system prompt to pass through the raw JSON unchanged — is a **change to the chat surface contract**, with downstream consequences for every other tool-result rendering and for ADR-ARCH-001 / DDR-019 narration ergonomics. It belongs in its own task with its own architectural review, not in a runbook-fold. The task's own out-of-scope statement explicitly defers (b); this review confirms the deferral. Whether (b) ever happens is **not gating** for this runbook fold — the runbook adapts to what the operator's eyes actually see.

**Suggested optional follow-up (filed but not blocking):** `TASK-JARVIS-SUPERVISOR-PROMPT-PASSTHROUGH-RAW-TOOL-JSON` (or similar) — tighten the supervisor prompt template so non-narrative tool results pass through verbatim. If/when that lands, §6.2 should be re-tightened back to the JSON shape.

### Q5. Gap #5 (stale §5.1 expected-warnings) — CONFIRMED clean across the entire boot, not just FRR-001's three subscriptions

Re-read `/tmp/jarvis-runbook-evidence/phase5-boot.log` (28 lines, full boot through `session_ended`). The only non-info entries are:

- Line 2-4: `web_search_provider='tavily' but TAVILY_API_KEY ... is not set — web search will be disabled.` — operator-config-dependent, **not** a NATS subscription warning, will reproduce on any host without `JARVIS_TAVILY_API_KEY` set, has nothing to do with TASK-FRR-001.
- Line 11-12: `graphiti_skipped_no_endpoint` / `graphiti_available: false` — info-level, expected DDR-019 path when `JARVIS_GRAPHITI_ENDPOINT` is unset, also unrelated to TASK-FRR-001.

Crucially, **none of the three TASK-FRR-001 subscription warnings reproduce**:
- No `stream name already in use with a different configuration` from `fleet_register_published`
- No `agent-registry KV bind` failure
- No `BadRequestError code=10101 description='consumer must be deliver all on workqueue stream'` from `forge_subscriber attach`

And the boot terminates with `jarvis_startup_complete` at line 23 with `nats_available=true, capabilities_mode=live`. This is the success signature TASK-FRR-001 was designed to land. **§5.1's expected-warnings table is now strictly stale — every documented warning is gone.**

**Fold this gap as proposed.** Demote TASK-FRR-001 to "✅ resolved 2026-05-08" footnote in the Known Issues table and remove the boot-warning expectation entirely from §5.1 (rewrite it positively: *"a clean `jarvis_startup_complete` log entry with `nats_available=true, capabilities_mode=live` and zero NATS subscription warnings"*). The two pre-existing non-NATS warnings (TAVILY, graphiti-skip) are operator-config-dependent and should not be folded into §5.1 as "expected" — they are documented elsewhere (§0.4 for TAVILY, §4.2/§8.3 for graphiti).

### Q6. Gap #6 (graphiti probe collision with open-webui) — DECISION: fold (a) Content-Type / first-line guard

**Decision: fold (a)** — inline shell guard that checks `Content-Type` (or first line) and rejects HTML responses, with the docker-internal-only reality of `graphiti-mcp` on GB10 documented as a known operator hazard.

Rationale: option (b) — `docker exec` into the docker-internal network — has two failure modes the runbook would have to also document: (1) the container name (`graphiti-mcp`) needs to be stable across hosts, which is a stronger assumption than the runbook's portability target wants to make; (2) a Tailscale-walkthrough host might not have `graphiti-mcp` running locally at all (the operator may be pointing at a remote graphiti via `JARVIS_GRAPHITI_ENDPOINT`), and `docker exec` gives no signal in that case. Option (a) handles both scenarios with one probe shape and degrades gracefully (a docker-internal-only graphiti just looks "unreachable from host," which is the correct signal for the soft-fail offload path in §8.3).

Concrete fold for §4.2:

```bash
ssh promaxgb10-41b1 'PROBE_URL="${JARVIS_GRAPHITI_ENDPOINT:-http://localhost:8080}/healthz"; \
    RESP=$(curl -sf -i "$PROBE_URL" 2>/dev/null || echo ""); \
    if echo "$RESP" | head -1 | grep -q "^HTTP.*200" && \
       echo "$RESP" | grep -i "^Content-Type:" | grep -qiv "text/html"; then \
        echo "graphiti probe OK"; \
    else \
        echo "graphiti unreachable (or returned HTML — likely port hijack)"; \
    fi'
```

…with an inline operator-hazard note: *"On GB10, host-network `open-webui` holds port 8080 and returns an HTML splash page that looks like a 200 reply. The Content-Type guard above rejects HTML responses. The `graphiti-mcp` container on GB10 lives on a docker-internal network only and is not reachable from the host — leave `JARVIS_GRAPHITI_ENDPOINT` unset and rely on the §8.3 DDR-019 soft-fail offload path."*

This is a **shape-neutral** fold for the Tailscale walkthrough — on a host with a real host-mapped graphiti endpoint, the same probe just works.

### Q7. Phase 7 forward-reference framing — needs deeper rewrite than "add a forward-reference"

Reviewing the current §7.1 + §7.3 against the FOLLOWUP-A / -B reality reveals that the existing language is anchored on the **previous** integration generation (FEAT-FORGE-010 orchestrator-wiring) and the **abandoned** original-FRR-001 design (synthetic single-envelope dispatch). Specifically:

1. The opening prose of §7 (line 471) reads: *"If FEAT-FORGE-010 (orchestrator wiring) has not merged, expect Phase 7 to fail in the same shape as the 2026-05-01 run"*. This is now obsolete — FEAT-FORGE-010 has effectively been superseded by PEBR-WIREUP, which **has** merged at HEAD `1b82236`. The new gating dependency is FOLLOWUP-A (`lifecycle_bridge_registry` migration into `bind_production_serve`) and FOLLOWUP-B (bridge↔runner state-update contract).
2. §7.1's "Hard rejects" list (line 514) calls out a specific historical regression — *"only one stage-complete envelope arrives, with stage_label='dispatch' — that was the synthetic placeholder the abandoned FRR-001 design was going to ship."* This is no longer the contemporary failure mode and an operator hitting the runbook fresh in 2026-05-08+ would be confused.
3. §7.3's failure-mode table (line 553) has rows keyed on the F009 / FEAT-FORGE-010 / abandoned-FRR-001 hypotheses. The current real failure mode (FOLLOWUP-A symptom — `register_ack_handle raised (no such table: lifecycle_bridge_registry)` on every dispatch, falling back to legacy ack_callback that doesn't publish; OR the FOLLOWUP-B symptom — bridge attaches cleanly but never emits) is **not in the table at all**.

**This is more than "tweak §7.1 forward-reference language" — it's a re-anchoring of §7's whole "what is gating Phase 7?" framing.** Suggested fold:

- Replace the §7 opening prose to anchor on **PEBR-WIREUP merged + FOLLOWUP-A/-B pending** as the contemporary state.
- Replace §7.1's "Hard rejects" list with the FOLLOWUP-A symptom signature (`register_ack_handle raised (no such table: lifecycle_bridge_registry)`) as the **expected** FAIL until FOLLOWUP-A lands, plus the FOLLOWUP-B symptom (`lifecycle_bridge.attach … observer task scheduled` + clean SSE open + zero outbound envelopes) as the **second-stage** expected FAIL until FOLLOWUP-B lands.
- Add a new top row to §7.3's failure-mode table: **"`register_ack_handle raised (no such table: lifecycle_bridge_registry)` on every dispatch, no outbound envelopes, ack_floor stuck"** → cause: FOLLOWUP-A not landed → action: **expected FAIL today, do NOT treat as operator setup mistake**, rerun after FOLLOWUP-A lands.
- Add a second new row: **"bridge attaches cleanly per its own logs, SSE GET 200 OK, but zero outbound envelopes for >5min"** → cause: FOLLOWUP-B (bridge↔runner state-update contract) → action: same, expected FAIL today.
- Demote (or remove) the F009 / FEAT-FORGE-010 / synthetic-dispatch rows — they are historical and no longer reachable from the current image.

**Confirmation requested at the decision checkpoint:** the task body's AC-9 / AC-10 / AC-11 wording needs slight re-scoping to authorise the §7 / §7.1 / §7.3 rewrite (not just a "forward-reference") — see "Scope additions" below.

### Q8. Scope check — two omissions discovered, one minor caveat

Re-reading the RESULTS file's "Runbook gaps discovered (gap-fold candidates)" table and the per-phase outcomes table, I confirm **all six rows** of the gap-fold table are represented in the task's Headlines section. However, the per-phase outcomes table surfaces **two operator-facing drift items not on the gap-fold candidates list** that the wave-2 fold should also absorb:

**Scope addition #1 — §4.1 graphiti-mcp health caveat is stale.** Current §4.1 (line 328) says: *"As of 2026-05-01 the GB10 graphiti-mcp reports unhealthy."* The 2026-05-08 RESULTS row 4.1 records *"`graphiti-mcp` Up 24h **healthy** (improvement vs 2026-05-01 baseline)"*. The current §4.1 caveat is misleading for the 2026-05-08+ operator. Fold: update the caveat to note that the 2026-05-01 unhealthy state has been resolved as of 2026-05-08; the runbook still tolerates an unhealthy graphiti-mcp via the §8.3 soft-fail offload, so the language is just refreshed, not load-bearing.

**Scope addition #2 — "Known issues / forward-references" table top-section is stale.** The existing table has six rows:
- TASK-FRR-001 — needs demotion (already covered by Gap #5 fold).
- TASK-FRR-002, TASK-FRR-003 — both completed, link targets in `tasks/completed/`. Should be demoted to "✅ resolved" footnotes alongside FRR-001.
- `forge-followup-1` ("wire dispatch_payload to real pipeline_consumer orchestrator + stage-complete publish path, today's default is a receipt-only stub") — **PEBR-WIREUP has effectively done this work** (the dispatch chain is now composed in `bind_production_serve` per `1b82236`). This row is obsolete and must be replaced by FOLLOWUP-A / FOLLOWUP-B.
- `forge-followup-2` (`FORGE_LOG_LEVEL` no-op `basicConfig`) — RESULTS evidence file `phase7-forge-prod-logs.log` exists with content (per the evidence index, *"Full forge-prod docker logs from clean boot through 13+ minutes runtime"*), suggesting `docker logs forge-prod` is no longer empty. Whether this is because forge-followup-2 has landed, or the operator passed the log level differently, is **not directly verifiable from the evidence I can see** (I'd need to compare against the forge HEAD's `_serve_production.py` `logging.basicConfig` call site). **Recommend leaving forge-followup-2 in the table for wave-2** with a "verify against current image" note, deferred to wave-3.
- `forge-followup-3` (build-image.sh cwd) — workaround in §2.1 still applied per RESULTS row 2.1; runbook should keep it. **Leave as-is for wave-2.**

**Scope addition #2 fold:** rewrite the "Known issues / forward-references" table top-section to:
- Demote TASK-FRR-001, TASK-FRR-002, TASK-FRR-003 to "✅ resolved 2026-05-08 (or earlier)" footnotes.
- **Replace** the `forge-followup-1` row with **two new rows**: TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A (missing `lifecycle_bridge_registry` migration; Phase 7 will FAIL until landed) and TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B (bridge↔runner state-update contract; even with A applied, no `pipeline.build-started.*` envelope appears).
- **Keep** `forge-followup-2` and `forge-followup-3` rows as-is.
- Mark the **"✅ resolved 2026-05-08" milestone explicitly** in the table or in a top-of-table note so future readers know wave-2 is the current state.

**Other per-phase rows** I considered and decided are *not* gap-fold candidates:

- Row 0.4, 1.x, 2.1, 2.3, 3.x — all green, no caveats requiring runbook update.
- Row 4.3 — green, no caveats.
- Row 5.2 — "skipped, folded into 6.2" — operator workflow note, not a gap.
- Row 6.3 — green, no caveats.
- Row 8.1, 8.3 — green, no caveats.
- Row 8.2 — skipped because graphiti was unreachable, fell to 8.3 — that's the documented DDR-019 soft-fail behaviour, working as designed, not a gap.
- Row 8.4 — `command_history.md` deferred — RESULTS file fulfilled the evidence trail; this is a one-time evidence-trail decision specific to that walkthrough, **not a runbook gap**. The runbook itself still says §8.4 should be filed; that's correct guidance for future operators.

So the wave-2 fold should absorb: **6 original gaps + Phase 7 re-anchoring (Q7) + 2 scope additions (graphiti-mcp health caveat + Known-Issues table refresh)** = effectively 8-9 distinct edits, all in the same task.

## Decision Matrix

| Fold | Decision | Rationale | Risk |
|---|---|---|---|
| Gap #1 — `--config <path>` + minimal forge.yaml inline | **Apply as proposed** | Schema verified at HEAD `1b82236`; operator-facing fail-fast message confirmed | Low |
| Gap #2 — §2.0 langgraph-runner sidecar + stripped config | **Apply as proposed** | `from agents import` failure verified at HEAD `1b82236`; forward-reference forge follow-up | Low |
| Gap #3 — host DB mount + uid 1000 chown | **Apply as proposed** | `DEFAULT_DB_PATH` verified; uid 1000 = container's forge user (clarify in fold) | Low |
| Gap #4 — §6.2 markdown vs JSON | **Apply as proposed (option a — docs-only adapt)** | Actual rendered shape verified in `phase6-chat.log:28-33`; option (b) defer to optional follow-up | Low |
| Gap #5 — §5.1 stale expected-warnings | **Apply as proposed** | Boot log verified clean across 28 lines; FRR-001 fully resolved | Low |
| Gap #6 — §4.2 graphiti probe | **Apply as proposed (option a — Content-Type guard)** | Most portable across hosts; option (b) trades one failure mode for another | Low |
| Q7 — Phase 7 framing | **Re-anchor §7 / §7.1 / §7.3 against FOLLOWUP-A/-B (broader than "forward-reference")** | Existing language is anchored on superseded FEAT-FORGE-010 / abandoned-FRR-001 | Medium — touches more of §7 than the task originally implied; recommend explicit AC update |
| Scope addition #1 — §4.1 graphiti-mcp health caveat | **Add to wave-2 fold** | One-line refresh, matches RESULTS row 4.1 evidence | Low |
| Scope addition #2 — Known-issues table refresh | **Add to wave-2 fold** | `forge-followup-1` is obsolete; FRR-002/-003 resolved; FOLLOWUP-A/-B replace forge-followup-1 | Low |

## Recommendations (in priority order)

1. **[I]mplement** the six original folds + Q7 Phase 7 re-anchoring + the two scope additions in this same task.
2. **Update task ACs** before implementing — specifically AC-9 ("Known issues / forward-references section is updated to: …") needs to absorb scope addition #2 (which it partly already covers — it mentions FRR-001 demotion and FOLLOWUP-A/-B addition, but does not mention FRR-002/-003 demotion or `forge-followup-1` replacement explicitly). And AC-10 ("§7.1's close criterion explicitly forward-references FOLLOWUP-A + FOLLOWUP-B") understates the change required — should authorise §7.1 + §7.3 + §7-opening rewrite.
3. **File two optional follow-ups in `tasks/backlog/feat-jarvis-internal-001-followups/`** alongside this fold:
   - **Optional (a) — supervisor prompt passthrough**: tighten the supervisor system prompt so non-narrative tool results pass through verbatim, allowing §6.2 to be re-tightened to the JSON shape. Low priority; non-blocking.
   - **Optional (b) — verify forge-followup-2 status**: confirm whether `logging.basicConfig()` is now called in the forge image, and demote `forge-followup-2` from the runbook's known-issues table if so. Low priority; deferred to wave-3.
4. **Do NOT** modify any source code in this task. Pure documentation; the only file expected to change is `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`. The task notes already enforce this; this review confirms.
5. **Validation strategy** (per task body): dry-run the rewritten runbook on the GB10 — operator should reach end of Phase 6 with no manual gap-folds, and Phase 7 should fail with the FOLLOWUP-A symptom (or FOLLOWUP-B symptom if A has landed by then) the runbook anticipates. **AC-12 (no manual gap-folds through Phase 6) is the load-bearing acceptance criterion.**

## Out of Scope (confirmed deferrals)

- The actual Phase 7 wire-level fix (Gap A migration drift / Gap B bridge↔runner contract) — forge territory, tracked as TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A and -B. This task forward-references them.
- Tightening the supervisor prompt to pass through `queue_build`'s raw JSON unchanged — explicitly out-of-scope per task body; review confirms deferral.
- Fixing `forge/langgraph.json`'s `orchestrator` graph import failure — separate forge follow-up; documented inline as known caveat with workaround.
- MacBook-over-Tailscale walkthrough — natural next runbook execution; not a deliverable of this task.

## Context Used

- **Codebase analysis** (8 source files / 5 evidence files inspected — see "Evidence sources verified" in Review Details).
- **Knowledge graph context**: queried via Graphiti CLI, returned 0 nodes/facts for this scope (project graph empty for runbook-fold topic).
- **No external ADRs / past review findings** influenced the recommendations — every fold-shape decision was anchored on direct codebase + evidence inspection.

## Appendix — minor language nits (apply during implementation)

- The existing §2.2 still says `FORGE_NATS_URL` is required; the wave-2 fold should additionally note `FORGE_AUTOBUILD_RUNNER_URL` is required (per the new §2.0 sidecar reality). The task's AC-5 covers this.
- The runbook's "Cross-repo state preconditions (verified 2026-05-01)" table's `forge` row claims FEAT-FORGE-010 is the gating dependency for Phase 7. This is now obsolete (PEBR-WIREUP supersedes). Refresh the row to reference forge HEAD `1b82236` (or current) and note FOLLOWUP-A/-B as gating. **This is implicit in the Q7 / scope-addition #2 folds but worth calling out so the implementing edit picks it up.**
- The `command_history.md` filename convention from wave-1 (underscore, not hyphen) is preserved. Confirmed as required by AC-12.
