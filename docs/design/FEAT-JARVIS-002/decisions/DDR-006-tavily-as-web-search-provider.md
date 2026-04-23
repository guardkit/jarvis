# DDR-006: Tavily is the v1 provider behind `search_web`

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** External Tool Context; `jarvis.tools.general.search_web`

## Context

The Phase 2 scope document leaves the web-search provider open — *"Tavily (matches specialist-agent) is the default preference; ADR may pin"* ([phase2-dispatch-foundations-scope.md §Open Questions](../../../research/ideas/phase2-dispatch-foundations-scope.md)). `search_web` is a reused dependency — the FEAT-JARVIS-003 `long_research` subagent (once its scope is reconciled with ADR-ARCH-011) will call it, so the provider choice affects more than one feature.

## Decision

**`search_web` uses Tavily via `langchain-tavily` as the v1 provider.** The provider is wrapped behind an internal `WebSearchProvider` protocol inside `jarvis.tools.general`; the tool docstring does not name Tavily (it talks about "the configured web-search provider" internally), so a future swap does not require changing routing behaviour.

Environment variable: `JARVIS_TAVILY_API_KEY` → `JarvisConfig.tavily_api_key: SecretStr | None`.
Provider selector: `JarvisConfig.web_search_provider: Literal["tavily", "none"] = "tavily"`.
When `web_search_provider == "none"`, the tool always returns `ERROR: config_missing — no web-search provider configured`.

## Alternatives considered

1. **Bing Web Search API.** Rejected — recent Microsoft pricing changes make it ~3× the per-query cost, and integration is more surface (multiple response fields, scoring differences).
2. **SerpAPI.** Rejected — cost-per-query is higher than Tavily and the response format is tailored to SERP scraping, which is not what Jarvis needs.
3. **Provider-agnostic via a direct HTTP wrapper.** Rejected — adds a compatibility layer Jarvis doesn't need; `langchain-tavily` is already pinned for the fleet (specialist-agent uses it) and the `WebSearchProvider` protocol gives us swap-freedom later.
4. **No default — fail closed when provider is unconfigured.** Adopted in spirit: `search_web` returns a structured error at call time rather than failing at startup. The startup-time warning (Phase 1 `validate_provider_keys` extension) surfaces the config gap without blocking `jarvis chat` when web search isn't needed.

## Consequences

- **+** One provider, one API-key management path, one quota. Specialist-agent and Jarvis share it.
- **+** Tool docstring does not name Tavily — swapping to a different provider is a one-file change in `general.py` that doesn't touch routing.
- **+** `search_web` degrades gracefully when the API key is absent — the reasoning model receives a structured error and can fall back (e.g. ask the user, defer, or use `dispatch_by_capability` against a research-shaped specialist once v1.5 long_research lands).
- **−** Tavily outages mean Jarvis loses web-search capability until the provider recovers. Mitigation: structured `DEGRADED:` return lets the reasoning model adapt per ADR-ARCH-021.
- **−** Tavily pricing changes over time; the cost signal in the tool docstring (`~$0.005/query`) becomes approximate.
