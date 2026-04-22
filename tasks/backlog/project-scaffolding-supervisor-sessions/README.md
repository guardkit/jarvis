# FEAT-JARVIS-001 — Project Scaffolding, Supervisor Skeleton & Session Lifecycle

Phase 1 foundation feature for Jarvis. 11 tasks organised into 5 waves. Produces a runnable `jarvis` package, a DeepAgents supervisor with built-ins only, thread-per-session `SessionManager` with user-keyed Memory Store, and a minimal CLI (`chat` / `version` / `health`).

**Day-1 success criterion:** Rich holds a useful conversation on the CLI, and a fact stated in session A is recalled in session B for the same user.

## Quick links

- [Implementation Guide](IMPLEMENTATION-GUIDE.md) — Mermaid diagrams, integration contracts, wave structure
- [Review task](../TASK-REV-J001-plan-project-scaffolding-supervisor-sessions.md) — decision review output
- Upstream: [feature spec](../../../features/project-scaffolding-supervisor-sessions/), [design](../../../docs/design/FEAT-JARVIS-001/), [architecture](../../../docs/architecture/)

## Tasks

| Wave | ID | Title | Type | Complexity | Mode |
|------|-----|-------|------|------------|------|
| 1 | [TASK-J001-001](TASK-J001-001-pyproject-toml-and-deepagents-pin.md) | pyproject.toml + deepagents pin | scaffolding | 4 | direct |
| 1 | [TASK-J001-002](TASK-J001-002-shared-primitives.md) | shared/ primitives | declarative | 3 | direct |
| 1 | [TASK-J001-010](TASK-J001-010-reserved-empty-packages.md) | Reserve-empty packages | scaffolding | 2 | direct |
| 2 | [TASK-J001-003](TASK-J001-003-config-jarvis-settings.md) | config/JarvisConfig | declarative | 5 | task-work |
| 2 | [TASK-J001-004](TASK-J001-004-prompts-and-test-scaffold.md) | prompts + conftest | scaffolding | 3 | direct |
| 3 | [TASK-J001-005](TASK-J001-005-infrastructure-logging-lifecycle.md) | infrastructure/ logging + lifecycle | feature | 5 | task-work |
| 3 | [TASK-J001-006](TASK-J001-006-agents-supervisor-factory.md) | agents/supervisor — build_supervisor | feature | 7 | task-work |
| 4 | [TASK-J001-007](TASK-J001-007-sessions-session-and-manager.md) | sessions/ — Session + SessionManager | feature | 8 | task-work |
| 5 | [TASK-J001-008](TASK-J001-008-cli-main-click-group.md) | cli/main.py | feature | 7 | task-work |
| 6 | [TASK-J001-009](TASK-J001-009-tests-end-to-end-smoke.md) | End-to-end smoke + import-graph regression | testing | 4 | direct |
| 6 | [TASK-J001-011](TASK-J001-011-env-example-and-readme-quickstart.md) | .env.example + README Quickstart | documentation | 2 | direct |

## Execution

```bash
/feature-build FEAT-JARVIS-001              # autonomous Player-Coach
# or manually, wave-by-wave:
/task-work TASK-J001-001 --implement-only   # wave 1 (parallel with -002, -010)
/task-work TASK-J001-003 --implement-only   # wave 2
# ... continue through wave 5
/task-review FEAT-JARVIS-001                # feature gate
```

## Invariants (do not re-litigate during build)

- DeepAgents pin `>=0.5.3,<0.6` (ADR-ARCH-010)
- Five-group layout (ADR-ARCH-006) · CLI three commands only (DDR-003)
- Memory Store namespace `("user", user_id)` — no session_id segment (DDR-002)
- `thread_id == session_id` (DDR-004) · Supervisor = DeepAgents built-ins only
- Local-first inference via llama-swap at `promaxgb10-41b1:9000` — no accidental cloud-LLM calls
- 6 assumption-resolved behaviours (ASSUM-001..006) are binding — see feature file
