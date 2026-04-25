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
