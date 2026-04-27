# ADR-ARCH-010: Python pin and DeepAgents/LangChain ecosystem pins

**Status:** Accepted (revised 2026-04-27 — see Revision 2 below)
**Date:** 2026-04-20 (original) / 2026-04-27 (rev2)
**Deciders:** Rich + /system-arch session

## Context

DeepAgents 0.5.3 (released 15 April 2026) introduced `AsyncSubAgent` as a preview feature. Jarvis's single-reasoner architecture (ADR-ARCH-011) depends on this primitive. Preview features have API-break risk in minor version bumps. Python 3.12 is the fleet-wide baseline.

## Decision

Pin:
- **Python**: `>=3.11` *(rev2 — see Revision 2; was `>=3.12, <3.13`)*
- **DeepAgents**: `>=0.5.3, <0.6` (upper-bound exclusive to prevent accidental 0.6 breakage)
- **LangChain core / langchain / LangGraph**: coherent 1.x with `<2` caps *(rev2 — see Revision 2)*
- **Pydantic**: `^2`
- **nats-core**: installed from sibling repo (pip-installed wheel) *(retained for in-place developer iteration; the 2025-10 collision rationale no longer applies — see Revision 2)*

The DeepAgents 0.6 upgrade is gated by ADR-ARCH-025 (compatibility review).

## Alternatives considered

1. **Pin DeepAgents to exact 0.5.3** *(rejected)*: Too strict — patch releases that fix AsyncSubAgent bugs would be blocked.
2. **Follow DeepAgents main** *(rejected)*: Preview-feature breakage risk is unacceptable on the learning-data producing path (would lose trace continuity).

## Consequences

- Scheduled review when DeepAgents 0.6 ships — see ADR-ARCH-025.
- Python 3.12 features (pattern matching, improved type parameter syntax) remain available; rev2's `>=3.11` floor still permits 3.12+ syntax in code.
- Forge parity simplifies cross-repo tooling (pytest, mypy, ruff configs can be shared/aligned).

---

## Revision 2 — 2026-04-27

**Trigger**: GuardKit AutoBuild trapdoor incident (TASK-REV-FA04 in the GuardKit repo). FEAT-J004-702C autobuild stalled for 33 minutes on Mac because `/usr/local/bin/python3` had advanced to 3.14 (released 2025-10-07), and the original `>=3.12, <3.13` pin excluded it. GuardKit's environment bootstrap silently continued past the mismatch; TASK-J004-004's Coach independent-test step then failed on `import jarvis` (no editable install). The full diagnostic, including C4 diagrams and a portfolio comparison, lives at `appmilla_github/guardkit/.claude/reviews/TASK-REV-FA04-report.md`.

### Verified facts (2026-04-27)

- Upstream `nats-core` PyPI metadata now declares `requires-python = ">=3.10"` (was `>=3.13` in 2025-10 when the original tight pin was set). The collision rationale that motivated `<3.13` is fully obsolete.
- `specialist-agent`, `forge`, `study-tutor`, `agentic-dataset-factory` all use `requires-python = ">=3.11"` (matches the LangChain DeepAgents template canonical at `appmilla_github/guardkit/installer/core/templates/langchain-deepagents*/templates/other/other/pyproject.toml.template`). Jarvis was the lone outlier.
- LangChain ecosystem advanced from coordinated 0.x to coordinated 1.x. The 0.x `langchain-core` stopped publishing the `block_translators.langchain_v0` compat helpers that 0.x `langchain` agents still imported. The original open-floor pins (`langchain-core>=0.3`, `langgraph>=0.3`, `langchain-openai>=0.2`, `langchain-anthropic>=0.2`, `langchain-google-genai>=2.0`) let the resolver pick mismatched 0.x / 1.x pairs and produced runtime `ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'` on machines where 1.x got selected.
- Empirical test on Python 3.14 with the rev2 pins (langchain-core 1.3.2, langchain 1.2.15, langgraph 1.1.10, langchain-anthropic 1.4.1, langchain-openai 1.2.1, langchain-google-genai 4.2.2): full Jarvis test suite drops from 25 failures (mixed-major resolver state) to 7 failures, of which **0 are langchain-runtime failures**. The remaining 7 are pin-tracking guard tests (rebased in lockstep with this revision), pre-existing docstring drift, and `uv pip list` test-infra fragility.

### Revised decision

- **Python**: `>=3.11` (was `>=3.12, <3.13`). Open upper bound; align with portfolio canonical.
- **LangChain ecosystem**: pinned to coherent 1.x with `<2` caps:
  - `langchain-core>=1.3,<2`
  - `langchain>=1.2,<2` *(now an explicit runtime dependency; was implicit transitively)*
  - `langgraph>=1.1,<2`
  - `langchain-openai>=1.2,<2`
  - `langchain-anthropic>=1.4,<2` (in `[project.optional-dependencies].providers`)
  - `langchain-google-genai>=4.2,<5` (in `[project.optional-dependencies].providers`)
- **DeepAgents**: unchanged at `>=0.5.3, <0.6` (verified compatible with langchain 1.x via empirical test).
- **Pydantic**: unchanged at `>=2`.
- **nats-core sibling source**: retained for developer ergonomics (in-place iteration on `appmilla_github/nats-core/`), but the 2025-10 collision rationale is recorded as historical only. Future migration to `nats-core` purely from PyPI is a one-line cleanup (`[tool.uv.sources]` removal) deferred separately.

### Why open upper bound on Python (not `>=3.11,<3.14` or similar)

Closed upper bounds on `requires-python` decay silently. The 2025-10 `<3.13` cap was load-bearing on the day it was added; six months later the upstream constraint that motivated it had resolved, but the cap stayed put and silently broke consumer-side autobuild. The structural lesson (per `appmilla_github/guardkit/docs/guides/portfolio-python-pinning.md`) is that defensive Python upper bounds belong in CI matrices and known-bad version exclusions, not in `requires-python`. The same-major (`<2`) caps on the langchain packages are a different category — those are protection against a specific known breaking-change pattern in a fast-moving ecosystem, and they're calibrated to the next major bump rather than to a date.

### Why explicit `langchain` dep

The original Phase 1 dependency list pinned `langchain-core`, `langgraph`, and `langchain-openai` but not `langchain` itself. The package was being pulled in transitively (via `deepagents` or `langchain-openai`), and at runtime Jarvis code in `src/jarvis/agents/supervisor.py` and the test suite use `langchain.agents.middleware`. Making it explicit gives Jarvis direct version control over what the resolver is allowed to pick — exactly what protects against the 0.x / 1.x mismatch pattern that surfaced this incident.

### Test rebase

`tests/test_phase2_dependencies.py::TestAC004Phase1DependenciesUntouched.PHASE_1_RUNTIME_PINS` and `PHASE_1_OPTIONAL_PROVIDERS` constants have been updated in lockstep with this revision; their docstrings record the rebaseline rationale. `test_python_pin_unchanged` now asserts `>=3.11`. `tests/test_build_system.py::test_requires_python_312` likewise asserts the new pin (method name preserved for git-blame continuity).

### Forward review

When DeepAgents ships 0.6 (ADR-ARCH-025), revisit:
- Whether `langchain` 2.x has shipped and what the migration cost is.
- Whether `nats-core` from PyPI has reached parity with the sibling-repo source (and the `[tool.uv.sources]` entry can be retired).
- Whether 3.11 floor still makes sense (consider raising to 3.12 if a feature genuinely justifies it).
