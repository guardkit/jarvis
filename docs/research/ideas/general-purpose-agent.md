# General Purpose Agent — The "Everything Else" Bucket

## For: `/system-arch` session · Part of Jarvis agent fleet · March 2026

---

## Purpose of this document

Captures the vision for the General Purpose Agent — the default agent that Jarvis dispatches
to when a request doesn't match any specialist (GuardKit Factory, YouTube Planner, Ideation
Agent). This is what makes Jarvis feel like a real assistant rather than a collection of
specialist tools.

---

## The Problem It Solves

Without a General Purpose Agent, Jarvis can only help with software engineering (GuardKit
Factory), content planning (YouTube Planner), and brainstorming (Ideation Agent). That's
useful but it's not Jarvis — it's three tools with a voice interface.

A real assistant handles the mundane: "What's the weather?", "Draft a message to James
about the FinProxy timeline", "Research the latest on NVIDIA driver 590", "What's happening
at AI Tinkerers Bristol this month?", "Add milk to the shopping list", "What time is the
DDD Southwest talk submission deadline?"

None of these need an adversarial loop, a multi-stage pipeline, or weighted evaluation.
They need a capable ReAct agent with good tools and fast turnaround.

---

## Architecture

### Template
`langchain-deepagents` (base template — no adversarial loop, no Coach, no weighted evaluation)

### Agent Pattern
Single ReAct agent with tool selection. The agent receives a natural language request,
reasons about which tools to use, executes them, and returns a result. One-shot or
short multi-turn — not long-running pipelines.

### Model Routing (Intent-Based)
- **Simple queries** (weather, time, basic lookups) → Local vLLM on GB10 (fast, free)
- **Complex reasoning** (research synthesis, drafting, analysis) → Cloud API (Gemini 3.1 Pro or Claude)
- **Privacy-sensitive** (personal data, calendar, email) → Local model on GB10

This mirrors the privacy router concept from NemoClaw but implemented simply via
the existing `agent-config.yaml` provider pattern.

---

## Tool Categories

The General Purpose Agent's power comes from its toolset. Each new tool expands what
Jarvis can do without any architectural change.

### Phase 1 — Core Tools (MVP)
| Tool | Purpose | Integration |
|------|---------|------------|
| **Web Search** | Research, current events, lookups | Web search API |
| **Web Fetch** | Read full web pages | HTTP client |
| **Calendar** | Schedule queries, event creation | Google Calendar API / MCP |
| **Email Draft** | Compose messages (human sends) | Gmail API / MCP |
| **Slack Draft** | Compose Slack messages | Slack API |
| **File Operations** | Read/write local files | Filesystem access |
| **Weather** | Weather queries | Weather API |
| **Timer/Reminder** | Set reminders, timers | Local scheduling + NATS notification |

### Phase 2 — Productivity Tools
| Tool | Purpose | Integration |
|------|---------|------------|
| **Linear** | Check sprint status, create tickets | Linear API |
| **Git** | Repo status, recent commits, branch info | Git CLI |
| **Note Taking** | Capture and retrieve notes | Local markdown + optional Graphiti |
| **Calculator** | Math, unit conversion | Python eval |

### Phase 3 — Home & Personal
| Tool | Purpose | Integration |
|------|---------|------------|
| **Home Automation** | Lights, heating, devices | Home Assistant API |
| **Shopping List** | Add/view/manage lists | Local storage or Todoist API |
| **Travel** | Route planning, transit times | Google Maps API |

### Phase 4 — Cross-Agent Tools
| Tool | Purpose | Integration |
|------|---------|------------|
| **Agent Status** | "What's the GuardKit Factory doing?" | NATS `agents.status.*` subscriber |
| **Agent Trigger** | "Start a pipeline for X" | NATS `jarvis.dispatch.*` publisher |
| **Knowledge Query** | "What did we decide about NemoClaw?" | Graphiti search |

---

## What Makes This Different from ChatGPT/Claude Desktop

Three things:

1. **Persistent presence** — It's always available via Reachy Mini voice, Telegram, or
   dashboard. You don't open an app and start a conversation; you speak or message and
   get a response.

2. **Local-first** — Simple queries run on your GB10 with zero latency and zero cost.
   Personal data never leaves your network.

3. **Fleet awareness** — It knows about the other agents. "What's building right now?"
   queries the fleet status. "Run that through the ideation agent" triggers a handoff.
   It's part of a system, not a standalone chat.

---

## Build Complexity

This is genuinely the simplest agent in the fleet. The base `langchain-deepagents` template
already provides:
- Agent scaffolding with tool registration
- Model factory with provider switching
- Observability and logging
- Preflight validation

The work is primarily:
1. Define and implement the Phase 1 tool set
2. Wire NATS adapter for input/output
3. Configure model routing rules
4. Test with Telegram adapter (quickest feedback loop)

**Estimated build time:** Weekend project once NATS infrastructure and templates are solid.

---

## Compounding Effect

Every new tool added to the General Purpose Agent expands Jarvis's capabilities without
building a new specialist agent. This is the fastest path to making Jarvis feel capable:

- Add a Google Calendar MCP tool → Jarvis manages your schedule
- Add a Linear tool → Jarvis checks your sprint
- Add a Home Assistant tool → Jarvis controls your lights
- Add a Spotify tool → Jarvis plays music

Each addition is a tool implementation, not an architecture change. The ReAct pattern
handles tool selection automatically.

---

## Open Questions for `/system-arch`

1. **Co-location vs separate repo** — Does this live in the `jarvis` repo alongside the
   intent router, or in its own repo? Co-location argument: it's the default/fallback,
   tightly coupled to the router. Separate repo argument: follows the pattern of all
   other agents.

2. **Session context** — How much conversation history does the General Purpose Agent
   retain? Single-turn (stateless, fast) or multi-turn (needs memory, slower)?

3. **Tool discovery** — Static tool list or dynamic? MCP server pattern would allow
   plugging in new tools at runtime.

4. **Escalation** — When should the General Purpose Agent say "this needs the Ideation
   Agent" or "this sounds like a GuardKit Factory task"? Reverse routing.
