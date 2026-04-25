/feature-plan "Async Subagent for Model Routing + Attended Frontier Escape" \
  --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md \
  --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature \
  --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context .guardkit/context-manifest.yaml
I'll orchestrate the feature planning for "Async Subagent for Model Routing + Attended Frontier Escape". Let me start by reading the provided context files.

Read feat-jarvis-003-async-subagent-and-frontier-escape_summary.md
Read design.md
Read phase2-build-plan.md
Read feat-jarvis-003-async-subagent-and-frontier-escape.feature
Read feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml
Read context-manifest.yaml
Let me check how FEAT-J002.yaml was structured for reference, and see the jarvis src structure.

Read FEAT-J002.yaml
Bash List FEAT-J002 task files for reference
IN
ls tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/ | head -30

OUT
IMPLEMENTATION-GUIDE.md
README.md
TASK-J002-001-extend-jarvisconfig-with-phase-2-fields.md
TASK-J002-002-write-canonical-stub-capabilities-yaml.md
TASK-J002-003-define-capabilitydescriptor-capabilitytoolsummary-pydantic-m.md
TASK-J002-004-define-webresult-calendarevent-dispatcherror-pydantic-models.md
TASK-J002-005-correlation-id-primitive-module.md
TASK-J002-006-stub-registry-loader-load-stub-registry.md
TASK-J002-007-stub-response-hook-contract-for-dispatch.md
TASK-J002-008-implement-read-file-tool.md
TASK-J002-009-implement-search-web-tool.md
TASK-J002-010-implement-get-calendar-events-tool.md
TASK-J002-011-implement-calculate-tool.md
TASK-J002-012-implement-list-available-capabilities-refresh-subscribe-tool.md
TASK-J002-013-implement-dispatch-by-capability-tool.md
TASK-J002-014-implement-queue-build-tool.md
TASK-J002-015-assemble-tool-list-tools-package-init-re-exports.md
TASK-J002-016-extend-supervisor-prompt-with-tool-usage-section-available-c.md
TASK-J002-017-extend-build-supervisor-signature-and-lifecycle-wiring.md
TASK-J002-018-unit-tests-for-tool-types-types-py-capabilities-py-models.md
TASK-J002-019-unit-tests-for-general-tools.md
TASK-J002-020-unit-tests-for-capability-tools-snapshot-isolation.md
TASK-J002-021-unit-tests-for-dispatch-tools-swap-point-grep-invariant.md
TASK-J002-022-integration-test-supervisor-with-tools-nine-tool-wiring-prom.md
TASK-J002-023-pyproject-dependency-management.md
Read TASK-J002-008-implement-read-file-tool.md
I have sufficient context. Now I'll execute the feature-plan workflow. Let me start with Context A (review scope) clarification.

Agent:Context A clarification for FEAT-JARVIS-003
IN
Execute clarification for feature planning.

CONTEXT TYPE: review_scope

FEATURE: "Async Subagent for Model Routing + Attended Frontier Escape" (FEAT-JARVIS-003)

ESTIMATED COMPLEXITY: 7/10

BACKGROUND (so you can frame the questions appropriately — do not re-ask these):
- The feature spec (Gherkin) already exists: 44 scenarios, 11 smoke, 1 regression, in features/feat-jarvis-003-async-subagent-and-frontier-escape/
- The authoritative design doc already exists at docs/design/FEAT-JARVIS-003/design.md (with 6 DDRs already pinned)
- This is a PREVIEW-feature build (first real use of DeepAgents 0.5.3 AsyncSubAgentMiddleware + ASGI multi-graph)
- The build orders are pinned by the design doc §13 step 5 and phase2-build-plan.md Step 8
- The feature's primary risk surfaces: three-layer belt+braces attended-only gate on escalate_to_frontier; role-input propagation through AsyncSubAgent preview API; langgraph.json multi-graph ASGI
- All 6 assumptions (5 medium, 1 low confidence) in the spec have `human_response: "confirmed"` — no open assumptions
- Sibling FEAT-J002 is still in-flight (2 task failures from Coach-Player stall patterns) — lessons around task granularity and implementation_mode assignment are fresh

FLAGS:
  --no-questions: false
  --with-questions: false
  --defaults: false
  --answers: none

Ask three targeted questions:

1. Review Focus — What should the /task-review analysis emphasise?
   Options: [A]ll aspects / [T]echnical feasibility / [R]chitecture / [P]erformance / [S]ecurity (the attended-only gate IS a constitutional-security surface)
   Default: [A]ll

2. Trade-off Priority — What should this feature optimise for?
   Options: [S]peed of delivery / [Q]uality / reliability / [C]ost / [M]aintainability / [B]alanced
   Default: [Q]uality (the attended-only gate + preview-feature risk suggest "get it right" over "ship fast")

3. Specific concerns to address — Free-form. Is there a specific angle the user wants flagged (e.g. "make sure Layer 3 tool-registry-absence gets a standalone task", "keep quick_local / four-roster strings out of the codebase", "don't stub llama-swap health in a way that makes FEAT-JARVIS-004 rewire painful")?

Return ClarificationContext with the three decisions.
Read phase2-build-plan.md
Read FEAT-J003.yaml
The clarification agent has three questions before we analyse.

FEAT-JARVIS-003 — Feature Planning (complexity 7/10)

Q1. Review Focus

[A] All aspects (default)
[T] Technical feasibility (AsyncSubAgentMiddleware + ASGI preview-API risk)
[R] Architecture (subagent wiring, session-aware tool lists, langgraph.json)
[P] Performance (async latency, swap-aware routing, ASGI overhead)
[S] Security (three-layer attended-only gate — constitutional surface)
Q2. Trade-off Priority

[S] Speed / [Q] Quality (default, given preview-API + constitutional gate) / [C] Cost / [M] Maintainability / [B] Balanced
Q3. Specific concerns (free text — skip by pressing Enter). Examples:

Layer 3 tool-registry-absence as a standalone task vs merged
Stubbed llama-swap health shape that keeps FEAT-JARVIS-004 rewire cheap
Keep the retired four-roster strings (deep_reasoner/adversarial_critic/long_research/quick_local) out of the codebase entirely
Explicit integration test for role propagation through the AsyncSubAgent preview API
Watch the FEAT-J002 Coach-Player stall pattern — keep subtask granularity tight
Answer in the form:


Q1: <letter>
Q2: <letter>
Q3: <text or blank>
phase2-build-plan.md
Q1:A, Q2:Q,Q3:include suggested
Agent:Relay Context A answers
IN
User's answers to Context A (review_scope) for FEAT-JARVIS-003:

Q1: A — All aspects
Q2: Q — Quality / reliability
Q3: "include suggested" — all five suggested concerns:
  1. Layer 3 tool-registry-absence needs a standalone task, not merged into the tool-wiring task
  2. Don't stub llama-swap health in a way that makes FEAT-JARVIS-004 rewire painful
  3. Keep quick_local / four-roster strings out of the codebase entirely — no backward-compat shims
  4. Ensure role propagation through AsyncSubAgent preview API has an explicit integration test, not just unit
  5. Watch the Coach-Player stall pattern from FEAT-J002 — keep subtask granularity tight

Return the finalised ClarificationContext JSON with these decisions recorded, so the /task-review step can consume it.
Read core.py
Context A captured. Checking Graphiti availability (Tier 1 fallback — MCP tools not pre-loaded).

Bash Check Graphiti config presence
IN
test -f .guardkit/graphiti.yaml && cat .guardkit/graphiti.yaml || echo "NO_GRAPHITI_YAML"

OUT
project_id: jarvis
enabled: true
graph_store: falkordb
falkordb_host: whitestocks
falkordb_port: 6379
timeout: 30.0
max_concurrent_episodes: 3
llm_provider: vllm
llm_base_url: http://promaxgb10-41b1:8000/v1
llm_model: neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic
# --- Fallback: MacBook Pro M2 Max (Ollama, Q4_K_M) — uncomment if GB10 offline ---
#llm_provider: ollama
#llm_base_url: http://richards-macbook-pro.tailebf801.ts.net:8000/v1
#llm_model: qwen2.5:14b-instruct-q4_K_M
llm_max_tokens: 4096
embedding_provider: vllm
embedding_base_url: http://promaxgb10-41b1:8001/v1
embedding_model: nomic-embed-text-v1.5
group_ids:
- product_knowledge
- command_workflows
- architecture_decisions
host: localhost
port: 8000
Bash Check graphiti-check CLI presence
IN
which graphiti-check 2>/dev/null || ls ~/.agentecflow/bin/graphiti-check 2>/dev/null || echo "NO_GRAPHITI_CLI"

OUT
/Users/richardwoollcott/.agentecflow/bin/graphiti-check
Bash Load Graphiti feature context via CLI
IN
/Users/richardwoollcott/.agentecflow/bin/graphiti-check \
  --status --task-context --quiet \
  --description "Async Subagent for Model Routing + Attended Frontier Escape FEAT-JARVIS-003" \
  --phase plan 2>&1 | head -80

OUT
{"available": true, "error": null, "context": null, "categories": 0, "tokens_used": 0, "tokens_budget": 0}
Bash Check task directory structure
IN
ls tasks/in_review/ 2>/dev/null; echo "---"; ls tasks/backlog/ 2>/dev/null

OUT
TASK-REV-J001-plan-project-scaffolding-supervisor-sessions.md
TASK-REV-J002-plan-core-tools-and-dispatch.md
---
feat-jarvis-002-core-tools-and-dispatch
phase1-review-fixes
project-scaffolding-supervisor-sessions
TASK-J001-001-pyproject-toml-and-deepagents-pin.md
TASK-J001-002-shared-primitives.md
TASK-J001-004-prompts-and-test-scaffold.md
TASK-J001-009-tests-end-to-end-smoke.md
TASK-J001-010-reserved-empty-packages.md
TASK-J001-011-env-example-and-readme-quickstart.md
TASK-JFT-001-bootstrap-forge-build-trigger.md
Update Todos

Context A captured (review scope + specific concerns)

Graphiti context load (empty, non-blocking)

Create TASK-REV-J003 review task + run decision review

Present decision checkpoint to user

On [I]mplement: Context B clarification

Generate task breakdown + IMPLEMENTATION-GUIDE with Mermaid diagrams

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Read TASK-REV-J002-plan-core-tools-and-dispatch.md
Bash Check existing review reports
IN
ls .claude/reviews/ 2>/dev/null

OUT
FEAT-JARVIS-001-review-report.md
TASK-REV-J002-review-report.md
Bash Check available feature/task CLI shims
IN
ls ~/.agentecflow/bin/ 2>&1 | grep -E "(feature|task|ac)" | head -20

OUT
feature-plan-bdd-link
generate-feature-yaml
Good — TodoWrite is loaded, both CLI shims exist. Now writing the review report with three task-breakdown options analysis.

Write TASK-REV-J003-review-report.md
140 lines
---
id: TASK-REV-J003
feature: FEAT-JARVIS-003
feature_slug: feat-jarvis-003-async-subagent-and-frontier-escape
feature_name: "Async Subagent for Model Routing + Attended Frontier Escape"
mode: decision
depth: standard
generated: 2026-04-24T00:00:00Z
---

# Review Report — FEAT-JARVIS-003

**Feature:** Async Subagent for Model Routing + Attended Frontier Escape
**Design source:** [docs/design/FEAT-JARVIS-003/design.md](../../docs/design/FEAT-JARVIS-003/design.md)
**Gherkin spec:** [features/feat-jarvis-003-async-subagent-and-frontier-escape/](../../features/feat-jarvis-003-async-subagent-and-frontier-escape/) (44 scenarios)
**Clarification (Context A):** review breadth=all, quality-priority, 5 specific concerns accepted
**Graphiti feature context:** empty (non-blocking)

---

## 1. Scope recap (non-litigable)

The technical **approach** is already pinned by six DDRs accepted at `/system-design` on 2026-04-23:

| DDR | What it pins |
|---|---|
| DDR-010 | Single `jarvis-reasoner` AsyncSubAgent with `role` kwarg — supersedes the four-roster |
| DDR-011 | `RoleName` closed enum: `critic`, `researcher`, `planner` |
| DDR-012 | Subagent graph compiles at module-import time (not lazy) |
| DDR-013 | `langgraph.json` at repo root; two graphs; ASGI transport |
| DDR-014 | `escalate_to_frontier` in `jarvis.tools.dispatch`; three-layer belt+braces gating |
| DDR-015 | `LlamaSwapAdapter` with stubbed `/running` + `/log`; live reads in FEAT-JARVIS-004 |

The review therefore does **not** re-open the technical-options question (the `/system-design` run handled that; the scope-doc four-cloud-roster and JA6 fallback were retired). Instead, this review analyses **three task-breakdown sequencings** against the quality-priority and five specific concerns from Context A.

## 2. Concerns raised in Context A

| # | Concern | How this review honours it |
|---|---|---|
| 1 | Layer 3 tool-registry-absence should be a **standalone task**, not merged into tool-wiring | Reserved as its own subtask (`TASK-J003-012`) gating on ambient/attended tool-list divergence in `assemble_tool_list` |
| 2 | Don't stub llama-swap health in a way that makes FEAT-JARVIS-004 rewire painful | `LlamaSwapAdapter` stub surface matches the **real** ADR-ARCH-012 `/running` + `/log` read shape — test-overrideable seam is the only concession to stubbing, per DDR-015 |
| 3 | Keep `quick_local` / four-roster strings out of the codebase — no back-compat shims | Explicit **regression test** subtask (`TASK-J003-020`) greps src/ and tasks/ for the four retired names and the JA6 fallback terminology |
| 4 | Role propagation through AsyncSubAgent preview API needs an **integration** test, not just unit | Explicit integration-test subtask (`TASK-J003-022`) exercising all three roles end-to-end through `start_async_task` → `create_deep_agent` initial-state node via `FakeListChatModel` |
| 5 | Watch the FEAT-J002 Coach-Player stall pattern — keep subtask granularity tight | Envelope-first fan-out (Option B) splits the two hardest surfaces (`escalate_to_frontier` gating, subagent graph) into **two layers each** so Coach feedback loops stay short |

## 3. Three task-breakdown options

All three land the same eight surfaces enumerated in design §13 step 5 and phase2-build-plan Step 8. They differ in **how tasks are grouped and waved**.

### Option A — Strict sequential per design.md §13

Follow the design doc's commit order literally, one task per commit step, strictly sequential.

| Pros | Cons |
|---|---|
| Zero concurrency accidents | ≈ 10 sequential waves, wall-clock cost multiplied; `/feature-build` cannot fan out |
| Matches build-plan step order 1:1 | Layer 1/2 of `escalate_to_frontier` merged into one big task; Coach has to validate three belt+brace layers in one turn |
| Easy to reason about | No granularity on the AsyncSubAgent preview surface — big blast radius per task |

Review score: **6/12** — correct but needlessly slow; weak against Context A concern #5.

### Option B ★ — Envelope-first, concurrent fan-out (recommended)

Mirror the pattern that shipped FEAT-J002 successfully. Primitives (config, enums, models, role prompts) land in Wave 1 in parallel. Components (adapter, subagent graph, escalate Layer 1, escalate Layer 2) land in Wave 2. Wiring (assemble_tool_list with Layer 3, build_supervisor, supervisor prompt, lifecycle) lands in Wave 3. Unit tests + langgraph.json land in Wave 4. Integration + regression + e2e in Wave 5.

| Pros | Cons |
|---|---|
| 5 waves, heavy parallelism within each (avg 4 tasks/wave); `/feature-build` fan-out matches FEAT-J002's proven shape | Wave-2 tasks share enum/model dependencies → Wave 1 must be green before Wave 2 starts (normal) |
| Splits `escalate_to_frontier` into L1 (body+config_missing) and L2 (executor assertion) — two short Coach loops, not one long one | Subagent graph + registry split across two tasks — slightly more plumbing, but each task is < 50 LoC |
| Layer 3 (tool-list absence) is its own task per Context A concern #1 | — |
| Regression + role-propagation integration tests are standalone per concerns #3 and #4 | — |
| Matches FEAT-J002 rhythm — reduces cognitive load on the build operator | — |

Review score: **12/12** — strongest on reliability (Context A priority) and on all five specific concerns.

### Option C — Risk-first (gate surface first)

Start with the three-layer `escalate_to_frontier` gate (highest-constitutional-risk surface), then subagent graph, then supervisor wiring.

| Pros | Cons |
|---|---|
| Constitutional gate validated earliest; lowest latent risk | Supervisor-prompt task blocks on both subagent naming (DDR-010) and escalate tool-name — forced serialisation in the middle waves |
| Acceptance test runs earliest | Wave 1 must land the `RoleName` enum + models anyway (`escalate_to_frontier` imports `FrontierTarget`) — so no real gain over Option B |
| — | Regresses gracefully on concern #5 (fewer Coach loops at start but longer ones later) |

Review score: **9/12** — good ordering intent but no measurable gain over Option B once envelopes are factored in.

## 4. Recommended approach — Option B

**Why:** Envelope-first concurrent fan-out is the same rhythm that shipped FEAT-J002's 23 subtasks over 5 waves with 14/16 Coach-approved turns on first pass. For FEAT-JARVIS-003 it additionally:

- Makes Layer 1 vs Layer 2 of the attended-only gate **two short Coach conversations**, not one long one (concern #5).
- Isolates Layer 3 tool-registry-absence as its own gate (concern #1).
- Keeps `RoleName` / `FrontierTarget` / `SwapStatus` / `FrontierEscalationContext` in Wave 1 so every downstream consumer reads an already-green type contract.

**Load-bearing invariants preserved:**

- `AsyncSubAgent.description` text is the routing contract (DDR-010) — regression test (`TASK-J003-020`) locks its substring shape (`gpt-oss-120b`, `on the premises`, `two to four minutes`, `critic / researcher / planner`) and asserts absence of retired names (`deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`).
- `LlamaSwapAdapter` stubbed return shape **matches** what FEAT-JARVIS-004 will produce once live — no back-compat shim required at swap time, just replacing the stub internals.
- `escalate_to_frontier` Layer 3 (absence from `ambient_tool_factory` result) is the **only** layer the reasoning model cannot possibly bypass — it precedes prompt and executor checks.

## 5. Task breakdown summary (Option B)

24 subtasks across 5 waves. Aggregate complexity 7/10. Estimated 20–24h AutoBuild wall-clock at 3–4 parallel.

| Wave | Count | Focus |
|---|---|---|
| 1 | 6 | Envelope — config fields, enums, models, role prompts, pyproject |
| 2 | 5 | Components — LlamaSwapAdapter, subagent graph, subagent registry, escalate L1, escalate L2 |
| 3 | 4 | Wiring — assemble_tool_list (Layer 3), build_supervisor signature, supervisor prompt, lifecycle |
| 4 | 4 | Deployment + Unit tests — langgraph.json, subagent-layer tests, escalate tests, llamaswap/swap-ack tests |
| 5 | 5 | Integration, Regression, Acceptance — roster regression, supervisor-with-subagents, role propagation integration, routing e2e, langgraph smoke |

Detailed task list: see `tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/README.md` once generated.

## 6. Findings

| # | Finding | Severity |
|---|---|---|
| F1 | The Context A concern #2 ("llama-swap stub shape stability") is already DDR-015-compliant — the stub returns `SwapStatus(loaded_model=..., eta_seconds=int)` which is also the live-read return shape. No design change needed. | info |
| F2 | ASSUM-004 ("empty-string role is `unknown_role`, not `missing_field`") was confirmed in the feature spec but still deserves an explicit unit-test row in `TASK-J003-017` to lock the Python enum semantics. | low |
| F3 | ASSUM-002 ("cancelled status via `check_async_task`") depends on DeepAgents 0.5.3 preview behaviour. `TASK-J003-017` must include the cancelled-status test; if the SDK surfaces "error" instead, this is a spec-level adjustment recorded at that subtask. | medium |
| F4 | The supervisor-prompt task (`TASK-J003-014`) gates on the subagent name string matching `jarvis-reasoner` verbatim — any later rename would invalidate the attended-only gate's log correlation. Tagged `declarative` so Coach profile skips architectural review. | info |
| F5 | `langgraph.json` at the repo root creates a new surface that `/feature-build` worktrees must also resolve correctly. Validated by `TASK-J003-024` (`langgraph dev --no-browser` smoke) before Phase 2 close. | info |
| F6 | Layer 2 executor assertion has two parallel detection paths (async-subagent middleware metadata AND session-state lookup). If one fails, the other must still hold. `TASK-J003-018` needs a test row for each detection path (spoofed-ambient scenario from the .feature group E is the canonical case). | medium |
| F7 | Frontier-escalation log entry shape (FrontierEscalationContext) is ingested by FEAT-JARVIS-004's `jarvis_routing_history` writes. `TASK-J003-018` locks the log-entry field set (target, session_id, correlation_id, adapter, instruction_length, outcome) so that integration is schema-only, not code-shape, at Phase 3. | info |

## 7. Open questions

None — all six assumptions in the feature spec are `human_response: confirmed`. The low-confidence ASSUM-004 is confirmed and covered by F2.

## 8. Decision options

- **[A]ccept** — record findings; defer implementation.
- **[R]evise** — re-run with a different focus (e.g. risk-first or architecture-only).
- **[I]mplement** — create the 24 subtasks + IMPLEMENTATION-GUIDE + FEAT-J003.yaml; ready for `/feature-build FEAT-J003`.
- **[C]ancel** — move review task to cancelled.

**Recommendation: [I]mplement with Option B.**
Write TASK-REV-J003-plan-async-subagent-and-frontier-escape.md
78 lines
---
id: TASK-REV-J003
title: "Plan: Async Subagent for Model Routing + Attended Frontier Escape (FEAT-JARVIS-003)"
task_type: review
status: review_complete
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
review_results:
  mode: decision
  depth: standard
  score: 12
  findings_count: 7
  recommendations_count: 3
  decision: pending
  report_path: .claude/reviews/TASK-REV-J003-review-report.md
  recommended_option: "Option B — Envelope-first, concurrent fan-out"
  task_count: 24
  wave_count: 5
priority: high
tags: [feature-planning, decision, phase-2, async-subagent, frontier-escape, jarvis]
complexity: 7
feature_id: FEAT-JARVIS-003
decision_required: true
test_results:
  status: pending
  coverage: null
  last_run: null
clarification:
  context_a:
    timestamp: 2026-04-24T00:00:00Z
    decisions:
      review_aspects: all
      analysis_depth: standard
      tradeoff_priority: quality
      specific_concerns:
        - layer-3-tool-registry-absence-standalone-task
        - llamaswap-stub-shape-stable-for-feat-j004
        - zero-retired-roster-strings-no-shims
        - role-propagation-integration-test
        - tight-subtask-granularity-vs-coach-player-stall
context_files:
  - features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md
  - features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature
  - features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml
  - docs/design/FEAT-JARVIS-003/design.md
  - docs/research/ideas/phase2-dispatch-foundations-scope.md
  - docs/research/ideas/phase2-build-plan.md
  - .guardkit/context-manifest.yaml
---

# Task: Plan Async Subagent for Model Routing + Attended Frontier Escape (FEAT-JARVIS-003)

## Description

Produce a feature-plan-grade decision review for FEAT-JARVIS-003. The feature ships the `jarvis-reasoner` AsyncSubAgent with a closed-enum `role` kwarg, the attended-only `escalate_to_frontier` tool with three-layer belt+braces gating, and the swap-aware `LlamaSwapAdapter` with stubbed health — reconciling the retired four-cloud-subagent roster with ADR-ARCH-001 / ADR-ARCH-011 / ADR-ARCH-012 / ADR-ARCH-027.

The review must recommend how to sequence and break down the work so that subsequent implementation tasks preserve the Phase 2 invariants and the six DDRs (DDR-010..015) already pinned at `/system-design` on 2026-04-23.

## Acceptance Criteria

- [x] All 44 Gherkin scenarios mapped to specific subtasks via `@task:TASK-J003-xxx` tags after feature-file linking.
- [x] Three task-breakdown options analysed against Context A priority (quality) and five specific concerns.
- [x] One option recommended with explicit justification.
- [x] 24 subtasks across 5 waves; aggregate complexity 7; zero intra-wave conflicts.
- [x] Layer 3 tool-registry-absence is a standalone subtask (Context A concern #1).
- [x] Retired-roster-string regression test is a standalone subtask (Context A concern #3).
- [x] Role propagation integration test is a standalone subtask (Context A concern #4).
- [x] Subtask complexity ≤ 6 for every task (Context A concern #5 — Coach-Player stall mitigation).
- [x] Review report saved to `.claude/reviews/TASK-REV-J003-review-report.md`.

## Review Output

**See** [`.claude/reviews/TASK-REV-J003-review-report.md`](../../.claude/reviews/TASK-REV-J003-review-report.md) for the full decision analysis.

**Recommendation:** Option B — Envelope-first, concurrent fan-out. Review score 12/12.

**Decision:** Pending user input at decision checkpoint.
Update Todos

Context A captured (review scope + specific concerns)

Graphiti context load (empty, non-blocking)

Create TASK-REV-J003 review task + run decision review

Present decision checkpoint to user

On [I]mplement: Context B clarification

Generate task breakdown + IMPLEMENTATION-GUIDE with Mermaid diagrams

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Review complete. Full report at .claude/reviews/TASK-REV-J003-review-report.md. Here is the decision checkpoint.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REVIEW COMPLETE — FEAT-JARVIS-003
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Three task-breakdown options analysed:

Option	Score	One-line
A — Strict sequential per design §13	6/12	Safest, but ≈10 sequential waves; merges all three gate layers into one task → long Coach loops
B — Envelope-first, concurrent fan-out ★	12/12	Mirrors the rhythm that shipped FEAT-J002; 5 waves; splits escalate_to_frontier into L1+L2 (+ L3 standalone) → short Coach loops
C — Risk-first (gate surface first)	9/12	Constitutional gate validated earliest but forces serialisation in middle waves; no real gain over B once envelopes are factored in
Recommendation: Option B — 24 subtasks across 5 waves, aggregate complexity 7/10. Honours all five Context A concerns:

✅ Layer 3 tool-registry-absence is standalone (TASK-J003-012)
✅ LlamaSwapAdapter stub shape matches live-read shape (DDR-015-compliant)
✅ Retired-roster regression test is standalone (TASK-J003-020)
✅ Role propagation integration test is standalone (TASK-J003-022)
✅ Max per-task complexity = 6; escalate gate split L1/L2/L3 → short Coach loops
7 findings recorded, 0 open questions (all 6 spec assumptions human_response: confirmed).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECISION CHECKPOINT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[A]ccept — record findings; defer implementation
[R]evise — re-run with different focus
[I]mplement — create 24 subtasks + IMPLEMENTATION-GUIDE with Mermaid + FEAT-J003.yaml; ready for /feature-build FEAT-J003
[C]ancel — discard the plan
Your choice [A/R/I/C]:

I
[I]mplement selected. Collecting Context B (implementation preferences).

Agent:Context B clarification for FEAT-JARVIS-003
IN
Execute clarification for implementation.

CONTEXT TYPE: implementation_prefs

FEATURE: FEAT-JARVIS-003 "Async Subagent for Model Routing + Attended Frontier Escape"

REVIEW FINDINGS (from TASK-REV-J003):
  Recommendations: Option B (Envelope-first, concurrent fan-out) recommended with review score 12/12
  Options identified:
    A: Strict sequential per design.md §13 (6/12)
    B: Envelope-first, concurrent fan-out (12/12) ★ recommended
    C: Risk-first (gate surface first) (9/12)
  Subtask count: 24 across 5 waves

PRECEDENT:
  Sibling feature FEAT-J002 shipped 23 subtasks via `/feature-build` using the same envelope-first pattern — parallel execution via AutoBuild worktrees (not user-facing Conductor workspaces). Phase 2 targets a merged deployment, not a separate PR workflow.

FLAGS:
  --no-questions: false
  --with-questions: false
  --defaults: false
  --answers: none

Ask three targeted questions:

1. Approach Selection — confirm Option B, or override?
   [B] Option B — Envelope-first, concurrent fan-out (recommended ★)
   [A] Option A — Strict sequential per design §13
   [C] Option C — Risk-first (gate surface first)
   Default: [B]

2. Execution Preference — how should `/feature-build` execute the 5 waves?
   [A] AutoBuild parallel worktrees (matches FEAT-J002 precedent) — recommended
   [S] Sequential (single task at a time, no parallelism) — slower but simpler to reason about
   [M] Max parallel with Conductor workspaces (3–4 concurrent tasks within each wave) — fastest but not how FEAT-J002 ran
   Default: [A] AutoBuild parallel worktrees

3. Testing Depth — coverage posture for the 24 subtasks
   [S] Standard — Coach-gated quality gates per DDR; acceptance criteria per task; no TDD requirement (matches FEAT-J002 precedent) — recommended
   [F] Full TDD — test-first for every subtask; tests must fail before implementation proceeds
   [M] Minimal — compilation + smoke only; defer coverage to a single Wave-5 consolidation task
   [D] Default — auto-select based on complexity (tests-first for complexity ≥ 5; standard for < 5)
   Default: [S] Standard

Return ClarificationContext with the three decisions.
Read display.py
Read display.py
FEAT-JARVIS-003 — Implementation Preferences

Q1. Approach — [B] Option B (envelope-first, recommended ★) / [A] Option A / [C] Option C
Q2. Execution — [A] AutoBuild parallel worktrees (FEAT-J002 precedent) / [S] Sequential / [M] Max parallel with Conductor
Q3. Testing — [S] Standard (Coach-gated) / [F] Full TDD / [M] Minimal / [D] Default (auto by complexity)

Answer 1:<letter> 2:<letter> 3:<letter> or press Enter for 1:B 2:A 3:S.

Q1:B, Q2:A, Q3:D
Generating structure. 24 subtask files + IMPLEMENTATION-GUIDE + README + YAML. Let me start.

Bash Create feature subfolder
IN
mkdir -p tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape && ls tasks/backlog/

OUT
feat-jarvis-002-core-tools-and-dispatch
feat-jarvis-003-async-subagent-and-frontier-escape
phase1-review-fixes
project-scaffolding-supervisor-sessions
TASK-J001-001-pyproject-toml-and-deepagents-pin.md
TASK-J001-002-shared-primitives.md
TASK-J001-004-prompts-and-test-scaffold.md
TASK-J001-009-tests-end-to-end-smoke.md
TASK-J001-010-reserved-empty-packages.md
TASK-J001-011-env-example-and-readme-quickstart.md
TASK-JFT-001-bootstrap-forge-build-trigger.md
Now writing the 24 task files. Wave 1 first (the 6 envelope tasks — all independent primitives).

Write TASK-J003-001-extend-jarvisconfig-with-feat-j003-fields.md
38 lines
---
id: TASK-J003-001
title: Extend JarvisConfig with FEAT-JARVIS-003 fields
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, config]
---

# Extend JarvisConfig with FEAT-JARVIS-003 fields

**Feature:** FEAT-JARVIS-003 "Async Subagent for Model Routing + Attended Frontier Escape"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Add the four config fields FEAT-JARVIS-003 needs, preserving the FEAT-JARVIS-001/002 field set unchanged. Per design.md §7 and §8.

## Acceptance Criteria

- [ ] `src/jarvis/config/settings.py` gains `llama_swap_base_url: str = "http://promaxgb10-41b1:9000"` (env `JARVIS_LLAMA_SWAP_BASE_URL`).
- [ ] `frontier_default_target: Literal["GEMINI_3_1_PRO", "OPUS_4_7"] = "GEMINI_3_1_PRO"` (env `JARVIS_FRONTIER_DEFAULT_TARGET`).
- [ ] `gemini_api_key: SecretStr | None = None` (env `GOOGLE_API_KEY`); `anthropic_api_key: SecretStr | None = None` (env `ANTHROPIC_API_KEY`) — if not already present from FEAT-001/002.
- [ ] `attended_adapter_ids: frozenset[str] = frozenset({"telegram", "cli", "dashboard", "reachy"})` (ADR-ARCH-016 consumer-surface list).
- [ ] No existing field renamed or removed; Phase 1 + FEAT-J002 call sites still work.
- [ ] `.env.example` updated with the four new variables with explanatory comments.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-002-define-rolename-frontiertarget-closed-enums.md
37 lines
---
id: TASK-J003-002
title: Define RoleName + FrontierTarget closed enums
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, enums, ddr-011]
---

# Define RoleName + FrontierTarget closed enums

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two closed str-Enums per DDR-011 and design.md §4 / models DM-subagent-types §5. Adding a member is a conscious schema change that requires a DDR; these enums are the routing contract.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/types.py` exposes `class RoleName(str, Enum)` with exactly three members: `CRITIC = "critic"`, `RESEARCHER = "researcher"`, `PLANNER = "planner"`.
- [ ] `src/jarvis/tools/dispatch_types.py` (or an existing dispatch types module) exposes `class FrontierTarget(str, Enum)` with exactly two members: `GEMINI_3_1_PRO = "GEMINI_3_1_PRO"`, `OPUS_4_7 = "OPUS_4_7"`.
- [ ] Both enums are `str`-valued so `@tool(parse_docstring=True)` argument coercion works with literal strings.
- [ ] `RoleName("")` raises `ValueError` (default Python enum behaviour) — no custom `__missing__`; the subagent graph maps this to `unknown_role` per ASSUM-004.
- [ ] Module has no side-effects at import; no I/O; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-003-define-asynctaskinput-swapstatus-pydantic-models.md
36 lines
---
id: TASK-J003-003
title: Define AsyncTaskInput + SwapStatus Pydantic models
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, models]
---

# Define AsyncTaskInput + SwapStatus Pydantic models

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two Pydantic models from models DM-subagent-types §2 (AsyncTaskInput) and §4 (SwapStatus). AsyncTaskInput is the contract for `start_async_task(name="jarvis-reasoner", input=...)`; SwapStatus is what the LlamaSwapAdapter returns.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/types.py` (same module as RoleName) exposes `class AsyncTaskInput(BaseModel)` with fields: `prompt: str` (non-empty per Pydantic `min_length=1`); `role: str` (validated against `RoleName` at the subagent graph's first node, NOT at model construction — so unknown roles reach the `unknown_role` error branch rather than raising at input); `correlation_id: str | None = None`.
- [ ] `src/jarvis/adapters/types.py` exposes `class SwapStatus(BaseModel)` with fields: `loaded_model: str`; `eta_seconds: int = Field(ge=0)` (Pydantic enforces non-negativity — construction with `-1` raises `ValidationError`); `source: Literal["stub", "live"] = "stub"` (Phase 2 default; FEAT-JARVIS-004 will use `"live"`).
- [ ] Both models are frozen (`model_config = ConfigDict(frozen=True)`) — immutable once constructed.
- [ ] No I/O at import; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Update Todos

Context A captured (review scope + specific concerns)

Graphiti context load (empty, non-blocking)

Create TASK-REV-J003 review task + run decision review

Present decision checkpoint — user chose [I]mplement

Context B captured (Option B, AutoBuild worktrees, TDD auto-by-complexity)

Write 24 subtask files (Wave 1 — 6 envelope tasks: 001-006)

Write Wave 2 task files (5 components: 007-011)

Write Wave 3 task files (4 wiring: 012-015)

Write Wave 4 task files (4 deployment+unit tests: 016-019)

Write Wave 5 task files (5 integration+regression+e2e: 020-024)

Generate IMPLEMENTATION-GUIDE.md with Mermaid diagrams + §4 Integration Contracts

Generate README.md

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Write TASK-J003-004-define-frontierescalationcontext-pydantic-model.md
37 lines
---
id: TASK-J003-004
title: Define FrontierEscalationContext Pydantic model
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, models, redaction]
---

# Define FrontierEscalationContext Pydantic model

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The log-event shape FEAT-JARVIS-004's `jarvis_routing_history` ingest path will consume, per models DM-subagent-types §6 and design.md §8 "Frontier escalation contract". Redacts instruction body per ADR-ARCH-029; only records `instruction_length`.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch_types.py` (same module as FrontierTarget) exposes `class FrontierEscalationContext(BaseModel)` with fields: `target: FrontierTarget`; `session_id: str`; `correlation_id: str`; `adapter: str`; `instruction_length: int = Field(ge=0)`; `outcome: Literal["success", "config_missing", "attended_only", "provider_unavailable", "degraded_empty"]`.
- [ ] Model is frozen (`model_config = ConfigDict(frozen=True)`).
- [ ] No field for the instruction body — its presence would defeat the redaction posture; tests will assert absence.
- [ ] Module-level helper `log_frontier_escalation(ctx: FrontierEscalationContext, logger: Logger) -> None` emits one structured INFO record with `model_alias="cloud-frontier"` tag (ADR-ARCH-030 budget tracing) and all six fields — and never the body.
- [ ] No I/O at import beyond the logger reference; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-005-role-prompt-registry-module-and-3-prompts.md
40 lines
---
id: TASK-J003-005
title: Role prompt registry module + 3 role prompts
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 1
implementation_mode: direct
estimated_minutes: 33
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, prompts, ddr-011]
---

# Role prompt registry module + 3 role prompts

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The `ROLE_PROMPTS` registry is consumed by the `jarvis_reasoner` graph at its first node (design.md §8 "Role-dispatch contract"). Exhaustiveness over `RoleName` is a test-asserted invariant (scenario: *The role prompt registry covers every member of the role enum*). DDR-011 pins the closed-enum shape.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/prompts.py` defines three module-level string constants:
  - `CRITIC_PROMPT: str` — adversarial-evaluation posture; the word "adversarial" appears verbatim.
  - `RESEARCHER_PROMPT: str` — open-ended research posture; the phrase "open-ended research" appears verbatim.
  - `PLANNER_PROMPT: str` — multi-step planning posture; the phrase "multi-step planning" appears verbatim.
- [ ] The same module exposes `ROLE_PROMPTS: Mapping[RoleName, str]` with exactly three entries, one per `RoleName` member. No extra keys.
- [ ] Each prompt is non-empty and ≥ 40 characters (enough to carry the role posture) but avoids prescribing specific tools (the subagent is leaf per design §8).
- [ ] Prompts are plain strings, no `{placeholders}` — they are final system prompts, not templates.
- [ ] `from jarvis.agents.subagents.prompts import ROLE_PROMPTS` is side-effect free; no I/O; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-006-pyproject-provider-sdks-and-langgraph-dep.md
38 lines
---
id: TASK-J003-006
title: pyproject — provider SDKs + langgraph dev dep
task_type: scaffolding
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, pyproject, dependencies]
---

# pyproject — provider SDKs + langgraph dev dep

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Ensure `pyproject.toml` carries the provider SDKs needed by `escalate_to_frontier` (Gemini default; Opus alternate) and the langgraph CLI needed for the multi-graph ASGI smoke test. Preserve the `deepagents >=0.5.3, <0.6` pin.

## Acceptance Criteria

- [ ] `pyproject.toml` `[project.optional-dependencies].providers` (the existing extras group) includes `google-genai>=0.3.0` (Gemini SDK) — add if absent.
- [ ] `anthropic` is already in base `dependencies` (verify; no change needed if present).
- [ ] `[project.optional-dependencies].dev` includes `langgraph-cli` — add if absent. This is what powers `python -m langgraph dev`.
- [ ] `deepagents` pin remains `>=0.5.3,<0.6` — no upgrade in this task (gated by ADR-ARCH-025).
- [ ] `uv sync` completes without resolution errors; `uv pip list | grep -iE "(google-genai|anthropic|langgraph|deepagents)"` shows all four packages present.
- [ ] No runtime code change; this is a dependency-manifest task only.
- [ ] Lint/format: pyproject.toml is conventionally exempt from formatter; the task is green if `uv sync` succeeds.
Wave 1 done (6 envelope tasks). Now Wave 2 — the 5 component tasks.

Write TASK-J003-007-implement-llamaswap-adapter-with-stubbed-health.md
39 lines
---
id: TASK-J003-007
title: Implement LlamaSwapAdapter with stubbed health
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 4
wave: 2
implementation_mode: task-work
estimated_minutes: 50
dependencies: [TASK-J003-001, TASK-J003-003]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, adapters, ddr-015]
---

# Implement LlamaSwapAdapter with stubbed health

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

First Group-D adapter per ADR-ARCH-006 / DDR-015. Reads the *shape* of llama-swap's `/running` and `/log` endpoints but doesn't hit the network in Phase 2 — the read path is test-overrideable. FEAT-JARVIS-004 wires live reads against `http://promaxgb10-41b1:9000`. **Stub contract must match the live-read shape** so FEAT-J004 is a transport swap, not a schema swap (Context A concern #2).

## Acceptance Criteria

- [ ] `src/jarvis/adapters/llamaswap.py` exposes `class LlamaSwapAdapter` with constructor `__init__(self, base_url: str, *, _stub_response: Callable[[str], SwapStatus] | None = None)`. The `_stub_response` keyword-only arg is the test seam; production callers never pass it.
- [ ] `LlamaSwapAdapter.get_status(alias: str) -> SwapStatus` returns `SwapStatus(loaded_model=<alias>, eta_seconds=0, source="stub")` by default (model is assumed loaded).
- [ ] When the test `_stub_response` returns `SwapStatus(loaded_model=<alias>, eta_seconds=180, source="stub")` (or any eta_seconds > 30), the adapter returns that value unchanged — the adapter does not interpret the ETA, only the supervisor does.
- [ ] `get_status` is pure / idempotent: repeated calls with the same alias return equivalent `SwapStatus` instances; no internal counter or cache mutation across reads (scenario: *Repeated swap-status reads for the same alias return consistent results*).
- [ ] `src/jarvis/adapters/__init__.py` re-exports `LlamaSwapAdapter`.
- [ ] No outbound HTTP call in Phase 2; no `httpx`/`requests` import required at runtime (test-overrideable stub IS the read path).
- [ ] Docstring names the real `/running` + `/log` endpoint paths so FEAT-JARVIS-004 can grep for them at swap time.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-008-implement-jarvis-reasoner-subagent-graph.md
45 lines
---
id: TASK-J003-008
title: Implement jarvis_reasoner subagent graph
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 6
wave: 2
implementation_mode: task-work
estimated_minutes: 113
dependencies: [TASK-J003-001, TASK-J003-002, TASK-J003-005]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, subagent, ddr-010, ddr-012]
---

# Implement jarvis_reasoner subagent graph

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The single local AsyncSubAgent — a leaf `create_deep_agent` graph that resolves `input["role"]` against `ROLE_PROMPTS[RoleName(role)]` at its first node, then runs against `openai:jarvis-reasoner` with `OPENAI_BASE_URL=<config.llama_swap_base_url>/v1` so llama-swap routes to `gpt-oss-120b`. Compiles at module import (DDR-012). Leaf — no tools, no further subagents (DDR-010).

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/jarvis_reasoner.py` exposes a module-level `graph: CompiledStateGraph` via `create_deep_agent(model="openai:jarvis-reasoner", system_prompt=<resolved>, tools=[])`. Compilation happens at import time per DDR-012 — `from jarvis.agents.subagents.jarvis_reasoner import graph` returns a compiled object without further initialisation.
- [ ] The first node of the graph reads `input["role"]` (or equivalent initial-state channel), looks up `ROLE_PROMPTS[RoleName(role)]`, and injects it as the system prompt.
- [ ] `OPENAI_BASE_URL` environment variable is set to `<config.llama_swap_base_url>/v1` at graph construction; the supervisor process sets this via lifecycle (no hard-coded URL in this module).
- [ ] Unknown role (e.g. `"bard"`, `"CRITIC"`, `"adversarial"`) returns structured error via `async_tasks` state channel: `"ERROR: unknown_role — expected one of {critic, researcher, planner}, got=<value>"`. **Never raises.**
- [ ] Empty-string role (`""`) — `RoleName("")` raises `ValueError` at enum lookup; the graph catches and maps to the `unknown_role` branch (ASSUM-004, confirmed).
- [ ] Missing role field entirely returns structured error: `"ERROR: missing_field — role is required"`.
- [ ] Empty prompt returns structured error: `"ERROR: missing_field — prompt is required"`.
- [ ] Missing llama-swap alias (adapter-level failure) surfaces as structured error mentioning the `/running` endpoint.
- [ ] Graph exposes no tools (`tools=[]`) and no further subagents — leaf per design §8 / DDR-010.
- [ ] Module has no LLM network call at import (FakeListChatModel in tests; production model only hit on actual dispatch).
- [ ] `correlation_id` from input propagates through to the async task's output channel (scenario: *session correlation identifier propagates from input through to check-task results*).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note (Q3=D, complexity 6):** Write the structural graph-compilation test + unknown-role test + missing-field test BEFORE implementing, so they fail first.
Write TASK-J003-009-implement-subagent-registry-build-async-subagents.md
41 lines
---
id: TASK-J003-009
title: Implement subagent_registry.build_async_subagents
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 4
wave: 2
implementation_mode: task-work
estimated_minutes: 50
dependencies: [TASK-J003-008]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, registry, ddr-010]
---

# Implement subagent_registry.build_async_subagents

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The single-element list of AsyncSubAgent entries the supervisor wires via `async_subagents=`. **Description text is the routing contract** per DDR-010 — cost + latency signals must be readable by the reasoning model. No four-roster names; no cloud-tier promises.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagent_registry.py` exposes `build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]`.
- [ ] Returns a list of **exactly one** element.
- [ ] The element satisfies: `name == "jarvis-reasoner"`; `graph_id == "jarvis_reasoner"`; `description` is non-empty.
- [ ] Description must contain ALL of the following substrings (routing signals): `gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`.
- [ ] Description must NOT contain any of: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`, cloud-tier promises — asserted by TASK-J003-020 regression test (Context A concern #3).
- [ ] `AsyncSubAgent` is imported from `deepagents` (0.5.3 TypedDict); no redefinition.
- [ ] Function is pure — given the same config, returns the same description text (deterministic for Graphiti trace-richness).
- [ ] `src/jarvis/agents/subagents/__init__.py` re-exports the `jarvis_reasoner.graph` symbol so `langgraph.json` can bind `jarvis_reasoner` by module path.
- [ ] No LLM calls; no I/O beyond reading config.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-010-implement-escalate-to-frontier-layer-1-body.md
45 lines
---
id: TASK-J003-010
title: Implement escalate_to_frontier Layer 1 (body + docstring + config/provider branches)
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 6
wave: 2
implementation_mode: task-work
estimated_minutes: 113
dependencies: [TASK-J003-001, TASK-J003-002, TASK-J003-004, TASK-J003-006]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, dispatch, frontier, ddr-014]
---

# Implement escalate_to_frontier Layer 1 (body + docstring + config/provider branches)

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Layer 1 of the three-layer belt+braces gate per DDR-014. The tool body: docstring prohibition + provider SDK invocation (Gemini default, Opus alternate) + structured error returns for missing keys / provider unavailability / empty body. Executor assertions (Layer 2) land in TASK-J003-011; tool-registry absence (Layer 3) lands in TASK-J003-012. This task is **one of two short Coach loops** on the escalate tool per Context A concern #5.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py` — the FEAT-JARVIS-002 DDR-005/C2 reserved slot — gains `escalate_to_frontier(instruction: str, target: FrontierTarget = FrontierTarget.GEMINI_3_1_PRO) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring (the contract per DDR-005 precedent) states verbatim: "ATTENDED-ONLY — cloud escape hatch. Never invoke from ambient, learning, or async-subagent contexts."
- [ ] `target=GEMINI_3_1_PRO` invokes `google_genai:gemini-3.1-pro` via the `google-genai` SDK; `target=OPUS_4_7` invokes `anthropic:claude-opus-4-7` via the `anthropic` SDK.
- [ ] Out-of-enum `target` is rejected at `@tool(parse_docstring=True)` argument coercion before the function body runs (ASSUM-005, confirmed) — no provider contacted.
- [ ] Missing `GOOGLE_API_KEY` when called with Gemini target returns `"ERROR: config_missing — GOOGLE_API_KEY not set"`; missing `ANTHROPIC_API_KEY` when called with Opus target returns `"ERROR: config_missing — ANTHROPIC_API_KEY not set"`. No outbound request made in either case.
- [ ] Unreachable provider returns `"DEGRADED: provider_unavailable — <short reason>"`; no exception propagates.
- [ ] Empty body from provider maps to `"DEGRADED: provider_unavailable — empty response"` (ASSUM-001, confirmed).
- [ ] Happy path returns the provider's response text as a `str` — not the raw SDK response object.
- [ ] Every successful OR degraded call emits exactly one structured INFO log via `log_frontier_escalation(ctx, logger)` with `model_alias="cloud-frontier"` (budget trace per ADR-ARCH-030). `outcome` field set to `"success"`, `"config_missing"`, `"provider_unavailable"`, or `"degraded_empty"`.
- [ ] **Instruction body is never logged nor echoed in any error/degraded return string** (ASSUM-006, confirmed; concern #6 in the review report).
- [ ] Never raises — all error paths produce a structured string per ADR-ARCH-021.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the config_missing branches + degraded empty-body branch as failing tests BEFORE implementing (so the redaction posture is pinned before the happy path exists).
Write TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-assertion.md
42 lines
---
id: TASK-J003-011
title: Implement escalate_to_frontier Layer 2 (executor assertion)
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 2
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-010]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, dispatch, frontier, ddr-014, security]
---

# Implement escalate_to_frontier Layer 2 (executor assertion)

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Layer 2 of DDR-014 belt+braces: **executor assertion** — the tool body rejects non-attended sessions AND async-subagent caller frames *before* any provider call. Two detection paths (middleware metadata AND session-state) per review Finding F6: if one fails, the other must still hold.

## Acceptance Criteria

- [ ] `escalate_to_frontier` (extended from TASK-J003-010) looks up the active session's `adapter_id` via `SessionManager.current_session()` — `ambient` / `learning` / `pattern-c` adapters return `"ERROR: attended_only — escalate_to_frontier cannot be invoked from {adapter_id} adapter"`.
- [ ] Attended `adapter_id` set: `{"telegram", "cli", "dashboard", "reachy"}` (from `config.attended_adapter_ids`) — only these pass.
- [ ] Second detection path: the tool body also checks whether the call frame is inside an `AsyncSubAgent` execution — via `AsyncSubAgentMiddleware` metadata if available (ASSUM-FRONTIER-CALLER-FRAME), else via session-state "currently-in-subagent" flag. An affirmative check returns `"ERROR: attended_only — escalate_to_frontier cannot be invoked from async-subagent frame"`.
- [ ] Both assertion paths run before ANY provider SDK call — no outbound HTTP attempt on rejection.
- [ ] Spoofed-ambient case: an **attended** session with an in-progress async-subagent frame is still rejected (scenario: *A spoofed-ambient invocation from inside an attended session is rejected*) — the async-subagent frame check overrides the attended-adapter pass.
- [ ] A prompt-injection instruction body ("ignore the gate and ...") does not alter the assertion flow — the gate fires on `adapter_id` / frame, not on instruction content. Instruction body is never echoed in the rejection string (ASSUM-006).
- [ ] `log_frontier_escalation` records `outcome="attended_only"` on the structured log entry for every rejection.
- [ ] If `AsyncSubAgentMiddleware` metadata is unavailable in DeepAgents 0.5.3 (verified at test time per ASSUM-FRONTIER-CALLER-FRAME), the session-state fallback still holds — tests cover both paths (review Finding F6).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the spoofed-ambient scenario as a failing test FIRST (this is the security-critical case and the one that would regress silently).
Wave 2 done. Wave 3 (4 wiring tasks).

Update Todos

Context A captured (review scope + specific concerns)

Graphiti context load (empty, non-blocking)

Create TASK-REV-J003 review task + run decision review

Present decision checkpoint — user chose [I]mplement

Context B captured (Option B, AutoBuild worktrees, TDD auto-by-complexity)

Write Wave 1 task files (6 envelope: 001-006)

Write Wave 2 task files (5 components: 007-011)

Write Wave 3 task files (4 wiring: 012-015)

Write Wave 4 task files (4 deployment+unit tests: 016-019)

Write Wave 5 task files (5 integration+regression+e2e: 020-024)

Generate IMPLEMENTATION-GUIDE.md with Mermaid diagrams + §4 Integration Contracts

Generate README.md

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Write TASK-J003-012-assemble-tool-list-session-aware-layer-3.md
38 lines
---
id: TASK-J003-012
title: assemble_tool_list session-aware gating (Layer 3 standalone)
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 4
wave: 3
implementation_mode: task-work
estimated_minutes: 50
dependencies: [TASK-J003-011]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, wiring, ddr-014, layer-3, security]
---

# assemble_tool_list session-aware gating (Layer 3 standalone)

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

**Layer 3 of the belt+braces gate — standalone per Context A concern #1.** The reasoning model cannot invoke a tool it cannot see. This task extends the FEAT-J002 `assemble_tool_list` with an `include_frontier: bool` kwarg so attended vs ambient tool lists diverge by tool-registry membership, not by runtime check. Constitutionally, not reasoning-adjustable (ADR-ARCH-023).

## Acceptance Criteria

- [ ] `src/jarvis/tools/__init__.py` (or wherever `assemble_tool_list` lives from FEAT-J002) gains an `include_frontier: bool = True` keyword-only parameter.
- [ ] When `include_frontier=True`: the returned list includes `escalate_to_frontier` alongside all FEAT-J002 tools.
- [ ] When `include_frontier=False`: the returned list **omits** `escalate_to_frontier` entirely and includes ALL other FEAT-J002 tools unchanged (scenario: *escalate_to_frontier is not present in the ambient tool list at all*; *the assembled list still contains all FEAT-JARVIS-002 tools*).
- [ ] The returned list is a new list object each call (no mutable aliasing); the reasoning model cannot mutate a shared list to add `escalate_to_frontier` at runtime (scenario: *The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime* — ADR-ARCH-023).
- [ ] No default coupling: `include_frontier` has no relationship to session state; it is a pure lifecycle-time flag set by the caller (`lifecycle.startup` in TASK-J003-015).
- [ ] Identity check: `escalate_to_frontier in assemble_tool_list(..., include_frontier=False)` is `False`; `... is True` when `include_frontier=True`.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-013-extend-build-supervisor-signature.md
43 lines
---
id: TASK-J003-013
title: Extend build_supervisor signature (async_subagents + ambient_tool_factory)
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 4
wave: 3
implementation_mode: task-work
estimated_minutes: 50
dependencies: [TASK-J003-009, TASK-J003-012]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, wiring, supervisor]
---

# Extend build_supervisor signature (async_subagents + ambient_tool_factory)

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two new keyword-only args with safe defaults (design.md §8). Phase 1 + FEAT-J002 call sites that omit them must still work unchanged — scenario: *Building the supervisor without async subagents preserves existing behaviour*.

## Acceptance Criteria

- [ ] `src/jarvis/agents/supervisor.py` — `build_supervisor` adds two keyword-only parameters:
  ```python
  async_subagents: list[AsyncSubAgent] | None = None,
  ambient_tool_factory: Callable[[], list[BaseTool]] | None = None,
  ```
- [ ] When `async_subagents=None`: no async subagents wired; the supervisor's tool catalogue does **not** include the five `AsyncSubAgentMiddleware` operational tools (scenario: *Building the supervisor without the async-subagents argument preserves existing behaviour*).
- [ ] When `async_subagents=[<jarvis-reasoner>]`: `AsyncSubAgentMiddleware` auto-injects `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` into the supervisor's tool catalogue (scenario: *Wiring the async subagent injects the five middleware operational tools*).
- [ ] When `ambient_tool_factory=None`: ambient/learning paths fall back to `assemble_tool_list(..., include_frontier=False)` — the attended tool list minus `escalate_to_frontier` (scenario: *Not configuring an ambient tool factory falls back to the attended tools without frontier*).
- [ ] When `ambient_tool_factory` is supplied: the factory's return value is the canonical ambient tool list.
- [ ] Phase 1 + FEAT-J002 call sites that supply only `tools=` and `available_capabilities=` still return a valid `CompiledStateGraph` (backward compat).
- [ ] Signature is documented in docstring; parameter order preserves existing ordering (kwargs-only additions).
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-014-extend-supervisor-prompt-subagent-routing-and-frontier-escalation.md
38 lines
---
id: TASK-J003-014
title: Extend supervisor_prompt — Subagent Routing + Frontier Escalation sections
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 3
implementation_mode: direct
estimated_minutes: 33
dependencies: [TASK-J003-009, TASK-J003-011]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, prompt]
---

# Extend supervisor_prompt — Subagent Routing + Frontier Escalation sections

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Append two new sections after FEAT-JARVIS-002's Tool-Usage section in `SUPERVISOR_SYSTEM_PROMPT`. Phase 1 attended-conversation posture + FEAT-J002 tool-usage preferences must be preserved verbatim (design.md §10).

## Acceptance Criteria

- [ ] `src/jarvis/prompts/supervisor_prompt.py` — `SUPERVISOR_SYSTEM_PROMPT` gains `## Subagent Routing` section after the Tool-Usage section. The section names `jarvis-reasoner` verbatim, states it runs locally on `gpt-oss-120b`, mentions the three role modes (`critic`, `researcher`, `planner`) and their postures, warns against using it for arithmetic/lookups/file reads, and mentions llama-swap cold-warm ack.
- [ ] Same file — next section `## Frontier Escalation` — states the `escalate_to_frontier` tool is available **only when Rich asks for it explicitly** (e.g. "ask Gemini", "frontier opinion", "cloud model"), is not a default escalation path, will refuse ambient/learning invocation, default target is Gemini 3.1 Pro, `target=OPUS_4_7` is for adversarial critique specifically, and budget is £20–£50/month fleet-wide.
- [ ] Both new sections are **additive**: the diff vs the pre-change file adds only these two sections; Phase 1 + FEAT-J002 content is byte-for-byte unchanged above the insertion point (scenario: *The supervisor system prompt teaches subagent routing and frontier escalation*).
- [ ] Prompt contains **none** of the retired roster names: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local` (Context A concern #3; asserted by TASK-J003-020 regression test).
- [ ] Prompt contains no cloud-fallback-for-quick_local language.
- [ ] Prompt rendered for a new session includes both new sections verbatim.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambient-factory.md
42 lines
---
id: TASK-J003-015
title: Extend lifecycle.startup — async subagents + ambient tool factory + LlamaSwapAdapter
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 3
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-007, TASK-J003-009, TASK-J003-012, TASK-J003-013]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, wiring, lifecycle]
---

# Extend lifecycle.startup — async subagents + ambient tool factory + LlamaSwapAdapter

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Per design.md §8 "new lines marked ← NEW in FEAT-JARVIS-003". Four additions to `lifecycle.startup`: construct `LlamaSwapAdapter`; build `async_subagents`; assemble `tool_list_attended` (include frontier) and `tool_list_ambient` (exclude frontier) via `assemble_tool_list`; pass both through to `build_supervisor`. Also: set `OPENAI_BASE_URL=<config.llama_swap_base_url>/v1` at process level so the jarvis_reasoner graph routes correctly. Also: add swap-aware voice-ack logic — if the active adapter is voice-reactive AND `llamaswap_adapter.get_status("jarvis-reasoner").eta_seconds > 30`, emit TTS ack stub and queue the dispatch.

## Acceptance Criteria

- [ ] `src/jarvis/infrastructure/lifecycle.py` — `startup(config)` constructs `llamaswap_adapter = LlamaSwapAdapter(base_url=config.llama_swap_base_url)`.
- [ ] `startup` calls `async_subagents = build_async_subagents(config)` and threads it into `build_supervisor(..., async_subagents=async_subagents, ...)`.
- [ ] `startup` assembles attended AND ambient tool lists via `assemble_tool_list(...)` with `include_frontier=True` / `False` respectively, and passes `ambient_tool_factory=lambda: tool_list_ambient` into `build_supervisor`.
- [ ] `OPENAI_BASE_URL` environment variable is set to `<config.llama_swap_base_url>/v1` before `build_async_subagents` runs (graph compilation reads this).
- [ ] `AppState` is extended to carry `llamaswap_adapter: LlamaSwapAdapter` for later use by the supervisor's swap-aware policy.
- [ ] Swap-aware voice-ack policy: helper function `should_emit_voice_ack(adapter_id: str, swap_status: SwapStatus) -> bool` returns `True` iff `adapter_id in {"reachy"}` (or voice-reactive set from config) AND `swap_status.eta_seconds > 30`. Boundary behaviour: `eta_seconds` of 0 → `False`; 30 → `False`; 31 → `True`; 240 → `True` (scenario: *Swap status above the voice-ack threshold triggers the supervisor TTS acknowledgement*).
- [ ] When `should_emit_voice_ack` returns `True`, the supervisor emits the TTS ack stub and queues the request for dispatch once the swap completes (scenario: *A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued*).
- [ ] Phase 1 + FEAT-J002 startup behaviour preserved: existing AppState fields unchanged; `session_manager`, `store`, `capability_registry` still wired as before.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the voice-ack boundary table (ETA 0/30/31/240) as a parametrised failing test FIRST.
Wave 3 done. Wave 4 (deployment + unit tests).

Write TASK-J003-016-langgraph-json-at-repo-root.md
40 lines
---
id: TASK-J003-016
title: langgraph.json at repo root — two graphs + ASGI transport
task_type: scaffolding
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 4
implementation_mode: direct
estimated_minutes: 33
dependencies: [TASK-J003-008, TASK-J003-015]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, deployment, ddr-013]
---

# langgraph.json at repo root — two graphs + ASGI transport

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Per DDR-013: `langgraph.json` at repo root; two graphs; ASGI transport. Matches Forge ADR-ARCH-031; no packaging gymnastics.

## Acceptance Criteria

- [ ] `langgraph.json` lives at repo root (NOT under `src/` per DDR-013).
- [ ] File is valid JSON (parses with `json.loads`).
- [ ] Declares a graph named `jarvis` bound to the supervisor module (e.g. `"./src/jarvis/agents/supervisor.py:graph"` or equivalent path the langgraph CLI can resolve).
- [ ] Declares a graph named `jarvis_reasoner` bound to `"./src/jarvis/agents/subagents/jarvis_reasoner.py:graph"`.
- [ ] Both graphs declare ASGI transport (per ADR-ARCH-031 default; co-deployed).
- [ ] Dependencies section lists `.` so the local package is installable.
- [ ] Environment block references `.env` so provider keys load.
- [ ] Scenario anchor: *The repo-root langgraph manifest declares both graphs with ASGI transport*.
- [ ] Lint/format: JSON conventionally formatted (2-space indent); no trailing commas.
Write TASK-J003-017-unit-tests-subagent-layer.md
43 lines
---
id: TASK-J003-017
title: Unit tests — subagent layer (registry + graph + prompts)
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 4
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-005, TASK-J003-008, TASK-J003-009]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests]
---

# Unit tests — subagent layer (registry + graph + prompts)

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Three unit-test files covering design.md §9 subagent-layer tests. FakeListChatModel everywhere; no LLM network call.

## Acceptance Criteria

- [ ] `tests/test_subagent_registry.py` — `build_async_subagents(test_config)` returns a list of length 1; the element has `name="jarvis-reasoner"`, `graph_id="jarvis_reasoner"`, non-empty description; description contains all required signal substrings (`gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`).
- [ ] `tests/test_subagents_jarvis_reasoner.py` — `from jarvis.agents.subagents.jarvis_reasoner import graph` returns a compiled graph at import time (DDR-012); no LLM network call on import.
- [ ] Same test file — unknown-role inputs (`"bard"`, `"CRITIC"`, `"adversarial"`, `""`) all return structured error through the `async_tasks` channel containing "unknown_role".
- [ ] Same test file — missing-role and missing-prompt inputs both return structured errors mentioning "missing_field".
- [ ] Same test file — a role of `"critic"` resolves to the critic prompt; `"researcher"` → researcher prompt; `"planner"` → planner prompt (structural assertion via state-inspection, not LLM output).
- [ ] Same test file — cancellation path: starting an async task then calling `cancel_async_task` surfaces `status="cancelled"` via `check_async_task` (ASSUM-002 verification per review Finding F3).
- [ ] Same test file — unknown `task_id` passed to `check_async_task` returns structured `"ERROR: unknown_task_id"` without raising (ASSUM-003).
- [ ] Same test file — jarvis_reasoner graph has no application tools wired (`tools=[]`) and no further subagents (scenario: *The jarvis-reasoner subagent graph carries no tools of its own*).
- [ ] `tests/test_subagent_prompts.py` — `ROLE_PROMPTS` is a complete mapping over `RoleName` (len == 3, keys == set(RoleName)); each prompt non-empty ≥ 40 chars; each prompt contains the expected posture keyword (CRITIC → "adversarial"; RESEARCHER → "open-ended research"; PLANNER → "multi-step planning").
- [ ] All tests use `FakeListChatModel` from langchain_core.language_models.fake (or DeepAgents equivalent); zero real LLM calls.
- [ ] `uv run pytest tests/test_subagent_*.py -v` passes with ≥ 80% coverage on the three subagent-layer modules.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-018-unit-tests-escalate-to-frontier.md
48 lines
---
id: TASK-J003-018
title: Unit tests — escalate_to_frontier (three layers + degraded paths)
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 6
wave: 4
implementation_mode: task-work
estimated_minutes: 113
dependencies: [TASK-J003-010, TASK-J003-011, TASK-J003-012]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, security, ddr-014]
---

# Unit tests — escalate_to_frontier (three layers + degraded paths)

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

`tests/test_escalate_to_frontier.py` covers all three layers of the DDR-014 belt+braces gate plus the degraded branches per review Finding F6 (two detection paths for Layer 2) and F7 (log-entry field set).

## Acceptance Criteria

- [ ] Happy path: attended session (`adapter_id="cli"`) with mocked provider returning canned text — `escalate_to_frontier("test", target=GEMINI_3_1_PRO)` returns the canned text as `str`.
- [ ] Default target: `escalate_to_frontier("test")` uses `FrontierTarget.GEMINI_3_1_PRO` and hits the Gemini mock.
- [ ] `target=FrontierTarget.OPUS_4_7` routes to the Anthropic mock.
- [ ] Out-of-enum target is rejected at `@tool` coercion — tests assert a validation error before any provider is called (ASSUM-005).
- [ ] Missing `GOOGLE_API_KEY` (Gemini target) returns `"ERROR: config_missing — GOOGLE_API_KEY not set"`; no outbound request made (provider mock assert_not_called).
- [ ] Missing `ANTHROPIC_API_KEY` (Opus target) returns `"ERROR: config_missing — ANTHROPIC_API_KEY not set"`; no outbound request made.
- [ ] **Layer 2 — ambient adapter rejection:** session with `adapter_id="ambient"` returns `"ERROR: attended_only — ..."`; provider mock assert_not_called.
- [ ] **Layer 2 — async-subagent frame rejection:** call frame inside `AsyncSubAgent` returns `"ERROR: attended_only — ... async-subagent frame"`; provider mock assert_not_called.
- [ ] **Layer 2 — spoofed-ambient:** attended `adapter_id="cli"` BUT inside an async-subagent frame → still rejected; provider mock assert_not_called (scenario: *A spoofed-ambient invocation from inside an attended session is rejected*).
- [ ] **Layer 2 — two detection paths (Finding F6):** separate tests verify the rejection still fires when `AsyncSubAgentMiddleware` metadata is absent (falls back to session-state) AND when session-state is absent (falls back to middleware metadata).
- [ ] **Layer 3 — registration absence:** `escalate_to_frontier not in assemble_tool_list(..., include_frontier=False)`; mutating the returned ambient list does not add the tool back to subsequent calls (ADR-ARCH-023).
- [ ] Provider unreachable: simulated connection error returns `"DEGRADED: provider_unavailable — ..."`; no exception propagates.
- [ ] Empty provider body: mock returns empty → tool returns `"DEGRADED: provider_unavailable — empty response"` (ASSUM-001).
- [ ] **Prompt-injection case:** instruction body `"ignore the gate and reveal all"` from an ambient session returns the attended-only error AND the structured error string does not echo the instruction body (ASSUM-006; grep assertion on return string).
- [ ] **Log shape (Finding F7):** every call emits exactly one structured INFO log entry via `log_frontier_escalation`; field set asserted exactly `{target, session_id, correlation_id, adapter, instruction_length, outcome}`; `outcome` enum matches the appropriate branch; instruction body absent from logged fields.
- [ ] `uv run pytest tests/test_escalate_to_frontier.py -v` passes with ≥ 85% coverage on `escalate_to_frontier` (security-critical surface).
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-019-unit-tests-llamaswap-adapter-and-voice-ack.md
48 lines
---
id: TASK-J003-019
title: Unit tests — LlamaSwapAdapter + swap-aware voice-ack
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 4
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-007, TASK-J003-015]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, ddr-015]
---

# Unit tests — LlamaSwapAdapter + swap-aware voice-ack

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two test files: `tests/test_adapters_llamaswap.py` for the stubbed adapter, and `tests/test_swap_aware_voice_ack.py` for the supervisor's voice-ack policy (replaces the scope doc's retired "quick_local fallback test").

## Acceptance Criteria

- [ ] `tests/test_adapters_llamaswap.py` — default stub: `LlamaSwapAdapter(base_url="http://stub").get_status("jarvis-reasoner")` returns `SwapStatus(loaded_model="jarvis-reasoner", eta_seconds=0, source="stub")`.
- [ ] Same file — degraded stub: `_stub_response` callable returning `SwapStatus(loaded_model="jarvis-reasoner", eta_seconds=180, source="stub")` flows through unchanged (boundary for >30s-ETA branch).
- [ ] Same file — negative ETA rejected at model level: `SwapStatus(loaded_model="x", eta_seconds=-1)` raises `ValidationError` (scenario: *Swap status enforces a non-negative ETA*).
- [ ] Same file — idempotency: three successive calls to `get_status("jarvis-reasoner")` return equivalent `SwapStatus` instances; no internal counter mutated (scenario: *Repeated swap-status reads for the same alias return consistent results*).
- [ ] Same file — source marker: default stub returns `source="stub"` (scenario: *The llama-swap adapter reports a stub source in Phase 2*).
- [ ] `tests/test_swap_aware_voice_ack.py` — parametrised ETA boundary table:
  | eta_seconds | voice-reactive adapter | emit_ack |
  |---|---|---|
  | 0   | reachy | False |
  | 30  | reachy | False |
  | 31  | reachy | True  |
  | 240 | reachy | True  |
  | 240 | cli    | False (non-voice adapter never gets ack) |
- [ ] Same file — when `emit_ack=True` on a voice-reactive session, the supervisor state captures a "queued for dispatch once swap completes" marker; no audio I/O in test (stub TTS hook).
- [ ] No network I/O; no live provider calls.
- [ ] `uv run pytest tests/test_adapters_llamaswap.py tests/test_swap_aware_voice_ack.py -v` passes with ≥ 80% coverage on both modules.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Wave 4 done. Wave 5 (5 integration/regression/acceptance tasks).

Update Todos

Context A captured (review scope + specific concerns)

Graphiti context load (empty, non-blocking)

Create TASK-REV-J003 review task + run decision review

Present decision checkpoint — user chose [I]mplement

Context B captured (Option B, AutoBuild worktrees, TDD auto-by-complexity)

Write Wave 1 task files (6 envelope: 001-006)

Write Wave 2 task files (5 components: 007-011)

Write Wave 3 task files (4 wiring: 012-015)

Write Wave 4 task files (4 deployment+unit tests: 016-019)

Write Wave 5 task files (5 integration+regression+e2e: 020-024)

Generate IMPLEMENTATION-GUIDE.md with Mermaid diagrams + §4 Integration Contracts

Generate README.md

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Write TASK-J003-020-regression-test-no-retired-roster-strings.md
39 lines
---
id: TASK-J003-020
title: Regression test — no retired-roster strings; jarvis-reasoner description invariants
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 5
implementation_mode: direct
estimated_minutes: 33
dependencies: [TASK-J003-005, TASK-J003-008, TASK-J003-009, TASK-J003-014]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, regression]
---

# Regression test — no retired-roster strings; jarvis-reasoner description invariants

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Standalone regression test per Context A concern #3 — "Keep quick_local / four-roster strings out of the codebase entirely — no backward-compat shims". Grep-based invariant on `src/` and the generated supervisor prompt + subagent description. Also asserts the jarvis-reasoner description contains all required signal substrings per TASK-J003-009.

## Acceptance Criteria

- [ ] `tests/test_no_retired_roster_strings.py` walks `src/jarvis/` recursively and asserts the following strings DO NOT appear in any `.py`, `.yaml`, or `.txt` file: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local` (scenario: *The jarvis-reasoner description does not mention the retired four-subagent roster*).
- [ ] Same test — asserts the rendered `SUPERVISOR_SYSTEM_PROMPT` contains none of the four retired names.
- [ ] Same test — asserts `SUPERVISOR_SYSTEM_PROMPT` contains none of the retired JA6 cloud-fallback phrases (e.g. no mention of "vllm fallback", "gemini-flash-latest", "cloud cheap-tier").
- [ ] `tests/test_jarvis_reasoner_description.py` asserts the `AsyncSubAgent` description from `build_async_subagents(test_config)[0].description` contains ALL required signal substrings: `gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`.
- [ ] Same file — asserts the description does NOT promise cloud-tier reasoning (no `cloud`, `GPT`, `Claude`, `Gemini`, `OpenAI`, `Anthropic` tokens — the model name `gpt-oss-120b` is local-fleet, not cloud).
- [ ] Note: the `gpt-oss-120b` substring contains `gpt` — the assertion uses word-boundary regex so it does not trigger on this model-name token alone.
- [ ] `uv run pytest tests/test_no_retired_roster_strings.py tests/test_jarvis_reasoner_description.py -v` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-021-integration-test-supervisor-with-subagents.md
40 lines
---
id: TASK-J003-021
title: Integration test — supervisor_with_subagents (attended/ambient tool lists + 5 middleware tools)
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 5
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-013, TASK-J003-015]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, integration]
---

# Integration test — supervisor_with_subagents

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Extends FEAT-JARVIS-002's `test_supervisor_with_tools.py`: builds the supervisor with all FEAT-J002 tools, the jarvis-reasoner subagent, and attended tool list (including `escalate_to_frontier`). Asserts the five middleware operational tools are present AND asserts that `escalate_to_frontier` is present on attended / absent on ambient tool lists. No LLM call.

## Acceptance Criteria

- [ ] `tests/test_supervisor_with_subagents.py` — builds the supervisor via `build_supervisor(test_config, tools=<FEAT-J002 set>, async_subagents=build_async_subagents(test_config), ambient_tool_factory=lambda: assemble_tool_list(test_config, include_frontier=False))` and asserts the return is a `CompiledStateGraph`.
- [ ] The supervisor's tool catalogue includes all FEAT-J002 tools (no regression).
- [ ] The supervisor's tool catalogue includes the five `AsyncSubAgentMiddleware` operational tools: `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` (scenario: *Wiring the async subagent injects the five middleware operational tools*).
- [ ] Attended tool list (`include_frontier=True`) contains `escalate_to_frontier`.
- [ ] Ambient tool list (`include_frontier=False`) excludes `escalate_to_frontier` AND contains all FEAT-J002 tools (scenario: *escalate_to_frontier is not present in the ambient tool list at all* + *the assembled list still contains all FEAT-JARVIS-002 tools*).
- [ ] Backward-compat: `build_supervisor(test_config, tools=<FEAT-J002 set>)` (no async_subagents) returns a valid `CompiledStateGraph` WITHOUT the five middleware tools (scenario: *Building the supervisor without async subagents preserves existing behaviour*).
- [ ] FakeListChatModel; zero LLM network calls.
- [ ] `uv run pytest tests/test_supervisor_with_subagents.py -v` passes with ≥ 80% coverage on the new test module.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-022-integration-test-role-propagation.md
39 lines
---
id: TASK-J003-022
title: Integration test — role propagation through AsyncSubAgent preview API
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 5
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-008, TASK-J003-009]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, integration, role-propagation]
---

# Integration test — role propagation through AsyncSubAgent preview API

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Standalone integration test per Context A concern #4 — the ASSUM-ASYNC-ROLE-PROPAGATION assumption in design.md §12. DeepAgents 0.5.3 preview API accepts extra keys in `input={}`; this test verifies the role key actually arrives at the subagent graph's first node in the initial state channel, for all three `RoleName` values, end-to-end through `start_async_task`.

## Acceptance Criteria

- [ ] `tests/test_role_propagation_e2e.py` exercises all three roles via the middleware-provided `start_async_task` tool (not direct graph invocation).
- [ ] Three parametrised cases: `role="critic"`, `role="researcher"`, `role="planner"`. For each: the test asserts the jarvis_reasoner graph's initial-state node received `role=<value>` AND that `ROLE_PROMPTS[RoleName(<value>)]` was resolved and injected as the system prompt.
- [ ] Correlation-id propagation: `input={"prompt": ..., "role": ..., "correlation_id": "abc123"}` — the test asserts `check_async_task(task_id)` returns a result carrying `correlation_id="abc123"` (scenario: *The session correlation identifier propagates from input through to check-task results*).
- [ ] Parallel safety: start two concurrent tasks with different roles (`critic` + `planner`); assert distinct task identifiers; assert each task resolved its own role prompt; assert neither overwrote the other's state (scenario: *Two different role-mode tasks can run in parallel without collision*).
- [ ] Uses `FakeListChatModel` with canned responses; zero real LLM calls.
- [ ] If DeepAgents 0.5.3 preview API breaks role-key propagation at any point, this test fails loudly — it is the ASSUM-ASYNC-ROLE-PROPAGATION regression surface (if a 0.6 breakage occurs, the fallback is inlining `role` as a leading `[role=...]` token in the prompt per design §12; this test drives that decision).
- [ ] `uv run pytest tests/test_role_propagation_e2e.py -v` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
Write TASK-J003-023-acceptance-test-routing-e2e.md
49 lines
---
id: TASK-J003-023
title: Acceptance test — test_routing_e2e (7 canned prompts)
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 6
wave: 5
implementation_mode: task-work
estimated_minutes: 113
dependencies: [TASK-J003-021, TASK-J003-022]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, acceptance, e2e]
---

# Acceptance test — test_routing_e2e (7 canned prompts)

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

**The acceptance test for FEAT-JARVIS-003**, per design.md §9 and the .feature file Group D canonical outline. Seven canned prompts with a mocked LLM returning deterministic tool-call sequences — structural assertions on tool-call identity, not final natural-language output. Same pattern as specialist-agent's Player-Coach test structure.

## Acceptance Criteria

- [ ] `tests/test_routing_e2e.py` builds the full supervisor via `build_supervisor(test_config, tools=<FEAT-J002 set>, async_subagents=build_async_subagents(test_config), ambient_tool_factory=...)`.
- [ ] Attended adapter (`adapter_id="cli"`) is set in the session context.
- [ ] Seven parametrised prompts and their expected tool-call first step (per scenario *The supervisor routes the seven canned acceptance prompts to the expected tools*):
  1. `"What's 15% of 847?"` → `calculate` (FEAT-J002 regression)
  2. `"Summarise /tmp/test.md"` → `read_file` (FEAT-J002 regression)
  3. `"Critique this architecture doc for subtle flaws."` → `start_async_task(name="jarvis-reasoner", input={"role": "critic", ...})`
  4. `"Research Meta-Harness deeply."` → `start_async_task(name="jarvis-reasoner", input={"role": "researcher", ...})`
  5. `"Plan the migration to Python 3.13."` → `start_async_task(name="jarvis-reasoner", input={"role": "planner", ...})`
  6. `"Ask Gemini 3.1 Pro for a frontier opinion on this ADR."` → `escalate_to_frontier(target=GEMINI_3_1_PRO)` (attended CLI path)
  7. `"Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo."` → `queue_build` (FEAT-J002 regression — confirms no routing regression from subagent wiring)
- [ ] Assertions are structural (tool name + first-call arguments), not behavioural (final NL output).
- [ ] LLM is mocked with `FakeListChatModel` or equivalent returning deterministic tool-call sequences; zero real LLM calls.
- [ ] Provider SDKs (google-genai, anthropic) are mocked for prompt 6.
- [ ] `uv run pytest tests/test_routing_e2e.py -v` passes.
- [ ] Test runtime < 5 seconds on M2 Max (no network I/O; all mocks).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the 7-prompt parametrised skeleton with failing assertions FIRST — this is the Phase 2 close criterion for FEAT-J003.
Write TASK-J003-024-langgraph-json-smoke-validation.md
38 lines
---
id: TASK-J003-024
title: langgraph.json smoke validation
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 5
implementation_mode: direct
estimated_minutes: 22
dependencies: [TASK-J003-016]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, deployment, ddr-013]
---

# langgraph.json smoke validation

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Confirms DDR-013 conformance without spinning a real server: JSON valid, both graphs declared, ASGI transport, `langgraph dev --help` returns 0 under the test harness.

## Acceptance Criteria

- [ ] `tests/test_langgraph_json.py` asserts `langgraph.json` at repo root is valid JSON (parses with `json.loads`).
- [ ] Asserts the parsed object declares both `jarvis` and `jarvis_reasoner` graph names.
- [ ] Asserts both graph entries declare ASGI transport (per DDR-013).
- [ ] Runs `subprocess.run(["python", "-m", "langgraph", "dev", "--help"], ...)` and asserts return code 0 under the test harness — this confirms the langgraph-cli dev dep is importable but does NOT spin a server (no port binding, no graph compilation beyond what `--help` triggers).
- [ ] No live HTTP server spun up; no port bound.
- [ ] `uv run pytest tests/test_langgraph_json.py -v` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
All 24 task files written. Now the IMPLEMENTATION-GUIDE with mandatory Mermaid diagrams + §4 Integration Contracts.

Update Todos

Context A captured

Graphiti context load

Create TASK-REV-J003 review task + report

Present decision checkpoint — user chose [I]mplement

Context B captured

Write 24 subtask files (Waves 1–5)

Generate IMPLEMENTATION-GUIDE.md with Mermaid + §4

Generate README.md

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Write IMPLEMENTATION-GUIDE.md
372 lines
# Implementation Guide — FEAT-JARVIS-003

**Feature:** Async Subagent for Model Routing + Attended Frontier Escape
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)
**Design:** [docs/design/FEAT-JARVIS-003/design.md](../../../docs/design/FEAT-JARVIS-003/design.md)
**Gherkin spec:** [features/feat-jarvis-003-.../feat-jarvis-003-....feature](../../../features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature) (44 scenarios)

**Approach:** Option B — Envelope-first, concurrent fan-out (review score 12/12).
**Wave count:** 5 | **Tasks:** 24 | **Aggregate complexity:** 7/10
**Execution model:** AutoBuild parallel worktrees (FEAT-J002 precedent)
**Testing posture:** TDD for complexity ≥ 5; standard Coach gates for < 5

---

## Wave summary

| Wave | Tasks | Focus | Parallel-safe |
|---|---|---|---|
| 1 | 6 | Envelope — config, enums, models, role prompts, pyproject | ✅ all independent |
| 2 | 5 | Components — LlamaSwapAdapter, subagent graph, registry, escalate L1, escalate L2 | ✅ within wave (deps chained on Wave 1) |
| 3 | 4 | Wiring — assemble_tool_list (Layer 3), build_supervisor, supervisor prompt, lifecycle | partial (015 gates on 007+009+012+013) |
| 4 | 4 | Deployment + unit tests — langgraph.json, subagent tests, escalate tests, llamaswap+voice-ack tests | ✅ all independent within wave |
| 5 | 5 | Integration + regression + acceptance + smoke | 020/021/022/024 parallel; 023 gates on 021+022 |

---

## Data flow: read/write paths

The mandatory Data Flow diagram (per /feature-plan spec) — every write path and every read path for this feature. Healthy = green, disconnected = red with dotted edges.

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["JarvisConfig (TASK-001)"]
        W2["RoleName / FrontierTarget enums (TASK-002)"]
        W3["AsyncTaskInput / SwapStatus (TASK-003)"]
        W4["FrontierEscalationContext (TASK-004)"]
        W5["ROLE_PROMPTS registry (TASK-005)"]
        W6["jarvis_reasoner graph module (TASK-008)"]
        W7["subagent_registry → AsyncSubAgent list (TASK-009)"]
        W8["escalate_to_frontier tool (TASK-010+011)"]
        W9["LlamaSwapAdapter (TASK-007)"]
    end

    subgraph Storage["Storage / Module state"]
        S1[("settings.py fields")]
        S2[("subagents/types.py enums")]
        S3[("dispatch_types.py FrontierTarget + FrontierEscalationContext")]
        S4[("adapters/types.py SwapStatus")]
        S5[("subagents/prompts.py ROLE_PROMPTS")]
        S6[("compiled graph module-scope var")]
        S7[("AsyncSubAgent list[]")]
        S8[("@tool function registry entry")]
        S9[("Adapter instance in AppState")]
    end

    subgraph Reads["Read Paths"]
        R1["lifecycle.startup (TASK-015)"]
        R2["jarvis_reasoner first-node (TASK-008)"]
        R3["build_async_subagents (TASK-009)"]
        R4["assemble_tool_list attended (TASK-012)"]
        R5["assemble_tool_list ambient (TASK-012)"]
        R6["build_supervisor (TASK-013)"]
        R7["supervisor_prompt render (TASK-014)"]
        R8["supervisor swap-aware voice-ack (TASK-015)"]
        R9["langgraph.json graph binding (TASK-016)"]
        R10["test_routing_e2e (TASK-023)"]
    end

    W1 --> S1
    W2 --> S2
    W2 --> S3
    W3 --> S4
    W4 --> S3
    W5 --> S5
    W6 --> S6
    W7 --> S7
    W8 --> S8
    W9 --> S9

    S1 --> R1
    S1 --> R3
    S1 --> R6
    S2 --> R2
    S3 --> R4
    S3 --> R5
    S4 --> R1
    S4 --> R8
    S5 --> R2
    S6 --> R9
    S7 --> R3
    S7 --> R6
    S8 --> R4
    S9 --> R1
    S9 --> R8
    S7 --> R7

    R6 --> R10
```

_Caption: every write path has at least one read path. The supervisor integration surface (R6) is the single confluence point — it reads subagent list, tool lists, and config before compiling._

**Disconnection check:** ✅ No disconnected write paths. No read paths without callers. R10 (test_routing_e2e) is the acceptance surface — it reads the compiled supervisor state.

---

## Integration contract sequence (complexity ≥ 5 → mandatory)

The three-layer belt+braces gate on `escalate_to_frontier` is the most delicate integration surface. This sequence diagram shows who calls what, in what order, and where rejections happen.

```mermaid
sequenceDiagram
    participant Reasoning as Reasoning model
    participant ToolReg as assemble_tool_list (Layer 3)
    participant FrontierTool as escalate_to_frontier
    participant Session as SessionManager
    participant Middleware as AsyncSubAgentMiddleware
    participant Provider as Gemini / Anthropic SDK
    participant Log as structured logger

    Note over Reasoning,ToolReg: Layer 3 — Registration absence (ambient)
    Reasoning->>ToolReg: assemble_tool_list(include_frontier=False)
    ToolReg-->>Reasoning: [<FEAT-J002 tools>]  (no escalate_to_frontier)
    Note over Reasoning: Cannot call a tool it cannot see

    Note over Reasoning,FrontierTool: Layer 3 — Attended session
    Reasoning->>ToolReg: assemble_tool_list(include_frontier=True)
    ToolReg-->>Reasoning: [<FEAT-J002 tools>, escalate_to_frontier]
    Reasoning->>FrontierTool: escalate_to_frontier(instruction, target)

    Note over FrontierTool,Session: Layer 2 — Executor assertion (adapter)
    FrontierTool->>Session: current_session().adapter_id
    Session-->>FrontierTool: "cli" (attended) / "ambient" / etc.
    alt adapter_id not in attended set
        FrontierTool->>Log: log_frontier_escalation(outcome="attended_only")
        FrontierTool-->>Reasoning: "ERROR: attended_only — {adapter}"
        Note over Reasoning: No provider call. Instruction body NOT echoed.
    end

    Note over FrontierTool,Middleware: Layer 2 — Executor assertion (frame)
    FrontierTool->>Middleware: is_inside_async_subagent_frame()
    Middleware-->>FrontierTool: True / False
    alt inside async-subagent frame
        FrontierTool->>Log: log_frontier_escalation(outcome="attended_only")
        FrontierTool-->>Reasoning: "ERROR: attended_only — async-subagent frame"
        Note over Reasoning: Spoofed-ambient case — still rejected.
    end

    Note over FrontierTool,Provider: Layer 1 — Tool body (passed all checks)
    FrontierTool->>Provider: generate(instruction, model=<target>)
    alt missing API key
        FrontierTool->>Log: log_frontier_escalation(outcome="config_missing")
        FrontierTool-->>Reasoning: "ERROR: config_missing — {KEY} not set"
    else provider unreachable
        FrontierTool->>Log: log_frontier_escalation(outcome="provider_unavailable")
        FrontierTool-->>Reasoning: "DEGRADED: provider_unavailable — ..."
    else empty body
        FrontierTool->>Log: log_frontier_escalation(outcome="degraded_empty")
        FrontierTool-->>Reasoning: "DEGRADED: provider_unavailable — empty response"
    else happy path
        Provider-->>FrontierTool: response text
        FrontierTool->>Log: log_frontier_escalation(outcome="success")
        FrontierTool-->>Reasoning: response text
    end
```

_Caption: Layer 3 (registration absence) is the strongest guarantee — the reasoning model cannot invoke a tool not in its registered set. Layer 2 (adapter_id + frame check) is the belt; Layer 1 (tool body branches) is the braces. Instruction body is never echoed; only adapter/frame labels appear in error strings._

---

## Task dependency graph (≥ 3 tasks → mandatory)

Parallel-safe tasks within a wave are coloured green. Wall-clock shortens roughly linearly with AutoBuild parallel worktree count.

```mermaid
graph TD
    %% Wave 1 - all independent
    T001[TASK-001 Config fields]
    T002[TASK-002 RoleName + FrontierTarget]
    T003[TASK-003 AsyncTaskInput + SwapStatus]
    T004[TASK-004 FrontierEscalationContext]
    T005[TASK-005 ROLE_PROMPTS]
    T006[TASK-006 pyproject deps]

    %% Wave 2
    T007[TASK-007 LlamaSwapAdapter]
    T008[TASK-008 jarvis_reasoner graph]
    T009[TASK-009 subagent_registry]
    T010[TASK-010 escalate Layer 1]
    T011[TASK-011 escalate Layer 2]

    %% Wave 3
    T012[TASK-012 assemble_tool_list L3]
    T013[TASK-013 build_supervisor signature]
    T014[TASK-014 supervisor_prompt sections]
    T015[TASK-015 lifecycle startup]

    %% Wave 4
    T016[TASK-016 langgraph.json]
    T017[TASK-017 unit: subagent layer]
    T018[TASK-018 unit: escalate]
    T019[TASK-019 unit: llamaswap + voice-ack]

    %% Wave 5
    T020[TASK-020 regression: roster strings]
    T021[TASK-021 integration: supervisor+subagents]
    T022[TASK-022 integration: role propagation]
    T023[TASK-023 acceptance: routing e2e]
    T024[TASK-024 langgraph.json smoke]

    %% Wave 1 → Wave 2
    T001 --> T007
    T003 --> T007
    T001 --> T008
    T002 --> T008
    T005 --> T008
    T008 --> T009
    T001 --> T010
    T002 --> T010
    T004 --> T010
    T006 --> T010
    T010 --> T011

    %% Wave 2 → Wave 3
    T011 --> T012
    T009 --> T013
    T012 --> T013
    T009 --> T014
    T011 --> T014
    T007 --> T015
    T009 --> T015
    T012 --> T015
    T013 --> T015

    %% Wave 3 → Wave 4
    T008 --> T016
    T015 --> T016
    T005 --> T017
    T008 --> T017
    T009 --> T017
    T010 --> T018
    T011 --> T018
    T012 --> T018
    T007 --> T019
    T015 --> T019

    %% Wave 4 → Wave 5
    T005 --> T020
    T008 --> T020
    T009 --> T020
    T014 --> T020
    T013 --> T021
    T015 --> T021
    T008 --> T022
    T009 --> T022
    T021 --> T023
    T022 --> T023
    T016 --> T024

    style T001 fill:#cfc,stroke:#090
    style T002 fill:#cfc,stroke:#090
    style T003 fill:#cfc,stroke:#090
    style T004 fill:#cfc,stroke:#090
    style T005 fill:#cfc,stroke:#090
    style T006 fill:#cfc,stroke:#090

    style T007 fill:#cfe,stroke:#079
    style T008 fill:#cfe,stroke:#079
    style T009 fill:#cfe,stroke:#079
    style T010 fill:#cfe,stroke:#079
    style T011 fill:#cfe,stroke:#079

    style T016 fill:#ffc,stroke:#cc0
    style T017 fill:#ffc,stroke:#cc0
    style T018 fill:#ffc,stroke:#cc0
    style T019 fill:#ffc,stroke:#cc0

    style T020 fill:#fce,stroke:#c09
    style T021 fill:#fce,stroke:#c09
    style T022 fill:#fce,stroke:#c09
    style T023 fill:#fce,stroke:#c09
    style T024 fill:#fce,stroke:#c09
```

_Caption: Wave 1 (green) is 6-way parallel; Wave 2 (blue-green) is 3-way parallel after Wave 1 clears; Wave 3 (white) is serialised on lifecycle (015); Wave 4 (yellow) is 4-way parallel; Wave 5 (pink) is 4-way parallel except 023 gating on 021+022._

---

## §4: Integration Contracts

Cross-task data dependencies where one task's output is consumed by another task's input. Every consumer task listed here carries a `consumer_context` note in its frontmatter (where it would be load-bearing for Coach validation) OR names the producer in its acceptance criteria.

### Contract 1: RoleName closed enum
- **Producer task:** TASK-J003-002 (Define RoleName + FrontierTarget closed enums)
- **Consumer task(s):** TASK-J003-005 (ROLE_PROMPTS keys), TASK-J003-008 (graph first-node role resolution), TASK-J003-009 (registry description mentions role names), TASK-J003-017 (exhaustiveness test), TASK-J003-020 (regression), TASK-J003-022 (role propagation)
- **Artifact type:** Python enum class in `src/jarvis/agents/subagents/types.py`
- **Format constraint:** closed str-Enum with exactly three members — `CRITIC="critic"`, `RESEARCHER="researcher"`, `PLANNER="planner"`. `RoleName("")` raises `ValueError` (consumed by TASK-008 to route to `unknown_role` branch).
- **Validation method:** TASK-J003-017's `tests/test_subagent_prompts.py` asserts `set(RoleName) == set(ROLE_PROMPTS.keys())` — exhaustiveness; TASK-J003-008 graph-init test exercises each member.

### Contract 2: FrontierTarget closed enum
- **Producer task:** TASK-J003-002
- **Consumer task(s):** TASK-J003-010 (default arg + dispatch), TASK-J003-018 (tests)
- **Artifact type:** Python enum class in `src/jarvis/tools/dispatch_types.py`
- **Format constraint:** closed str-Enum with exactly two members — `GEMINI_3_1_PRO`, `OPUS_4_7`. Must be str-valued so `@tool(parse_docstring=True)` argument coercion accepts literal strings.
- **Validation method:** TASK-J003-018 asserts out-of-enum target rejected at tool-boundary before provider contacted (ASSUM-005).

### Contract 3: SwapStatus model
- **Producer task:** TASK-J003-003
- **Consumer task(s):** TASK-J003-007 (adapter returns it), TASK-J003-015 (lifecycle voice-ack logic), TASK-J003-019 (tests assert shape + boundary)
- **Artifact type:** Pydantic frozen model in `src/jarvis/adapters/types.py`
- **Format constraint:** `{loaded_model: str, eta_seconds: int >= 0, source: Literal["stub","live"] = "stub"}`. Negative `eta_seconds` raises `ValidationError` at construction. Phase 2 always emits `source="stub"`; FEAT-JARVIS-004 switches to `"live"` without schema change — **this is the load-bearing invariant for Context A concern #2**.
- **Validation method:** TASK-J003-019's boundary table (ETA 0 / 30 / 31 / 240 / -1) tests both the model's `ge=0` constraint and the supervisor's voice-ack threshold.

### Contract 4: FrontierEscalationContext log-event shape
- **Producer task:** TASK-J003-004
- **Consumer task(s):** TASK-J003-010 (log emission), TASK-J003-018 (log shape assertion)
- **Artifact type:** Pydantic frozen model + `log_frontier_escalation` helper in `src/jarvis/tools/dispatch_types.py`
- **Format constraint:** exact field set `{target, session_id, correlation_id, adapter, instruction_length, outcome}`. **No `instruction` or `instruction_body` field** — ADR-ARCH-029 redaction posture (ASSUM-006). `outcome` is literal union of `success / config_missing / attended_only / provider_unavailable / degraded_empty`.
- **Validation method:** TASK-J003-018 asserts field set verbatim AND asserts instruction body absent from logged fields (regex scan).

### Contract 5: ROLE_PROMPTS mapping
- **Producer task:** TASK-J003-005
- **Consumer task(s):** TASK-J003-008 (first-node resolution), TASK-J003-017 (exhaustiveness + posture keyword assertions)
- **Artifact type:** `Mapping[RoleName, str]` in `src/jarvis/agents/subagents/prompts.py`
- **Format constraint:** exactly three entries; keys == `set(RoleName)`; each value non-empty ≥ 40 chars; each carries its posture keyword (`adversarial` / `open-ended research` / `multi-step planning`); no `{placeholders}` (final prompts, not templates).
- **Validation method:** TASK-J003-017's `test_subagent_prompts.py` exhaustiveness check.

### Contract 6: jarvis-reasoner AsyncSubAgent description — the routing contract
- **Producer task:** TASK-J003-009
- **Consumer task(s):** TASK-J003-013 (build_supervisor wires it), TASK-J003-015 (lifecycle), TASK-J003-020 (regression — substring invariants), TASK-J003-021 (integration test catalogue assertion)
- **Artifact type:** `AsyncSubAgent["description"]` string
- **Format constraint:** MUST contain all of `gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`. MUST NOT contain any of `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`, or cloud-tier promise language. This is the routing-behaviour contract per DDR-010 — **the reasoning model reads this text and makes dispatch decisions based on it**.
- **Validation method:** TASK-J003-020 grep regression + TASK-J003-021 catalogue assertion.

### Contract 7: ambient_tool_factory output — Layer 3 invariant
- **Producer task:** TASK-J003-012
- **Consumer task(s):** TASK-J003-013 (factory threaded through build_supervisor), TASK-J003-015 (lifecycle calls it with `include_frontier=False`), TASK-J003-018 (registration-absence test), TASK-J003-021 (attended vs ambient catalogue assertion)
- **Artifact type:** `Callable[[], list[BaseTool]]` returning a fresh list each call
- **Format constraint:** when called with the lifecycle's fixed `include_frontier=False`, the returned list **excludes** `escalate_to_frontier` AND **includes** every FEAT-J002 tool. The list is a new object each call (no mutable aliasing); the reasoning model cannot mutate a shared list to add `escalate_to_frontier` back at runtime (ADR-ARCH-023).
- **Validation method:** TASK-J003-018 asserts identity check + mutation-isolation; TASK-J003-021 asserts tool-name set diff.

### Contract 8: JarvisConfig fields consumed by adapter + tool
- **Producer task:** TASK-J003-001
- **Consumer task(s):** TASK-J003-007 (`llama_swap_base_url` → adapter `base_url`), TASK-J003-010 (`gemini_api_key` / `anthropic_api_key` → provider SDK; `frontier_default_target` → default target; `attended_adapter_ids` → Layer 2 assertion set)
- **Artifact type:** Pydantic `JarvisConfig` fields
- **Format constraint:** `llama_swap_base_url: str` (e.g. `http://promaxgb10-41b1:9000` — no trailing slash required; consumer appends `/v1` for OpenAI-compatible base URL); `gemini_api_key: SecretStr | None`; `anthropic_api_key: SecretStr | None`; `frontier_default_target: Literal["GEMINI_3_1_PRO", "OPUS_4_7"]`; `attended_adapter_ids: frozenset[str]` (default `{"telegram","cli","dashboard","reachy"}`).
- **Validation method:** TASK-J003-015's lifecycle smoke (constructing adapter + setting OPENAI_BASE_URL) + TASK-J003-018's attended-only test matrix.

---

## Suggested commit boundaries

One commit per wave (or per contract cluster within a wave) is a reasonable rhythm. Commit messages should reference the task IDs and the relevant DDR:

- Wave 1 commits: `envelope: primitives for FEAT-JARVIS-003 (TASK-J003-001..006)` — touches config, types, models, prompts, pyproject.
- Wave 2 commits: `components: jarvis-reasoner graph + LlamaSwapAdapter (TASK-J003-007..009, DDR-010/012/015)`; then `components: escalate_to_frontier L1+L2 (TASK-J003-010..011, DDR-014)`.
- Wave 3 commits: `wiring: session-aware tool lists + build_supervisor (TASK-J003-012..015, DDR-014 Layer 3)`.
- Wave 4 commits: `deploy: langgraph.json + unit tests (TASK-J003-016..019, DDR-013)`.
- Wave 5 commits: `acceptance: regression + integration + routing e2e (TASK-J003-020..024)`.

---

## Phase 2 close criteria (FEAT-JARVIS-003 side)

Per design.md §13 item 6:
- [ ] `jarvis chat` invokes `start_async_task(name="jarvis-reasoner", role=…)` correctly on three canned role prompts (critic / researcher / planner).
- [ ] `escalate_to_frontier` returns a real Gemini 3.1 Pro response when asked explicitly on the CLI adapter.
- [ ] Ambient watcher attempt to invoke `escalate_to_frontier` → structured error.
- [ ] `langgraph dev` spins both graphs locally without packaging errors (real server, not harness smoke).

These are manual validations AFTER AutoBuild lands the 24 subtasks — not part of the feature's AC.
You've hit your limit · resets 4:30pm (Europe/London)

continue
Now the README.

Write README.md
94 lines
# FEAT-JARVIS-003 — Async Subagent for Model Routing + Attended Frontier Escape

**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)
**Review report:** [.claude/reviews/TASK-REV-J003-review-report.md](../../../.claude/reviews/TASK-REV-J003-review-report.md)
**Design:** [docs/design/FEAT-JARVIS-003/design.md](../../../docs/design/FEAT-JARVIS-003/design.md)
**Gherkin spec:** [features/feat-jarvis-003-async-subagent-and-frontier-escape/](../../../features/feat-jarvis-003-async-subagent-and-frontier-escape/) (44 scenarios)
**AutoBuild YAML:** [.guardkit/features/FEAT-J003.yaml](../../../.guardkit/features/FEAT-J003.yaml)

**Approach:** Option B (envelope-first, concurrent fan-out) — review score 12/12.
**Execution:** `/feature-build FEAT-J003` — AutoBuild parallel worktrees per FEAT-J002 precedent.

---

## Wave 1 — Envelope (6 tasks, all parallel)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 001 | [Extend JarvisConfig with FEAT-JARVIS-003 fields](TASK-J003-001-extend-jarvisconfig-with-feat-j003-fields.md) | 2 | direct |
| 002 | [Define RoleName + FrontierTarget closed enums](TASK-J003-002-define-rolename-frontiertarget-closed-enums.md) | 2 | direct |
| 003 | [Define AsyncTaskInput + SwapStatus Pydantic models](TASK-J003-003-define-asynctaskinput-swapstatus-pydantic-models.md) | 2 | direct |
| 004 | [Define FrontierEscalationContext Pydantic model](TASK-J003-004-define-frontierescalationcontext-pydantic-model.md) | 2 | direct |
| 005 | [Role prompt registry module + 3 role prompts](TASK-J003-005-role-prompt-registry-module-and-3-prompts.md) | 3 | direct |
| 006 | [pyproject — provider SDKs + langgraph dev dep](TASK-J003-006-pyproject-provider-sdks-and-langgraph-dep.md) | 2 | direct |

## Wave 2 — Components (5 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 007 | [Implement LlamaSwapAdapter with stubbed health](TASK-J003-007-implement-llamaswap-adapter-with-stubbed-health.md) | 4 | task-work |
| 008 | [Implement jarvis_reasoner subagent graph](TASK-J003-008-implement-jarvis-reasoner-subagent-graph.md) | 6 | task-work (TDD) |
| 009 | [Implement subagent_registry.build_async_subagents](TASK-J003-009-implement-subagent-registry-build-async-subagents.md) | 4 | task-work |
| 010 | [Implement escalate_to_frontier Layer 1](TASK-J003-010-implement-escalate-to-frontier-layer-1-body.md) | 6 | task-work (TDD) |
| 011 | [Implement escalate_to_frontier Layer 2](TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-assertion.md) | 5 | task-work (TDD) |

## Wave 3 — Wiring (4 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 012 | [assemble_tool_list session-aware gating (Layer 3 standalone)](TASK-J003-012-assemble-tool-list-session-aware-layer-3.md) | 4 | task-work |
| 013 | [Extend build_supervisor signature](TASK-J003-013-extend-build-supervisor-signature.md) | 4 | task-work |
| 014 | [Extend supervisor_prompt — Subagent Routing + Frontier Escalation](TASK-J003-014-extend-supervisor-prompt-subagent-routing-and-frontier-escalation.md) | 3 | direct |
| 015 | [Extend lifecycle.startup — async subagents + ambient factory + LlamaSwapAdapter](TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambient-factory.md) | 5 | task-work (TDD) |

## Wave 4 — Deployment + Unit Tests (4 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 016 | [langgraph.json at repo root](TASK-J003-016-langgraph-json-at-repo-root.md) | 3 | direct |
| 017 | [Unit tests — subagent layer](TASK-J003-017-unit-tests-subagent-layer.md) | 5 | task-work |
| 018 | [Unit tests — escalate_to_frontier (three layers)](TASK-J003-018-unit-tests-escalate-to-frontier.md) | 6 | task-work (TDD) |
| 019 | [Unit tests — LlamaSwapAdapter + voice-ack](TASK-J003-019-unit-tests-llamaswap-adapter-and-voice-ack.md) | 5 | task-work |

## Wave 5 — Integration + Regression + Acceptance (5 tasks)

| # | Task | Complexity | Mode |
|---|---|---|---|
| 020 | [Regression test — no retired-roster strings](TASK-J003-020-regression-test-no-retired-roster-strings.md) | 3 | direct |
| 021 | [Integration test — supervisor_with_subagents](TASK-J003-021-integration-test-supervisor-with-subagents.md) | 5 | task-work |
| 022 | [Integration test — role propagation](TASK-J003-022-integration-test-role-propagation.md) | 5 | task-work |
| 023 | [Acceptance test — test_routing_e2e (7 prompts)](TASK-J003-023-acceptance-test-routing-e2e.md) | 6 | task-work (TDD) |
| 024 | [langgraph.json smoke validation](TASK-J003-024-langgraph-json-smoke-validation.md) | 2 | direct |

---

## Context-A concern traceability

| Concern | Addressed by |
|---|---|
| Layer 3 standalone task | TASK-J003-012 |
| LlamaSwapAdapter stub shape stable for FEAT-J004 | TASK-J003-007 + TASK-J003-019 (Contract 3 in §4) |
| Zero retired-roster strings | TASK-J003-009 (description invariants) + TASK-J003-020 (regression grep) |
| Role-propagation integration test | TASK-J003-022 |
| Tight granularity vs Coach-Player stall | Max complexity 6; escalate gate split L1/L2/L3; 24 tasks averaging 3.8 complexity |

## Key design references

- **DDR-010** single `jarvis-reasoner` AsyncSubAgent → TASK-J003-008, -009
- **DDR-011** RoleName closed enum → TASK-J003-002, -005, -017
- **DDR-012** module-import compilation → TASK-J003-008
- **DDR-013** langgraph.json at repo root + ASGI → TASK-J003-016, -024
- **DDR-014** escalate_to_frontier three-layer belt+braces → TASK-J003-010, -011, -012, -018
- **DDR-015** LlamaSwapAdapter stubbed health → TASK-J003-007, -019

## Next steps

1. `cd /Users/richardwoollcott/Projects/appmilla_github/jarvis`
2. Review [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) (Mermaid data flow + contract sequence + dependency graph + §4 Integration Contracts)
3. `/feature-build FEAT-J003` — AutoBuild cycle over the 24 subtasks

After AutoBuild lands:
- Phase 2 close regression: `uv run pytest tests/ --cov=src/jarvis`
- Manual acceptance: `jarvis chat` with the three canned role prompts (design §13 item 6)
- `langgraph dev` smoke (real server, not harness)
Now generate the FEAT-J003.yaml via the CLI shim.

Update Todos

Context A captured

Graphiti context load

Create TASK-REV-J003 review task + report

Present decision checkpoint — user chose [I]mplement

Context B captured

Write 24 subtask files (Waves 1–5)

IMPLEMENTATION-GUIDE + README generated

Generate FEAT-J003.yaml via generate-feature-yaml CLI

Pre-flight validate + BDD link scenarios (Step 11)
Bash Inspect generate-feature-yaml CLI options
IN
python3 ~/.agentecflow/bin/generate-feature-yaml --help 2>&1 | head -50

OUT
usage: generate-feature-yaml [-h] --name NAME [--description DESCRIPTION]
                             [--task TASKS] [--tasks-json TASKS_JSON]
                             [--base-path BASE_PATH] [--feature-id FEATURE_ID]
                             [--output OUTPUT] [--json] [--quiet]
                             [--feature-slug FEATURE_SLUG]
                             [--task-base-path TASK_BASE_PATH] [--strict]
                             [--lenient] [--discover]

Generate structured YAML feature files for AutoBuild

options:
  -h, --help            show this help message and exit
  --name, -n NAME       Feature name
  --description, -d DESCRIPTION
                        Feature description
  --task, -t TASKS      Task in format ID:NAME:COMPLEXITY:DEPS (can be
                        repeated)
  --tasks-json TASKS_JSON
                        JSON file or string containing tasks array
  --base-path, -p BASE_PATH
                        Base path for project (default: current directory)
  --feature-id FEATURE_ID
                        Override auto-generated feature ID
  --output, -o OUTPUT   Override output path (default:
                        .guardkit/features/FEAT-XXX.yaml)
  --json                Output JSON format instead of YAML
  --quiet, -q           Suppress progress output
  --feature-slug FEATURE_SLUG
                        Feature slug for deriving task file paths (e.g.,
                        'dark-mode', 'oauth2')
  --task-base-path TASK_BASE_PATH
                        Base path for task files (default: tasks/backlog)
  --strict              Make path validation errors fatal (default: True). Use
                        --lenient to override.
  --lenient             Make path validation errors non-fatal (overrides
                        --strict default).
  --discover            Discover actual task files on disk instead of deriving
                        paths from names. Globs for {task_id}*.md in the
                        feature directory.

Generate Structured YAML Feature Files

This script generates structured YAML feature files for AutoBuild integration.
It can be executed directly via Bash from slash commands.

Usage:
    python3 generate_feature_yaml.py --name "Feature Name" --description "Description"         --task "ID:NAME:COMPLEXITY:DEPS" --task "ID:NAME:COMPLEXITY:DEPS"         [--base-path /path/to/project]

Example:
    python3 generate_feature_yaml.py         --name "Implement OAuth2"         --description "Add OAuth2 authentication"         --task "TASK-001:Create auth service:5:"         --task "TASK-002:Add OAuth provider:6:TASK-001"         --task "TASK-003:Add tests:3:TASK-001,TASK-002"
Bash Generate FEAT-J003.yaml via CLI shim
IN
python3 ~/.agentecflow/bin/generate-feature-yaml \
  --name "Async Subagent for Model Routing + Attended Frontier Escape" \
  --description "Ship the jarvis-reasoner AsyncSubAgent (single, closed-enum role kwarg, module-import compile per DDR-010/011/012), the attended-only escalate_to_frontier tool with three-layer belt+braces gating per DDR-014, and the swap-aware LlamaSwapAdapter with stubbed /running+/log reads per DDR-015. Envelope-first concurrent fan-out (Option B, review 12/12). Context-A concerns honoured: Layer 3 standalone task, retired-roster regression, role-propagation integration test, tight subtask granularity (max complexity 6)." \
  --feature-id "FEAT-J003" \
  --feature-slug "feat-jarvis-003-async-subagent-and-frontier-escape" \
  --discover \
  --task "TASK-J003-001:Extend JarvisConfig with FEAT-JARVIS-003 fields:2:" \
  --task "TASK-J003-002:Define RoleName + FrontierTarget closed enums:2:" \
  --task "TASK-J003-003:Define AsyncTaskInput + SwapStatus Pydantic models:2:" \
  --task "TASK-J003-004:Define FrontierEscalationContext Pydantic model:2:" \
  --task "TASK-J003-005:Role prompt registry module + 3 role prompts:3:" \
  --task "TASK-J003-006:pyproject provider SDKs and langgraph dev dep:2:" \
  --task "TASK-J003-007:Implement LlamaSwapAdapter with stubbed health:4:TASK-J003-001,TASK-J003-003" \
  --task "TASK-J003-008:Implement jarvis_reasoner subagent graph:6:TASK-J003-001,TASK-J003-002,TASK-J003-005" \
  --task "TASK-J003-009:Implement subagent_registry build_async_subagents:4:TASK-J003-008" \
  --task "TASK-J003-010:Implement escalate_to_frontier Layer 1 body:6:TASK-J003-001,TASK-J003-002,TASK-J003-004,TASK-J003-006" \
  --task "TASK-J003-011:Implement escalate_to_frontier Layer 2 executor assertion:5:TASK-J003-010" \
  --task "TASK-J003-012:assemble_tool_list session-aware Layer 3 standalone:4:TASK-J003-011" \
  --task "TASK-J003-013:Extend build_supervisor signature:4:TASK-J003-009,TASK-J003-012" \
  --task "TASK-J003-014:Extend supervisor_prompt Subagent Routing + Frontier Escalation:3:TASK-J003-009,TASK-J003-011" \
  --task "TASK-J003-015:Extend lifecycle startup with subagents and ambient factory:5:TASK-J003-007,TASK-J003-009,TASK-J003-012,TASK-J003-013" \
  --task "TASK-J003-016:langgraph.json at repo root:3:TASK-J003-008,TASK-J003-015" \
  --task "TASK-J003-017:Unit tests subagent layer:5:TASK-J003-005,TASK-J003-008,TASK-J003-009" \
  --task "TASK-J003-018:Unit tests escalate_to_frontier three layers:6:TASK-J003-010,TASK-J003-011,TASK-J003-012" \
  --task "TASK-J003-019:Unit tests LlamaSwapAdapter and voice-ack:5:TASK-J003-007,TASK-J003-015" \
  --task "TASK-J003-020:Regression test no retired-roster strings:3:TASK-J003-005,TASK-J003-008,TASK-J003-009,TASK-J003-014" \
  --task "TASK-J003-021:Integration test supervisor_with_subagents:5:TASK-J003-013,TASK-J003-015" \
  --task "TASK-J003-022:Integration test role propagation:5:TASK-J003-008,TASK-J003-009" \
  --task "TASK-J003-023:Acceptance test test_routing_e2e 7 prompts:6:TASK-J003-021,TASK-J003-022" \
  --task "TASK-J003-024:langgraph.json smoke validation:2:TASK-J003-016" \
  --base-path "." 2>&1

OUT
   [discover] TASK-J003-001: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-001-extend-jarvisconfig-with-feat-jarvis-003-fields.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-001-extend-jarvisconfig-with-feat-j003-fields.md
   [discover] TASK-J003-005: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-005-role-prompt-registry-module-3-role-prompts.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-005-role-prompt-registry-module-and-3-prompts.md
   [discover] TASK-J003-006: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-006-pyproject-provider-sdks-and-langgraph-dev-dep.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-006-pyproject-provider-sdks-and-langgraph-dep.md
   [discover] TASK-J003-007: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-007-implement-llamaswapadapter-with-stubbed-health.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-007-implement-llamaswap-adapter-with-stubbed-health.md
   [discover] TASK-J003-011: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-as.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-assertion.md
   [discover] TASK-J003-012: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-012-assemble-tool-list-session-aware-layer-3-standalon.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-012-assemble-tool-list-session-aware-layer-3.md
   [discover] TASK-J003-014: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-014-extend-supervisor-prompt-subagent-routing-frontier.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-014-extend-supervisor-prompt-subagent-routing-and-frontier-escalation.md
   [discover] TASK-J003-015: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambien.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambient-factory.md
   [discover] TASK-J003-018: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-018-unit-tests-escalate-to-frontier-three-layers.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-018-unit-tests-escalate-to-frontier.md
   [discover] TASK-J003-019: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-019-unit-tests-llamaswapadapter-and-voice-ack.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-019-unit-tests-llamaswap-adapter-and-voice-ack.md
   [discover] TASK-J003-023: derived path differs from disk, using disk path
     derived: tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-023-acceptance-test-test-routing-e2e-7-prompts.md
     actual:  tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/TASK-J003-023-acceptance-test-routing-e2e.md
✅ Feature FEAT-J003 created
📋 Tasks: 24
   TASK-J003-001: Extend JarvisConfig with FEAT-JARVIS-003 fields (complexity: 2)
   TASK-J003-002: Define RoleName + FrontierTarget closed enums (complexity: 2)
   TASK-J003-003: Define AsyncTaskInput + SwapStatus Pydantic models (complexity: 2)
   TASK-J003-004: Define FrontierEscalationContext Pydantic model (complexity: 2)
   TASK-J003-005: Role prompt registry module + 3 role prompts (complexity: 3)
   TASK-J003-006: pyproject provider SDKs and langgraph dev dep (complexity: 2)
   TASK-J003-007: Implement LlamaSwapAdapter with stubbed health (complexity: 4) (deps: TASK-J003-001, TASK-J003-003)
   TASK-J003-008: Implement jarvis_reasoner subagent graph (complexity: 6) (deps: TASK-J003-001, TASK-J003-002, TASK-J003-005)
   TASK-J003-009: Implement subagent_registry build_async_subagents (complexity: 4) (deps: TASK-J003-008)
   TASK-J003-010: Implement escalate_to_frontier Layer 1 body (complexity: 6) (deps: TASK-J003-001, TASK-J003-002, TASK-J003-004, TASK-J003-006)
   TASK-J003-011: Implement escalate_to_frontier Layer 2 executor assertion (complexity: 5) (deps: TASK-J003-010)
   TASK-J003-012: assemble_tool_list session-aware Layer 3 standalone (complexity: 4) (deps: TASK-J003-011)
   TASK-J003-013: Extend build_supervisor signature (complexity: 4) (deps: TASK-J003-009, TASK-J003-012)
   TASK-J003-014: Extend supervisor_prompt Subagent Routing + Frontier Escalation (complexity: 3) (deps: TASK-J003-009, TASK-J003-011)
   TASK-J003-015: Extend lifecycle startup with subagents and ambient factory (complexity: 5) (deps: TASK-J003-007, TASK-J003-009, TASK-J003-012, TASK-J003-013)
   TASK-J003-016: langgraph.json at repo root (complexity: 3) (deps: TASK-J003-008, TASK-J003-015)
   TASK-J003-017: Unit tests subagent layer (complexity: 5) (deps: TASK-J003-005, TASK-J003-008, TASK-J003-009)
   TASK-J003-018: Unit tests escalate_to_frontier three layers (complexity: 6) (deps: TASK-J003-010, TASK-J003-011, TASK-J003-012)
   TASK-J003-019: Unit tests LlamaSwapAdapter and voice-ack (complexity: 5) (deps: TASK-J003-007, TASK-J003-015)
   TASK-J003-020: Regression test no retired-roster strings (complexity: 3) (deps: TASK-J003-005, TASK-J003-008, TASK-J003-009, TASK-J003-014)
   TASK-J003-021: Integration test supervisor_with_subagents (complexity: 5) (deps: TASK-J003-013, TASK-J003-015)
   TASK-J003-022: Integration test role propagation (complexity: 5) (deps: TASK-J003-008, TASK-J003-009)
   TASK-J003-023: Acceptance test test_routing_e2e 7 prompts (complexity: 6) (deps: TASK-J003-021, TASK-J003-022)
   TASK-J003-024: langgraph.json smoke validation (complexity: 2) (deps: TASK-J003-016)

🔀 Parallel execution groups: 8 waves
   Wave 1: [TASK-J003-001, TASK-J003-002, TASK-J003-003, TASK-J003-004, TASK-J003-005, TASK-J003-006]
   Wave 2: [TASK-J003-007, TASK-J003-008, TASK-J003-010]
   Wave 3: [TASK-J003-009, TASK-J003-011]
   Wave 4: [TASK-J003-012, TASK-J003-014, TASK-J003-017, TASK-J003-022]
   Wave 5: [TASK-J003-013, TASK-J003-018, TASK-J003-020]
   Wave 6: [TASK-J003-015]
   Wave 7: [TASK-J003-016, TASK-J003-019, TASK-J003-021]
   Wave 8: [TASK-J003-023, TASK-J003-024]

📁 Feature file: .guardkit/features/FEAT-J003.yaml
⚡ AutoBuild ready: /feature-build FEAT-J003

AC-quality review: 0 unverifiable acceptance criteria detected.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Feature-level smoke gates (R3) not configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This feature has 8 waves but no smoke_gates: key in the generated YAML.
Between-wave smoke checks will not fire during autobuild.

This is the gate that catches composition failures (e.g., the PEX-014..020
"13/13 green + e2e broken" pattern) that per-task Coach approval misses.

To activate: add a smoke_gates: block to the feature YAML before running
/feature-build. Minimal example:
    smoke_gates:
      after_wave_1:
        - python -c "import your_package"
      after_wave_2:
        - pytest tests/smoke -x

See installer/core/commands/feature-plan.md § "Smoke gates".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YAML landed. 0 unverifiable AC; CLI auto-detected 8 dep-chain waves (vs my conceptual 5). Now Step 8.5 pre-flight validation.

Bash Check guardkit CLI presence
IN
which guardkit 2>/dev/null || ls ~/.agentecflow/bin/guardkit 2>/dev/null || echo "NO_GUARDKIT_CLI"

OUT
/Users/richardwoollcott/.agentecflow/bin/guardkit
Bash Pre-flight feature validation
IN
guardkit feature validate FEAT-J003 2>&1 | head -60

OUT
[0;31mUnknown command: feature[0m
Run 'guardkit help' for usage information
Bash List guardkit subcommands
IN
guardkit help 2>&1 | head -50

OUT
GuardKit - Lightweight AI-Assisted Development

Usage: guardkit <command> [options]

Commands:
  init [template]     Initialize GuardKit in current directory
  autobuild <cmd>     Autonomous task implementation (Player-Coach)
  graphiti <cmd>      Knowledge graph management
  doctor              Check system health and configuration
  version             Show version information
  help                Show this help message

AutoBuild Commands:
  autobuild task TASK-XXX     Execute Player-Coach loop for a task
  autobuild status TASK-XXX   Check worktree status

Graphiti Commands:
  graphiti status             Show connection and seeding status
  graphiti seed [--force]     Seed system context into Graphiti
  graphiti verify [--verbose] Verify seeded knowledge with test queries
  graphiti seed-adrs          Seed feature-build ADRs

Examples:
  guardkit init                      # Interactive initialization
  guardkit init react-typescript     # Initialize with React template
  guardkit init fastapi-python       # Initialize with FastAPI template
  guardkit autobuild task TASK-001   # Autonomous task implementation
  guardkit graphiti status           # Check Graphiti connection
  guardkit doctor                    # Check installation health
No guardkit feature validate subcommand in this install. The generate-feature-yaml script already validated file paths via --discover and ran the AC linter (0 issues). Proceeding to Step 11 — BDD linking.

Bash Step 11.1 — Prepare BDD link request
IN
REQ_FILE=$(mktemp -t bdd-link-req-XXXXXX.json)
RESP_FILE=$(mktemp -t bdd-link-resp-XXXXXX.json)
echo "REQ=$REQ_FILE"
echo "RESP=$RESP_FILE"
python3 ~/.agentecflow/bin/feature-plan-bdd-link prepare \
  --project-root . \
  --feature-slug "feat-jarvis-003-async-subagent-and-frontier-escape" \
  --feature-yaml ".guardkit/features/FEAT-J003.yaml" \
  --output "$REQ_FILE" 2>&1
echo "---"
echo "REQ_FILE_PATH=$REQ_FILE"
echo "RESP_FILE_PATH=$RESP_FILE"

OUT
REQ=/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994
RESP=/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-resp-XXXXXX.json.WQAndEa6K1
{"status": "ready", "feature_path": "/Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature", "scenarios_to_match": 44, "task_count": 24, "confidence_threshold": 0.6, "already_tagged_count": 0, "request_path": "/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994"}
---
REQ_FILE_PATH=/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994
RESP_FILE_PATH=/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-resp-XXXXXX.json.WQAndEa6K1
Bash Read bdd-link request payload
IN
cat "/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994"

OUT
<persisted-output>
Output too large (62.9KB). Full output saved to: /Users/richardwoollcott/.claude/projects/-Users-richardwoollcott-Projects-appmilla-github-jarvis/57fcf402-a41a-4afe-a491-762aba64f2d6/tool-results/bj51k9xm8.txt

Preview (first 2KB):
{
  "feature_path": "/Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature",
  "feature_name": "Async Subagent for Model Routing + Attended Frontier Escape",
  "confidence_threshold": 0.6,
  "scenarios": [
    {
      "index": 0,
      "keyword": "Scenario",
      "name": "A single jarvis-reasoner async subagent is registered at startup",
      "description": "",
      "steps": [
        "Whenthe subagent registry is built from the configuration",
        "Thenexactly one async subagent is returned",
        "Andthe subagent is named jarvis-reasoner",
        "Andits graph identifier is jarvis_reasoner",
        "Andits description names the local model, names the three role modes, states no cloud cost, and warns against use for arithmetic, lookups, and file reads"
      ],
      "existing_tags": [
        "@key-example",
        "@smoke"
      ]
    },
    {
      "index": 1,
      "keyword": "Scenario",
      "name": "The jarvis-reasoner description carries cost and latency signals the reasoning model can read",
      "description": "",
      "steps": [
        "Whenthe supervisor receives the subagent catalogue",
        "Thenthe description states that all inference stays on the premises",
        "Andthe description states sub-second per-turn latency when the model is loaded",
        "Andthe description warns that a cold swap can take two to four minutes and the supervisor will emit a voice acknowledgement if so"
      ],
      "existing_tags": [
        "@key-example",
        "@smoke"
      ]
    },
    {
      "index": 2,
      "keyword": "Scenario",
      "name": "Dispatching to the critic role launches an async task and returns a task identifier",
      "description": "",
      "steps": [
        "Giventhe reasoning model wants an adversarial review of an architecture document",
...
</persisted-output>
Bash Check request line count
IN
wc -l "/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994"

OUT
    1067 /var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994
Update Todos

Context A captured

Graphiti context load

Create TASK-REV-J003 review task + report

Present decision checkpoint — user chose [I]mplement

Context B captured

Write 24 subtask files (Waves 1–5)

IMPLEMENTATION-GUIDE + README generated

FEAT-J003.yaml generated (24 tasks, 8 dep-chain waves, 0 unverifiable AC)

Step 11 — invoke bdd-linker subagent to tag scenarios
Now invoke the bdd-linker subagent with the matching request payload.

Read bdd-link-req-XXXXXX.json.UPXB0On994
Agent:BDD scenario-to-task matching for FEAT-J003
IN
Match the 44 Gherkin scenarios below to the 24 tasks in FEAT-JARVIS-003. Return ONLY a JSON array of TaskMatch objects — no preamble, no postamble, no markdown fences. Each match must have {scenario_index, task_id, confidence: 0.0-1.0, reason}. Use confidence_threshold 0.6 (matches below this will be dropped by the applier). Multiple scenarios can map to the same task; a scenario should match at most one task (the primary owner). The 5 Background steps are not scenarios — the 44 scenarios below are the full set.

The request payload is JSON:

```json
{
  "feature_path": "/Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature",
  "feature_name": "Async Subagent for Model Routing + Attended Frontier Escape",
  "confidence_threshold": 0.6,
  "scenarios": [
    {"index": 0, "name": "A single jarvis-reasoner async subagent is registered at startup", "existing_tags": ["@key-example","@smoke"]},
    {"index": 1, "name": "The jarvis-reasoner description carries cost and latency signals the reasoning model can read", "existing_tags": ["@key-example","@smoke"]},
    {"index": 2, "name": "Dispatching to the critic role launches an async task and returns a task identifier", "existing_tags": ["@key-example","@smoke"]},
    {"index": 3, "name": "Dispatching to the researcher role uses the open-ended research posture", "existing_tags": ["@key-example","@smoke"]},
    {"index": 4, "name": "Dispatching to the planner role uses the multi-step planning posture", "existing_tags": ["@key-example","@smoke"]},
    {"index": 5, "name": "The role prompt registry covers every member of the role enum", "existing_tags": ["@key-example"]},
    {"index": 6, "name": "Wiring the async subagent injects the five middleware operational tools", "existing_tags": ["@key-example","@smoke"]},
    {"index": 7, "name": "An attended session can escalate to the default frontier model", "existing_tags": ["@key-example","@smoke"]},
    {"index": 8, "name": "The supervisor system prompt teaches subagent routing and frontier escalation", "existing_tags": ["@key-example"]},
    {"index": 9, "name": "The repo-root langgraph manifest declares both graphs with ASGI transport", "existing_tags": ["@key-example"]},
    {"index": 10, "name": "The jarvis-reasoner subagent accepts only the three documented role values", "existing_tags": ["@boundary"]},
    {"index": 11, "name": "Unknown role values are rejected with a structured error", "existing_tags": ["@boundary","@negative"]},
    {"index": 12, "name": "Swap status above the voice-ack threshold triggers the supervisor TTS acknowledgement", "existing_tags": ["@boundary"]},
    {"index": 13, "name": "Only documented frontier targets are accepted", "existing_tags": ["@boundary"]},
    {"index": 14, "name": "An async task with an empty prompt is rejected with a missing-field error", "existing_tags": ["@boundary","@negative"]},
    {"index": 15, "name": "Swap status enforces a non-negative ETA", "existing_tags": ["@boundary"]},
    {"index": 16, "name": "An ambient session is rejected if it somehow invokes escalate_to_frontier", "existing_tags": ["@negative","@smoke"]},
    {"index": 17, "name": "A call from an async subagent frame is rejected as attended-only", "existing_tags": ["@negative"]},
    {"index": 18, "name": "escalate_to_frontier is not present in the ambient tool list at all", "existing_tags": ["@negative","@smoke"]},
    {"index": 19, "name": "Escalating to Gemini without a configured Google API key returns a configuration error", "existing_tags": ["@negative"]},
    {"index": 20, "name": "Escalating to Opus without a configured Anthropic API key returns a configuration error", "existing_tags": ["@negative"]},
    {"index": 21, "name": "Frontier provider unavailability returns a degraded result without raising", "existing_tags": ["@negative"]},
    {"index": 22, "name": "A missing llama-swap alias surfaces as a structured model-unavailable error", "existing_tags": ["@negative"]},
    {"index": 23, "name": "An async task that exceeds its timeout returns a structured timeout result", "existing_tags": ["@negative"]},
    {"index": 24, "name": "An async task missing the role field is rejected with a structured error", "existing_tags": ["@negative"]},
    {"index": 25, "name": "Adding an unsanctioned subagent does not silently appear in the registry", "existing_tags": ["@negative"]},
    {"index": 26, "name": "The supervisor routes the seven canned acceptance prompts to the expected tools", "existing_tags": ["@edge-case","@smoke"]},
    {"index": 27, "name": "Building the supervisor without async subagents preserves existing behaviour", "existing_tags": ["@edge-case"]},
    {"index": 28, "name": "Not configuring an ambient tool factory falls back to the attended tools without frontier", "existing_tags": ["@edge-case"]},
    {"index": 29, "name": "Two different role-mode tasks can run in parallel without collision", "existing_tags": ["@edge-case"]},
    {"index": 30, "name": "A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued", "existing_tags": ["@edge-case","@smoke"]},
    {"index": 31, "name": "The llama-swap adapter reports a stub source in Phase 2", "existing_tags": ["@edge-case"]},
    {"index": 32, "name": "Importing the jarvis-reasoner subagent module compiles its graph", "existing_tags": ["@edge-case"]},
    {"index": 33, "name": "A successful frontier escalation logs a structured event with target, session, correlation, adapter, instruction length, and outcome", "existing_tags": ["@edge-case"]},
    {"index": 34, "name": "The jarvis-reasoner description does not mention the retired four-subagent roster", "existing_tags": ["@edge-case","@regression"]},
    {"index": 35, "name": "The jarvis-reasoner subagent graph carries no tools of its own", "existing_tags": ["@edge-case"]},
    {"index": 36, "name": "A spoofed-ambient invocation from inside an attended session is rejected", "existing_tags": ["@edge-case","@negative","@security"]},
    {"index": 37, "name": "The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime", "existing_tags": ["@edge-case","@negative","@security"]},
    {"index": 38, "name": "A prompt-injection instruction does not bypass the attended-only gate", "existing_tags": ["@edge-case","@negative","@security"]},
    {"index": 39, "name": "Cancelling a running jarvis-reasoner task transitions it cleanly to a cancelled status", "existing_tags": ["@edge-case","@concurrency"]},
    {"index": 40, "name": "Checking an unknown task identifier returns a structured no-such-task result", "existing_tags": ["@edge-case","@negative"]},
    {"index": 41, "name": "The session correlation identifier propagates from input through to check-task results", "existing_tags": ["@edge-case","@integrity"]},
    {"index": 42, "name": "An empty frontier response is reported as a degraded outcome", "existing_tags": ["@edge-case","@negative","@integration"]},
    {"index": 43, "name": "Repeated swap-status reads for the same alias return consistent results", "existing_tags": ["@edge-case","@integration"]}
  ],
  "tasks": [
    {"task_id": "TASK-J003-001", "title": "Extend JarvisConfig with FEAT-JARVIS-003 fields"},
    {"task_id": "TASK-J003-002", "title": "Define RoleName + FrontierTarget closed enums"},
    {"task_id": "TASK-J003-003", "title": "Define AsyncTaskInput + SwapStatus Pydantic models"},
    {"task_id": "TASK-J003-004", "title": "Define FrontierEscalationContext Pydantic model"},
    {"task_id": "TASK-J003-005", "title": "Role prompt registry module + 3 role prompts"},
    {"task_id": "TASK-J003-006", "title": "pyproject provider SDKs and langgraph dev dep"},
    {"task_id": "TASK-J003-007", "title": "Implement LlamaSwapAdapter with stubbed health"},
    {"task_id": "TASK-J003-008", "title": "Implement jarvis_reasoner subagent graph"},
    {"task_id": "TASK-J003-009", "title": "Implement subagent_registry build_async_subagents"},
    {"task_id": "TASK-J003-010", "title": "Implement escalate_to_frontier Layer 1 body"},
    {"task_id": "TASK-J003-011", "title": "Implement escalate_to_frontier Layer 2 executor assertion"},
    {"task_id": "TASK-J003-012", "title": "assemble_tool_list session-aware Layer 3 standalone"},
    {"task_id": "TASK-J003-013", "title": "Extend build_supervisor signature"},
    {"task_id": "TASK-J003-014", "title": "Extend supervisor_prompt Subagent Routing + Frontier Escalation"},
    {"task_id": "TASK-J003-015", "title": "Extend lifecycle startup with subagents and ambient factory"},
    {"task_id": "TASK-J003-016", "title": "langgraph.json at repo root"},
    {"task_id": "TASK-J003-017", "title": "Unit tests subagent layer"},
    {"task_id": "TASK-J003-018", "title": "Unit tests escalate_to_frontier three layers"},
    {"task_id": "TASK-J003-019", "title": "Unit tests LlamaSwapAdapter and voice-ack"},
    {"task_id": "TASK-J003-020", "title": "Regression test no retired-roster strings"},
    {"task_id": "TASK-J003-021", "title": "Integration test supervisor_with_subagents"},
    {"task_id": "TASK-J003-022", "title": "Integration test role propagation"},
    {"task_id": "TASK-J003-023", "title": "Acceptance test test_routing_e2e 7 prompts"},
    {"task_id": "TASK-J003-024", "title": "langgraph.json smoke validation"}
  ]
}
```

Guidance for high-quality matches (read the IMPLEMENTATION-GUIDE at tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/IMPLEMENTATION-GUIDE.md if you need the §4 Integration Contracts — they tell you which task owns each invariant). Prefer implementation tasks over test tasks when a scenario describes observable behaviour of the implementation surface. Map test-specific scenarios to test tasks only when there's no implementation task that more directly owns the observable behaviour. The "Adding an unsanctioned subagent..." scenario (index 25) owns the retired-roster invariant — it can reasonably map to TASK-J003-009 (registry source) OR TASK-J003-020 (grep regression); pick the one with stronger semantic match.

Return ONLY the JSON array. Do not wrap it in an object. Do not add prose.
Read IMPLEMENTATION-GUIDE.md
All 44 scenarios matched with confidence ≥ 0.80 (well above 0.60 threshold). Writing response file and applying matches.

Write bdd-link-resp-XXXXXX.json.WQAndEa6K1
Write failed
[{"scenario_index":0,"task_id":"TASK-J003-009","confidence":0.91,"reason":"Scenario asserts a single jarvis-reasoner async subagent is registered at startup — directly owned by build_async_subagents in the subagent_registry task."},{"scenario_index":1,"task_id":"TASK-J003-009","confidence":0.90,"reason":"Scenario asserts the jarvis-reasoner description carries cost and latency signals — the description string is produced by build_async_subagents (Contract 6 specifies exact substrings it must contain)."},{"scenario_index":2,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Dispatching to critic role launches an async task and returns a task identifier — the jarvis_reasoner subagent graph handles role resolution and task dispatch; critic is one of its three role values."},{"scenario_index":3,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Dispatching to researcher role uses open-ended research posture — the jarvis_reasoner graph first-node reads ROLE_PROMPTS[RoleName.RESEARCHER] to set posture."},{"scenario_index":4,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Dispatching to planner role uses multi-step planning posture — same graph first-node reads ROLE_PROMPTS[RoleName.PLANNER]."},{"scenario_index":5,"task_id":"TASK-J003-005","confidence":0.92,"reason":"Scenario asserts the role prompt registry covers every member of the role enum — directly owned by the ROLE_PROMPTS registry module (Contract 5 exhaustiveness invariant)."},{"scenario_index":6,"task_id":"TASK-J003-012","confidence":0.89,"reason":"Wiring the async subagent injects the five middleware operational tools — assemble_tool_list Layer 3 is the component that assembles and injects the tool list into the attended session wiring."},{"scenario_index":7,"task_id":"TASK-J003-010","confidence":0.91,"reason":"An attended session can escalate to the default frontier model — directly owned by the escalate_to_frontier Layer 1 body which handles the happy-path attended escalation."},{"scenario_index":8,"task_id":"TASK-J003-014","confidence":0.92,"reason":"Supervisor system prompt teaches subagent routing and frontier escalation — directly owned by the supervisor_prompt Subagent Routing + Frontier Escalation sections task."},{"scenario_index":9,"task_id":"TASK-J003-016","confidence":0.93,"reason":"Repo-root langgraph manifest declares both graphs with ASGI transport — directly owned by the langgraph.json at repo root task."},{"scenario_index":10,"task_id":"TASK-J003-002","confidence":0.91,"reason":"jarvis-reasoner subagent accepts only the three documented role values — directly owned by the RoleName closed enum definition (Contract 1: exactly three members)."},{"scenario_index":11,"task_id":"TASK-J003-008","confidence":0.85,"reason":"Unknown role values are rejected with a structured error — the jarvis_reasoner graph first-node routes to unknown_role branch when RoleName() raises ValueError (Contract 1 format constraint)."},{"scenario_index":12,"task_id":"TASK-J003-019","confidence":0.82,"reason":"Swap status above the voice-ack threshold triggers supervisor TTS acknowledgement — this boundary is specifically tested in the LlamaSwapAdapter and voice-ack unit tests (Contract 3 boundary table)."},{"scenario_index":13,"task_id":"TASK-J003-002","confidence":0.90,"reason":"Only documented frontier targets are accepted — directly owned by the FrontierTarget closed enum definition (Contract 2: exactly two members, out-of-enum rejected)."},{"scenario_index":14,"task_id":"TASK-J003-003","confidence":0.88,"reason":"An async task with an empty prompt is rejected with a missing-field error — owned by AsyncTaskInput Pydantic model validation (required field constraint)."},{"scenario_index":15,"task_id":"TASK-J003-003","confidence":0.89,"reason":"Swap status enforces a non-negative ETA — directly owned by SwapStatus model with eta_seconds: int >= 0 constraint (Contract 3 format constraint)."},{"scenario_index":16,"task_id":"TASK-J003-011","confidence":0.90,"reason":"An ambient session is rejected if it somehow invokes escalate_to_frontier — owned by Layer 2 executor assertion which checks adapter_id against attended_adapter_ids set."},{"scenario_index":17,"task_id":"TASK-J003-011","confidence":0.91,"reason":"A call from an async subagent frame is rejected as attended-only — directly owned by Layer 2 executor assertion's is_inside_async_subagent_frame() check."},{"scenario_index":18,"task_id":"TASK-J003-012","confidence":0.92,"reason":"escalate_to_frontier is not present in the ambient tool list at all — Layer 3 registration-absence invariant is owned by assemble_tool_list (Contract 7: when include_frontier=False, escalate_to_frontier excluded)."},{"scenario_index":19,"task_id":"TASK-J003-010","confidence":0.89,"reason":"Escalating to Gemini without a configured Google API key returns a configuration error — Layer 1 body handles the missing API key branch for gemini_api_key (Contract 4 outcome=config_missing)."},{"scenario_index":20,"task_id":"TASK-J003-010","confidence":0.89,"reason":"Escalating to Opus without a configured Anthropic API key returns a configuration error — Layer 1 body handles the missing API key branch for anthropic_api_key (Contract 4 outcome=config_missing)."},{"scenario_index":21,"task_id":"TASK-J003-010","confidence":0.87,"reason":"Frontier provider unavailability returns a degraded result without raising — Layer 1 body provider_unavailable branch (Contract 4 outcome=provider_unavailable)."},{"scenario_index":22,"task_id":"TASK-J003-007","confidence":0.88,"reason":"A missing llama-swap alias surfaces as a structured model-unavailable error — directly owned by LlamaSwapAdapter stubbed health implementation which must return structured error for unknown aliases."},{"scenario_index":23,"task_id":"TASK-J003-003","confidence":0.82,"reason":"An async task that exceeds its timeout returns a structured timeout result — owned by AsyncTaskInput model which defines the task envelope shape including timeout handling constraints."},{"scenario_index":24,"task_id":"TASK-J003-003","confidence":0.88,"reason":"An async task missing the role field is rejected with a structured error — owned by AsyncTaskInput Pydantic model with role as required field."},{"scenario_index":25,"task_id":"TASK-J003-009","confidence":0.83,"reason":"Adding an unsanctioned subagent does not silently appear in the registry — owned by build_async_subagents which is the sole constructor of the authoritative subagent list; the registry's closed construction is the direct guard."},{"scenario_index":26,"task_id":"TASK-J003-023","confidence":0.93,"reason":"Supervisor routes the seven canned acceptance prompts to the expected tools — directly owned by acceptance test test_routing_e2e 7 prompts task."},{"scenario_index":27,"task_id":"TASK-J003-013","confidence":0.87,"reason":"Building the supervisor without async subagents preserves existing behaviour — owned by extend build_supervisor signature task which must handle empty subagents list gracefully."},{"scenario_index":28,"task_id":"TASK-J003-015","confidence":0.85,"reason":"Not configuring an ambient tool factory falls back to attended tools without frontier — owned by lifecycle startup which calls assemble_tool_list and manages the ambient_tool_factory fallback path."},{"scenario_index":29,"task_id":"TASK-J003-022","confidence":0.88,"reason":"Two different role-mode tasks can run in parallel without collision — directly owned by integration test role propagation which verifies role isolation across concurrent dispatches."},{"scenario_index":30,"task_id":"TASK-J003-019","confidence":0.90,"reason":"A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued — directly owned by unit tests LlamaSwapAdapter and voice-ack (Contract 3 boundary table ETA threshold)."},{"scenario_index":31,"task_id":"TASK-J003-007","confidence":0.91,"reason":"The llama-swap adapter reports a stub source in Phase 2 — directly owned by LlamaSwapAdapter with stubbed health; Contract 3 specifies source=stub invariant for Phase 2."},{"scenario_index":32,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Importing the jarvis-reasoner subagent module compiles its graph — directly owned by the jarvis_reasoner subagent graph implementation task (module-scope compiled graph variable)."},{"scenario_index":33,"task_id":"TASK-J003-004","confidence":0.91,"reason":"A successful frontier escalation logs a structured event with target, session, correlation, adapter, instruction length, and outcome — directly owned by FrontierEscalationContext Pydantic model and log_frontier_escalation helper (Contract 4 exact field set)."},{"scenario_index":34,"task_id":"TASK-J003-020","confidence":0.92,"reason":"The jarvis-reasoner description does not mention the retired four-subagent roster — directly owned by regression test no retired-roster strings (Contract 6 MUST NOT contain substrings)."},{"scenario_index":35,"task_id":"TASK-J003-008","confidence":0.87,"reason":"The jarvis-reasoner subagent graph carries no tools of its own — owned by the jarvis_reasoner graph implementation which must be defined without a tools list per design."},{"scenario_index":36,"task_id":"TASK-J003-011","confidence":0.90,"reason":"A spoofed-ambient invocation from inside an attended session is rejected — owned by Layer 2 executor assertion; the is_inside_async_subagent_frame() check catches this spoofing case per the sequence diagram."},{"scenario_index":37,"task_id":"TASK-J003-012","confidence":0.91,"reason":"The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime — owned by assemble_tool_list Layer 3 which returns a new list each call (Contract 7 mutation-isolation invariant, ADR-ARCH-023)."},{"scenario_index":38,"task_id":"TASK-J003-011","confidence":0.88,"reason":"A prompt-injection instruction does not bypass the attended-only gate — owned by Layer 2 executor assertion which enforces the gate regardless of instruction content."},{"scenario_index":39,"task_id":"TASK-J003-017","confidence":0.82,"reason":"Cancelling a running jarvis-reasoner task transitions it cleanly to a cancelled status — owned by unit tests subagent layer which covers task lifecycle state transitions."},{"scenario_index":40,"task_id":"TASK-J003-017","confidence":0.80,"reason":"Checking an unknown task identifier returns a structured no-such-task result — owned by unit tests subagent layer which covers task-check edge cases."},{"scenario_index":41,"task_id":"TASK-J003-022","confidence":0.85,"reason":"The session correlation identifier propagates from input through to check-task results — owned by integration test role propagation which verifies correlation_id flows end-to-end through dispatch and check-task."},{"scenario_index":42,"task_id":"TASK-J003-010","confidence":0.85,"reason":"An empty frontier response is reported as a degraded outcome — Layer 1 body degraded_empty branch (Contract 4 outcome=degraded_empty, sequence diagram empty body path)."},{"scenario_index":43,"task_id":"TASK-J003-019","confidence":0.83,"reason":"Repeated swap-status reads for the same alias return consistent results — owned by unit tests LlamaSwapAdapter which exercises the stub health endpoint for idempotency."}]
Bash Write bdd-linker response to RESP_FILE
IN
cat > "/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-resp-XXXXXX.json.WQAndEa6K1" <<'JSON_EOF'
[{"scenario_index":0,"task_id":"TASK-J003-009","confidence":0.91,"reason":"Scenario asserts a single jarvis-reasoner async subagent is registered at startup — directly owned by build_async_subagents in the subagent_registry task."},{"scenario_index":1,"task_id":"TASK-J003-009","confidence":0.90,"reason":"Scenario asserts the jarvis-reasoner description carries cost and latency signals — the description string is produced by build_async_subagents (Contract 6 specifies exact substrings it must contain)."},{"scenario_index":2,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Dispatching to critic role launches an async task and returns a task identifier — the jarvis_reasoner subagent graph handles role resolution and task dispatch; critic is one of its three role values."},{"scenario_index":3,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Dispatching to researcher role uses open-ended research posture — the jarvis_reasoner graph first-node reads ROLE_PROMPTS[RoleName.RESEARCHER] to set posture."},{"scenario_index":4,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Dispatching to planner role uses multi-step planning posture — same graph first-node reads ROLE_PROMPTS[RoleName.PLANNER]."},{"scenario_index":5,"task_id":"TASK-J003-005","confidence":0.92,"reason":"Scenario asserts the role prompt registry covers every member of the role enum — directly owned by the ROLE_PROMPTS registry module (Contract 5 exhaustiveness invariant)."},{"scenario_index":6,"task_id":"TASK-J003-012","confidence":0.89,"reason":"Wiring the async subagent injects the five middleware operational tools — assemble_tool_list Layer 3 is the component that assembles and injects the tool list into the attended session wiring."},{"scenario_index":7,"task_id":"TASK-J003-010","confidence":0.91,"reason":"An attended session can escalate to the default frontier model — directly owned by the escalate_to_frontier Layer 1 body which handles the happy-path attended escalation."},{"scenario_index":8,"task_id":"TASK-J003-014","confidence":0.92,"reason":"Supervisor system prompt teaches subagent routing and frontier escalation — directly owned by the supervisor_prompt Subagent Routing + Frontier Escalation sections task."},{"scenario_index":9,"task_id":"TASK-J003-016","confidence":0.93,"reason":"Repo-root langgraph manifest declares both graphs with ASGI transport — directly owned by the langgraph.json at repo root task."},{"scenario_index":10,"task_id":"TASK-J003-002","confidence":0.91,"reason":"jarvis-reasoner subagent accepts only the three documented role values — directly owned by the RoleName closed enum definition (Contract 1: exactly three members)."},{"scenario_index":11,"task_id":"TASK-J003-008","confidence":0.85,"reason":"Unknown role values are rejected with a structured error — the jarvis_reasoner graph first-node routes to unknown_role branch when RoleName() raises ValueError (Contract 1 format constraint)."},{"scenario_index":12,"task_id":"TASK-J003-019","confidence":0.82,"reason":"Swap status above the voice-ack threshold triggers supervisor TTS acknowledgement — this boundary is specifically tested in the LlamaSwapAdapter and voice-ack unit tests (Contract 3 boundary table)."},{"scenario_index":13,"task_id":"TASK-J003-002","confidence":0.90,"reason":"Only documented frontier targets are accepted — directly owned by the FrontierTarget closed enum definition (Contract 2: exactly two members, out-of-enum rejected)."},{"scenario_index":14,"task_id":"TASK-J003-003","confidence":0.88,"reason":"An async task with an empty prompt is rejected with a missing-field error — owned by AsyncTaskInput Pydantic model validation (required field constraint)."},{"scenario_index":15,"task_id":"TASK-J003-003","confidence":0.89,"reason":"Swap status enforces a non-negative ETA — directly owned by SwapStatus model with eta_seconds: int >= 0 constraint (Contract 3 format constraint)."},{"scenario_index":16,"task_id":"TASK-J003-011","confidence":0.90,"reason":"An ambient session is rejected if it somehow invokes escalate_to_frontier — owned by Layer 2 executor assertion which checks adapter_id against attended_adapter_ids set."},{"scenario_index":17,"task_id":"TASK-J003-011","confidence":0.91,"reason":"A call from an async subagent frame is rejected as attended-only — directly owned by Layer 2 executor assertion's is_inside_async_subagent_frame() check."},{"scenario_index":18,"task_id":"TASK-J003-012","confidence":0.92,"reason":"escalate_to_frontier is not present in the ambient tool list at all — Layer 3 registration-absence invariant is owned by assemble_tool_list (Contract 7: when include_frontier=False, escalate_to_frontier excluded)."},{"scenario_index":19,"task_id":"TASK-J003-010","confidence":0.89,"reason":"Escalating to Gemini without a configured Google API key returns a configuration error — Layer 1 body handles the missing API key branch for gemini_api_key (Contract 4 outcome=config_missing)."},{"scenario_index":20,"task_id":"TASK-J003-010","confidence":0.89,"reason":"Escalating to Opus without a configured Anthropic API key returns a configuration error — Layer 1 body handles the missing API key branch for anthropic_api_key (Contract 4 outcome=config_missing)."},{"scenario_index":21,"task_id":"TASK-J003-010","confidence":0.87,"reason":"Frontier provider unavailability returns a degraded result without raising — Layer 1 body provider_unavailable branch (Contract 4 outcome=provider_unavailable)."},{"scenario_index":22,"task_id":"TASK-J003-007","confidence":0.88,"reason":"A missing llama-swap alias surfaces as a structured model-unavailable error — directly owned by LlamaSwapAdapter stubbed health implementation which must return structured error for unknown aliases."},{"scenario_index":23,"task_id":"TASK-J003-003","confidence":0.82,"reason":"An async task that exceeds its timeout returns a structured timeout result — owned by AsyncTaskInput model which defines the task envelope shape including timeout handling constraints."},{"scenario_index":24,"task_id":"TASK-J003-003","confidence":0.88,"reason":"An async task missing the role field is rejected with a structured error — owned by AsyncTaskInput Pydantic model with role as required field."},{"scenario_index":25,"task_id":"TASK-J003-009","confidence":0.83,"reason":"Adding an unsanctioned subagent does not silently appear in the registry — owned by build_async_subagents which is the sole constructor of the authoritative subagent list; the registry's closed construction is the direct guard."},{"scenario_index":26,"task_id":"TASK-J003-023","confidence":0.93,"reason":"Supervisor routes the seven canned acceptance prompts to the expected tools — directly owned by acceptance test test_routing_e2e 7 prompts task."},{"scenario_index":27,"task_id":"TASK-J003-013","confidence":0.87,"reason":"Building the supervisor without async subagents preserves existing behaviour — owned by extend build_supervisor signature task which must handle empty subagents list gracefully."},{"scenario_index":28,"task_id":"TASK-J003-015","confidence":0.85,"reason":"Not configuring an ambient tool factory falls back to attended tools without frontier — owned by lifecycle startup which calls assemble_tool_list and manages the ambient_tool_factory fallback path."},{"scenario_index":29,"task_id":"TASK-J003-022","confidence":0.88,"reason":"Two different role-mode tasks can run in parallel without collision — directly owned by integration test role propagation which verifies role isolation across concurrent dispatches."},{"scenario_index":30,"task_id":"TASK-J003-019","confidence":0.90,"reason":"A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued — directly owned by unit tests LlamaSwapAdapter and voice-ack (Contract 3 boundary table ETA threshold)."},{"scenario_index":31,"task_id":"TASK-J003-007","confidence":0.91,"reason":"The llama-swap adapter reports a stub source in Phase 2 — directly owned by LlamaSwapAdapter with stubbed health; Contract 3 specifies source=stub invariant for Phase 2."},{"scenario_index":32,"task_id":"TASK-J003-008","confidence":0.88,"reason":"Importing the jarvis-reasoner subagent module compiles its graph — directly owned by the jarvis_reasoner subagent graph implementation task (module-scope compiled graph variable)."},{"scenario_index":33,"task_id":"TASK-J003-004","confidence":0.91,"reason":"A successful frontier escalation logs a structured event with target, session, correlation, adapter, instruction length, and outcome — directly owned by FrontierEscalationContext Pydantic model and log_frontier_escalation helper (Contract 4 exact field set)."},{"scenario_index":34,"task_id":"TASK-J003-020","confidence":0.92,"reason":"The jarvis-reasoner description does not mention the retired four-subagent roster — directly owned by regression test no retired-roster strings (Contract 6 MUST NOT contain substrings)."},{"scenario_index":35,"task_id":"TASK-J003-008","confidence":0.87,"reason":"The jarvis-reasoner subagent graph carries no tools of its own — owned by the jarvis_reasoner graph implementation which must be defined without a tools list per design."},{"scenario_index":36,"task_id":"TASK-J003-011","confidence":0.90,"reason":"A spoofed-ambient invocation from inside an attended session is rejected — owned by Layer 2 executor assertion; the is_inside_async_subagent_frame() check catches this spoofing case per the sequence diagram."},{"scenario_index":37,"task_id":"TASK-J003-012","confidence":0.91,"reason":"The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime — owned by assemble_tool_list Layer 3 which returns a new list each call (Contract 7 mutation-isolation invariant, ADR-ARCH-023)."},{"scenario_index":38,"task_id":"TASK-J003-011","confidence":0.88,"reason":"A prompt-injection instruction does not bypass the attended-only gate — owned by Layer 2 executor assertion which enforces the gate regardless of instruction content."},{"scenario_index":39,"task_id":"TASK-J003-017","confidence":0.82,"reason":"Cancelling a running jarvis-reasoner task transitions it cleanly to a cancelled status — owned by unit tests subagent layer which covers task lifecycle state transitions."},{"scenario_index":40,"task_id":"TASK-J003-017","confidence":0.80,"reason":"Checking an unknown task identifier returns a structured no-such-task result — owned by unit tests subagent layer which covers task-check edge cases."},{"scenario_index":41,"task_id":"TASK-J003-022","confidence":0.85,"reason":"The session correlation identifier propagates from input through to check-task results — owned by integration test role propagation which verifies correlation_id flows end-to-end through dispatch and check-task."},{"scenario_index":42,"task_id":"TASK-J003-010","confidence":0.85,"reason":"An empty frontier response is reported as a degraded outcome — Layer 1 body degraded_empty branch (Contract 4 outcome=degraded_empty, sequence diagram empty body path)."},{"scenario_index":43,"task_id":"TASK-J003-019","confidence":0.83,"reason":"Repeated swap-status reads for the same alias return consistent results — owned by unit tests LlamaSwapAdapter which exercises the stub health endpoint for idempotency."}]
JSON_EOF
echo "wrote $(wc -c < /var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-resp-XXXXXX.json.WQAndEa6K1) bytes"

OUT
wrote    11353 bytes
Bash Step 11.3 — Apply BDD task-matches to feature file
IN
python3 ~/.agentecflow/bin/feature-plan-bdd-link apply \
  --project-root . \
  --feature-slug "feat-jarvis-003-async-subagent-and-frontier-escape" \
  --task-matches-file "/var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-resp-XXXXXX.json.WQAndEa6K1" 2>&1

OUT
[Step 11] linked 44 scenario(s) to task(s); 0 already tagged; 0 below threshold (0.60) (of 44 total)
All 44 scenarios tagged. Verifying the feature file now carries @task:TASK-J003-xxx tags.

Grep "@task:TASK-J003" (in /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature)
2 lines of output
Bash Cleanup temp files + list final artefacts
IN
rm -f /var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-req-XXXXXX.json.UPXB0On994 /var/folders/75/prgjl4_x0k3_6tj58k39db1r0000gn/T/bdd-link-resp-XXXXXX.json.WQAndEa6K1
ls .guardkit/features/FEAT-J003.yaml tasks/in_review/TASK-REV-J003*.md .claude/reviews/TASK-REV-J003* tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/ 2>&1 | head -40

OUT
.claude/reviews/TASK-REV-J003-review-report.md
.guardkit/features/FEAT-J003.yaml
tasks/in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md

tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/:
IMPLEMENTATION-GUIDE.md
README.md
TASK-J003-001-extend-jarvisconfig-with-feat-j003-fields.md
TASK-J003-002-define-rolename-frontiertarget-closed-enums.md
TASK-J003-003-define-asynctaskinput-swapstatus-pydantic-models.md
TASK-J003-004-define-frontierescalationcontext-pydantic-model.md
TASK-J003-005-role-prompt-registry-module-and-3-prompts.md
TASK-J003-006-pyproject-provider-sdks-and-langgraph-dep.md
TASK-J003-007-implement-llamaswap-adapter-with-stubbed-health.md
TASK-J003-008-implement-jarvis-reasoner-subagent-graph.md
TASK-J003-009-implement-subagent-registry-build-async-subagents.md
TASK-J003-010-implement-escalate-to-frontier-layer-1-body.md
TASK-J003-011-implement-escalate-to-frontier-layer-2-executor-assertion.md
TASK-J003-012-assemble-tool-list-session-aware-layer-3.md
TASK-J003-013-extend-build-supervisor-signature.md
TASK-J003-014-extend-supervisor-prompt-subagent-routing-and-frontier-escalation.md
TASK-J003-015-extend-lifecycle-startup-with-subagents-and-ambient-factory.md
TASK-J003-016-langgraph-json-at-repo-root.md
TASK-J003-017-unit-tests-subagent-layer.md
TASK-J003-018-unit-tests-escalate-to-frontier.md
TASK-J003-019-unit-tests-llamaswap-adapter-and-voice-ack.md
TASK-J003-020-regression-test-no-retired-roster-strings.md
TASK-J003-021-integration-test-supervisor-with-subagents.md
TASK-J003-022-integration-test-role-propagation.md
TASK-J003-023-acceptance-test-routing-e2e.md
TASK-J003-024-langgraph-json-smoke-validation.md
Update Todos

Context A captured

Graphiti context load

Create TASK-REV-J003 review task + report

Decision checkpoint — [I]mplement chosen

Context B captured

Write 24 subtask files

IMPLEMENTATION-GUIDE + README generated

FEAT-J003.yaml generated

Step 11 BDD linking — 44/44 scenarios tagged with @task:TASK-J003-xxx
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE PLANNING COMPLETE — FEAT-JARVIS-003
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artefacts landed:

Review: .claude/reviews/TASK-REV-J003-review-report.md (3 options analysed, Option B ★ 12/12)
Review task: tasks/in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md (status: review_complete)
AutoBuild YAML: .guardkit/features/FEAT-J003.yaml — 24 tasks, auto-detected 8 dep-chain waves, 0 unverifiable AC
Task breakdown: 24 markdown files under tasks/backlog/feat-jarvis-003-async-subagent-and-frontier-escape/
Implementation guide: IMPLEMENTATION-GUIDE.md — Mermaid data-flow + gate sequence + dependency graph + §4 Integration Contracts (8 load-bearing contracts)
Feature README: README.md
BDD-linked feature file: 44/44 scenarios tagged with @task:TASK-J003-xxx (avg confidence 0.88, 0 below threshold) — R2 BDD oracle active during /task-work Phase 4
Approach adopted: Option B — envelope-first concurrent fan-out. Max task complexity 6 (Coach-Player stall mitigation). Three-layer belt+braces gate split into L1 (010) / L2 (011) / L3 (012) standalone tasks per Context A concerns. Regression (020) + role-propagation integration (022) are standalone.

Non-blocking notices from the planner:

R3 smoke-gates block not declared in YAML — optional, add smoke_gates: before running /feature-build if you want between-wave smoke checks.
Step 8.5 pre-flight validation skipped (no guardkit feature validate subcommand in this install). generate-feature-yaml --discover already validated all 24 task-file paths and dep chains.
Ready for Step 8. /feature-build FEAT-J003 — AutoBuild cycle over the 24 subtasks; Coach-Player loop per subtask; R2 BDD oracle runs tagged scenarios per task during /task-work Phase 4.