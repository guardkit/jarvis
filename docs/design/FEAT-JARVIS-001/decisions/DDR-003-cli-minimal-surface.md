# DDR-003: CLI surface is exactly three commands — `chat`, `version`, `health`

**Status:** Accepted
**Date:** 2026-04-21
**Feature:** FEAT-JARVIS-001
**Deciders:** Rich + /system-design session

---

## Context

[ADR-ARCH-018](../../../architecture/decisions/ADR-ARCH-018-calibration-approvals-cli-only-v1.md) names the CLI as the only v1 approval surface for `CalibrationAdjustment` entities (`jarvis approve-adjustment`). [ARCHITECTURE.md §3E](../../../architecture/ARCHITECTURE.md) lists `jarvis.cli` as the cross-cutting module housing "Click CLI for operator control (status / confirm-adjustment / health)". But FEAT-JARVIS-001 is the scaffolding feature — sessions + Memory Store + supervisor builder. The learning flywheel that produces `CalibrationAdjustment`s arrives in FEAT-JARVIS-008 (deferred to v1.5). NATS-based status queries arrive in FEAT-JARVIS-004.

The design question: which subset of the eventual CLI surface ships in Phase 1?

## Decision

Phase 1 ships **exactly three commands**: `chat`, `version`, `health`. See [API-cli.md](../contracts/API-cli.md).

**Reserved but not implemented** (names Phase 1 must not shadow with other semantics):

| Command | Intended feature | Intended function |
|---|---|---|
| `jarvis status` | FEAT-JARVIS-004 | List active sessions + in-flight dispatches |
| `jarvis approve-adjustment` | FEAT-JARVIS-008 (v1.5) | CalibrationAdjustment PROPOSED → CONFIRMED round-trip |
| `jarvis confirm-adjustment` | FEAT-JARVIS-008 (v1.5) | Alias — match ADR-ARCH-018 wording |
| `jarvis purge-traces` | FEAT-JARVIS-011 (v1.1) | Graphiti trace deletion operator primitive |

## Rationale

- **`chat` meets the day-1 criterion.** Without `chat`, Phase 1 has no user-facing surface. It is the minimum viable product of the entire phase.
- **`version` is free.** One line, zero dependencies, useful for `pip install -e .` verification.
- **`health` is the wiring-debug primitive.** It validates config + builds the supervisor without invoking the model. This catches ~80% of scaffolding regressions during AutoBuild without burning LLM tokens.
- **`status` belongs in FEAT-JARVIS-004.** `status` means nothing useful until NATS dispatches and sessions-across-adapters exist. Implementing a stub now would need rewriting.
- **`approve-adjustment` belongs in FEAT-JARVIS-008 (v1.5).** No learning in v1.

Keeping the Phase 1 CLI to three commands also matches [phase1-build-plan.md §11 change 8](../../../research/ideas/phase1-build-plan.md) — the build-plan prescribes these three exact subcommands.

## Alternatives considered

1. **Include `jarvis status` as an empty-stub from Phase 1** *(rejected)* — stub CLI commands that print "not yet implemented" clutter the surface; better to 404 with Click's default error.
2. **Defer `health` to FEAT-JARVIS-002** *(rejected)* — `health` is the fastest-to-implement and highest-leverage diagnostic for AutoBuild. Cutting it trades 20 lines of code for many hours of debug pain during the scaffold build.
3. **Adopt a Forge-style `jarvis --scope` / `jarvis --docs` surface** *(rejected)* — those flags exist for Forge's AutoBuild pipeline; Jarvis is a conversational agent, not a build orchestrator. The scope/docs flags have no analogue here.
4. **Ship `jarvis tools list`** *(rejected)* — no custom tools in Phase 1.

## Consequences

- Future features (002, 004, 008, 011) each add 1–2 commands. The `jarvis.cli.main` module stays a Click group — each feature registers new subcommands at its own layer. No pre-emptive plumbing needed.
- Click argument parsing must accept standard `--help` / `--version` top-level flags. `--version` is an alias for the `version` subcommand (Click idiom).
- `jarvis` with no args prints the command list + exits 0. This is Click's default behaviour — no custom code required.
- Later features' CLI-surface review will reference this DDR as the baseline; a reviewer can check that additions don't shadow reserved names.

## Related

- [API-cli.md](../contracts/API-cli.md)
- [ADR-ARCH-018](../../../architecture/decisions/ADR-ARCH-018-calibration-approvals-cli-only-v1.md)
- [phase1-build-plan.md §11 change 8](../../../research/ideas/phase1-build-plan.md)
