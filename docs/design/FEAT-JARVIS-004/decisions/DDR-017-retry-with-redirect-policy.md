# DDR-017 — Retry-with-redirect: max 1 redirect, prefer same-capability match

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** [ADR-J-P4](../../../research/ideas/phase3-fleet-integration-scope.md) (fleet contract spirit), ADR-ARCH-015 (Forge capability-driven dispatch — pattern source), [DDR-016](DDR-016-dispatch-timeout-default-60s.md), [DDR-018](DDR-018-routing-history-schema-authoritative.md)

## Context

Phase 3 scope §"FEAT-JARVIS-004 Change 4" specifies retry-with-redirect:

> On timeout: retries with redirect — picks an alternative specialist via `list_available_capabilities` if another agent matches the capability (same pattern as Forge's redirect policy). If no alternative, returns a structured timeout error the supervisor surfaces to Rich.

Two open questions deferred to `/system-design`:

1. **Max redirect count.** Unbounded would loop until the catalogue is exhausted; 1 caps wall-clock; >2 multiplies attended-conversation latency.
2. **Selection criterion.** Same role with different `agent_id`? Different role with matching capability? The scope-doc says "prefer same-capability match" but doesn't pin the resolver behaviour.

The risk-mitigation table flags loops: "Max retry count (e.g. 2 total attempts); loop guard via visited-set on `agent_id`."

## Decision

Retry-with-redirect policy:

1. **Max 1 redirect** = 2 total attempts (original + 1 retry). Worst-case wall-clock = 2 × `timeout_seconds`.
2. **Selection criterion** — invoke the existing `_resolve_agent_id(tool_name, intent_pattern, registry, exclude=visited)` resolver (Phase 2 logic, extended with `exclude`). Resolution order:
   1. Exact `tool_name` match in any descriptor's `capability_list` (excluding visited `agent_id`s).
   2. Intent-pattern fallback — descriptor whose `role` or `description` substring-matches `intent_pattern` (excluding visited).
   3. `None` → outcome `"exhausted"`.
3. **Visited-set** — `set[str]` of attempted `agent_id`s, scoped to a single `dispatch_by_capability` invocation. Prevents loops if two specialists somehow expose the same capability in the catalogue but both time out / fail.
4. **Redirect triggers** on:
   - `asyncio.TimeoutError` — specialist did not reply within `timeout_seconds`.
   - `ResultPayload.success == False` — specialist explicitly errored. The error reason is captured in `RedirectAttempt.reason_skipped`.
5. **Redirect does NOT trigger on:**
   - `NATSConnectionError` — transport failure; immediate `DEGRADED: transport_unavailable` (DDR-021).
   - Pydantic validation errors on the reply — that's a contract violation; surfaces as `specialist_error`, no redirect (the next specialist would likely violate the same contract).

Lexicographic ordering of `agent_id` in the resolver is preserved so retry-with-redirect is **deterministic across runs** — testable, reproducible, and trace-record reproducible.

## Rationale

- **1 redirect, not 0.** Zero defeats the resilience case; if `architect-v1` times out and `architect-v2` exposes the same capability, redirect should let the second one serve.
- **1 redirect, not 2+.** Wall-clock doubles per attempt; 3+ attempts push attended latency past tolerable thresholds. The catalogue is small in v1 — multiple redundant specialists for the same capability are rare. When `jarvis.learning` (FEAT-J008) detects systemic timeout patterns, the response is to fix the timeout default or the catalogue, not to add more retries.
- **Same-capability priority** matches the spirit of "prefer same-capability match" from the scope-doc and Forge ADR-ARCH-015. Different-role-with-matching-capability is the fallback only when no exact-match exists.
- **Visited-set required.** Without it, two descriptors exposing the same `tool_name` could ping-pong on the same retries. The set is per-dispatch (not per-session) so a future dispatch starts fresh.
- **Lexicographic determinism** survives audit replay — the trace record's `attempts[0].agent_id` always equals the lexicographic-first match excluding the original.

## Alternatives considered

| Option | Why not |
|---|---|
| 0 redirects (no retry) | Defeats resilience; one specialist's transient timeout breaks the whole dispatch |
| 2+ redirects | Doubles or triples worst-case wall-clock; attended-UX degradation |
| Different-role priority | Diverges from Forge convention; harder to reason about; no observed motivating case in v1 |
| Random selection from candidates | Non-deterministic — breaks test reproducibility and trace audit replay |
| Reasoning-model-driven retry (return error → reasoning picks next agent) | Adds round-trip + token cost per retry; the resolver is structurally smarter (knows the catalogue + visited-set); reasoning still gets the final outcome and decides next steps |

## Consequences

- `_resolve_agent_id(tool_name, intent_pattern, registry, exclude=visited)` — `exclude` parameter added; default empty set preserves Phase 2 callers.
- `dispatch_by_capability` body gains the redirect loop per [design §8](../design.md).
- `JarvisRoutingHistoryEntry.attempts: list[RedirectAttempt]` captures the per-attempt detail (DDR-018).
- `outcome_type` Literal includes `"redirected"` and `"exhausted"`.
- Worst-case wall-clock bound: 2 × `timeout_seconds` = 120s default (DDR-016).
- `tests/test_dispatch_by_capability_integration.py` covers: (a) timeout → exhausted (no second specialist), (b) timeout → redirect → success, (c) timeout → redirect → timeout (exhausted), (d) specialist_error → redirect → success.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. If `jarvis.learning` (FEAT-J008) surfaces patterns suggesting more retries help, change is via append-only DDR.
