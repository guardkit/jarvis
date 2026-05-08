# RESULTS: Jarvis → Architect Align — DDD South West Demo (verification dry-run)

**Date:** 2026-05-08
**Operator:** Claude Code (non-interactive, stdin-piped REPL driver)
**Machine:** GB10 (`promaxgb10-41b1`) — single-host all-local
**Jarvis HEAD:** `ca2ba6b` (post `dcaa8eb` lifecycle subscriber widening + `6071fe0` TASK-FRR-F010Db disjoint filter)
**specialist-agent HEAD:** `7345e33` (post `11f0b54` TASK-LLM-0D07 — local provider wired to LOCAL_MODEL)
**Image:** `specialist-agent:latest` (built 2026-05-08 07:06 BST)
**Runbook driven:** `docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md` (Option A — ADR-ARCH-001 vs Opus 4.7 escalation proposal)
**ADR pair:** `docs/architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md` (jarvis local-first)

**Outcome:** ⏸ **BLOCKED before Phase 4 lands a wire envelope.** Phases 0–3 are clean and green; the dispatch path itself is structurally broken in a way the runbook's §2.5 "Catalogue-vs-stub note" claimed was a non-issue. **Gap DISPATCH-STUB-RESOLVER (NEW): the live KV-backed CapabilitiesRegistry is wired into the supervisor's prompt-block and `capabilities_*` tools, but is NOT wired into the `dispatch_by_capability` resolver.** The resolver iterates a static snapshot of `stub_capabilities.yaml` taken at boot; that stub lists architect-agent's tools as `run_architecture_session` + `draft_adr` only, so `dispatch_by_capability(tool_name="architect_align", ...)` returns `ERROR: unresolved` even though §2.5 verifies the live `agent-registry` KV row publishes the four real architect tools (`architect_align` / `architect_greenfield` / `architect_explore` / `architect_feasibility`). Wire taps on `agents.command.architect-agent.>` and `agents.result.architect-agent.>` captured **zero envelopes** across three dispatch attempts; the supervisor's narrative "the architect-agent has no heartbeat" was its own LLM-rendered misinterpretation of the unresolved error. Three FRR-003 routing-history offload traces saved with `outcome_type=unresolved` corroborate the resolver-level failure.

**Demo blocking?** YES. The DDD South West demo (2026-05-16) cannot dispatch via `dispatch_by_capability` to architect-agent until Gap DISPATCH-STUB-RESOLVER is closed — config-level workaround OR code-level fix. The runbook author needs to be told the §2.5 claim ("This is not a problem because ... the live KV watch ... replaces the stub entries") is structurally wrong: the live registry feeds the prompt block but **not** the resolver.

---

## Summary in one paragraph

Phases 0 (pre-flight), 1 (NATS provisioning), and 2 (specialist-agent dual-role + manifest with architect_align) all green. Phase 3 boots jarvis chat clean (no NATS subscription errors, F010Db disjoint filter holds, capabilities_mode=live, four-tool stub catalogue loaded). Phase 4 was attempted three times — once with the runbook's natural-language prompt (Option A from §4.1), once with an explicit `dispatch_by_capability(tool_name="architect_align", ...)` instruction, and once with an additional `intent_pattern="Architect"` arg. The supervisor (`openai:qwen36-workhorse`) called `dispatch_by_capability` correctly on attempts 2 and 3, but every call returned `ERROR: unresolved — no capability matches tool_name=architect_align intent_pattern=<None>`. Three FRR-003 routing-history offload traces (`becfa233-...`, `c428dc05-...`, `d8525237-...`) confirm the resolver-level failure (`outcome_type: "unresolved"`, `attempts: []`, `visited: []` — no candidate ever even considered). Wire taps captured zero envelopes on either subject because the dispatch never made it to the wire. The supervisor's third-attempt prose claim "the architect-agent has no heartbeat" is incorrect — the real cause is that the dispatch resolver looks up `tool_name` against `_dispatch._capability_registry`, a static snapshot of the stub yaml taken at boot, which doesn't list `architect_align`. The Live registry exists and works (it correctly hydrates the supervisor's "Available Capabilities" prompt block from KV) but is not the source of truth the resolver consults. **Gap DISPATCH-STUB-RESOLVER is one wiring step deep** (mirroring the FEAT-PEBR PEBR-WIREUP shape from `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md`): the live registry's `snapshot()` call needs to be threaded into `_dispatch._capability_registry` at boot AND on every KV-watch event, not the stub list.

## Per-phase outcomes

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main + clean tree | ✅ | HEAD=`ca2ba6b`; only modified file is `docs/history/command_history.md` (in-flight) |
| 0.2 | specialist-agent main + image freshness | ✅ | Image rebuilt 2026-05-08 07:06; `docker-compose.dual-role.yml` has the user's local `extra_hosts: host.docker.internal:host-gateway` patch |
| 0.3 | llama-swap on :9000, `architect-agent` alias loaded | ✅ | `architect-agent`, `gemma4-tutor`, `nomic-embed`, `qwen36-workhorse`, `qwen-graphiti` all present |
| 0.4 | NATS up, APPMILLA creds loaded | ✅ | `ships-computer-nats` Up 22h healthy; `RICH_NATS_PASSWORD` sourced from `nats-infrastructure/.env` |
| 0.5 | ADR pair pre-staged (Option A) | ✅ | ADR-ARCH-001 file confirmed at `docs/architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md` |
| 1 | Canonical NATS provisioning | ✅ | `verify-nats.sh` reports 7 streams (incl. AGENTS) + 4 KV buckets (incl. `agent-registry`) all green |
| 2.1 | `.env` set to local | ✅ with caveat | `AGENT_MODELS__REASONING_MODEL=local`, `LLM_BASE_URL=http://promaxgb10-41b1:9000`, `OPENAI_BASE_URL` not set, `OPENAI_API_KEY` is a real `sk-proj-...` key (not `not-needed`). `ARCHITECT_LOCAL_MODEL` / `PO_LOCAL_MODEL` come from compose patch defaults |
| 2.2 | Dual-role stack Up | ✅ | Both `specialist-agent-architect-agent-1` and `specialist-agent-product-owner-agent-1` Up 46m at runbook start (re-used existing session; no down+up bounce needed) |
| 2.3 | Container env audit | ✅ | architect: `REASONING_MODEL=local`, `LOCAL_MODEL=architect-agent`, `LLM_BASE_URL=http://host.docker.internal:9000`, `NATS_URL=nats://host.docker.internal:4222`, `NATS_USER=rich`, `NATS_PASSWORD` set |
| 2.4 | `agent-registry` KV registration | ✅ | 3 rows: `jarvis` (supervisor self-registration), `architect-agent`, `product-owner-agent` |
| 2.5 | `architect_align` published in architect's tool surface | ✅ | `tool count: 4` matches runbook expectation: `architect_greenfield`, **`architect_align`**, `architect_explore`, `architect_feasibility` |
| 3.1 | jarvis chat boots clean | ✅ | `nats_connect_success`, `jarvis_capability_registry_loaded path=src/jarvis/config/stub_capabilities.yaml count=4`, `forge_notifications_subscribed subjects=[pipeline.build-started.>, pipeline.stage-complete.>, pipeline.build-complete.>, pipeline.build-failed.>]`, `jarvis_startup_complete nats_available=true graphiti_available=false capabilities_mode=live`. Boot is clean — F010Db disjoint filter holding |
| 3.2 | Live catalogue surfaces architect_align | ⏭ skipped (per runbook "Don't dwell in the talk") | n/a — the supervisor's prompt block IS hydrated from the live registry, which DOES contain `architect_align` (verified via the supervisor's third-attempt prose: "architect_align was in the catalogue") |
| 4 (attempt 1) | Natural-language prompt (Option A) | ❌ no dispatch fired | Supervisor wrote inline analysis without invoking any tool; output ends "The architect agent appears to be unavailable right now. Let me give you my analysis directly..." |
| 4 (attempt 2) | Explicit `dispatch_by_capability(tool_name="architect_align", payload_json={...})` instruction | ❌ `ERROR: unresolved` | Supervisor invoked the tool twice (per chat HTTP traffic + 2 trace files at 07:58:23 and 07:58:35); resolver returned `ERROR: unresolved` on both. Supervisor concluded with "Note: The direct dispatch_by_capability call also failed to resolve (architect_align was in the catalogue but the dispatch returned `unresolved`), which aligns with the architect-agent having no heartbeat" — the heartbeat speculation is incorrect; see Gap below |
| 4 (attempt 3) | Same plus explicit `intent_pattern="Architect"` arg | ❌ `ERROR: unresolved` (intent_pattern dropped by supervisor) | Trace `d8525237-...` shows `outcome_detail.intent_pattern: null` — the supervisor LLM did not pass the intent_pattern arg through despite explicit instruction. With the stub having `architect-agent.role="Architect"`, an honoured intent_pattern would have resolved via the fallback at `dispatch.py:249-254`. Without it, the resolver returns unresolved against the stub's `tool_name` set |
| 5.1 | `agents.command.architect-agent.>` tail | ❌ 0 lines captured | `/tmp/dddsw-demo-architect-command.log` empty across all three attempts — dispatch never reached the wire |
| 5.2 | `agents.result.architect-agent.>` tail | ❌ 0 lines captured | `/tmp/dddsw-demo-architect-result.log` empty (consequence of 5.1) |
| 5.3 | AlignmentJudgment captured for slide | ⏭ N/A | No real architect call landed; nothing to capture |
| 7.1 | Chat transcript saved | ✅ | `docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/chat-attempt3-intent-pattern-arg-dropped.log` (the most-instructive of the three; first two not retained). The supervisor's third-attempt prose explicitly names the unresolved error — it's the canonical evidence |
| 7.2 | Routing-history offload | ✅ | Three FRR-003 traces under `~/.jarvis/traces/` and copied to evidence dir: `becfa233-...`, `c428dc05-...`, `d8525237-...` — all `outcome_type=unresolved`, `outcome_detail.tool_name=architect_align`, `attempts=[]`, `visited=[]` |
| 7.3 | `command_history.md` entry | ⏳ | To append after this RESULTS file lands |
| 7.4 | RESULTS file | ✅ | THIS FILE |
| 8 | Demo close | ❌ | Demo path NOT green. Phases 0–3 clean; Phase 4 blocked by Gap DISPATCH-STUB-RESOLVER. Dual-role stack left running for next attempt. |

## Gap discovered (NEW — 2026-05-08)

**Gap DISPATCH-STUB-RESOLVER — the live CapabilitiesRegistry is not wired into the dispatch resolver's source of truth.**

### Symptom (operator-visible)

Three independent attempts at the runbook §4 demo turn each ended with `ERROR: unresolved — no capability matches tool_name=architect_align intent_pattern=<None>`, despite `agent-registry` KV containing a fully-published architect-agent manifest with `architect_align` in its tool surface (confirmed by runbook §2.5). Wire taps on `agents.command.architect-agent.>` for the duration of all three attempts captured zero envelopes — the dispatch never made it to JetStream.

### Symptom (trace-level)

Three FRR-003 routing-history offload traces produced (one per dispatch invocation):

```jsonc
// ~/.jarvis/traces/d8525237-9d59-432d-a785-9204fd2b058a.json (attempt 3)
{
  "outcome_type": "unresolved",
  "outcome_detail": {
    "intent_pattern": null,                  // ← supervisor dropped my explicit arg
    "tool_name": "architect_align",          // ← correct tool name passed through
    "visited": []                            // ← resolver had no candidates to try
  },
  "attempts": [],                            // ← never reached the wire
  "capability_snapshot_hash": "64818d5b…0301",
  "supervisor_reasoning_summary": "dispatch_by_capability"
}
```

### Root cause (code-level)

The wiring at boot establishes **two separate capability registries** that the lifecycle plumbs to **different consumers**:

1. **Stub list** — loaded at `lifecycle.py:547` from `src/jarvis/config/stub_capabilities.yaml` into `capability_registry: list[CapabilityDescriptor]`. Logged as `jarvis_capability_registry_loaded path=...stub_capabilities.yaml count=4`.
2. **Live registry** — `LiveCapabilitiesRegistry.create(nats_client)` at `lifecycle.py:628`, which (per its own docstring) warms a 30s-TTL cache via an immediate `refresh()` and opens an async `watchall()` on the `agent-registry` KV bucket. Result is bound to a **separate** local: `capabilities_registry: CapabilitiesRegistry`.

Both are then passed into `assemble_tool_list` (`lifecycle.py:695-704` for attended, `:714-723` for ambient):

```python
tool_list_attended = assemble_tool_list(
    config,
    capability_registry,                     # ← STUB LIST (positional)
    include_frontier=True,
    nats_client=nats_client,
    routing_history_writer=routing_history_writer,
    dispatch_semaphore=dispatch_semaphore,
    forge_subscriber=forge_subscriber,
    capabilities_registry=capabilities_registry,  # ← LIVE REGISTRY (kwarg)
)
```

Inside `assemble_tool_list` (`tools/__init__.py:252-263`):

```python
# Live registry → catalogue tools (list_available_capabilities, capabilities_refresh, capabilities_subscribe_updates)
_capabilities._capability_registry = capabilities_registry          # ← LIVE

# Stub list snapshot → dispatch tool's resolver
_dispatch._capability_registry = list(capability_registry)          # ← STUB
```

The dispatch tool's resolver (`tools/dispatch.py:438`) reads from `_dispatch._capability_registry` only:

```python
registry_snapshot = list(_capability_registry)                      # ← STUB
…
agent_id = _resolve_agent_id(tool_name, intent_pattern, registry_snapshot, …)
```

The stub yaml lists architect-agent as:

```yaml
- agent_id: architect-agent
  role: Architect
  capability_list:
    - tool_name: run_architecture_session
    - tool_name: draft_adr
```

— neither of which matches `architect_align`. The resolver iterates the stub list (sorted by agent_id), finds no `tool_name="architect_align"` match, has no `intent_pattern` to fall back on (the supervisor dropped that arg), and returns `None` → callers see `ERROR: unresolved`.

The runbook §2.5 "Catalogue-vs-stub note" claim:

> ... jarvis runs `capabilities_mode: live`: `jarvis.infrastructure.capabilities_registry.KVCapabilityRegistry` opens a `watchall()` on `agent-registry` at boot and replaces the stub entries with whatever the live containers advertise. The supervisor's session-start "Available Capabilities" injection therefore reflects `architect_align`/etc., not the stub.

is **half-correct**: the prompt-block injection (via `capabilities_*` tools) IS hydrated from the Live registry, so the supervisor's prompt sees `architect_align`. But the dispatch resolver is NOT — it stays bound to the stub list.

This is the **same shape** as Gap PEBR-WIREUP from `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md`: the underlying machinery (the Live registry) is fully implemented, the wireup function (`assemble_tool_list`) accepts both registries as parameters, but exactly one wiring step is missing — the line that snapshots the Live registry's view into `_dispatch._capability_registry`.

### Why the existing tests didn't catch this

Suspected (not verified — would need to audit the FEAT-JARVIS-004 test corpus): the unit tests likely use a hand-rolled `_dispatch._capability_registry` fixture seeded with the desired CapabilityDescriptor list, rather than driving the full `assemble_tool_list` boot path against a Live KV with new tool names. The integration test that *would* catch this is one that:

1. Boots a real or near-real LiveCapabilitiesRegistry with KV content that has `architect_align` (or any tool not in the stub yaml).
2. Asserts that `dispatch_by_capability(tool_name="architect_align", payload_json="{}", timeout_seconds=5)` returns either a TIMEOUT (architect not actually running in the test) or a wire envelope on `agents.command.architect-agent.>` — but specifically NOT `ERROR: unresolved`.

The runbook §2.5 "Catalogue-vs-stub note" and §3.2 "live catalogue surfaced architect_align" tests verify the prompt-block path, not the resolver path — same kind of test gap as Gap PEBR-WIREUP's PEB-013.

### Fix shape (indicative, single function)

Inside `assemble_tool_list` at `tools/__init__.py:263`, replace:

```python
# Stub list snapshot → dispatch tool's resolver
_dispatch._capability_registry = list(capability_registry)
```

with:

```python
# Live registry snapshot → dispatch tool's resolver. Initial snapshot is
# taken synchronously (LiveCapabilitiesRegistry.create() warms its cache
# inside the constructor per its docstring); a watch-driven callback
# refreshes _dispatch._capability_registry on every KV update.
_dispatch._capability_registry = list(capabilities_registry.snapshot())
def _refresh_dispatch_registry() -> None:
    _dispatch._capability_registry = list(capabilities_registry.snapshot())
capabilities_registry.subscribe_updates(_refresh_dispatch_registry)
```

Plus a graceful-degradation fallback: if `capabilities_registry` is the StubCapabilitiesRegistry (DDR-021 NATS-down soft-fail path, see `lifecycle.py:637/639`), `snapshot()` should still return the stub-derived descriptors so dispatch keeps working in NATS-down mode. The `_build_stub_capabilities_registry` helper at `lifecycle.py:637` already wraps the stub list, so `snapshot()` from that wrapper should be equivalent to the current `list(capability_registry)` behavior — verify before shipping.

The integration test that protects this fix should drive `assemble_tool_list` with a Live registry pre-loaded with a tool name not in the stub yaml, then assert the dispatch resolver finds it.

## What this DOES NOT block (informational)

Phases 0–3 prove that the surrounding plumbing IS green:

- llama-swap is serving `architect-agent` (the fine-tuned Gemma 4 26B-A4B MoE alias) and `qwen36-workhorse` (supervisor) — host process on `:9000`, both reachable
- specialist-agent dual-role compose is up, both containers registered to `agent-registry` KV with full manifests, architect's tool surface includes `architect_align` exactly per the runbook §2.5 expectation
- jarvis chat boots clean — no NATS subscription errors, F010Db disjoint filter holding, `capabilities_mode: live` reported
- The supervisor's prompt-block IS hydrated from the live KV (the supervisor explicitly said in attempt 3: "architect_align was in the catalogue") — so the discoverability story works
- Forge dispatch path (FEAT-JARVIS-INTERNAL-001) is unaffected — `queue_build` does not use `dispatch_by_capability` (it's a dedicated tool), so it sits on a different wiring path entirely

This means: **closing Gap DISPATCH-STUB-RESOLVER is the only thing standing between this rerun and a green demo.** Once the wiring is fixed, Phases 0–3 should still hold, Phase 4 should produce a real `agents.command.architect-agent.<corr>` envelope, the architect container's command router should map `architect_align → align`, llama-swap should run the fine-tuned model, and a real `AlignmentJudgment` should land in the chat REPL.

## Available pre-fix workarounds (not applied today — user opted to write up the gap rather than patch)

For reference, three workarounds exist if a stage demo is needed before the code fix lands:

1. **Patch `stub_capabilities.yaml`** — add `architect_align`, `architect_greenfield`, `architect_explore`, `architect_feasibility` to the architect-agent's `capability_list` to mirror what the live KV publishes. Demo runs end-to-end. One-edit, reversible. Side-effect: masks the gap in any future verification run that doesn't hit the same stub.
2. **Patch `lifecycle.py` (real fix)** — apply the fix shape above. Bigger blast radius (requires unit tests) but actually closes the gap.
3. **Use the `intent_pattern` resolver fallback** — instruct the supervisor to call `dispatch_by_capability(tool_name="architect_align", intent_pattern="Architect", …)`. The stub's `architect-agent.role` is exactly "Architect", so the fallback at `dispatch.py:249-254` would resolve. **Caveat:** verified empirically today (attempt 3) that `qwen36-workhorse` does NOT honour the explicit `intent_pattern` instruction — it drops the arg. A larger or differently-tuned supervisor model might preserve it. Not reliable.

## Operator-side observations (informational)

- Both wire taps require the inline `RICH_NATS_PASSWORD` export prefix on every command — the harness resets shell cwd between Bash calls so persistent env is not available. The runbook's §0.4 "in the same shell" guarantee does not survive a non-interactive multi-call execution model, and each NATS-touching command must re-source the password.
- Three trace files emerged in `~/.jarvis/traces/` — one per dispatch attempt. The FRR-003 offload path is fully functional even on resolver-level failures, which is good news for post-mortem visibility.
- The supervisor's narrative explanation of the `unresolved` error ("the architect-agent has no heartbeat") in attempts 2 and 3 is **incorrect** — `last_heartbeat_at` IS `null` on the stub yaml entries (it's never populated), but that's not what the resolver checks. The resolver matches `tool_name` against `capability_list[].tool_name`, full stop. Heartbeat is not consulted. The supervisor's prose is plausible-sounding hallucination; future operators reading the chat output should not be misled.
- The runbook §6 "failure modes" table row for "`dispatch_by_capability` returns `ERROR: unresolved`" suggests "Run §2.5 — if tool count is 0, redo §0.4 + §2.2; if non-zero, restart jarvis chat to force the watch to re-prime." This is **incorrect guidance** — restarting jarvis chat doesn't help because the dispatch resolver is bound to the stub yaml regardless of how many times the live KV watch primes. The §6 row needs updating to mention Gap DISPATCH-STUB-RESOLVER.

## Decision

- [ ] Phase 4 closed canonical (demo path green)
- [x] **Phase 4 BLOCKED with one-step-deep gap** — Phases 0–3 are green; Phase 4 dispatch fails at the resolver level due to the live registry not being wired into `_dispatch._capability_registry`. Gap is single-function-deep (one wiring line in `tools/__init__.py:263`); fix shape documented above.
- [ ] Partial — single-phase failure with follow-up task

## Recommended follow-ups

1. **jarvis — Gap DISPATCH-STUB-RESOLVER (NEW):** In `jarvis.tools.__init__.assemble_tool_list`, change the `_dispatch._capability_registry` snapshot from `list(capability_registry)` (stub list) to `list(capabilities_registry.snapshot())` (Live registry view). Add a watch-driven refresh callback so KV updates propagate to the dispatch tool. Add an integration test driving `assemble_tool_list` with a Live registry pre-loaded with a tool name not in the stub yaml; assert the dispatch resolver finds it (or at minimum doesn't return `ERROR: unresolved` for that tool). Audit the FEAT-JARVIS-004 test corpus to confirm whether any existing test exercises this exact path — if it does, understand why the gap shipped through; if not, that's why.
2. **runbook — `RUNBOOK-jarvis-architect-align-dddsw-demo.md`:**
   - §2.5 "Catalogue-vs-stub note" — rewrite. The current text claims live KV watch "replaces the stub entries"; that's true for the prompt-block injection but FALSE for the dispatch resolver. The note misleads operators into expecting Phase 4 to work when Gap DISPATCH-STUB-RESOLVER is open.
   - §6 "failure modes" — update the `ERROR: unresolved` row. Restarting jarvis chat doesn't help; the actual cause is the stub yaml not listing the tool name. Add a row referencing Gap DISPATCH-STUB-RESOLVER.
   - §0 — add a new pre-flight gate: "Confirm stub yaml ↔ live KV alignment for the demo's tool name." Until DISPATCH-STUB-RESOLVER closes, this would be the single guard that saves a demo.
3. **specialist-agent / fleet docs:** consider whether the stub yaml format should be deprecated entirely once DISPATCH-STUB-RESOLVER closes. The stub serves two purposes today (DDR-021 NATS-down fallback + dispatch resolver source-of-truth); fixing DISPATCH-STUB-RESOLVER eliminates the second purpose, making the stub a NATS-down-only safety net.
4. **DDD South West demo (2026-05-16) preparation:** if Gap DISPATCH-STUB-RESOLVER does not close before 2026-05-15 dress-rehearsal, fall back to workaround #1 (patch stub yaml) for the demo, and file the code fix as an immediate post-talk follow-up. Workaround #3 (intent_pattern fallback) is not reliable with `qwen36-workhorse` as supervisor.

## Cross-machine state observed

- **NATS** (`ships-computer-nats`, host-network): up 22h healthy. 7 streams + 4 KV buckets all present. `agent-registry` has 3 rows: jarvis (self-registration), architect-agent (manifest with 4 tools), product-owner-agent.
- **specialist-agent dual-role** (bridge network with `host.docker.internal:host-gateway` patch from compose, image rebuilt today 07:06): both architect-agent and product-owner-agent containers Up 46m+, fully registered, environments correct. Heartbeats publishing every 30s per container log. Architect's tool manifest correctly exposes all four `architect_*` tools.
- **llama-swap**: up via systemd, serving on `:9000`. `architect-agent` (fine-tuned Gemma 4 26B-A4B MoE) loaded; `qwen36-workhorse` available for the supervisor. Both reachable from host and from bridge-networked containers via `host.docker.internal:host-gateway`.
- **jarvis chat**: boots clean from `~/Projects/appmilla_github/jarvis/.venv/bin/jarvis`. Three sessions launched today during runbook execution; all closed cleanly. No NATS subscription errors, F010Db disjoint filter holds (post `6071fe0`).
- **Graphiti**: skipped (deliberate; FRR-003 trace-offload path used instead, and it works).

## Evidence files

All under `~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/`:

- `chat-attempt3-intent-pattern-arg-dropped.log` — full chat output for attempt 3 (the most-instructive of three; supervisor's own narrative explicitly names the unresolved error and the false "no heartbeat" claim is preserved here for reference)
- `trace-attempt2-becfa233.json` — first dispatch attempt's FRR-003 trace (07:58:23)
- `trace-attempt2-c428dc05.json` — second dispatch attempt within the same chat session (07:58:35; supervisor retried after first unresolved)
- `trace-attempt3-d8525237.json` — third attempt's trace (07:02:36); definitive evidence — `outcome_type: unresolved`, `outcome_detail.intent_pattern: null` (proves the supervisor dropped my arg), `attempts: []`, `visited: []`

Original copies retained in `~/.jarvis/traces/` and `/tmp/dddsw-demo-*.log` (latter ephemeral; will be cleared on next reboot).

## See also

- **Gap PEBR-WIREUP** (the structurally-identical forge-side gap discovered 2026-05-08): `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md`. Both gaps share the shape: code shipped + tested in isolation + missing exactly one wiring step at the integration boundary, caught only when the runbook walks the full path.
- **Single-machine MCP-stdio architect validation** (the inference-quality baseline this demo path generalises): `specialist-agent/docs/research/ideas/fine-tuned-architect-local-inference-validation.md`
- **NATS dual-role evidence-capture script** (confirms the `agents.command.*` → `agents.result.*` round-trip works when called directly, bypassing jarvis): `specialist-agent/scripts/nats-evidence-runbook.md`. Worth running as an isolation test to prove the architect-side wire is healthy independent of the jarvis-side resolver gap.
- **dispatch_by_capability tool surface**: `jarvis/src/jarvis/tools/dispatch.py:351-410`
- **The exact wiring line that needs to change**: `jarvis/src/jarvis/tools/__init__.py:263`
- **The capability registries that exist but aren't both consumed**: `jarvis/src/jarvis/infrastructure/capabilities_registry.py:170-330` (LiveCapabilitiesRegistry); `jarvis/src/jarvis/config/stub_capabilities.yaml` (Stub)
