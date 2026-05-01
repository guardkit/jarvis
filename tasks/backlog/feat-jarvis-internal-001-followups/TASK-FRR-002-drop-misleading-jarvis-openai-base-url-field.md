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
status: backlog
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
updated: 2026-05-01 00:00:00+00:00
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

- [ ] In `src/jarvis/config/settings.py`: rename the `openai_base_url` field to something that does not imply cloud OpenAI. Two acceptable shapes:
  - **Preferred:** remove the field entirely if `llama_swap_base_url` already does the job (audit consumers — they appear to overlap; if so, collapse to a single field).
  - **Otherwise:** rename to `llama_swap_base_url_override` (or similar) and document that this is the llama-swap endpoint, not a cloud endpoint.
  Audit every consumer of the old field name across `src/` and `tests/` and update.
- [ ] In `.env.example`: drop `JARVIS_OPENAI_BASE_URL` from the documented surface entirely OR replace its commentary with a clear statement: *"this is the llama-swap endpoint on the GB10, **not** cloud OpenAI; cloud OpenAI is not a supported supervisor target — see ADR-ARCH-001 (local-first inference)"*.
- [ ] In `src/jarvis/infrastructure/lifecycle.py:569-570`: the unconditional set **stays** (correct per the local-only ethos), but a comment block citing ADR-ARCH-001 explicitly states why the override is unconditional, so future readers understand the design intent. Sample shape:
  ```python
  # ADR-ARCH-001: local-first inference. The supervisor always routes through
  # llama-swap on the GB10 (or its Tailscale-reachable equivalent). Cloud OpenAI
  # is NOT a supported supervisor target; this OPENAI_BASE_URL clobber is
  # intentional and unconditional. If you need to point at a different
  # llama-swap instance, set JARVIS_LLAMA_SWAP_BASE_URL (or whatever the
  # post-FRR-002 field name is) — there is no escape hatch to cloud APIs.
  os.environ["OPENAI_BASE_URL"] = f"{config.llama_swap_base_url}/v1"
  ```
- [ ] Audit any related ADRs / DDRs that reference the old field name and update wording to align (e.g. ADR-ARCH-001 itself if it mentions `JARVIS_OPENAI_BASE_URL`; any Phase 0.4 / config-surface references in `docs/runbooks/`).
- [ ] Existing tests that exercise `OPENAI_BASE_URL` handling are preserved or updated to match the new field name. Specifically check:
  - `tests/test_lifecycle_startup_*.py` — any references to the old field.
  - `tests/test_settings.py` (or equivalent) — Pydantic settings round-trip tests.
  Field-rename refactor must keep test coverage at the post-FRR-002 baseline.
- [ ] `tests/test_settings.py` (or equivalent) gains an explicit assertion that there is **no** documented config surface that suggests cloud OpenAI is reachable as a supervisor target — e.g. by asserting that the settings model has no field whose name contains `openai_base_url` (post-rename) or whose `Field(description=...)` mentions `api.openai.com`.
- [ ] `mypy src/jarvis/` and `ruff check src/jarvis/` remain at zero violations on the touched files.

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
