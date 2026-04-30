# Jarvis — General Purpose DeepAgent & Fleet Coordinator

Jarvis is the attended surface of the three-surface agent fleet (Jarvis +
Forge + specialist agents). One reasoning model, running locally on GB10,
that knows which role to apply, which specialist to dispatch to, and when
to queue a build for the Forge. Operators interact via four adapter
surfaces (Telegram, CLI, Dashboard, Reachy Mini); Jarvis coordinates the
rest of the fleet through NATS JetStream.

> One local reasoning model that knows which role to apply, which
> specialist to invoke, and when to escalate.

## Status

**Phase 3 — code-complete + regression-clean.** Phase 1 + Phase 2 +
FEAT-JARVIS-004 (NATS fleet registration & specialist dispatch) +
FEAT-JARVIS-005 (build-queue dispatch to Forge) + TASK-J004-FIX-001 are
all merged to `main`. Step 11 of the Phase 3 build plan PASSED on commit
`7e29363` — the regression suite is green at 92% line coverage with no
mypy errors, and `langgraph dev` boots both the `jarvis` and
`jarvis_reasoner` graphs cleanly.

**Phase 3 close criterion — Step 14: end-to-end Forge round-trip.** The
remaining work is one real-world dispatch: Jarvis receives a request,
publishes a `pipeline.build-queued.*` payload to JetStream, the Forge
picks it up, runs an autobuild, and Jarvis renders the
`pipeline.stage-complete.*` notifications back through the originating
adapter. Hard prerequisites: NATS on GB10, Forge running, Graphiti on
GB10, and provider keys for the subagents. Step 12 (in-process
integration server) and Step 13 (pick a FEAT-JARVIS-INTERNAL-***
candidate as the dispatch payload) gate Step 14.

After Step 14 closes, Jarvis v1 is functionally complete for dispatch and
Phase 4 (Pattern B watchers + learning loop) opens.

See [docs/research/ideas/phase3-build-plan.md](docs/research/ideas/phase3-build-plan.md)
for the full Status Log and wave-by-wave history.

## Quick Start

Run everything via `uv run …`; `uv` selects the project's pinned 3.12
interpreter (see `.python-version`).

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd jarvis

# 2. Create the project venv (uv reads .python-version → 3.12)
#    and install runtime + dev deps in one step.
uv sync

# 3. (Optional) install provider extras for cloud-escape models
uv sync --extra providers

# 4. Copy the example env file and configure
cp .env.example .env
# Edit .env with your provider keys / NATS / Graphiti endpoints

# 5. Run the test suite
uv run pytest

# 6. Launch the LangGraph dev server (boots both jarvis +
#    jarvis_reasoner graphs from langgraph.json)
uv run python -m langgraph dev

# 7. Or drive the operator CLI
uv run jarvis version
```

`uv sync` is the canonical install command and `python -m langgraph dev`
is the canonical runtime command — both should be invoked through
`uv run …` so they bind to the pinned interpreter.

### Development — Tests, Lint, Types

Every dev command goes through `uv run …`. That resolves the tool from
`.venv/bin/` against the pinned 3.12 interpreter; bypassing it (bare
`pytest`, bare `ruff`) can silently hit a system Python with different
package versions.

```bash
# Full regression (Step 11 of the Phase 3 build plan)
uv run pytest                                          # full suite
uv run pytest --cov=src/jarvis --cov-report=term       # with coverage
uv run ruff check src/jarvis/ tests/                   # lint
uv run mypy src/jarvis/                                # types (strict)

# Targeted runs while iterating
uv run pytest tests/test_supervisor.py -v              # one file
uv run pytest tests/test_supervisor.py::TestBuildSupervisorReturnsGraph -v
uv run pytest -k "supervisor and not no_llm" -v        # keyword filter
uv run pytest --lf                                     # re-run last failures
```

#### Dev dependency layout

Dev tooling (pytest, ruff, mypy, types-*) lives in
`[dependency-groups].dev` (PEP 735), **not**
`[project.optional-dependencies]`. This means:

- Bare `uv sync` installs them by default — no `--extra dev` / `--dev`
  flag needed. Earlier iterations had them as an optional-extra, which
  caused `uv sync` to silently prune `.venv/bin/pytest` on every run and
  then `uv run pytest` fell through to the system Python.
- `uv sync --no-dev` skips them (useful for prod/release builds).
- `uv sync --extra providers` adds the optional provider SDKs
  (`langchain-anthropic`, `langchain-google-genai`) — those are still an
  `[project.optional-dependencies]` extra because they are runtime, not
  dev.

#### Troubleshooting

**`uv run` warns about `VIRTUAL_ENV=…` not matching `.venv`.** Something
in your shell exported `VIRTUAL_ENV` pointing at a non-project
interpreter (often a framework Python). `uv run` ignores it, but you can
silence the warning with `unset VIRTUAL_ENV` or `deactivate`.

**Tests fail with `ModuleNotFoundError: No module named 'jarvis'` in a
subprocess.** `.venv/bin/python` is fine, but something invoked a
different Python. Verify with
`uv run python -c "import sys; print(sys.executable)"` — it must resolve
to `.venv/bin/python3`. If not, re-sync: `rm -rf .venv && uv sync`.

**`OpenAIError: The api_key client option must be set…` in supervisor
tests.** Only unmocked tests would hit a real OpenAI client. Every test
that calls `build_supervisor` must patch
`jarvis.agents.supervisor.init_chat_model` — use the `fake_llm` fixture
from [tests/conftest.py](tests/conftest.py). See
`tests/test_supervisor.py::TestBuildSupervisorReturnsGraph` for the
canonical pattern.

## Architecture

Jarvis is a **General Purpose DeepAgent with dispatch tools** — Clean /
Hexagonal modules inside a DeepAgents 0.5.3+ supervisor. The
`create_deep_agent(...)` compiled state graph is the shell (reasoning
loop, built-in tools, async subagent dispatch, Memory Store, Skills);
inside, pure domain modules (routing, watchers, learning, discovery,
sessions) carry no I/O imports; thin adapters at the edges talk to NATS,
Graphiti, and llama-swap. NATS is the control-plane bus, llama-swap is
the inference front door — there is no transport abstraction layer.

For the full system architecture, the C4 diagrams, the module map, and
the technology stack, see:

- [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) —
  master architecture document (what Jarvis is, structural pattern,
  module map, technology stack, deployment).
- [docs/architecture/system-context.md](docs/architecture/system-context.md) —
  C4 Level 1 (system context).
- [docs/architecture/container.md](docs/architecture/container.md) —
  C4 Level 2 (containers).
- [docs/architecture/domain-model.md](docs/architecture/domain-model.md) —
  bounded contexts and the domain types they own.
- [docs/architecture/assumptions.yaml](docs/architecture/assumptions.yaml) —
  architecture-level assumptions register.

## Design Decisions

Jarvis tracks design decisions at two levels: **architecture-wide ADRs**
that span the whole repo, and **feature-local DDRs** scoped to a single
FEAT-JARVIS-*** delivery. Both are append-only — once accepted, an entry
is superseded rather than rewritten.

- [docs/architecture/decisions/](docs/architecture/decisions/) —
  architecture decision records (ADR-ARCH-001 … ADR-ARCH-030). Covers
  local-first inference via llama-swap, Clean / Hexagonal layout,
  bounded-context split, NATS-only transport, the DeepAgents 0.5.3 pin,
  the Pattern B watcher ceiling, and the budget envelope.
- [docs/design/FEAT-JARVIS-004/decisions/](docs/design/FEAT-JARVIS-004/decisions/) —
  FEAT-JARVIS-004 design decision records (DDR-016 … DDR-024). Covers
  dispatch timeouts, retry-with-redirect, the routing-history schema,
  fire-and-forget Graphiti writes, the concurrent-dispatch cap, and the
  trace-file collision policy.
- [docs/design/FEAT-JARVIS-005/decisions/](docs/design/FEAT-JARVIS-005/decisions/) —
  FEAT-JARVIS-005 design decision records (DDR-025 … DDR-031). Covers
  the real `queue_build` JetStream transport, the
  `forge_notifications.py` module placement, the ephemeral push consumer
  with `deliver_policy=NEW`, the bounded in-memory correlation map, the
  append-only `stage_complete` edge model, CLI between-prompts
  rendering, and adapter identity from `Session.adapter`.

## Repository Layout

```
src/jarvis/         — production source (5-group module layout per ADR-ARCH-006)
  ├── agents/       — DeepAgents shell + supervisor factory
  ├── adapters/     — NATS, Graphiti, llama-swap I/O edges
  ├── routing/      — capability-description assembly + decision types
  ├── tools/        — @tool functions (dispatch, graphiti, external, …)
  ├── sessions/     — thread-per-session model + summary-bridge
  └── …
tests/              — pytest suite (unit + integration)
docs/               — architecture, design, research, history, reviews
features/           — Gherkin feature files per FEAT-JARVIS-***
tasks/              — backlog / completed task records
langgraph.json      — LangGraph graph manifest (jarvis + jarvis_reasoner)
```

## Further Reading

- [docs/research/ideas/jarvis-vision.md](docs/research/ideas/jarvis-vision.md) —
  master vision (intent router, fleet topology, NATS topics, build
  sequence).
- [docs/research/ideas/general-purpose-agent.md](docs/research/ideas/general-purpose-agent.md) —
  the "everything else" ReAct agent design.
- [docs/research/ideas/phase3-build-plan.md](docs/research/ideas/phase3-build-plan.md) —
  Phase 3 build plan with the Status Log driving Step 14.
- [docs/README.md](docs/README.md) — documentation index.
- [CLAUDE.md](CLAUDE.md) — repo-level guidance for Claude Code.
