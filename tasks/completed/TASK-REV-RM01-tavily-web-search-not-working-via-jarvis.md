---
id: TASK-REV-RM01
title: "Tavily web search returns config_missing when invoked via Jarvis from Reachy Mini"
task_type: review
review_mode: decision
review_depth: standard
status: completed
created: 2026-05-13T00:00:00Z
updated: 2026-05-13T00:00:00Z
completed: 2026-05-13T00:00:00Z
priority: high
tags: [jarvis, tavily, web-search, config, env-vars, reachy, ask_jarvis, surfaced-by-conversation]
complexity: 0
decision_required: true
decision: option_c
decision_made_at: 2026-05-13T00:00:00Z
surfaced_by:
  - source: reachy-mini-conversation
    history: docs/history/reachy-run-1-history.md
    turn_lines: "73-97"
    run_date: 2026-05-13
context_files:
  - src/jarvis/config/settings.py            # Lines 67-72 (web_search_provider/tavily_api_key), 198-210 (env_prefix="JARVIS_"), 258-273 (warn-only validator)
  - src/jarvis/tools/general.py              # Lines 125-167 (TavilyProvider), 176-191 (_resolve_api_key), 249-330 (search_web tool)
  - .env                                     # Currently sets bare TAVILY_API_KEY (no JARVIS_ prefix) — not picked up
  - .env.example                             # Does not currently document TAVILY_API_KEY at all
evidence_files:
  - docs/history/reachy-run-1-history.md     # Lines 73-97 capture the failed search ("Tavily API key isn't configured in this environment")
test_results:
  status: passed
  coverage: null
  last_run: 2026-05-13T00:00:00Z
  command: "uv run pytest tests/test_config_phase2.py tests/test_config.py tests/test_config_settings.py tests/test_config_feat_j003.py tests/test_search_web.py tests/test_tools_general.py"
  summary: "253 passed (19 in test_config_phase2.py incl. new TASK-REV-RM01 regression, 234 in broader config + search_web suites)"
---

# Task: Tavily web search returns config_missing when invoked via Jarvis from Reachy Mini

## Description

During the 2026-05-13 Reachy Mini conversation (recorded in
[`docs/history/reachy-run-1-history.md`](../../docs/history/reachy-run-1-history.md)),
Rich asked the Reachy scholar adapter to use Jarvis to web-search for "Talk Factory"
and later "software factories / dark factories". On both attempts the `ask_jarvis`
tool returned a response beginning:

> *"I can't do a web search right now — the Tavily API key isn't configured in this environment."*

This is the human-rephrased form of the structured-error string emitted by the
`search_web` tool at
[`src/jarvis/tools/general.py:286`](../../src/jarvis/tools/general.py#L286):

```
ERROR: config_missing — tavily_api_key not set in JarvisConfig
```

The error is fired by `_resolve_api_key()` at
[`general.py:176-191`](../../src/jarvis/tools/general.py#L176-L191) when
`JarvisConfig.tavily_api_key` is `None`.

## Likely Root Cause (Hypothesis)

`JarvisConfig` is declared with `env_prefix="JARVIS_"` at
[`settings.py:198-210`](../../src/jarvis/config/settings.py#L198-L210), and the
`tavily_api_key` field at
[`settings.py:69`](../../src/jarvis/config/settings.py#L69) has **no**
`validation_alias=AliasChoices(...)` declaration. That means pydantic-settings
will only populate the field from `JARVIS_TAVILY_API_KEY` — the bare
`TAVILY_API_KEY` variable currently set in this repo's `.env` is silently
ignored.

Compare the analogous case at
[`settings.py:85-88`](../../src/jarvis/config/settings.py#L85-L88), where
`gemini_api_key` *does* honour both `GOOGLE_API_KEY` and
`JARVIS_GEMINI_API_KEY`:

```python
gemini_api_key: SecretStr | None = Field(
    default=None,
    validation_alias=AliasChoices("GOOGLE_API_KEY", "JARVIS_GEMINI_API_KEY"),
)
```

The validator at
[`settings.py:258-273`](../../src/jarvis/config/settings.py#L258-L273) does
emit a warning when Tavily is selected but `tavily_api_key` is empty — but
it's a `warnings.warn(...)` plus a logger line, so the symptom only surfaces
at search time, not at startup.

## Investigation Scope

Before committing to the alias-fix, confirm where Jarvis is actually running
and which `.env` (if any) it loads:

1. **Which Jarvis process answered the Reachy ask?** Was it the local repo
   running on the GB10 host, a checked-out worktree, or a service deployment?
2. **What does that process see for `JARVIS_TAVILY_API_KEY` vs `TAVILY_API_KEY`?**
   pydantic-settings is case-insensitive (`case_sensitive=False`) but the prefix
   is hard. The expectation that the bare key should work needs to be tested,
   not assumed.
3. **Is the langchain-tavily install actually wired in `.[providers]`?** A
   `ModuleNotFoundError` on `langchain_tavily` would surface as
   `DEGRADED: provider_unavailable`, not `ERROR: config_missing`, but worth
   ruling out while we have the bench open.

## Decision Options

Once the env-resolution gap is confirmed, three plausible fixes:

- **Option A — Add `AliasChoices("TAVILY_API_KEY", "JARVIS_TAVILY_API_KEY")`
  to the `tavily_api_key` field.** Matches the `gemini_api_key` precedent at
  [`settings.py:85-88`](../../src/jarvis/config/settings.py#L85-L88). Smallest
  diff. Honours the user's existing `.env` shape and the upstream
  `TAVILY_API_KEY` convention used by `langchain-tavily`.
- **Option B — Require `JARVIS_TAVILY_API_KEY` only, and update `.env` /
  `.env.example` / docs accordingly.** Cleaner namespace ownership, but
  breaks the upstream-convention principle that gemini/openai already bend
  on.
- **Option C — Hybrid: alias the field (Option A) AND document
  `TAVILY_API_KEY` in `.env.example`.** Recommended unless there's a
  namespace-purity argument against.

## Acceptance Criteria

- [ ] Confirm via repro (or runtime introspection of the deployed Jarvis)
      that the symptom is env-name resolution, not missing key or broken
      `langchain-tavily` install.
- [ ] Pick an option (A / B / C / other) with a written justification in this
      task's review-results section.
- [ ] If Option A or C: add the `AliasChoices` declaration following the
      `gemini_api_key` precedent.
- [ ] Update `.env.example` to document the supported env-var name(s).
- [ ] Add a regression test in `tests/` (next to existing config-resolution
      tests for `gemini_api_key`) asserting that `TAVILY_API_KEY` populates
      `JarvisConfig.tavily_api_key` when the alias is configured.
- [ ] Smoke-test from Reachy or `langgraph dev`: re-run the "search for X"
      flow and observe a non-error JSON payload from `search_web`.

## Test Requirements

- [ ] Unit test for `JarvisConfig` env resolution covering whichever alias
      shape is adopted.
- [ ] Confirm the existing warn-on-startup behaviour at
      [`settings.py:258-273`](../../src/jarvis/config/settings.py#L258-L273)
      still fires when *no* form of the key is set.

## Implementation Notes

- Do not log or echo the resolved Tavily key — `SecretStr` masking must be
  preserved end-to-end per the existing pattern.
- The Reachy adapter is one of four entries in `attended_adapter_ids` at
  [`settings.py:93`](../../src/jarvis/config/settings.py#L93) — once the key
  resolves, no further attended-surface gating should block `search_web`.
- Consider whether the boot-time warning at
  [`settings.py:258-273`](../../src/jarvis/config/settings.py#L258-L273)
  should be promoted to a hard fail on the GB10 deployment when
  `web_search_provider == "tavily"` and no key resolves — out of scope for
  this task but worth surfacing in the review write-up.

## Review Decision (2026-05-13)

**Chosen: Option C — Alias the field AND document `TAVILY_API_KEY` in `.env.example`.**

### Justification

The hypothesis was confirmed by direct inspection of all four context files:

- `.env` on this checkout currently has `TAVILY_API_KEY=tvly-dev-1RKfrK...`
  (bare, no `JARVIS_` prefix).
- `JarvisConfig.tavily_api_key` at `src/jarvis/config/settings.py:69`
  (pre-fix) had no `validation_alias`, so `env_prefix="JARVIS_"` was the
  only resolution path — the bare line was silently dropped by
  pydantic-settings.
- `gemini_api_key` at `settings.py:85-88` is the exact precedent: it
  honours both `GOOGLE_API_KEY` (the upstream SDK's native env name) and
  `JARVIS_GEMINI_API_KEY` via `AliasChoices(...)`. The langchain-tavily
  SDK uses `TAVILY_API_KEY` natively, so applying the same pattern keeps
  one `.env` line satisfying both consumers.
- `.env.example` did not mention `TAVILY_API_KEY` at all — a doc gap
  independent of the alias question. Option B (rename to JARVIS-prefix
  only) would require changing every operator's `.env` and would break
  the upstream-convention principle gemini/openai already bend on.
  Option A (alias only) would leave the doc gap. Option C closes both.

The boot-time hard-fail suggestion from the Implementation Notes is
deliberately not actioned here — that's a behavioural change worth its
own DDR and not in scope for this review.

### Changes Landed

1. **`src/jarvis/config/settings.py:67-78`** — wrapped the
   `tavily_api_key` declaration in `Field(default=None,
   validation_alias=AliasChoices("TAVILY_API_KEY",
   "JARVIS_TAVILY_API_KEY"))`. Inline comment cites the gemini precedent
   and this task ID. `populate_by_name=True` is already set on
   `model_config`, so the `JARVIS_TAVILY_API_KEY` form continues to
   work (covered by the pre-existing
   `test_jarvis_tavily_api_key_env_var` at
   `tests/test_config_phase2.py:110`).

2. **`.env.example`** — added a `# ---- Tavily web-search API key ----`
   block alongside the existing provider keys, documenting that the
   field reads bare `TAVILY_API_KEY` first and falls back to
   `JARVIS_TAVILY_API_KEY`. The block names the structured-error string
   operators would otherwise hit at search time.

3. **`tests/test_config_phase2.py`** — added
   `test_tavily_api_key_reads_unprefixed_tavily_api_key` next to the
   existing JARVIS-prefixed test, mirroring the gemini pair at
   `tests/test_config_feat_j003.py:123-141`. The test docstring records
   the TASK-REV-RM01 provenance.

### Verification

- `uv run pytest tests/test_config_phase2.py -v` → **19 passed**, including
  the new regression and the existing JARVIS-prefix backwards-compat case.
- `uv run pytest tests/test_config.py tests/test_config_settings.py
  tests/test_config_feat_j003.py tests/test_search_web.py
  tests/test_tools_general.py` → **234 passed** (no regressions). The
  `UserWarning: web_search_provider='tavily' but TAVILY_API_KEY
  (JARVIS_TAVILY_API_KEY) is not set` lines emitted by the existing
  `validate_provider_keys()` tests confirm the warn-on-missing path at
  `settings.py:258-273` still fires when no form of the key resolves —
  i.e. the AC requirement to preserve that behaviour is met.
- Repro check: `JarvisConfig()` instantiated against this checkout's
  `.env` now resolves `tavily_api_key` to a `SecretStr` starting
  `tvly-dev`, and `repr(cfg)` does not leak the value (confirms the
  `SecretStr` masking constraint from Implementation Notes).
- Live Reachy smoke-test (re-running the "search for Talk Factory"
  flow) is deferred to the next attended-surface session — out of scope
  for the code change but flagged below.

### Out-of-Scope / Follow-Ups

- **Boot-time hard-fail on the GB10 deployment.** Implementation Notes
  flagged that the `settings.py:258-273` warn-only behaviour could be
  promoted to a hard fail when `web_search_provider == "tavily"` and no
  key resolves. This would have surfaced the env-resolution gap at
  startup instead of at first search. Worth a separate review/DDR
  before changing — leaving the warn-only path in place for now so
  `pytest tests/` continues to pass without env configuration.
- **`langchain-tavily` install verification.** The wider question of
  whether `.[providers]` actually pulls in `langchain-tavily` on the
  GB10 deployment was not exercised here (the symptom turned out to be
  pure env-resolution, not import failure). The existing
  `DEGRADED: provider_unavailable` path would catch the import failure
  if it ever surfaces; consider a future task to add an explicit
  `import langchain_tavily` smoke check to `tests/test_phase*_dependencies.py`.
- **Live Reachy smoke-test.** Re-running the "search for Talk Factory"
  flow via the Reachy adapter to confirm the structured-success JSON
  payload from `search_web` is the last unchecked AC item.

## Test Execution Log

- 2026-05-13 — `uv run pytest tests/test_config_phase2.py -v` →
  `19 passed in 0.46s` (incl. new
  `test_tavily_api_key_reads_unprefixed_tavily_api_key`).
- 2026-05-13 — `uv run pytest tests/test_config.py
  tests/test_config_settings.py tests/test_config_feat_j003.py
  tests/test_search_web.py tests/test_tools_general.py` →
  `234 passed in 0.80s` (no regressions; warn-on-missing-key
  `UserWarning`s observed as expected at `settings.py:258-273`).
- 2026-05-13 — repro `JarvisConfig()` against checkout `.env`:
  `tavily_api_key=SecretStr` with prefix `tvly-dev`,
  `repr leaks key=False`, `web_search_provider='tavily'`.
