# API-tools — Tool Surface Contract

> **Surface:** DeepAgents `@tool(parse_docstring=True)` functions registered on the Jarvis supervisor graph.
> **Consumer:** the reasoning model running inside `create_deep_agent(...)`. Tool docstrings ARE the contract — the reasoning model reads them at decision time per ADR-ARCH-016-equivalent pattern.
> **Failure discipline:** every tool follows [ADR-ARCH-021](../../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md) — return a structured string on failure; never raise. Prefix conventions: `ERROR:`, `DEGRADED:`, `TIMEOUT:`.
> **All docstrings below are the *authoritative* docstring text for the AutoBuild player.** Changes require a note in the commit message because docstrings change routing behaviour (per Phase 2 scope §Do-Not-Change ¶7, adapted to the tool layer).

---

## 1. General Tools — `jarvis.tools.general`

### 1.1 `read_file(path: str) -> str`

```python
@tool(parse_docstring=True)
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the user's workspace and return its contents.

    Use this tool when the user refers to a file on disk ("summarise /tmp/foo.md",
    "what's in my notes folder") or when you need file contents to answer. Do NOT
    use it for binary files or files outside the configured workspace root — those
    return a structured error.

    Near-zero cost, <100ms typical latency. No network I/O.

    Args:
        path: Absolute or workspace-relative path. Path traversal outside the
              workspace root is rejected.

    Returns:
        The file contents as a string, OR a structured error:
          - ``ERROR: path_traversal — path resolves outside workspace: <resolved>``
          - ``ERROR: not_found — path does not exist: <path>``
          - ``ERROR: not_a_file — path is a directory or special file: <path>``
          - ``ERROR: too_large — file exceeds 1MB, refusing to read: <path>``
          - ``ERROR: encoding — file is not valid UTF-8: <path>``
    """
```

**Safety:** workspace root is `JarvisConfig.workspace_root` (defaulting to the current working directory resolved at startup). File size cap: 1 MB. Uses the same path-safety guards as DeepAgents built-in filesystem per Phase 2 scope §1.1.

---

### 1.2 `search_web(query: str, max_results: int = 5) -> str`

```python
@tool(parse_docstring=True)
def search_web(query: str, max_results: int = 5) -> str:
    """Run a web search and return up to N results as JSON.

    Use this tool for factual lookups, recent information, or when the user asks
    you to find something online. Prefer over invoking a subagent for simple
    lookups — the subagent cost and latency are higher. Do NOT use it for
    knowledge already in the conversation or for reasoning tasks.

    Moderate cost (~$0.005/query via Tavily), ~1–3s typical latency.
    Requires TAVILY_API_KEY configured; returns a structured error otherwise.

    Args:
        query: The search query string. Non-empty.
        max_results: Maximum number of results to return (1–10). Default 5.

    Returns:
        JSON array of WebResult objects:
          ``[{"title": str, "url": str, "snippet": str, "score": float}, ...]``
        OR a structured error:
          - ``ERROR: config_missing — tavily_api_key not set in JarvisConfig``
          - ``ERROR: invalid_query — query must be non-empty``
          - ``ERROR: invalid_max_results — must be between 1 and 10, got <n>``
          - ``DEGRADED: provider_unavailable — Tavily returned <status>``
    """
```

**Provider:** Tavily, per [DDR-006](../decisions/DDR-006-tavily-as-web-search-provider.md). Provider abstraction allows swap without changing the docstring.

---

### 1.3 `get_calendar_events(window: Literal["today", "tomorrow", "this_week"] = "today") -> str`

```python
@tool(parse_docstring=True)
def get_calendar_events(window: str = "today") -> str:
    """Return calendar events for a named time window.

    Use this tool when the user asks "what's on today", "do I have time next
    Thursday", or similar calendar-shaped questions. Prefer this over reasoning
    about the calendar from memory — the tool reads live data when a real
    provider is configured.

    STUB in Phase 2: returns an empty list ``[]`` (or a canned list configured
    for tests). Signature is stable — FEAT-JARVIS-007's morning-briefing skill
    depends on this shape. Near-zero cost, <50ms latency.

    Args:
        window: One of "today", "tomorrow", "this_week". Default "today".

    Returns:
        JSON array of CalendarEvent objects:
          ``[{"id": str, "title": str, "start": ISO8601, "end": ISO8601,
              "location": str | null, "description": str | null}, ...]``
        OR a structured error:
          - ``ERROR: invalid_window — must be one of today/tomorrow/this_week, got <value>``
    """
```

---

### 1.4 `calculate(expression: str) -> str`

```python
@tool(parse_docstring=True)
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely and return the result.

    Use this tool for ANY arithmetic — percentages, unit conversion, compound
    calculations. You are bad at arithmetic; the tool is not. Do NOT use it for
    symbolic manipulation, calculus, or anything that requires an algebra
    system — those return a structured error.

    Near-zero cost, <10ms latency. No network I/O.

    Args:
        expression: A mathematical expression. Supported operators: + - * / ** %
                    and parentheses. Supported functions: sqrt, log, exp, sin,
                    cos, tan, abs, min, max, round. Variables are NOT supported.

    Returns:
        The result as a string (numeric or truthy), OR a structured error:
          - ``ERROR: unsafe_expression — disallowed token: <token>``
          - ``ERROR: parse_error — <detail>``
          - ``ERROR: division_by_zero``
          - ``ERROR: overflow — result exceeds float range``
    """
```

**Implementation:** `asteval` (AST-based evaluator; no `eval`) per [DDR-007](../decisions/DDR-007-asteval-for-calculate.md).

---

## 2. Capability Catalogue Tools — `jarvis.tools.capabilities`

### 2.1 `list_available_capabilities() -> str`

```python
@tool(parse_docstring=True)
def list_available_capabilities() -> str:
    """Return the current fleet capability catalogue as JSON.

    The catalogue is also injected into your system prompt at session start
    (under "## Available Capabilities"). Call this tool only when you suspect
    the injected snapshot is stale — e.g., the user says "a new agent just came
    online" or more than ~10 minutes have elapsed in the same session.

    In Phase 2 this reads from an in-memory stub registry; in FEAT-JARVIS-004
    (Phase 3) it will read from the live NATS KV manifest registry. The
    signature and response shape are identical across phases.

    Near-zero cost, <5ms latency (stub) / <30ms (cached live registry).

    Returns:
        JSON array of CapabilityDescriptor objects:
          ``[{"agent_id": str, "role": str, "description": str,
              "capability_list": [{"tool_name": str, "description": str,
                                   "risk_level": str}, ...],
              "cost_signal": str, "latency_signal": str,
              "last_heartbeat_at": ISO8601 | null,
              "trust_tier": "core" | "specialist" | "extension"}, ...]``
        OR a structured error:
          - ``ERROR: registry_unavailable — <detail>``
    """
```

### 2.2 `capabilities_refresh() -> str`

```python
@tool(parse_docstring=True)
def capabilities_refresh() -> str:
    """Invalidate the cached capability catalogue and re-read the source of truth.

    Call this ONLY when the user explicitly indicates the catalogue is stale —
    e.g. "the architect agent should be up now, check again". The injected
    system-prompt snapshot is refreshed at session start; mid-session refresh
    is rarely useful.

    STUB in Phase 2: no-op that returns a structured acknowledgement. Phase 3
    (FEAT-JARVIS-004) triggers a real NATS KV re-read.

    Returns:
        ``OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)``
        OR a structured error in Phase 3+.
    """
```

### 2.3 `capabilities_subscribe_updates() -> str`

```python
@tool(parse_docstring=True)
def capabilities_subscribe_updates() -> str:
    """Subscribe the current session to live capability-change notifications.

    STUB in Phase 2: no-op that returns a structured acknowledgement. Phase 3
    (FEAT-JARVIS-004) attaches a NATS KV watcher that will re-inject the
    capability block into future turns when fleet membership changes.

    Call at most once per session.

    Returns:
        ``OK: subscribed (stubbed in Phase 2 — no live updates)``
        OR a structured error in Phase 3+.
    """
```

---

## 3. Dispatch Tools — `jarvis.tools.dispatch`

### 3.1 `dispatch_by_capability(tool_name: str, payload_json: str, intent_pattern: str | None = None, timeout_seconds: int = 60) -> str`

**This tool supersedes `call_specialist` per [DDR-005](../decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md).** No `agent_id` parameter — resolution happens against the capability catalogue per ADR-ARCH-016-equivalent pattern.

```python
@tool(parse_docstring=True)
def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str | None = None,
    timeout_seconds: int = 60,
) -> str:
    """Dispatch work to a specialist agent by capability name, not agent name.

    Resolution order:
      1. Exact match on a registered ToolCapability.name across the catalogue.
      2. If no exact match, match IntentCapability.pattern (if intent_pattern
         is provided) with highest confidence wins.
      3. If still unresolved, returns ``ERROR: unresolved``. Reason the
         response yourself — do not retry the same dispatch with a different
         tool_name unless the user confirms.

    Use this tool when the user asks for work that falls under a specialist
    agent's description (e.g. "ask the architect for a C4 diagram", "have
    product-owner review this spec"). Check the capability catalogue first —
    injected at session start under "## Available Capabilities" — to find the
    tool_name you need. Do NOT pass agent IDs; pass capability names.

    In Phase 2 the transport is stubbed: the tool builds a real CommandPayload
    per nats-core, logs it, and returns a canned ResultPayload JSON for tests.
    FEAT-JARVIS-004 replaces the stub with real NATS round-trips without
    changing this docstring.

    Cost depends on the resolved specialist; latency is capped by
    timeout_seconds. Moderate cost (~$0.10–$2 per dispatch, specialist-
    dependent); 5–60s typical wall-clock.

    Args:
        tool_name: The ToolCapability.name to invoke (e.g.
                   ``run_architecture_session``). Required.
        payload_json: JSON string matching the tool's parameters schema as
                     declared in its ToolCapability.parameters. Must be a JSON
                     object literal (starts with ``{``). The tool does NOT
                     validate your payload against the schema in Phase 2 — the
                     specialist will.
        intent_pattern: Optional intent pattern (e.g. ``architecture.generate``)
                       used only when no exact tool match is found.
        timeout_seconds: How long to wait for the specialist's reply, between
                        5 and 600. Default 60. Timeout returns a structured
                        TIMEOUT error; it does NOT cancel the specialist — the
                        result may still appear in NATS after timeout
                        (Phase 3+).

    Returns:
        JSON string of the specialist's ResultPayload on success:
          ``{"command": str, "result": {...}, "correlation_id": str,
             "success": true}``
        OR a structured error:
          - ``ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>``
          - ``ERROR: invalid_payload — payload_json is not a JSON object literal``
          - ``ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>``
          - ``TIMEOUT: agent_id=<id> tool_name=<x> timeout_seconds=<n>``
          - ``ERROR: specialist_error — agent_id=<id> detail=<reason>``
          - ``DEGRADED: transport_stub — (Phase 2 stub, real NATS arrives in FEAT-JARVIS-004)``
    """
```

**Stub behaviour (Phase 2):** configurable per test via a module-level `_stub_response_hook`:

| Stub mode | Returns |
|---|---|
| `success` (default) | Canned `ResultPayload` with `success=True` and `result={"stub": true, "tool_name": <x>}` |
| `timeout` | `TIMEOUT: ...` structured error |
| `specialist_error` | `ERROR: specialist_error — agent_id=<id> detail=<reason>` |

**Phase 3 (FEAT-JARVIS-004) migration points:** The log line `JARVIS_DISPATCH_STUB tool_name=... agent_id=... correlation_id=...` is the grep anchor — swapping the stub for real NATS publish/subscribe loops replaces the log line with an actual publish. Tool docstring and return shape stay identical.

---

### 3.2 `queue_build(feature_id: str, feature_yaml_path: str, repo: str, branch: str = "main", originating_adapter: str = "terminal", correlation_id: str | None = None, parent_request_id: str | None = None) -> str`

```python
@tool(parse_docstring=True)
def queue_build(
    feature_id: str,
    feature_yaml_path: str,
    repo: str,
    branch: str = "main",
    originating_adapter: str = "terminal",
    correlation_id: str | None = None,
    parent_request_id: str | None = None,
) -> str:
    """Queue a Forge build for an already-planned feature. Pattern A per
    ADR-SP-014: Jarvis publishes and walks away; Forge consumes from JetStream.

    Use this tool when the user has a feature spec already produced (via
    /feature-spec and /feature-plan) and says "build it" or equivalent. Do NOT
    use it to kick off planning — that is not a Forge responsibility. If the
    user asks you to plan, route to the architect or product-owner specialist
    via dispatch_by_capability instead.

    In Phase 2 the transport is stubbed: the tool builds a real
    BuildQueuedPayload per nats-core, logs it, and returns a canned ACK.
    FEAT-JARVIS-005 replaces the stub with a real
    pipeline.build-queued.{feature_id} JetStream publish without changing this
    docstring.

    Fire-and-forget. Near-zero publish latency when real; Forge may take hours
    to complete the build — you will receive pipeline.* progress events via
    notifications in FEAT-JARVIS-005. Do not await completion.

    Args:
        feature_id: FEAT-XXX identifier matching ``^FEAT-[A-Z0-9]{3,12}$``.
        feature_yaml_path: Path to the feature YAML spec, relative to the
                           repo root (e.g. ``features/feat-jarvis-002/....yaml``).
        repo: GitHub org/repo, e.g. ``guardkit/jarvis`` or ``appmilla/forge``.
              Must match ``^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$``.
        branch: Base branch to branch from. Default ``main``.
        originating_adapter: Which Jarvis adapter the human used. One of
                            ``terminal``, ``voice-reachy``, ``telegram``,
                            ``slack``, ``dashboard``, ``cli-wrapper``.
                            Default ``terminal`` (CLI). ``triggered_by`` is
                            always set to ``jarvis`` by this tool.
        correlation_id: Stable ID for tracing. Auto-generated if omitted.
        parent_request_id: The Jarvis dispatch message ID that spawned this
                          build, for progress-event correlation. Optional.

    Returns:
        JSON string of the QueueBuildAck on success:
          ``{"feature_id": str, "correlation_id": str,
             "queued_at": ISO8601,
             "publish_target": "pipeline.build-queued.{feature_id}",
             "status": "queued"}``
        OR a structured error:
          - ``ERROR: invalid_feature_id — must match FEAT-XXX pattern, got <value>``
          - ``ERROR: invalid_repo — must be org/name format, got <value>``
          - ``ERROR: invalid_adapter — <value> not in allowed list``
          - ``ERROR: validation — <pydantic detail>``
          - ``DEGRADED: transport_stub — (Phase 2 stub, real publish arrives in FEAT-JARVIS-005)``
    """
```

**Stub behaviour (Phase 2):** always returns success. Log line prefix: `JARVIS_QUEUE_BUILD_STUB feature_id=... correlation_id=... repo=...`.

**Phase 4 (FEAT-JARVIS-005) migration:** the log-only stub becomes a real `jetstream.publish(subject=Topics.Pipeline.BUILD_QUEUED.format(...), payload=MessageEnvelope(...))` call. Tool signature, docstring, and return shape unchanged.

---

## 4. Registration on the supervisor

All 9 tools are collected into a single list via `jarvis.tools.assemble_tool_list(config, capability_registry)` and passed to `build_supervisor(config, tools=..., available_capabilities=...)`. The ordering in the list is not semantically significant (DeepAgents surfaces tool descriptions alphabetically), but the registration module keeps a stable alphabetical order to reduce prompt-cache churn.

Deferred to later features:

- `start_async_task`, `wait_for_async_tasks`, etc. — added by `AsyncSubAgentMiddleware` in FEAT-JARVIS-003.
- `escalate_to_frontier` — reserved slot in `jarvis.tools.dispatch`; lands with its own feature ticket after ADR-ARCH-027 implementation work.
- `record_routing_decision`, `record_ambient_event`, `query_knowledge` — Graphiti tools, FEAT-JARVIS-004.
- `emit_notification` — FEAT-JARVIS-004 / 006.
