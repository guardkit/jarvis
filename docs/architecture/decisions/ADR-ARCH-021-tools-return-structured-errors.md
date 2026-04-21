# ADR-ARCH-021: Tools return structured errors, never raise

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Mirrors:** Forge ADR-ARCH-025

## Context

DeepAgents `@tool` functions run inside the reasoning loop. An unhandled exception terminates the supervisor's current tool call; the reasoning model loses the signal that something went wrong and cannot adapt. The `langchain-tool-decorator-specialist` rule already requires this pattern.

## Decision

All `@tool(parse_docstring=True)` functions in `jarvis.tools.*` follow the structured-error pattern:

- Wrap logic in `try/except`.
- On success, return a string (may be JSON-formatted — the reasoning model reads it).
- On failure, return a structured error string (`"ERROR: <category> — <detail>"`) rather than raise.
- Adapter exceptions are converted to structured errors at the tool-layer boundary.

Degraded modes are reasoning inputs: if llama-swap is swapping, the tool returns a structured `"DEGRADED: model_swap_in_progress, eta_seconds=N"` — the supervisor decides how to respond (see ADR-ARCH-012).

## Alternatives considered

1. **Raise-and-catch at supervisor level** *(rejected)*: Loses the degraded-mode-as-reasoning-input property.
2. **Silent retry inside tool** *(partially adopted — for Pattern B watchers)*: Pattern B watchers retry inside the tool per ADR-ARCH-024; but the final result still returns structurally to the supervisor.

## Consequences

- Consistent behaviour across all Jarvis tools — reasoning model always receives a result string, never crashes.
- Easier to unit-test — tools are pure input → output functions (no exception behaviour to verify).
- Error strings are part of the reasoning context — write them clearly and machine-parseable (e.g. prefix with `ERROR:` / `DEGRADED:` / `TIMEOUT:`).
