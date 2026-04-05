# Jarvis — Intent Router & Ship's Computer

The central orchestration layer for the Ship's Computer agent fleet. Jarvis classifies
natural language requests from any input adapter (Reachy Mini voice, Telegram, Slack,
dashboard, CLI) and dispatches them to the appropriate specialist agent.

## Status: Pre-Architecture

Vision documents ready in `docs/research/ideas/`. Next step: run `/system-arch`.

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
