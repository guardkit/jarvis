# DDR-008: Capabilities reach the supervisor via BOTH a `@tool` call AND a prompt-injected placeholder

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** Fleet Dispatch Context; `jarvis.prompts.supervisor_prompt`; `jarvis.tools.capabilities`; `jarvis.agents.supervisor`

## Context

Two competing signals about how the reasoning model should see the capability catalogue:

- [Phase 2 scope §1.2](../../../research/ideas/phase2-dispatch-foundations-scope.md) puts `list_available_capabilities()` on the tool surface — the reasoning model calls a tool to get the list.
- [ARCHITECTURE.md §3.A](../../../architecture/ARCHITECTURE.md) places `{available_capabilities}` as a placeholder in the supervisor system prompt — the list arrives as context at session start, as Forge ADR-ARCH-016 does for its reasoning model.

These are not mutually exclusive. Each has distinct properties:

| | Tool call | Prompt injection |
|---|---|---|
| When the reasoning model sees it | On demand | At session start, every turn |
| Cost | Tokens on demand | Tokens every turn |
| Staleness | Explicit opt-in refresh | Re-injected per session, not per turn |
| When it works well | Large catalogues, infrequent routing | Small catalogues, frequent routing |
| Failure mode | Missed tool call → routing blind | Cached snapshot stale if agent added mid-session |

Jarvis's catalogue is small (Phase 2: 4 entries; v1 launch expected: <20) and routing is frequent (every dispatch decision). Prompt injection is the dominant signal; the tool is an escape hatch.

## Decision

**Ship both.**

1. **Prompt injection (primary path).** `SUPERVISOR_SYSTEM_PROMPT` gains a `{available_capabilities}` placeholder between the attended-conversation section and the trace-richness section. `build_supervisor(...)` renders the registry snapshot (joining `CapabilityDescriptor.as_prompt_block()` with double newlines) and substitutes the placeholder via `str.format(...)`. When the registry is empty, the fallback text is literally `"No capabilities currently registered."` — asserted byte-equal by tests.

2. **Tool access (escape hatch).** `list_available_capabilities()`, `capabilities_refresh()`, and `capabilities_subscribe_updates()` remain on the tool surface with docstrings explicitly steering the reasoning model to the injected snapshot first.

3. **Consistency.** The rendered injection and the tool return serialise the *same* descriptors from the *same* registry snapshot. Tests assert this equivalence to prevent drift.

## Alternatives considered

1. **Prompt injection only (drop the tool).**
   Rejected — offers no path for mid-session refresh in Phase 3+ when real KV updates arrive. The tool surface is cheap to keep and it costs nothing in Phase 2.

2. **Tool only (drop the prompt placeholder).**
   Rejected — forces the reasoning model to issue a tool call on every turn that might need routing. With only 4–20 entries, the token overhead of prompt injection is dwarfed by the round-trip cost of an extra tool call.

3. **Tool-only but with result caching inside the tool.**
   Rejected — caching hides state from the reasoning model; the model can't tell whether it's looking at fresh or cached data. Prompt injection is explicit about "this is the snapshot at session start".

4. **Load-bearing docstring with static specialist names.**
   Rejected — violates ADR-ARCH-016 (no pre-coded catalogue); duplicates DDR-005's dispatch pattern.

## Consequences

- **+** Routing decisions work from turn 1 — no warm-up tool call needed.
- **+** Operators can inspect the catalogue Jarvis sees by reading the rendered prompt (available via `jarvis health` in FEAT-JARVIS-007+ or via debug logging in Phase 2).
- **+** The tool path is preserved for future use: mid-session refresh once FEAT-JARVIS-004's NATS KV watch is live, and as a debugging hook.
- **+** Phase 2's scope doc and ARCHITECTURE.md are both honoured — no contradiction with either.
- **−** Token cost per turn for the injected block. Mitigation: Phase 2 catalogue is small (~400 tokens across 4 descriptors); prompt caching at the LLM layer keeps this cheap.
- **−** The two paths must stay in sync. Mitigation: one shared render function (`CapabilityDescriptor.as_prompt_block()`) used by both; test asserts they serialise identically.
