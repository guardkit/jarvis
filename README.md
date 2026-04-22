# Jarvis — Intent Router & Ship's Computer

The central orchestration layer for the Ship's Computer agent fleet. Jarvis classifies
natural language requests from any input adapter (Reachy Mini voice, Telegram, Slack,
dashboard, CLI) and dispatches them to the appropriate specialist agent.

## Status: Pre-Architecture

Vision documents ready in `docs/research/ideas/`. Next step: run `/system-arch`.

## Quickstart

Run everything via `uv run …`; `uv` selects the project's pinned 3.12 interpreter (see `.python-version`).

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd jarvis

# 2. Create the project venv (uv reads .python-version → 3.12)
#    and install runtime + dev deps in one step.
uv sync

# 3. Copy the example env file and configure
cp .env.example .env
# Edit .env with your provider keys / endpoints

# 4. Run the test suite
uv run pytest

# 5. Launch the CLI
uv run jarvis version
```

## Development — Tests, Lint, Types

Every dev command goes through `uv run …`. That resolves the tool from
`.venv/bin/` against the pinned 3.12 interpreter; bypassing it (bare `pytest`,
bare `ruff`) can silently hit a system Python with different package versions.

```bash
# Full regression (what CI-equivalent Step 7 of the build plan runs)
uv run pytest                                          # 341 passing
uv run pytest --cov=src/jarvis --cov-report=term       # with coverage
uv run ruff check src/jarvis/ tests/                   # lint
uv run mypy src/jarvis/                                # types (strict)

# Targeted runs while iterating
uv run pytest tests/test_supervisor.py -v              # one file
uv run pytest tests/test_supervisor.py::TestBuildSupervisorReturnsGraph -v
uv run pytest -k "supervisor and not no_llm" -v        # keyword filter
uv run pytest --lf                                     # re-run last failures
```

### Dev dependency layout

Dev tooling (pytest, ruff, mypy, types-*) lives in `[dependency-groups].dev`
(PEP 735), **not** `[project.optional-dependencies]`. This means:

- Bare `uv sync` installs them by default — no `--extra dev` / `--dev` flag
  needed. Earlier iterations had them as an optional-extra, which caused
  `uv sync` to silently prune `.venv/bin/pytest` on every run and then
  `uv run pytest` fell through to the system Python.
- `uv sync --no-dev` skips them (useful for prod/release builds).
- `uv sync --extra providers` adds the optional provider SDKs
  (`langchain-anthropic`, `langchain-google-genai`) — those are still an
  `[project.optional-dependencies]` extra because they are runtime, not dev.

### Troubleshooting

**`uv run` warns about `VIRTUAL_ENV=…` not matching `.venv`.** Something in
your shell exported `VIRTUAL_ENV` pointing at a non-project interpreter (often
a framework Python). `uv run` ignores it, but you can silence the warning
with `unset VIRTUAL_ENV` or `deactivate`.

**Tests fail with `ModuleNotFoundError: No module named 'jarvis'` in a
subprocess.** `.venv/bin/python` is fine, but something invoked a different
Python (e.g. a stale `uv run` picked up `/usr/local/bin/pytest`). Verify
with `uv run python -c "import sys; print(sys.executable)"` — it must resolve
to `.venv/bin/python3`. If not, re-sync: `rm -rf .venv && uv sync`.

**`OpenAIError: The api_key client option must be set…` in supervisor tests.**
Only unmocked tests would hit a real OpenAI client. Every test that calls
`build_supervisor` must patch `jarvis.agents.supervisor.init_chat_model` — use
the `fake_llm` fixture from `tests/conftest.py`. See
`tests/test_supervisor.py::TestBuildSupervisorReturnsGraph` for the canonical
pattern.

## The Full Pipeline

```
Ideation Agent → Product Owner Agent → Architect Agent → GuardKit Factory
(explore)        (document)             (architect)       (implement)
```

Plus YouTube Planner (content), General Purpose Agent (everything else), and GCSE Tutor (future).

## Agent Fleet (8 Agents)

| Agent | Repo | Complexity | Purpose |
|-------|------|-----------|---------|
| **Intent Router** | `jarvis` | Low | Classify intent, dispatch to specialist |
| **General Purpose** | `jarvis` | Low | Everything else — research, drafts, chores, tools |
| **Ideation** | `ideation-agent` | Medium | Structured brainstorming with weighted evaluation |
| **Product Owner** | `product-owner-agent` | Medium | Raw info → structured product documentation |
| **Architect** | `architect-agent` | Medium | Product docs → C4/ADRs → `/system-arch` input |
| **GuardKit Factory** | `guardkitfactory` | High | Autonomous software development pipeline |
| **YouTube Planner** | `youtube-planner` | Medium | Content planning from idea to script |
| **GCSE Tutor** | (future) | Medium | Fine-tuned Nemotron Nano via Reachy "Scholar" |

All weighted-evaluation agents use `langchain-deepagents-weighted-evaluation` template
with Gemini 3.1 Pro for reasoning. All communicate via NATS JetStream.

## Docs

- `docs/research/ideas/jarvis-vision.md` — Master vision, fleet architecture, intent classification, NATS topics, build sequence
- `docs/research/ideas/general-purpose-agent.md` — The "everything else" ReAct agent with phased tool categories
- `docs/research/ideas/nemoclaw-assessment.md` — Evidence-based NemoClaw rejection (D6) with revisit signals
- `docs/research/ideas/reachy-mini-integration.md` — Embodied voice interface (Scholar + Bridge units)

## Fleet Master Index

The single document that ties all repos together:
`guardkitfactory/docs/research/ideas/fleet-master-index.md`

## Build Command

```bash
# 1. Paste jarvis-vision.md into a new Claude Desktop conversation
# 2. Run: /system-arch "Jarvis Intent Router"
# 3. Then: /system-design → /system-plan → /feature-spec → /feature-plan → autobuild
```
