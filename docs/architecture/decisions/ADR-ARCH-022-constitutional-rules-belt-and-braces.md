# ADR-ARCH-022: Constitutional rules enforced belt+braces — prompt AND executor assertion

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Mirrors:** Forge ADR-ARCH-026

## Context

Prompt-injection is a real risk: voice input (Reachy), email content (IMAP read-only v1), web search results, and Telegram messages from non-Rich sources (if ever) are all vectors for adversarial instructions. Defence in depth is required.

## Decision

Constitutional rules are enforced **belt+braces** — both:

1. **In the system prompt** — explicit instructions that certain tools / paths must never be invoked from ambient or untrusted contexts; ignored-input-frame patterns for untrusted content.
2. **At the executor** — assertion checks in the tool implementations themselves. E.g. `escalate_to_frontier` reads the current session context and asserts the session adapter is attended (`telegram` / `cli` / `dashboard` / `reachy`) AND that the caller frame is not an ambient watcher.

Both must hold for the action to proceed. Either alone is bypassable (prompt-injection defeats #1; reasoning-model mistakes defeat #2).

## Alternatives considered

1. **Prompt-only defence** *(rejected)*: Bypassable by sufficient prompt injection.
2. **Executor-only defence** *(rejected)*: Model may route around by invoking equivalent-effect tools; principled prompts help.

## Consequences

- `escalate_to_frontier` (ADR-ARCH-027) and other sensitive tools assert caller context at runtime.
- Constitutional prompt sections are versioned and live in `jarvis.prompts`.
- Captured as `ASSUM-015` — tighter sandboxing may be needed once real ambient usage data accumulates.
