# ADR-ARCH-015: CI = ruff + mypy --strict + pytest; manual deploy

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Fleet repos use a shared quality bar. Jarvis has no operational CI/CD today; this ADR sets the v1 target.

## Decision

GitHub Actions workflow runs on every PR and push to main:

1. `ruff check` + `ruff format --check`
2. `mypy --strict` (blocks merge on violations)
3. `pytest` (unit + integration tests; `pytest-asyncio` for async paths)
4. Container image build (on merge to main) — stored in GHCR

**No coverage threshold gate in v1** — Jarvis's learning loop and ambient surfaces are genuinely novel and hard to meaningfully cover at an arbitrary percentage. Coverage is reported but not gated.

Deployment is **manual** — Rich runs `docker compose pull && docker compose up -d` on GB10 when ready to ship. No auto-deploy.

## Alternatives considered

1. **Add coverage threshold (e.g. 85%)** *(rejected for v1)*: Forge hits ~98% in practice; arbitrary thresholds for Jarvis v1 would be either trivially easy (mocking the entire learning loop) or chilling on genuinely novel code.
2. **Lighter gate (ruff + pytest only, mypy advisory)** *(rejected)*: Type-safety regressions are hard to catch after the fact; strict mypy from v1 keeps the codebase maintainable as it grows.
3. **Auto-deploy on merge** *(rejected)*: Single-operator deploy doesn't benefit from automation; Rich prefers explicit deploy control.

## Consequences

- Quality bar matches Forge (enables shared tooling / pre-commit configs).
- Mypy `--strict` catches boundary violations (domain modules importing adapters, wrong `nats-core` type usage).
- Manual deploy avoids surprise deploys during active work; slight ops overhead.
