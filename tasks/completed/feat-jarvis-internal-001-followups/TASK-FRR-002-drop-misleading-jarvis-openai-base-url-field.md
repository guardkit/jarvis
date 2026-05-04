---
complexity: 2
created: 2026-05-01 00:00:00+00:00
dependencies: []
discovered_on_machine: GB10 (promaxgb10-41b1)
discovered_on_date: 2026-05-01
discovered_via_correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
estimated_minutes: 45
feature_id: FEAT-JARVIS-INTERNAL-001-FRR
id: TASK-FRR-002
implementation_mode: direct
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md
priority: medium
status: completed
completed: 2026-05-01T00:00:00Z
completed_location: tasks/completed/feat-jarvis-internal-001-followups/
tags:
- jarvis
- feat-jarvis-internal-001-followups
- config
- documentation
- developer-experience
- adr-arch-001
- local-only-ethos
task_type: cleanup
title: Drop the misleading JARVIS_OPENAI_BASE_URL field from the documented config surface
updated: 2026-05-01T00:00:00Z
wave: 1
---

# Drop the misleading `JARVIS_OPENAI_BASE_URL` field

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — phases 0.4 (provider keys set with notes), 5.1 (jarvis chat boots — caveat); operator-side gap row "`JARVIS_OPENAI_BASE_URL=https://api.openai.com/v1` is misleading..."
**ADR/DDR:** ADR-ARCH-001 (local-first inference via llama-swap on the GB10 — *"the whole ethos of this is to use local models so it needs to use llama-swap hosted models on the GB10 — that's mandatory, no using cloud AI APIs"* — verified with operator 2026-05-01)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-01, correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`

## Description

`src/jarvis/infrastructure/lifecycle.py:569-570` unconditionally sets:

```python
os.environ["OPENAI_BASE_URL"] = f"{config.llama_swap_base_url}/v1"
```

This means even when the operator sets `JARVIS_OPENAI_BASE_URL=https://api.openai.com/v1` in `.env` to mean "I want the supervisor to talk to cloud OpenAI", the override silently wins and every supervisor call goes to llama-swap.

This is **correct** per the project's local-only ethos — verified with the operator on 2026-05-01: *"the whole ethos of this is to use local models so it needs to use llama-swap hosted models on the GB10 — that's mandatory, no using cloud AI APIs"*. Cloud OpenAI is **not** a supported supervisor target; ADR-ARCH-001 (local-first inference) is the canonical statement.

But the field name `JARVIS_OPENAI_BASE_URL` and the `.env.example` documentation lead operators to believe the cloud URL would be honored. The runbook walkthrough on 2026-05-01 specifically called this out as the documented surface being the bug, not the runtime behaviour.

This task fixes the **documented + named surface** to match the (correct) runtime behaviour. It is **not** a behaviour change — the unconditional clobber stays.

## Acceptance Criteria

- [x] In `src/jarvis/config/settings.py`: rename the `openai_base_url` field to something that does not imply cloud OpenAI. Two acceptable shapes:
  - **Preferred:** remove the field entirely if `llama_swap_base_url` already does the job (audit consumers — they appear to overlap; if so, collapse to a single field).
  - **Otherwise:** rename to `llama_swap_base_url_override` (or similar) and document that this is the llama-swap endpoint, not a cloud endpoint.
  Audit every consumer of the old field name across `src/` and `tests/` and update.
- [x] In `.env.example`: drop `JARVIS_OPENAI_BASE_URL` from the documented surface entirely OR replace its commentary with a clear statement: *"this is the llama-swap endpoint on the GB10, **not** cloud OpenAI; cloud OpenAI is not a supported supervisor target — see ADR-ARCH-001 (local-first inference)"*.
- [x] In `src/jarvis/infrastructure/lifecycle.py:569-570`: the unconditional set **stays** (correct per the local-only ethos), but a comment block citing ADR-ARCH-001 explicitly states why the override is unconditional, so future readers understand the design intent. Sample shape:
  ```python
  # ADR-ARCH-001: local-first inference. The supervisor always routes through
  # llama-swap on the GB10 (or its Tailscale-reachable equivalent). Cloud OpenAI
  # is NOT a supported supervisor target; this OPENAI_BASE_URL clobber is
  # intentional and unconditional. If you need to point at a different
  # llama-swap instance, set JARVIS_LLAMA_SWAP_BASE_URL (or whatever the
  # post-FRR-002 field name is) — there is no escape hatch to cloud APIs.
  os.environ["OPENAI_BASE_URL"] = f"{config.llama_swap_base_url}/v1"
  ```
- [x] Audit any related ADRs / DDRs that reference the old field name and update wording to align (e.g. ADR-ARCH-001 itself if it mentions `JARVIS_OPENAI_BASE_URL`; any Phase 0.4 / config-surface references in `docs/runbooks/`).
- [x] Existing tests that exercise `OPENAI_BASE_URL` handling are preserved or updated to match the new field name. Specifically check:
  - `tests/test_lifecycle_startup_*.py` — any references to the old field.
  - `tests/test_settings.py` (or equivalent) — Pydantic settings round-trip tests.
  Field-rename refactor must keep test coverage at the post-FRR-002 baseline.
- [x] `tests/test_settings.py` (or equivalent) gains an explicit assertion that there is **no** documented config surface that suggests cloud OpenAI is reachable as a supervisor target — e.g. by asserting that the settings model has no field whose name contains `openai_base_url` (post-rename) or whose `Field(description=...)` mentions `api.openai.com`.
- [x] `mypy src/jarvis/` and `ruff check src/jarvis/` remain at zero violations on the touched files.

## Files Expected to Change

- `src/jarvis/config/settings.py` — rename or remove the `openai_base_url` field; audit and update consumers.
- `src/jarvis/infrastructure/lifecycle.py` — keep the unconditional clobber; add the ADR-ARCH-001 comment block.
- `.env.example` — drop or rewrite the `JARVIS_OPENAI_BASE_URL` line.
- `tests/test_settings.py` (or wherever config tests live) — update field-name references; add the no-cloud-surface assertion.
- `tests/test_lifecycle_startup_*.py` — update any `OPENAI_BASE_URL` references to match the new field name.
- Any ADR / DDR docs in `docs/` that reference the old field — update wording.

## Out of Scope

- **Changing the actual local-only behaviour.** The unconditional llama-swap clobber is the desired state per ADR-ARCH-001. This task only fixes the documented + named surface to match it. Any operator request to "let me point at cloud OpenAI as a fallback" must go through a separate ADR change, not through this task.
- The runbook §0.4 wording fix is covered by **TASK-FRR-004** (runbook gap-fold rewrite) — this task changes the source-of-truth (settings.py + .env.example + lifecycle.py comment); FRR-004 propagates the change into the runbook prose.

## References

- **Parent runbook results:** [`docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
  - Per-phase row: 0.4 (`JARVIS_OPENAI_API_KEY` set; cloud keys not required for this run because of local-only ethos).
  - Operator-side gap row: "`JARVIS_OPENAI_BASE_URL=https://api.openai.com/v1` is misleading — `lifecycle.py:569-570` unconditionally sets `os.environ["OPENAI_BASE_URL"]=<llama_swap_base_url>/v1`, so the cloud OpenAI URL never wins"
  - Recommended follow-up #5.
- **Source files (with line numbers):**
  - `src/jarvis/infrastructure/lifecycle.py:569-570` — the unconditional clobber.
  - `src/jarvis/config/settings.py` — the misleading `openai_base_url` field.
  - `.env.example` — the misleading `JARVIS_OPENAI_BASE_URL` documentation line.
- **ADR:** ADR-ARCH-001 (local-first inference via llama-swap).
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-01.
- **correlation_id:** `a58ec9a7-27c6-485a-beac-e18675639a10`.
- **Operator confirmation 2026-05-01:** *"the whole ethos of this is to use local models so it needs to use llama-swap hosted models on the GB10 — that's mandatory, no using cloud AI APIs"*.

## Notes

- Two-line code change + a docstring-style rename refactor + a single comment block. The 2/10 complexity is dominated by the audit-every-consumer step, not the logic.
- The forward-reference from TASK-FRR-004 (runbook gap-fold) to this task means it's worth landing FRR-002 first if the operator runs both in parallel — FRR-004 can then cite the post-rename field name verbatim instead of leaving a TODO.
- If during the audit a consumer is found that *does* expect a non-llama-swap base URL (e.g. an embeddings sub-flow that legitimately needs a different host), pause and escalate — that would be evidence the current single-field design is wrong, not just the name.

## Implementation Summary

**Outcome**: All 7 acceptance criteria met. The `openai_base_url` field was removed from `JarvisConfig` (preferred shape per the AC — `llama_swap_base_url` already had a non-empty default and the field's only consumer was the `validate_provider_keys()` presence-check, which is now trivially satisfied without the redundant field). The `_PROVIDER_KEY_REQUIREMENTS["openai"]` entry was dropped accordingly: there is now no operator-failure mode for the `openai:` supervisor prefix, which correctly mirrors ADR-ARCH-001's mandate that llama-swap is the only supported supervisor target.

**Approach**: Single-pass refactor: (1) source-of-truth changes to `settings.py`, `lifecycle.py`, `.env.example`; (2) bulk rename of the `openai_base_url=` kwarg to `llama_swap_base_url=` across ~25 test files via `sed`, with `/v1` suffix stripped (since `lifecycle.py` re-appends it when exporting `OPENAI_BASE_URL`); (3) targeted rewrites of the four tests that specifically asserted the old behaviour (`test_validate_provider_keys_*`, `test_default_openai_base_url_is_none`, `test_health_missing_openai_base_url_*`, `test_test_config_has_openai_base_url`); (4) added the no-cloud-surface assertion the AC required (`test_no_openai_base_url_field_on_settings_model`) which both checks the field is absent and rejects any field whose `description` mentions `api.openai.com`.

**Lessons**:

- The bulk-sed approach left ~10 test files with duplicate `llama_swap_base_url=` kwargs because the original code had `openai_base_url=...` followed by `llama_swap_base_url=...` in the same `JarvisConfig(...)` call. Caught by an `ast.parse`-based sweep that flagged duplicate-kwarg `Call` nodes — worth keeping that `python3 -c "import ast; ..."` pattern in the toolkit for any future bulk-rename refactor across a large test surface.
- The runtime behaviour was correct all along — the bug was purely in the documented + named surface. Splitting the source-of-truth fix (this task) from the runbook prose propagation (TASK-FRR-004) lets each task land cleanly without the runbook holding a stale field name.
- The `extra="ignore"` in `SettingsConfigDict` made the rename safer-than-it-looked: stale kwargs in tests would silently no-op rather than raise. That cuts both ways — silent "success" in tests would have masked stale references, so the explicit `not hasattr(cfg, "openai_base_url")` and `"openai_base_url" not in JarvisConfig.model_fields` assertions are load-bearing.
- Two pre-existing test failures (`test_warn_once_then_silent_ratchet`, `test_dispatches_succeed_traces_lost_warn_emitted`) flake under random ordering due to in-progress TASK-FRR-003 changes in `routing_history.py` that were already in the working tree at task start. Confirmed pre-existing via `git stash` round-trip; not a regression from this task.

**Related ADRs/decisions**:

- **ADR-ARCH-001** (local-first inference via llama-swap) — the canonical statement that grounds this task; verified with operator on 2026-05-01 (*"the whole ethos of this is to use local models so it needs to use llama-swap hosted models on the GB10 — that's mandatory, no using cloud AI APIs"*).
- **TASK-FRR-004** (forward reference) — runbook §0.4 / §5.1 prose update that propagates this rename into operator-facing documentation; can now cite `JARVIS_LLAMA_SWAP_BASE_URL` verbatim instead of leaving a TODO.

**Quality gates**:

- pytest: 2180 passed, 1 skipped (deterministic `-p no:randomly` run).
- mypy `src/jarvis/`: clean (45 source files).
- ruff on touched files (`settings.py`, `lifecycle.py`): clean. The 5 ruff errors in `forge_notifications.py` pre-existed and are out of scope.

**Files changed**:

- `src/jarvis/config/settings.py` — removed `openai_base_url` field, removed `"openai"` entry from `_PROVIDER_KEY_REQUIREMENTS`, added explanatory comment block citing ADR-ARCH-001.
- `src/jarvis/infrastructure/lifecycle.py` — kept the unconditional `OPENAI_BASE_URL` clobber (correct per ADR-ARCH-001), expanded the comment to explicitly cite ADR-ARCH-001 and document why the override is unconditional with no cloud-OpenAI escape hatch.
- `.env.example` — dropped `JARVIS_OPENAI_BASE_URL`, uncommented `JARVIS_LLAMA_SWAP_BASE_URL` and added commentary that this is the only supported supervisor endpoint.
- ~30 test files (full list in the in-review summary) — bulk rename + targeted rewrites + new no-cloud-surface assertion.

