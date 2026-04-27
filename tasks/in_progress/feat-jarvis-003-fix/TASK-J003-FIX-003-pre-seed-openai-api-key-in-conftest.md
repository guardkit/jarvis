---
complexity: 1
created: 2026-04-26 00:00:00+00:00
dependencies: []
estimated_minutes: 15
feature_id: FEAT-J003-FIX
id: TASK-J003-FIX-003
implementation_mode: direct
parent_review: FEAT-JARVIS-003
priority: medium
status: backlog
tags:
- phase-2
- jarvis
- feat-jarvis-003-fix
- developer-experience
- testing
- ddr-012
task_type: bugfix
title: Pre-seed OPENAI_API_KEY stub in tests/conftest.py for fresh-env collection
updated: 2026-04-26 00:00:00+00:00
wave: 1
---

# Pre-seed OPENAI_API_KEY stub in tests/conftest.py for fresh-env collection

**Feature:** FEAT-J003-FIX
**Wave:** 1 | **Mode:** direct | **Complexity:** 1/10
**Parent review:** [FEAT-JARVIS-003 review report](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md) — Finding F2
**ADR/DDR:** DDR-012 (module-import compilation of `jarvis_reasoner` graph)

## Description

DDR-012 mandates that the `jarvis_reasoner` graph compile at module import time. The compilation calls `init_chat_model("openai:jarvis-reasoner")`, which constructs `ChatOpenAI(...)`, which raises `OpenAIError("api_key client option must be set...")` if `OPENAI_API_KEY` is not in `os.environ`. Today's `tests/conftest.py` clears the cwd via `monkeypatch.chdir(tmp_path)` to isolate the operator's `.env`, but does **not** pre-set a stub `OPENAI_API_KEY`. Fresh-environment `pytest tests/` therefore fails on collection (verified — `tests/test_async_task_input.py` is the first import that triggers the cascade).

`langgraph dev` should still fail loudly when the operator hasn't configured a real key (DDR-012's "fail fast" promise). The fix is scoped to the test environment only.

## Acceptance Criteria

- [ ] `tests/conftest.py` adds an autouse session-scoped (or module-scoped) fixture that monkeypatches `OPENAI_API_KEY` to a clearly-fake stub value (e.g. `"stub-for-tests-no-real-calls"`) **before** any test module imports — must run before `_isolate_dotenv` if there's a load-order dependency, or merge into `_isolate_dotenv`.
- [ ] The stub value is rejectable on shape — long enough to satisfy any future SDK-side length check but obviously not a real key. Document in the docstring that production environments inject real keys via `.env` and the test stub never reaches the wire.
- [ ] Running `unset OPENAI_API_KEY && uv run pytest tests/` from a clean shell **collects and passes 1585+ tests** (the ratchet is the post-FIX-001/FIX-002 test count; whatever it is must hold).
- [ ] Tests that intentionally exercise the missing-key error path (e.g. `test_escalate_to_frontier::test_gemini_returns_config_missing_when_GOOGLE_API_KEY_unset`) continue to pass — they monkeypatch `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` per-test and the autouse fixture must not stomp those per-test patches. Verify by reading the existing test bodies and confirming pytest's monkeypatch ordering (later patches override earlier autouse).
- [ ] `.env.example` (if it exists) gains a one-line comment noting that local development requires real keys — referenced from the README quickstart.
- [ ] `.claude/CLAUDE.md` quickstart section gains a one-liner: *"Tests require no environment configuration; `langgraph dev` requires `OPENAI_API_KEY` (or equivalent for the configured provider)."*

## Files Expected to Change

- `tests/conftest.py` — autouse fixture for `OPENAI_API_KEY` stub.
- `.env.example` — documentation comment (NEW or updated).
- `.claude/CLAUDE.md` — README quickstart note.

## Notes

Trivial in scope but high in developer-experience value — currently every fresh contributor or CI runner would hit the same wall. Independent of FIX-001 and FIX-002; lands in Wave 1 alongside FIX-002.
