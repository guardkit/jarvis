# Jarvis — Documentation

## docs/research/ideas/

Vision and ideation documents for the Jarvis system. These capture high-level thinking
and feed into `/system-arch` to produce formal architecture documents.

| Document | Purpose | Feeds Into |
|----------|---------|-----------|
| `jarvis-vision.md` | Master vision: intent router, agent fleet, NATS topics, adapters, build sequence | `/system-arch "Jarvis Intent Router"` |
| `general-purpose-agent.md` | The "everything else" ReAct agent: tools, model routing, compounding effect | `/system-arch "General Purpose Agent"` |
| `nemoclaw-assessment.md` | Evidence-based NemoClaw rejection (D6) with "when to revisit" signals | Reference — supports D6 decision |
| `reachy-mini-integration.md` | Embodied voice interface: two units, adapter architecture, CES validation | `/system-arch "Reachy Mini Adapter"` |

## How to Use

1. Pick the document for the component you want to build
2. Open a new Claude Desktop conversation
3. Paste the document content
4. Run the relevant `/system-arch` command
5. Continue through the GuardKit pipeline: `/system-design` → `/system-plan` → `/feature-spec` → `/feature-plan` → `autobuild`

## Build Order

Start with `jarvis-vision.md` — it's the umbrella that references everything else.
The General Purpose Agent can be built independently once NATS infrastructure exists.
Reachy Mini adapter comes last (hardware dependency).
