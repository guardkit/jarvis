# Runbook: Jarvis → Architect Align — DDD South West Demo

**Status:** Draft (rehearsal target). Demo date: **2026-05-16** (DDD South West). This runbook is intended to be executed end-to-end at least twice before the talk: once for verification (this week), once as a dress rehearsal the day before. Update Status to "Verified" after the first green walkthrough.

**Purpose:** Demonstrate the local-first agent dispatch path live on stage:

```
human prompt in jarvis chat REPL
  → supervisor reasons + selects dispatch_by_capability
  → tool_name=architect_align dispatch via NATS agents.command.architect-agent
  → specialist-agent-architect-agent container on Docker
  → llama-swap on the host serving the fine-tuned `architect-agent` Gemma 4 26B-A4B MoE model
  → structured AlignmentJudgment Pydantic returns via the NATS msg.reply inbox (_INBOX.>)
  → supervisor renders judgment/confidence/reasoning to the human
```

Zero cloud LLM on the path. Marginal cost per dispatch: effectively zero after the one-time fine-tuning investment. **This is the narrative payload of the "2026: The Year of the Software Factory" talk.**

**Companion / source-of-truth reference:**
- `specialist-agent/docs/research/ideas/fine-tuned-architect-local-inference-validation.md` — the 2026-05-07 single-machine MCP-stdio validation that this runbook generalises to NATS + dual-role + jarvis dispatch.
- `specialist-agent/scripts/nats-evidence-runbook.md` — the existing dual-role NATS round-trip recipe this runbook reuses for §2.
- `RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — the structural pattern (Phase 0 pre-flight → close criterion) this runbook mirrors.

**Machine layout (single-host):** GB10 (`promaxgb10-41b1`) hosts:
- NATS JetStream (`ships-computer-nats`, host-network, `:4222`)
- llama-swap (host process, `:9000`, serving `architect-agent` Gemma 4 + `qwen36-workhorse` for the supervisor)
- specialist-agent dual-role compose (`specialist-agent-architect-agent-1`, `specialist-agent-product-owner-agent-1`, bridge network with `host.docker.internal:host-gateway`)
- jarvis chat REPL (host venv)

**Expected wall-clock:** ~15–20 minutes for a clean dry-run (most of which is the supervisor + architect doing real work, not setup). On the day, expect 5–10 minutes from "type prompt" to "judgment rendered" — the architect takes 30–90s of llama-swap inference per call against a Gemma 4 26B MoE on Blackwell.

**Outputs:**
- `docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-<YYYY-MM-DD>.md` capturing per-phase outcomes and evidence pointers
- `~/.jarvis/transcripts/<correlation_id>.txt` — the chat transcript
- `~/.jarvis/traces/<correlation_id>.json` — DDR-019 / DDR-029 routing-history offload (FRR-003 path)
- The captured `AlignmentJudgment` JSON saved to `docs/runbooks/evidence/dddsw-demo/<correlation_id>.json` for the talk slide

---

## What this runbook does NOT cover

- **Forge / autobuild dispatch path** — covered by `RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` (and currently blocked by Gap PEBR-WIREUP per `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md`). The architect-align demo path is **wholly orthogonal** — specialist-agent dispatch uses `agents.command.<role>` request-reply, not the workqueue PIPELINE stream that the autobuild path requires. So the open forge gap does NOT block this demo.
- **Greenfield (Mode 1) / Exploration (Mode 3) / Feasibility (Mode 4) sessions** — they're long-running async modes (5–30 min); not appropriate for stage demo. We're using **Mode 2 (`architect_align`)** synchronous-single-pass exclusively per the validation doc's "Next Steps" section.

---

## Demo narrative (Talk Track) — read this first

The runbook below is the operator script. The talk track is what the operator says aloud while the runbook executes. Roughly:

1. **Frame** (~30s): "I'm going to take an ADR I wrote three weeks ago and a proposal I thought up this morning, and ask jarvis whether they align. The judgment will come from a fine-tuned 26B Gemma model running on this single Blackwell box behind me. No cloud LLM is involved at any point."
2. **Show topology slide** (~30s): five boxes, all-local arrows. "Jarvis is the supervisor. Specialist-agent is the architect. NATS is the message bus. llama-swap routes to the right model. Graphiti is dormant in this demo — we'll bring it in for the next one."
3. **Type the prompt** (~20s): one line into the chat REPL. (See §4.2.)
4. **While it runs** (~60–90s): narrate what's actually happening — the supervisor reasoning step, the JetStream request, the docker container picking it up, the llama-swap inference, the Pydantic-validated structured output threading back. **Have the `nats sub` window mirrored** so the audience sees the wire envelopes flow live (§5).
5. **Read the result aloud** (~30s): the `judgment` field, the `confidence`, the first sentence of `reasoning`. "This was produced by a domain-fine-tuned model that has never been to the cloud."
6. **Land the point** (~30s): "Marginal cost per architecture session is now zero. The one-time fine-tune cost has paid back. The agent runs with the same operational shape as a database — `docker compose up`."

Total: ~5 minutes. Buffer for architect inference latency.

---

## Phase 0: Go/no-go pre-flight

### 0.1 Confirm jarvis main + clean tree

```bash
cd ~/Projects/appmilla_github/jarvis
git fetch origin
git status -s -uno
git log --oneline -5
```

**Pass:** Working tree clean, branch `main` up-to-date with `origin/main`. The runbook tracks `main`; the specific HEAD SHA is not load-bearing. The two commits this demo's hygiene assumes are in (and have been in `main` since well before 2026-05-08) are `dcaa8eb` (lifecycle subscriber widening) and `6071fe0` (TASK-FRR-F010Db disjoint filter); without those, the chat REPL's between-prompt notification rendering would be stale. They don't affect this demo's request-reply path, but you want them in for hygiene. If `git log --oneline | grep -E '(dcaa8eb|6071fe0)'` returns both, you're fine.

### 0.2 Confirm specialist-agent main + image freshness

```bash
cd ~/Projects/appmilla_github/specialist-agent
git status -s -uno
git log --oneline -5
docker images specialist-agent --format 'table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}'
```

**Pass:** Image `specialist-agent:latest` exists; created date is post-2026-04-17 (per `scripts/nats-evidence-runbook.md` §0.3 — older images reject the `align` command with "Command 'align' is not supported"). When in doubt, rebuild:

```bash
cd ~/Projects/appmilla_github/specialist-agent && ./scripts/docker-build.sh
```

### 0.3 Confirm llama-swap is up and serving `architect-agent`

```bash
ss -tlnp 2>/dev/null | grep :9000
curl -sf http://localhost:9000/v1/models | jq -r '.data[].id' | sort
```

**Pass:** Port 9000 listening (llama-swap systemd service). Models list includes **`architect-agent`** (the fine-tuned Gemma 4 alias) and at least one chat model for the supervisor (`qwen36-workhorse` recommended).

> If `architect-agent` is missing from the model list, the demo fails at the architect's LLM call with "model not found". Check llama-swap's config for the alias mapping. The fine-tuned model must be loaded as `architect-agent` (no namespace prefix); that's the alias the role config in specialist-agent expects.

### 0.4 Confirm NATS is up + auth env is sourced

```bash
docker ps --filter name=ships-computer-nats --format '{{.Names}}\t{{.Status}}'
```

**Pass:** `ships-computer-nats` Up (healthy).

Surgically load the APPMILLA-account creds (per the user's reported workaround — `RICH_NATS_PASSWORD` is in `nats-infrastructure/.env` but you do **not** source the whole file because it has stale `OPENAI_API_KEY` baggage):

```bash
cd ~/Projects/appmilla_github/specialist-agent
export RICH_NATS_PASSWORD="$(grep '^RICH_NATS_PASSWORD=' ../nats-infrastructure/.env | cut -d= -f2-)"
export NATS_USER=rich
export NATS_PASSWORD="$RICH_NATS_PASSWORD"
echo "NATS_USER=$NATS_USER  NATS_PASSWORD set: $([[ -n "$NATS_PASSWORD" ]] && echo yes || echo no)"
```

**Pass:** `NATS_USER=rich  NATS_PASSWORD set: yes`. If `NATS_PASSWORD set: no`, the dual-role compose will boot but the containers will fail registration with `nats: 'Authorization Violation'` and the agent-registry KV will be empty (§2.4 trap).

> **First-run-symptom (operator already hit this):** without these exports, the architect/PO containers start but never register — the `agent-registry` KV stays empty and jarvis's `dispatch_by_capability` returns `ERROR: unresolved`. The fix is the export above, **then** `down + up -d` to re-substitute compose env. See `specialist-agent/scripts/nats-evidence-runbook.md` §1.1 for the canonical sequence.

### 0.5 Stub ↔ Live alignment (advisory, post-W2)

*Optional sanity check.* Confirm `src/jarvis/config/stub_capabilities.yaml`
matches the live KV's published surface for any agent the supervisor will
dispatch to. The dispatch resolver now reads the live KV directly
([TASK-DSR-003](../../tasks/completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)
W2), so divergence is operationally tolerated — the stub yaml is only used
as the bootstrap surface and as the NATS-down soft-fail (DDR-021). A CI
drift lint is a follow-up (see
[TASK-REV-CB48](../../.claude/reviews/TASK-REV-CB48-review-report.md)
review report R5).

For this demo the supervisor will dispatch `architect_align` to
`architect-agent`. To inspect the stub yaml directly:

```bash
cd ~/Projects/appmilla_github/jarvis
python3 -c "import yaml; d=yaml.safe_load(open('src/jarvis/config/stub_capabilities.yaml')); [print(a['agent_id'], '→', a.get('capability_list', [])) for a in d.get('capabilities', [])]"
```

**Pass:** the `architect-agent` row's `capability_list` contains
`architect_align` (added by
[TASK-DSR-001](../../tasks/completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-001-W1-stub-yaml-patch.md)
W1). The live KV is the canonical guard; this yaml is the NATS-down
fallback the resolver consults when the live registry is unavailable.

### 0.6 Pre-stage decision: which ADR + proposal pair?

Two recommended options for the demo. **Pick before stepping on stage.**

| Option | ADR | Proposal | Why pick it |
|---|---|---|---|
| **A (recommended)** | `ADR-ARCH-001-local-first-inference-via-llama-swap.md` (jarvis) | "Add a Claude Opus 4.7 escalation path inside the supervisor for high-stakes reasoning." | **Narrative-perfect for the talk:** the local-first ADR being asked to evaluate a *cloud-escalation* proposal. The architect should return `needs_clarification` or `misaligned` and cite the ADR's local-first invariant. **Live-loop closure** with the talk's central claim. |
| **B (drift-rich)** | `ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md` | "Forge has introduced `~/forge-state/forge.db` SQLite for build state. Should jarvis follow suit for routing-history offload?" | **Real architectural drift:** forge already broke ADR-008 with SQLite. The architect should detect the existing drift and judge whether the proposal compounds it. **Lands the point that fine-tuned local models can do real architectural reasoning.** Slightly riskier — the response shape is harder to predict without a dry-run. |

Capture the chosen pair in your `RESULTS-…-<DATE>.md` so the talk can reference it.

> Avoid making this decision live on stage. Pre-rehearse Option A end-to-end at least once. Hold Option B in reserve for Q&A or a second demo if there's time.

---

## Phase 1: Canonical NATS provisioning verified

This is a strict subset of `RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` §1. The demo path needs:

- The `AGENTS` JetStream stream (covers `agents.>` subjects)
- The `agent-registry` KV bucket (specialist-agent's `architect-agent` row lives here)

Both are part of the canonical `nats-infrastructure` provisioning.

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
bash scripts/verify-nats.sh
```

**Pass:** `verify-nats.sh` reports all 7 streams and all 4 KV buckets present. If you see auth-shaped misreports, see the first-real-run runbook §1.2.

> The PIPELINE stream is irrelevant to this demo (no forge dispatch). Don't be alarmed if it has leftover undrained envelopes from prior autobuild runs — they don't affect `agents.command.architect-agent` traffic.

---

## Phase 2: specialist-agent dual-role stack up and registered

### 2.1 Confirm `.env` has the LLM provider set to local

```bash
cd ~/Projects/appmilla_github/specialist-agent
grep -E '^(AGENT_MODELS__REASONING_MODEL|LLM_BASE_URL|OPENAI_BASE_URL|OPENAI_API_KEY|NATS_USER|NATS_PASSWORD|ARCHITECT_LOCAL_MODEL|PO_LOCAL_MODEL)=' .env
```

**Expect (values masked is fine):**

```
AGENT_MODELS__REASONING_MODEL=local
LLM_BASE_URL=http://host.docker.internal:9000
OPENAI_BASE_URL=http://host.docker.internal:9000/v1
OPENAI_API_KEY=not-needed
NATS_USER=rich
NATS_PASSWORD=<set>
ARCHITECT_LOCAL_MODEL=architect-agent
PO_LOCAL_MODEL=product-owner-agent
```

> **Per the user's workaround log (2026-05-08 setup):** `NATS_USER` and `NATS_PASSWORD` were added to `.env` from `nats-infrastructure/config/accounts/accounts.conf.template` because the first run failed with `Authorization Violation`. Per-role `LOCAL_MODEL` overrides come from the docker-compose patch that adds `extra_hosts: host.docker.internal:host-gateway` so the bridge-network containers reach the host's NATS and llama-swap.
>
> If `AGENT_MODELS__REASONING_MODEL` is `claude` or unset, the architect will try Anthropic and fail with an auth error (per `nats-evidence-runbook.md` §0.1 / failure-modes table). For this demo it MUST be `local`.

### 2.2 Bring the dual-role stack up

```bash
cd ~/Projects/appmilla_github/specialist-agent
docker compose -f docker-compose.dual-role.yml down
docker compose -f docker-compose.dual-role.yml up -d
sleep 5
docker ps --filter name=specialist-agent --format 'table {{.Names}}\t{{.Status}}'
```

**Pass:** Both `specialist-agent-architect-agent-1` and `specialist-agent-product-owner-agent-1` show Status `Up`. (Healthcheck status varies by image — `Up` is sufficient.)

### 2.3 Confirm both containers got the right env

```bash
docker exec specialist-agent-architect-agent-1 printenv AGENT_MODELS__REASONING_MODEL
docker exec specialist-agent-architect-agent-1 printenv LOCAL_MODEL
docker exec specialist-agent-architect-agent-1 printenv LLM_BASE_URL
docker exec specialist-agent-architect-agent-1 printenv NATS_URL | sed 's/:[^@]*@/:***@/'
```

**Expect:**

```
local
architect-agent
http://host.docker.internal:9000
nats://rich:***@host.docker.internal:4222
```

If `AGENT_MODELS__REASONING_MODEL=claude` or `LOCAL_MODEL=` is empty, redo §0.4 + §2.2 in the same shell — compose only re-substitutes env at `up -d` time.

### 2.4 Verify both agents registered to `agent-registry` KV

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" kv ls agent-registry
```

**Pass:** Output includes both `architect-agent` and `product-owner-agent` rows with non-zero size. Empty rows = registration failed; check container logs for `Authorization Violation` (redo §0.4 → §2.2) or `model not found` (redo §0.3).

### 2.5 Verify the architect actually publishes `architect_align` in its tool surface

This is the critical gate the first-real-run runbook didn't need but this one does — we're dispatching by capability, so the catalogue jarvis sees must include `architect_align`:

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    kv get agent-registry architect-agent --raw 2>/dev/null \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('agent_id:', d['agent_id']); print('tool count:', len(d['tools'])); [print('  -', t['name']) for t in d['tools']]"
```

**Pass:** Output:

```
agent_id: architect-agent
tool count: 4
  - architect_greenfield
  - architect_align
  - architect_explore
  - architect_feasibility
```

**If `tool count: 0` or `architect_align` is missing:** the manifest the running container publishes does not include the align mode. This means either (a) the image is pre-MDF-PORT (rebuild per §0.2) or (b) the role config has been edited. Stop and resolve before §3.

> **Catalogue-and-dispatch parity (post-W2):** Both the catalogue path
> (`KVCapabilityRegistry.watchall()` per
> `jarvis.infrastructure.capabilities_registry`) and the dispatch resolver
> (`tools/dispatch.py` via the live registry per
> [TASK-DSR-003](../../tasks/completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)
> W2) read the live `agent-registry` KV when jarvis runs
> `capabilities_mode: live`. Post-[TASK-DSR-001](../../tasks/completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-001-W1-stub-yaml-patch.md)
> W1, `src/jarvis/config/stub_capabilities.yaml` also publishes the
> live-aligned `architect_align`/`architect_greenfield`/`architect_explore`/`architect_feasibility`
> entries (alongside the legacy `run_architecture_session` / `draft_adr`),
> so the stub serves as bootstrap surface and as the NATS-down soft-fail
> (DDR-021); it is no longer a divergent source. Verified at boot via the
> `jarvis_capability_registry_loaded` log event followed by the live KV
> watch. Historical context — pre-W2 the resolver iterated the stub yaml
> only, the divergence captured in
> [TASK-REV-CB48](../../.claude/reviews/TASK-REV-CB48-review-report.md)
> and closed by W2.

---

## Phase 3: jarvis chat boots clean and surfaces architect_align in its catalogue

### 3.1 Boot jarvis chat (interactive — for the demo this is the ON-STAGE moment)

```bash
cd ~/Projects/appmilla_github/jarvis
set -a && source ../nats-infrastructure/.env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
set -a && source .env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
export JARVIS_LOG_LEVEL=INFO
.venv/bin/jarvis chat 2>&1 | tee /tmp/dddsw-demo-chat.log
```

**Pass (visible in boot log):**

- `nats_connect_success` ✅
- `jarvis_capability_registry_loaded path=src/jarvis/config/stub_capabilities.yaml count=4` (the bootstrap stub) ✅
- `forge_notifications_subscribed subjects=[pipeline.build-started.>, pipeline.stage-complete.>, pipeline.build-complete.>, pipeline.build-failed.>]` ✅ — these are unused for this demo but confirm the post-F010Db disjoint filter is applied so jarvis boots clean.
- `jarvis_startup_complete nats_available=true graphiti_available=false capabilities_mode=live` ✅
- The chat banner + `>` prompt rendered

> **JARVIS_LOG_LEVEL=INFO**, not DEBUG, for the demo run — DEBUG floods the screen with httpx envelopes and obscures the demo. Use DEBUG for rehearsals where you want full evidence; use INFO for the talk.

### 3.2 Confirm the live catalogue surfaced `architect_align`

In the REPL, type:

```text
> What architecture-related tools do you have available?
```

**Pass:** The supervisor's response names the architect-agent and at least one of: `architect_align`, `architect_greenfield`, `architect_explore`, `architect_feasibility`. If the response only mentions `run_architecture_session` and `draft_adr`, the live KV watch hasn't replaced the stub yet — wait 5–10s and re-ask. If it persists, see §6 troubleshooting.

> Don't dwell on this in the talk — it's an internal check. On stage, skip §3.2 and go straight to §4.

---

## Phase 4: The demo turn — review the chosen ADR via `architect_align`

### 4.1 The exact prompt to type (Option A — recommended)

In the chat REPL:

```text
> I want the architect to align this proposal against ADR-ARCH-001:
>
> ADR-ARCH-001 (jarvis) commits jarvis to local-first inference via llama-swap; cloud LLMs are explicitly out of the supervisor's hot path.
>
> Proposal: add a Claude Opus 4.7 escalation tool that the supervisor can call when its local reasoner has low confidence on safety-critical or high-stakes user requests. Bound by a per-session budget cap.
>
> Question: is this proposal architecturally sound given ADR-ARCH-001's local-first invariant? What changes to the ADR or the supervisor's contract would the architect need to see for this to be aligned?
```

**Operator-facing alternative (Option B — drift-rich):**

```text
> I want the architect to align this proposal against ADR-ARCH-008:
>
> ADR-ARCH-008 (jarvis) says no SQLite — Graphiti and the memory store are sufficient for jarvis's persistence needs.
>
> Proposal: forge has introduced ~/forge-state/forge.db SQLite for build state, and jarvis's DDR-019 trace offload is currently writing JSON files to ~/.jarvis/traces/. Should jarvis adopt SQLite for the trace offload, mirroring forge's choice?
>
> Question: does this proposal align with ADR-ARCH-008's no-SQLite stance, or does ADR-ARCH-008 itself need revisiting given the broader fleet's drift toward SQLite?
```

### 4.2 What should happen (the supervisor's expected behaviour)

The supervisor should:[^r1-explicit-args-path]

1. Recognise this as architect-routable work (the prompt explicitly names the architect role).
2. Resolve `architect_align` from the live capability catalogue (loaded from `agent-registry` KV in §3.1).
3. Construct a `payload_json` matching the architect_align manifest — three required fields: `context`, `proposal`, `question` (per `specialist_agent/adapters/manifest.py:113-141`).
4. Call `dispatch_by_capability(tool_name="architect_align", payload_json="{...}", timeout_seconds=180)`.
5. Wait for the response (typically 30–90s of architect llama-swap inference time).
6. Render the returned `AlignmentJudgment` to the chat — judgment / confidence / reasoning / suggestions.

**Stage tip:** while it runs, talk through the topology. The supervisor's reasoning step usually takes ~5–10s before dispatch fires, then there's the architect's inference window.

[^r1-explicit-args-path]: *Footnote (2026-05-08): R1 / break-glass path.* The §4.1 prompt templates use an explicit `Context: / Proposal: / Question:` framing that mirrors the three required `architect_align` args. This is the **R1 / break-glass path** — the catalogue-rendered tool surface currently omits the `Args (required):` block (the supervisor sees tool names but not parameter schemas), so the prompt has to enumerate the args inline for the supervisor to construct a valid `payload_json`. The 2026-05-08 success trace (`correlation_id=8df345b4-7b47-4214-8ae3-959aac5252e4`) was produced via this path. The natural-routing claim — that a free-text prompt routes correctly because the catalogue exposes the args schema — is **degraded until the R2 fix lands**. Tracking: [`TASK-CAPS-PROMPT-001`](../../tasks/in_progress/TASK-CAPS-PROMPT-001-render-tool-parameter-schema.md), targeted for 2026-05-13. Once R2 has merged to `main`, this footnote and the explicit-args framing in §4.1 can be replaced with a natural-language prompt and a citation of the snapshot test guarding the rendered `Args (required):` block. Same applies to the §6 fallback row that suggests rephrasing to `"Use dispatch_by_capability with tool_name=architect_align..."` — that fallback is operationally redundant with §4.1's prompt template under R1 and will be retired once R2 lands.

### 4.3 Expected response shape (per validation doc + Pydantic schema)

```json
{
  "judgment": "aligned" | "misaligned" | "needs_clarification",
  "confidence": 0.0,
  "reasoning": "Plain prose: where the proposal sits vs the ADR, what's missing, what's coherent...",
  "suggestions": [
    "First concrete change the architect would want to see",
    "Second concrete change..."
  ]
}
```

**For Option A**, the most likely judgment is `needs_clarification` (the architect should want to see the budget cap details, the "low confidence" trigger threshold, and a cloud-escalation audit trail) or `misaligned` (citing ADR-ARCH-001's invariant). Either is a winning demo outcome — both lead to a clear next-step conversation on stage.

**For Option B**, the most likely judgment is `misaligned` (ADR-ARCH-008 is explicit) or `needs_clarification` (the ADR may itself need revisiting given fleet drift). Either is a demo-able outcome.

### 4.4 Capture the correlation_id and the JSON payload from the REPL

The supervisor will print the response inline. Capture the `correlation_id` (it's threaded through the request and present in the response envelope) — you'll need it for §5 wire evidence and §7 transcript naming.

> **R1 / break-glass note:** the §4.1 prompt template's `Context: / Proposal: / Question:` framing is the R1 path while [`TASK-CAPS-PROMPT-001`](../../tasks/in_progress/TASK-CAPS-PROMPT-001-render-tool-parameter-schema.md) is in flight (see §4.2 footnote). The 2026-05-08 success trace `correlation_id=8df345b4-7b47-4214-8ae3-959aac5252e4` was produced via this path; if you reproduce that wire envelope shape (three top-level args: `context`, `proposal`, `question`) you are on the verified R1 path. Once R2 lands, the §4.1 prompt template will be reduced to free-text and this note can be retired.

---

## Phase 5: Wire-level evidence (parallel session — for the talk's "live wire" mirror)

This is the second SSH/terminal pane you have visible behind you on stage. Run before §4 so the envelopes are captured live.

### 5.1 Tail `agents.command.architect-agent`

In a second pane:

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.command.architect-agent.>" --raw \
  | tee /tmp/dddsw-demo-architect-command.log
```

**Pass during §4:** A single envelope arrives with `event_type` of dispatch shape, `correlation_id` matching §4.4, and a payload containing the `context` / `proposal` / `question` strings the supervisor extracted from your prompt. **This is the on-stage moment** — point at the wire envelope as it lands.

### 5.2 Tail the reply inbox (`_INBOX.>`) with a correlation-id filter

In a third pane. Specialist replies route via the NATS request/reply inbox subject (`_INBOX.>`)[^bug1-reply-channel], **not** `agents.result.architect-agent` — that subject is reserved for fan-out events, not point-to-point replies. `_INBOX.>` is high-traffic across the cluster, so we filter on the `correlation_id` from §5.1 to pluck out just our envelope:

```bash
# Capture the correlation_id from §5.1 once it lands (one of the visible fields
# in the command envelope tee'd to /tmp/dddsw-demo-architect-command.log).
# In this pane, set CID="<the correlation_id>" before subscribing — or pass it
# inline as below.
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "_INBOX.>" --raw \
  | tee /tmp/dddsw-demo-architect-result-raw.log \
  | jq -c --arg cid "$CID" 'select(.correlation_id == $cid)' \
  | tee /tmp/dddsw-demo-architect-result.log
```

If you want a no-filter pre-stage rehearsal capture (everything that lands on the inbox during the demo window), drop the `jq` filter — you'll see your reply alongside any other request/reply traffic on the cluster, and you can post-filter the tee'd raw log with `jq` after the fact.

**Pass during §4:** A single response envelope arrives 30–90s after the command (architect inference time). The envelope's `correlation_id` matches §5.1's; `payload.success: true`; `payload.result` contains the `AlignmentJudgment` JSON.

> **32-byte trap (per `nats-evidence-runbook.md`):** if the captured response file is exactly 32 bytes with `{"stream":"AGENTS","seq":N}` inside, you've subscribed wrong (you read a JetStream PubAck instead of the agent result). The `--raw` flag on `nats sub` does the right thing; only an issue if you use `nats request` interactively.

[^bug1-reply-channel]: *Footnote (2026-05-08, post-Bug #1):* Specialist replies route via the NATS `msg.reply` inbox subject (typically `_INBOX.>`), **not** the previous `agents.result.<agent_id>` subject. The `subscribe_with_reply` / `publish_raw` change in `nats-core` v0.4.0 (`8f2c532` / specialist-agent `1979aa8`) closed the request/reply round-trip; the old `agents.result.*` subject is reserved for fan-out events, not point-to-point replies. Pre-Bug #1 versions of this runbook tailed `agents.result.architect-agent.>` for §5.2 — that pane will be empty after the fix.

### 5.3 Save the AlignmentJudgment for the talk slide

After §4 completes, extract the judgment from the response log and save:

```bash
mkdir -p docs/runbooks/evidence/dddsw-demo
jq '.payload.result' /tmp/dddsw-demo-architect-result.log \
  > docs/runbooks/evidence/dddsw-demo/<correlation_id_from_4.4>.json
cat docs/runbooks/evidence/dddsw-demo/<correlation_id_from_4.4>.json | jq .
```

**Pass:** A clean JSON file under `docs/runbooks/evidence/dddsw-demo/` with judgment / confidence / reasoning / suggestions. **This is the artefact for the post-talk blog post and slide.**

---

## Phase 6: Failure modes — fast triage during rehearsal

Use this as a checklist if the demo fails during rehearsal. Don't read this on stage — internalise it.

| Symptom | Likely cause | Fix |
|---|---|---|
| `dispatch_by_capability` returns `ERROR: unresolved` | Neither the live `agent-registry` KV nor the bootstrap stub yaml publishes the `tool_name` for the matching `agent_id`. Post-W2 ([TASK-DSR-003](../../tasks/completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)) the resolver consults the live KV first; the stub yaml is the NATS-down soft-fail. Closure context: [TASK-REV-CB48 review report](../../.claude/reviews/TASK-REV-CB48-review-report.md). | First, confirm the live `agent-registry` KV is populated and contains the `tool_name` for the agent (§2.5). If the row is empty or missing tools, registration failed — most commonly `Authorization Violation` from skipped `NATS_USER` / `NATS_PASSWORD` exports — redo §0.4 + §2.2 in the same shell. If the live KV is fine and dispatch still fails, fall back to the bootstrap path: add the `tool_name` to the agent's `capability_list` in `src/jarvis/config/stub_capabilities.yaml` ([TASK-DSR-001](../../tasks/completed/feat-dsr-dispatch-stub-resolver-fix/TASK-DSR-001-W1-stub-yaml-patch.md), W1) — this is the NATS-down boot path the resolver reads when the live registry is unavailable. |
| `dispatch_by_capability` returns `TIMEOUT` after 180s | Architect container is up but llama-swap is overloaded or the fine-tuned model is cold-loading | Check llama-swap logs for the request; the architect's first call to a cold model may exceed 180s. Bump `timeout_seconds` to 300 in the prompt instruction, or warm the model first (one prior call) |
| Response `payload.success: false` with `error` mentioning Anthropic / `X-Api-Key` | Container has `AGENT_MODELS__REASONING_MODEL=claude` (the compose default if `.env` didn't override) | Stop, redo §2.1 — set `AGENT_MODELS__REASONING_MODEL=local` in `.env`, then `down + up -d` |
| Response `payload.success: false` with `error` mentioning `model not found` | llama-swap doesn't have `architect-agent` alias loaded | Redo §0.3 — the model alias must match `LOCAL_MODEL=architect-agent` in the container env |
| §5.2 `_INBOX.>` tail captures a 32-byte JetStream PubAck (`{"stream":"AGENTS","seq":N}`) instead of the AlignmentJudgment | `nats request` used instead of `sub`, or a stale subscriber attached to `agents.result.architect-agent.>` (which is JetStream-backed) | Use `nats sub --raw` on `_INBOX.>` per §5.2; the request/reply inbox is core NATS, not JetStream, so the PubAck does not apply once subscribed correctly |
| §5.2 `_INBOX.>` filter returns nothing for the demo's `correlation_id` | Either `$CID` not exported in the §5.2 pane, or the envelope landed on the inbox before the subscription attached | Verify `$CID` matches §5.1's command envelope `correlation_id`; subscribe to `_INBOX.>` *before* §4 (per the pane order in §5); fall back to post-filtering the unfiltered tee'd raw log |
| §5.2 pane stays empty during §4 even though the chat REPL renders an answer | Subscriber still tailing the legacy `agents.result.architect-agent.>` (pre-Bug #1 wiring) | Resubscribe to `_INBOX.>` per the post-Bug #1 §5.2; old subject is fan-out only |
| `agent-registry` KV is empty after `up -d` | `NATS_USER` / `NATS_PASSWORD` not propagated into containers (most common cause: §0.4 skipped or done in a different shell) | Container logs will show `nats: 'Authorization Violation'`. Redo §0.4 (in the same shell), then §2.2 |
| Boot log shows `JARVIS_OPENAI_BASE_URL` set but supervisor still routes to llama-swap | Working as designed — `lifecycle.py:569-570` unconditionally overrides to llama-swap (`JARVIS_OPENAI_BASE_URL` was retired by TASK-FRR-002, see jarvis/.env note) | Not a bug; ignore |
| Supervisor reasons but never calls `dispatch_by_capability` | Supervisor model is too small or the catalogue injection didn't surface architect tools | If using `qwen36-workhorse` and it's struggling, swap to `gemma4-tutor` for the supervisor; or rephrase the prompt to be more explicit ("Use dispatch_by_capability with tool_name=architect_align...") |
| Response renders but the `reasoning` field is empty / generic | Fine-tuned model needs a warmup call on cold start | Run one throwaway architect_align call before the demo to warm the model; first call cold can underperform vs. second call warm |

---

## Phase 7: Capture evidence

### 7.1 Save the chat transcript

```bash
cp /tmp/dddsw-demo-chat.log \
   ~/.jarvis/transcripts/<correlation_id_from_4.4>.txt
```

### 7.2 Verify the routing-history offload landed

```bash
ls -la ~/.jarvis/traces/<correlation_id_from_4.4>.json
jq '{decision_id, outcome_type, outcome_detail, supervisor_reasoning_summary}' \
   ~/.jarvis/traces/<correlation_id_from_4.4>.json
```

**Pass:** `outcome_type=success`, `outcome_detail.tool_name=architect_align`, `supervisor_reasoning_summary=dispatch_by_capability` per `dispatch.py:729`. `~/.jarvis/traces/` is auto-created by FRR-003's soft-fail path.

### 7.3 Append a `command_history.md` entry per LES1 §8

In `jarvis/docs/history/command_history.md`, append a section dated to today with:
- ADR + proposal pair used (Option A or B)
- correlation_id
- `judgment`, `confidence` from the response
- One-line summary of the architect's `reasoning`

This is for the post-talk write-up; not visible during the demo.

### 7.4 Write the RESULTS file

`docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-<YYYY-MM-DD>.md` mirroring this runbook's phase structure with a `Phase | Gate | Outcome | Evidence` table. Use the first-real-run RESULTS files as a template.

---

## Phase 8: Demo close

Once §4 has rendered the `AlignmentJudgment` and §5 has captured the wire envelopes:

- [ ] `agents.command.architect-agent` tail captured the inbound dispatch envelope with the same `correlation_id` jarvis published
- [ ] `_INBOX.>` tail (per §5.2) captured the response envelope ~30–90s later, same `correlation_id`, `payload.success: true`
- [ ] Chat REPL rendered the `AlignmentJudgment` with judgment / confidence / reasoning / suggestions all populated
- [ ] Routing-history trace landed at `~/.jarvis/traces/<correlation_id>.json` with `outcome_type=success`
- [ ] Talk track delivered against the rolling demo (~5 minutes total)

If all five check, the demo is **green**. Take down the dual-role stack only if you're done for the session:

```bash
cd ~/Projects/appmilla_github/specialist-agent
docker compose -f docker-compose.dual-role.yml down
```

Leave `ships-computer-nats` and llama-swap running — other work depends on them.

---

## See also

- **Single-machine MCP-stdio validation** (the fine-tuned-architect baseline this generalises): `specialist-agent/docs/research/ideas/fine-tuned-architect-local-inference-validation.md`
- **NATS dual-role evidence-capture script** (the `agents.command.*` → `agents.result.*` round-trip recipe): `specialist-agent/scripts/nats-evidence-runbook.md` + `specialist-agent/scripts/capture-nats-roundtrip.sh`
- **Forge dispatch path** (the orthogonal autobuild path; not used here): `jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` (currently blocked by Gap PEBR-WIREUP per `jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md` — does NOT block this demo).
- **dispatch_by_capability tool surface**: `jarvis/src/jarvis/tools/dispatch.py:351-410`
- **Architect manifest** (`architect_align` tool definition): `specialist-agent/src/specialist_agent/adapters/manifest.py:112-141`
- **Architect role command router**: `specialist-agent/src/specialist_agent/adapters/command_router.py` + `specialist-agent/src/specialist_agent/roles/architect/__init__.py` (the `"architect_align": "align"` mapping)
- **AlignmentJudgment Pydantic schema**: search specialist-agent for `class AlignmentJudgment`
- **Live capability KV watch** (proves `capabilities_mode: live` resolves the stub-vs-live discrepancy): `jarvis/src/jarvis/infrastructure/capabilities_registry.py:115-326`
