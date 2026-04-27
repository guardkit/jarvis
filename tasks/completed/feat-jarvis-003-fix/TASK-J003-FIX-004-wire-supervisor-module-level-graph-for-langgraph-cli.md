---
complexity: 3
created: 2026-04-27 00:00:00+00:00
dependencies: []
estimated_minutes: 45
feature_id: FEAT-J003-FIX
id: TASK-J003-FIX-004
implementation_mode: task-work
parent_review: FEAT-JARVIS-003
priority: high
status: completed
completed: '2026-04-27T00:00:00+00:00'
test_results:
  status: pass
  last_run: 2026-04-27
  ruff: "All checks passed!"
  mypy: "Success: no issues found in 39 source files"
  pytest: "1596 passed, 2 skipped"
  red_phase_commit: 4536bb8
  green_phase_commit: 9f49ae3
tags:
- phase-2
- jarvis
- feat-jarvis-003-fix
- langgraph
- deployment
- ddr-013
- tdd
task_type: bugfix
title: Wire supervisor module-level graph symbol so langgraph dev can spin both graphs
updated: 2026-04-27 00:00:00+00:00
wave: 3
---

# Wire supervisor module-level graph symbol so langgraph dev can spin both graphs

**Feature:** FEAT-J003-FIX
**Wave:** 3 | **Mode:** task-work (TDD) | **Complexity:** 3/10
**Parent review:** [FEAT-JARVIS-003 review report](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md) — Finding F8 (newly surfaced 2026-04-27 during Phase-2 manual close-out)
**ADR/DDR:** DDR-013 (`langgraph.json` at repo root with two ASGI graphs), DDR-012 (`jarvis_reasoner` module-import compilation precedent)

## Description

Phase-2 close criterion #6 (`langgraph dev` spins both graphs locally) cannot be validated today: `langgraph.json` declares `./src/jarvis/agents/supervisor.py:graph` but the supervisor module exposes only the `build_supervisor(config)` factory function — **there is no module-level `graph` symbol**. The langgraph CLI imports the path, looks up the symbol, and will fail with `AttributeError` at server startup.

```bash
$ uv run python -c "from jarvis.agents.supervisor import graph"
ImportError: cannot import name 'graph' from 'jarvis.agents.supervisor'
```

The `jarvis_reasoner.py` side is fine — DDR-012 mandated module-import compilation and `jarvis_reasoner.py:393` exposes `graph: CompiledStateGraph[...] = _build_graph()`. The supervisor side was never given the equivalent wiring.

The TASK-J003-024 smoke test (`test_jarvis_graph_path_resolves_to_supervisor_module`) only asserts that the *file* exists, not that the *symbol* resolves — which is why the regression slipped past the AutoBuild quality gate.

## Decision: factory-function form, not eager module-level compile

Two viable shapes:

**(A) Eager compile (mirroring `jarvis_reasoner.py`)**
```python
# Bottom of supervisor.py:
graph: CompiledStateGraph[Any, Any, Any, Any] = build_supervisor(JarvisConfig())
```
Drawbacks: triggers eager `JarvisConfig()` + `init_chat_model` + `assemble_tool_list` + capability-registry load at *import* time. Re-introduces F2-class fragility (test collection, missing `stub_capabilities.yaml`, etc.). Bypasses `lifecycle.build_app_state` so Layer 2 hooks would NOT be wired — silently regresses FIX-001.

**(B) Factory function delegating to lifecycle (chosen)**
```python
# In supervisor.py:
def make_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """Factory consumed by ``langgraph.json`` to materialise the supervisor.

    Delegates to :func:`jarvis.infrastructure.lifecycle.build_app_state` so
    every constitutional invariant (Layer 2 hook wiring per DDR-014, ambient
    tool factory per ADR-ARCH-027, capability snapshot per ASSUM-006) holds
    when the langgraph CLI loads the graph — not just when ``jarvis chat``
    builds it.
    """
    state = asyncio.run(build_app_state(JarvisConfig()))
    return state.supervisor
```
Then `langgraph.json`:
```json
"jarvis": { "path": "./src/jarvis/agents/supervisor.py:make_graph", "transport": "asgi" }
```

The factory form keeps imports side-effect-free (preserves the FIX-003 fresh-env collection fix) and matches the supervisor's contract: *"a fully-wired runtime, not a bare CompiledStateGraph"*.

## Acceptance Criteria

- [x] **TDD red phase.** Strengthen `tests/test_langgraph_json.py::test_jarvis_graph_path_resolves_to_supervisor_module` (or add a sibling test) so it actually imports the `module:variable` path and asserts the symbol resolves to a `CompiledStateGraph` (or a callable returning one). Test must FAIL on `main` today (proving F8). Commit the failing test on its own commit. ✅ `4536bb8` adds `TestJarvisGraphSymbolResolves` (3 sibling tests); all three failed on the pre-fix tree.
- [x] `src/jarvis/agents/supervisor.py` exposes a module-level `make_graph()` callable that returns a fully-wired `CompiledStateGraph`. Implementation delegates to `lifecycle.build_app_state(JarvisConfig())` — does NOT duplicate lifecycle wiring inline. ✅ `9f49ae3` — body lazy-imports `JarvisConfig` and `build_app_state`, runs `asyncio.run(build_app_state(JarvisConfig())).supervisor`.
- [x] `langgraph.json` updated: `"jarvis"` graph `path` field changed from `:graph` to `:make_graph`. The `jarvis_reasoner` graph stays at `:graph` (DDR-012's eager compile works correctly there). ✅ Verified — `jarvis_reasoner` line untouched in green commit.
- [x] **TDD green phase.** The strengthened smoke test now passes — both `from jarvis.agents.supervisor import make_graph; make_graph()` and `from jarvis.agents.subagents.jarvis_reasoner import graph` resolve to objects langgraph CLI can serve. ✅ All 29 tests in `test_langgraph_json.py` pass.
- [ ] **End-to-end manual smoke** (operator-side, documented in the task closeout note): `OPENAI_API_KEY=stub uv run python -m langgraph dev` starts without traceback; `curl http://127.0.0.1:2024/assistants/search -X POST -H 'Content-Type: application/json' -d '{}'` returns both `"graph_id": "jarvis"` and `"graph_id": "jarvis_reasoner"`. (Does NOT require llama-swap up — graph compilation only instantiates wrappers.) ⏸️ Operator-side; not run in this session — closes Phase-2 criterion #6 once executed.
- [x] Existing regression intact: `tests/test_langgraph_json.py` 26-test suite still passes; the strengthened symbol-resolution test is additive, not replacing. ✅ 26 originals + 3 new = 29 passed.
- [x] `mypy src/jarvis/` and `ruff check src/jarvis/` remain clean (zero errors). The new `make_graph` carries a return-type annotation and a docstring per project style. ✅ `mypy: Success: no issues found in 39 source files`; `ruff: All checks passed!`.
- [x] Layer 2 hooks remain wired post-`make_graph()` invocation — add an assertion that `dispatch._current_session_hook is not None` after calling `make_graph()`. Proves the factory honours FIX-001. ✅ `test_jarvis_graph_factory_invocation_wires_layer2_hooks` asserts both `_current_session_hook` and `_async_subagent_frame_hook` are non-None after invocation.
- [x] No new `# type: ignore` or `# noqa` without inline justification. ✅ None added.
- [x] `OPENAI_API_KEY=stub uv run pytest tests/` continues to report ≥1593 passed (the post-FIX baseline; new tests add to the count). ✅ `1596 passed, 2 skipped` (1593 baseline + 3 new symbol-resolution tests).

## Files Expected to Change

- `src/jarvis/agents/supervisor.py` — add `make_graph()` factory function at module scope; lazy-import `JarvisConfig` and `build_app_state` inside the factory body to keep import-time side-effects nil.
- `langgraph.json` — `:graph` → `:make_graph` for the `jarvis` graph entry only.
- `tests/test_langgraph_json.py` — strengthen the symbol-resolution test (importlib-based) + add a `make_graph()` invocation + Layer-2-hook-still-wired assertion.

## Out of scope

- Changing `jarvis_reasoner.py`'s eager-compile pattern. DDR-012 ratified that decision and the `:graph` symbol there resolves correctly.
- Adding integration tests that run a real `langgraph dev` server (subprocess). Manual operator smoke is sufficient for this fix; CI-driven server-spin tests can land later if Phase 3 needs them.
- Solving the `langgraph dev` + llama-swap dependency. Graph compilation does not hit the network; actual *invocation* needs llama-swap, but that's a separate workstream (operator-side infra, not Jarvis code).

## Notes

This task closes F8 cleanly without re-opening F2. After it lands, Phase-2 close criterion #6 becomes satisfiable independently of GB10 provisioning — operator can run `langgraph dev` locally on the M2 Max and confirm both graphs register.

The TDD posture (red commit then green commit) is deliberate — F8 is a deployment-surface defect that the existing smoke test missed; the strengthened test is itself a regression-prevention asset and the auditable two-commit history makes that clear.

Suggested commit messages:
- `test(langgraph): strengthen supervisor:graph symbol resolution check (TASK-J003-FIX-004 red, F8)`
- `fix(langgraph): wire supervisor.make_graph factory for langgraph CLI (TASK-J003-FIX-004 green, F8 / DDR-013)`

## Implementation Summary

**Outcome:** ✅ Closed Finding F8 from the FEAT-JARVIS-003 review (langgraph CLI cannot resolve `supervisor.py:graph` because no such symbol exists). Phase-2 close criterion #6 (`langgraph dev` spins both graphs locally) is now satisfiable on the operator's M2 Max independently of GB10/llama-swap provisioning — graph *registration* is verifiable; only graph *invocation* still needs llama-swap up.

**Approach:** Factory-function shape (NOT eager module-level compile) per the task's design decision. `supervisor.py` gains a zero-argument `make_graph()` whose body lazy-imports `JarvisConfig` and `build_app_state` and runs `asyncio.run(build_app_state(JarvisConfig())).supervisor`. The lazy imports keep `import jarvis.agents.supervisor` side-effect free (preserving the FIX-003 fresh-env collection contract); delegation to `build_app_state` ensures the FIX-001 Layer-2 hook wiring (DDR-014), ambient tool factory (ADR-ARCH-027), and capability snapshot (ASSUM-006) all hold when the langgraph CLI loads the graph at server startup — not just when `jarvis chat` builds it.

**Why factory, not eager compile**: An eager `graph = build_supervisor(JarvisConfig())` at module scope would (a) re-introduce F2-class fragility (test collection failures, missing stub_capabilities.yaml) by triggering `JarvisConfig()`/`init_chat_model`/`assemble_tool_list`/capability-registry load at import time, and (b) silently bypass `lifecycle.build_app_state` so the FIX-001 Layer-2 wiring would NOT hold for the langgraph-CLI-served supervisor — a regression of Finding F1 with no test coverage. The factory shape sidesteps both.

**Files changed (green commit `9f49ae3`):**
- `src/jarvis/agents/supervisor.py` — added `make_graph()` factory at module scope (lazy imports inside body).
- `langgraph.json` — `:graph` → `:make_graph` for the `jarvis` entry only; `jarvis_reasoner` keeps `:graph` per DDR-012's eager-compile rule (that leaf graph has no lifecycle dependencies).
- `tests/test_langgraph_json.py` — relaxed scenario-anchor `endswith(":graph")` to assert `module:variable` form generally; the per-symbol contract is enforced by `TestJarvisGraphSymbolResolves`.

**Files changed (red commit `4536bb8`):**
- `tests/test_langgraph_json.py` — new `TestJarvisGraphSymbolResolves` class with 3 sibling tests:
  1. `test_importlib_resolves_jarvis_graph_attr_from_manifest_path` — pure resolution path the langgraph CLI follows at server load (importlib-based; no invocation).
  2. `test_jarvis_graph_symbol_invocation_returns_compiled_state_graph` — invokes the resolved symbol (with `init_chat_model` patched, `JarvisConfig` substituted), asserts result is a `CompiledStateGraph`.
  3. `test_jarvis_graph_factory_invocation_wires_layer2_hooks` — asserts `dispatch._current_session_hook` and `dispatch._async_subagent_frame_hook` are non-None after invocation; explicitly fails (not vacuously) if a future refactor reverts to eager-compile shape.

**Quality gates (post-fix):**
- `OPENAI_API_KEY=stub uv run pytest tests/` → **1596 passed, 2 skipped** (1593 pre-FIX baseline + 3 new symbol-resolution tests).
- `mypy src/jarvis/` → **Success: no issues found in 39 source files.**
- `ruff check src/jarvis/` → **All checks passed!**
- Module import side-effects: ✅ None (`from jarvis.agents.supervisor import make_graph` does NOT wire Layer-2 hooks; only invocation does).

**Lessons captured:**
- **Smoke tests must follow the consumer's resolution path, not just file existence.** The pre-FIX `test_jarvis_graph_path_resolves_to_supervisor_module` only `Path.exists()`-checked the module file but never `importlib`-resolved the variable. A regression-grade smoke test for an external CLI consumer (langgraph CLI here) must execute the *same* import + getattr path the consumer executes. F8 slipped past CI because the symbol-resolution gap was outside the test's check boundary.
- **Lazy-import inside factory bodies preserves import-time side-effect contracts when the factory itself triggers heavy lifecycle wiring.** The pattern (`def make_graph(): import asyncio; from jarvis.config.settings import JarvisConfig; ...`) is the right shape when (a) the module is also imported for symbol resolution by external tools (langgraph CLI) and (b) the factory invocation is heavy. Module-level `from … import build_app_state` would have re-introduced F2-class fragility because pytest collection imports the module before any conftest fixture has a chance to seed env vars or stub registries.
- **Two-commit TDD history is auditable evidence for deployment-surface fixes.** The red→green commit pair (`4536bb8` failing, `9f49ae3` passing) makes the F8 closure self-evident in `git log` — important when the regression was a deployment defect rather than a code bug, because the strengthened smoke test itself is the long-lived regression-prevention asset.

**Cross-references:**
- DDR-013 — repo-root `langgraph.json` declares both Jarvis graphs (parent decision record).
- DDR-012 — `jarvis_reasoner` module-import compilation precedent (intentionally NOT mirrored on the supervisor side).
- ADR-ARCH-027 — attended-only escape hatch (FIX-001 invariant preserved by factory delegation to `build_app_state`).
- FEAT-JARVIS-003 review F8 — the surfaced finding closed by this task.
- TASK-J003-FIX-001 — the FIX-001 Layer-2 wiring this task ensures continues to hold for langgraph-CLI-served supervisor.

**Out of scope (deferred to operator / future phase):**
- Manual `langgraph dev` real-server smoke (one operator-side acceptance criterion remains pending; documented above with `⏸️`).
- CI-driven server-spin tests (subprocess-based) — Phase 3 candidate.
- llama-swap provisioning — separate operator-side infra workstream; graph compilation in this task does not hit the network.
