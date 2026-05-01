# FEAT-JARVIS-INTERNAL-001 Follow-ups (FRR — first-real-run)

**Source:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
**Run date:** 2026-05-01
**Run host:** GB10 (`promaxgb10-41b1`) — co-resident first walkthrough
**correlation_id:** `a58ec9a7-27c6-485a-beac-e18675639a10`
**Outcome of source run:** Partial — wire e2e proven up to forge consume+ack; runbook needs gap-folds before re-run; Phase 7 (stage-complete back-flow) is structurally unsatisfiable against `forge:732408f`.

---

## Why this folder exists

The first real walkthrough of the FEAT-JARVIS-INTERNAL-001 runbook on the GB10 produced a "Partial — closed with gap-folds" decision. The wire-level path (publish → JetStream → forge consume+ack) was proved, but four jarvis-side defects need follow-up work before a clean MacBook-over-Tailscale re-run can be claimed:

1. **Three startup-time NATS subscription failures** against canonical `nats-infrastructure` provisioning — fleet register, KV bucket bind, and forge_subscriber consumer attach all error out. The DDR-030 between-prompt notification path is dead until reconciled.
2. **A misleading `JARVIS_OPENAI_BASE_URL` config field** that operators reasonably read as "set this to point at cloud OpenAI" — but `lifecycle.py:569-570` unconditionally clobbers it back to llama-swap. The local-only ethos is correct (verified with operator); the documented surface is the bug.
3. **A silent trace-drop on the DDR-019 soft-fail offload path** when `~/.jarvis/traces/` doesn't exist — `routing_history_write_failed` is logged but no file lands and no alternate destination is reported.
4. **A stack of 13 runbook gap-folds** — wrong feature_id, wrong env-var names, wrong port defaults, wrong auth assumptions, broken commands that need a TTY, etc. — that the operator manually adjusted around during the GB10 run and that a fresh operator on the MacBook walkthrough must not have to re-derive.

These four follow-ups are scoped to jarvis (or jarvis-owned docs). Forge-side follow-ups (`dispatch_payload` real-orchestrator wiring, `logging.basicConfig` in `serve.py`, `scripts/build-image.sh` cwd fix, forge stage-complete publish path) are tracked in the forge repo and are referenced from these tasks where relevant but are out of scope here.

---

## The four tasks

| # | Task | Title | Complexity | Mode |
|---|---|---|---|---|
| 1 | [TASK-FRR-001](TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md) | Reconcile NATS subscriptions with canonical provisioning (fleet register, KV bind, forge_subscriber) | 5 | task-work (TDD) |
| 2 | [TASK-FRR-002](TASK-FRR-002-drop-misleading-jarvis-openai-base-url-field.md) | Drop the misleading `JARVIS_OPENAI_BASE_URL` field from documented config surface | 2 | direct |
| 3 | [TASK-FRR-003](TASK-FRR-003-ddr-019-trace-offload-autocreate-and-non-silent-drop.md) | DDR-019 trace-offload: autocreate `~/.jarvis/traces/` and stop silently dropping traces on the floor | 3 | task-work (TDD) |
| 4 | [TASK-FRR-004](TASK-FRR-004-runbook-gap-fold-rewrite.md) | Runbook gap-fold rewrite — fold all 13 gaps so a fresh operator can copy-paste end-to-end | 3 | direct |

Total: 4 tasks, aggregate complexity 13/40.

### Independence and ordering

- TASK-FRR-001, TASK-FRR-002, TASK-FRR-003 touch independent file scopes (`infrastructure/lifecycle.py` + NATS subscription internals; `config/settings.py` + `.env.example`; `infrastructure/routing_history.py` respectively) and can be parallelized.
- TASK-FRR-004 (runbook gap-fold) **forward-references** TASK-FRR-002 and TASK-FRR-001 — when those land their `JARVIS_OPENAI_BASE_URL` and `forge_subscriber` story changes, the runbook §0.4 and §5.1 wording lands clean. TASK-FRR-004 can land first with explicit forward-references to the other task IDs and be revised when they merge, OR can land last after they merge — operator preference.

---

## Source RESULTS row map

Each task is anchored to specific rows in the source RESULTS file's two tables:

| Task | Per-phase row(s) | Operator-side gap row(s) | Recommended follow-up #(s) |
|---|---|---|---|
| FRR-001 | 5.1 (jarvis chat boots — caveat), 7.1 (between-prompt notifications — failed) | "Jarvis fleet register, KV bind, and forge_subscriber attach all fail at startup..." | 4 |
| FRR-002 | 0.4 (provider keys), 5.1 (jarvis chat boots) | "`JARVIS_OPENAI_BASE_URL=https://api.openai.com/v1` is misleading..." | 5 |
| FRR-003 | 8.3 (local trace offload — none written) | (no dedicated gap row; covered in 8.3 evidence) | 6 |
| FRR-004 | all phases (operator transcript, gap-fold table is summary) | all 13 rows of the "Operator-side gaps in the runbook" table | 7 |

---

## Conventions used in this folder

- Task IDs: `TASK-FRR-NNN` where `FRR` = "first-real-run". Picked because:
  - The existing convention `TASK-J<feature-num>-NNN` (e.g. `TASK-J003-FIX-NNN`) implies these tasks belong to a numbered jarvis feature wave; these don't — they're follow-ups from a runbook walkthrough that spans jarvis + forge + nats-infrastructure.
  - `TASK-FEAT-JARVIS-INTERNAL-001-FOLLOWUPS-NNN` is unwieldy and `TASK-INT001-FRR-NNN` is no clearer.
  - `FRR` is short, mnemonic, and unambiguous against the existing namespace (no other `FRR` task IDs exist in `tasks/`).
- Task file shape: mirrors the `TASK-J003-FIX-NNN-*.md` style — YAML frontmatter (id, title, status, feature_id, etc.) + body sections (Description, Acceptance Criteria, Files Expected to Change, References, Notes).
- The `feature_id` frontmatter field for all four tasks is `FEAT-JARVIS-INTERNAL-001-FRR` (a synthetic id for this follow-up wave). The original feature `FEAT-43DE` (= FEAT-JARVIS-INTERNAL-001) is already merged and archived per `47ec4e5`; this wave is a follow-up wave on top of it, not part of it.

---

## Cross-references

- Source RESULTS file: `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`
- Source RUNBOOK file: `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`
- Original feature archive: `.guardkit/archive/FEAT-43DE/feature_state.yaml`
- Discovered-on machine: GB10 (`promaxgb10-41b1`)
- Run correlation_id: `a58ec9a7-27c6-485a-beac-e18675639a10`
- Run date: 2026-05-01
