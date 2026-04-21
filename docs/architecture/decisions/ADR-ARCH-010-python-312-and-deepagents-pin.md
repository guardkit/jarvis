# ADR-ARCH-010: Python 3.12 and DeepAgents >=0.5.3, <0.6 pin

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

DeepAgents 0.5.3 (released 15 April 2026) introduced `AsyncSubAgent` as a preview feature. Jarvis's single-reasoner architecture (ADR-ARCH-011) depends on this primitive. Preview features have API-break risk in minor version bumps. Python 3.12 is the fleet-wide baseline.

## Decision

Pin:
- **Python**: `>=3.12, <3.13`
- **DeepAgents**: `>=0.5.3, <0.6` (upper-bound exclusive to prevent accidental 0.6 breakage)
- **LangChain**: compatible with DeepAgents 0.5.3 requirements
- **LangGraph**: compatible with DeepAgents 0.5.3 requirements
- **Pydantic**: `^2`
- **nats-core**: installed from sibling repo (pip-installed wheel)

The DeepAgents 0.6 upgrade is gated by ADR-ARCH-025 (compatibility review).

## Alternatives considered

1. **Pin DeepAgents to exact 0.5.3** *(rejected)*: Too strict — patch releases that fix AsyncSubAgent bugs would be blocked.
2. **Follow DeepAgents main** *(rejected)*: Preview-feature breakage risk is unacceptable on the learning-data producing path (would lose trace continuity).

## Consequences

- Scheduled review when DeepAgents 0.6 ships — see ADR-ARCH-025.
- Python 3.12 features (pattern matching, improved type parameter syntax) are available.
- Forge parity simplifies cross-repo tooling (pytest, mypy, ruff configs can be shared/aligned).
