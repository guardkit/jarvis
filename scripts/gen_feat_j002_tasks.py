#!/usr/bin/env python3
"""Generate the 23 task markdown files for FEAT-J002.

Source-of-truth: .claude/reviews/TASK-REV-J002-review-report.md
Review-locked approach: Option B (envelope-first, concurrent fan-out).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent

FEATURE_ID = "FEAT-J002"
PARENT_REVIEW = "TASK-REV-J002"
FEATURE_SLUG = "feat-jarvis-002-core-tools-and-dispatch"
OUT_DIR = Path("tasks/backlog/feat-jarvis-002-core-tools-and-dispatch")
CREATED_AT = "2026-04-24T06:55:00Z"


# §4 Integration Contract metadata — used to inject `consumer_context:` blocks
# onto every consumer task's frontmatter and to emit Seam Tests sections.
CAPABILITY_DESCRIPTOR_CONTRACT = {
    "task": "TASK-J002-003",
    "consumes": "CapabilityDescriptor",
    "framework": "LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent",
    "driver": "pydantic v2",
    "format_note": (
        "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore'); "
        "agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension']; "
        "as_prompt_block() renders deterministic text (see DM-tool-types.md §'Prompt-block shape')."
    ),
}
CORRELATION_ID_CONTRACT = {
    "task": "TASK-J002-005",
    "consumes": "new_correlation_id",
    "framework": "stdlib uuid.uuid4",
    "driver": "stdlib",
    "format_note": (
        "new_correlation_id() -> str returning str(uuid.uuid4()); result matches "
        "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$; "
        "no shared state; safe under concurrent invocation (ASSUM-001)."
    ),
}
STUB_HOOK_CONTRACT = {
    "task": "TASK-J002-007",
    "consumes": "_stub_response_hook + LOG_PREFIX constants",
    "framework": "DDR-009 swap-point discipline",
    "driver": "stdlib logging + nats_core.events models",
    "format_note": (
        "_stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None; "
        "module-level LOG_PREFIX_DISPATCH='JARVIS_DISPATCH_STUB' and "
        "LOG_PREFIX_QUEUE_BUILD='JARVIS_QUEUE_BUILD_STUB' are the grep anchors. "
        "grep -rn must return exactly 4 lines (2 constants + 2 logger.info usages) post-Wave-3."
    ),
}
TOOL_LIST_CONTRACT = {
    "task": "TASK-J002-015",
    "consumes": "assemble_tool_list",
    "framework": "LangChain BaseTool list consumed by create_deep_agent",
    "driver": "langchain-core",
    "format_note": (
        "assemble_tool_list(config, capability_registry) -> list[BaseTool] returns the 9 tools "
        "in stable alphabetical order (calculate, capabilities_refresh, "
        "capabilities_subscribe_updates, dispatch_by_capability, get_calendar_events, "
        "list_available_capabilities, queue_build, read_file, search_web); closure-binds "
        "capability_registry into capability + dispatch tools (snapshot isolation)."
    ),
}


@dataclass
class Task:
    id: str
    title: str
    task_type: str  # scaffolding | feature | testing | declarative
    complexity: int
    wave: int
    dependencies: list[str]
    implementation_mode: str  # direct | task-work
    estimated_minutes: int
    description: str
    acceptance_criteria: list[str]
    scenarios_covered: list[str]
    swap_point_note: str | None = None
    consumer_context: list[dict] = field(default_factory=list)
    seam_tests: list[dict] = field(default_factory=list)  # each dict: contract metadata
    test_requirements: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# TASK DEFINITIONS
# --------------------------------------------------------------------------

TASKS: list[Task] = [
    Task(
        id="TASK-J002-001",
        title="Extend JarvisConfig with Phase 2 fields",
        task_type="declarative",
        complexity=2,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=30,
        description=(
            "Add four Phase-2 fields to JarvisConfig: web_search_provider, tavily_api_key, "
            "stub_capabilities_path, workspace_root. All respect the JARVIS_ env-var prefix. "
            "validate_provider_keys() emits a warning (not an error) when Tavily is selected "
            "without a key — startup should not fail merely because the provider is unconfigured."
        ),
        acceptance_criteria=[
            "`JarvisConfig` gains four fields: `web_search_provider: Literal[\"tavily\",\"none\"] = \"tavily\"`, `tavily_api_key: SecretStr | None = None`, `stub_capabilities_path: Path = Path(\"src/jarvis/config/stub_capabilities.yaml\")`, `workspace_root: Path = Path(\".\").resolve()`.",
            "Env var names respect the `JARVIS_` prefix (JARVIS_WEB_SEARCH_PROVIDER, JARVIS_TAVILY_API_KEY, JARVIS_STUB_CAPABILITIES_PATH, JARVIS_WORKSPACE_ROOT).",
            "`validate_provider_keys()` emits a warning (not a ConfigurationError) when `web_search_provider == \"tavily\"` and `tavily_api_key is None`.",
            "Phase 1 config tests in `tests/test_config.py` still pass unchanged.",
        ],
        scenarios_covered=[
            "Searching the web without a configured Tavily key returns a configuration error",
        ],
        swap_point_note=None,
    ),
    Task(
        id="TASK-J002-002",
        title="Write canonical stub_capabilities.yaml",
        task_type="declarative",
        complexity=1,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=20,
        description=(
            "Create the canonical 4-entry stub_capabilities.yaml fixture that Phase 2 uses in "
            "place of a real NATS KV manifest registry. Deleted in FEAT-JARVIS-004."
        ),
        acceptance_criteria=[
            "File exists at `src/jarvis/config/stub_capabilities.yaml` containing exactly four capabilities: `architect-agent`, `product-owner-agent`, `ideation-agent`, `forge`.",
            "Content matches byte-for-byte the canonical YAML in DM-stub-registry.md §\"Canonical Phase 2 content\".",
            "All `agent_id` values are kebab-case; all `tool_name` values are snake_case; all `trust_tier` values are one of `core|specialist|extension`.",
            "`forge` entry carries a `build_feature` capability so the reasoning model sees Forge alongside specialists in the catalogue.",
        ],
        scenarios_covered=[
            "Listing available capabilities returns the current stub registry",
        ],
        swap_point_note="DELETED in FEAT-JARVIS-004 when NATSKVManifestRegistry wires live reads. Grep anchor: `stub_capabilities.yaml`.",
    ),
    Task(
        id="TASK-J002-003",
        title="Define CapabilityDescriptor + CapabilityToolSummary Pydantic models",
        task_type="declarative",
        complexity=2,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=40,
        description=(
            "Define the Pydantic v2 models that carry capability metadata from the stub registry "
            "into the supervisor prompt and the dispatch resolver. Schema is frozen across "
            "Phase 2→3; extra='ignore' guards forward-compat with NATSKVManifestRegistry output."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/capabilities.py` defines `CapabilityToolSummary(BaseModel)` with fields `tool_name: str (min_length=1)`, `description: str (min_length=1)`, `risk_level: Literal[\"read_only\",\"mutating\",\"destructive\"] = \"read_only\"` and `ConfigDict(extra=\"ignore\")`.",
            "Same file defines `CapabilityDescriptor(BaseModel)` with fields `agent_id: str (pattern=r\"^[a-z][a-z0-9-]*$\")`, `role: str`, `description: str`, `capability_list: list[CapabilityToolSummary]`, `cost_signal: str = \"unknown\"`, `latency_signal: str = \"unknown\"`, `last_heartbeat_at: datetime | None = None`, `trust_tier: Literal[\"core\",\"specialist\",\"extension\"] = \"specialist\"`, and `ConfigDict(extra=\"ignore\")`.",
            "`CapabilityDescriptor.as_prompt_block() -> str` renders a deterministic text block whose format matches DM-tool-types.md §\"Prompt-block shape\" byte-for-byte.",
            "Module has no import of `jarvis.agents.*`, `jarvis.infrastructure.*`, or `jarvis.cli.*`.",
        ],
        scenarios_covered=[
            "Listing available capabilities returns the current stub registry",
            "The capability catalogue is injected into the supervisor system prompt at session start",
        ],
        swap_point_note="CapabilityDescriptor is the stable schema kept across Phase 2→3. No swap at this boundary.",
    ),
    Task(
        id="TASK-J002-004",
        title="Define WebResult, CalendarEvent, DispatchError Pydantic models",
        task_type="declarative",
        complexity=2,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=40,
        description=(
            "Define the three return-shape and error-envelope Pydantic models the general and "
            "dispatch tools use to structure their outputs per ADR-ARCH-021."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/types.py` defines `WebResult(BaseModel)` with `title: str (min_length=1)`, `url: str (min_length=1)`, `snippet: str = \"\"`, `score: float (ge=0, le=1) = 0.0`.",
            "Defines `CalendarEvent(BaseModel)` with `id: str`, `title: str`, `start: datetime`, `end: datetime`, `location: str | None`, `description: str | None`, and a `@model_validator(mode=\"after\")` asserting `end >= start`.",
            "Defines `DispatchError(BaseModel)` with `category: Literal[\"unresolved\",\"invalid_payload\",\"invalid_timeout\",\"timeout\",\"specialist_error\",\"transport_stub\"]`, `detail: str`, `agent_id: str | None`, `tool_name: str | None`, `correlation_id: str`, and `to_tool_string() -> str` method rendering `\"ERROR: <category> — <detail>\"` or `\"TIMEOUT: ...\"` per ADR-ARCH-021 conventions.",
            "All three models use `ConfigDict(extra=\"ignore\")`.",
        ],
        scenarios_covered=[
            "Searching the web with a configured provider returns result summaries",
            "Retrieving calendar events in Phase 2 returns an empty list",
        ],
        swap_point_note="n/a — stable schema across phases.",
    ),
    Task(
        id="TASK-J002-005",
        title="Correlation-ID primitive module",
        task_type="feature",
        complexity=2,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=30,
        description=(
            "Land the single callsite for dispatch-path correlation IDs per ASSUM-001. "
            "UUID4-based, no shared state — concurrent dispatches are isolated by construction."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/_correlation.py` exposes `new_correlation_id() -> str` returning `str(uuid.uuid4())`.",
            "Module has a single dependency: `uuid` from stdlib. No other imports.",
            "Unit test: 10,000 invocations produce 10,000 distinct strings; every string matches the UUID4 regex `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.",
            "Concurrent test: 100 threads each calling `new_correlation_id()` 100 times produce 10,000 distinct strings (no cross-contamination).",
            "Module docstring names this as the single callsite for dispatch-path correlation IDs per ASSUM-001.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Concurrent dispatch_by_capability calls produce distinct correlation ids and independent log lines",
        ],
        swap_point_note="n/a — correlation-id primitive is unchanged across phases.",
    ),
    Task(
        id="TASK-J002-006",
        title="Stub registry loader (load_stub_registry)",
        task_type="feature",
        complexity=3,
        wave=2,
        dependencies=["TASK-J002-003"],
        implementation_mode="direct",
        estimated_minutes=45,
        description=(
            "Load stub_capabilities.yaml into a validated list[CapabilityDescriptor]. "
            "Startup-fatal on missing or malformed YAML per design §7."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/capabilities.py` adds `load_stub_registry(path: Path) -> list[CapabilityDescriptor]`.",
            "Loads YAML at `path`; validates every entry against `CapabilityDescriptor`; returns list preserving YAML order.",
            "Raises `FileNotFoundError` if `path` does not exist (startup-fatal per design §7).",
            "Raises `pydantic.ValidationError` if any descriptor is malformed (e.g. uppercase `agent_id`).",
            "Rejects duplicate `agent_id` entries with a ValueError mentioning the duplicated id.",
            "Uses `yaml.safe_load` (never `yaml.load`).",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Starting Jarvis with a missing stub capabilities file fails fast at startup",
            "Starting Jarvis with a malformed stub capabilities file fails fast at startup",
        ],
        swap_point_note="DELETED in FEAT-JARVIS-004. Grep anchor: `load_stub_registry`.",
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT],
    ),
    Task(
        id="TASK-J002-007",
        title="Stub-response-hook contract for dispatch",
        task_type="scaffolding",
        complexity=2,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=30,
        description=(
            "Establish the named swap seam for dispatch. Creates the `_stub_response_hook` "
            "attribute, the StubResponse typed-dict/Literal union, and the two LOG_PREFIX "
            "constants. These are the DDR-009 grep anchors FEAT-JARVIS-004/005 will target."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/dispatch.py` defines a module-level attribute `_stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None`.",
            "Defines `StubResponse` as a typed dict / Literal union covering `(\"success\", ResultPayload) | (\"timeout\",) | (\"specialist_error\", str)`.",
            "Defines module-level string constants `LOG_PREFIX_DISPATCH = \"JARVIS_DISPATCH_STUB\"` and `LOG_PREFIX_QUEUE_BUILD = \"JARVIS_QUEUE_BUILD_STUB\"`.",
            "Module docstring carries a \"SWAP POINT\" section naming the two grep anchors and stating that FEAT-JARVIS-004 replaces `_stub_response_hook` with a real NATS round-trip.",
            "`grep -rn \"JARVIS_DISPATCH_STUB\\|JARVIS_QUEUE_BUILD_STUB\" src/jarvis/` returns exactly two lines (the two constant definitions) pre-feature wiring; after TASK-J002-013 and TASK-J002-014 land, it returns exactly four (two definitions + two `logger.info` usages).",
        ],
        scenarios_covered=[
            "Stubbed dispatches construct real nats-core payloads before logging",
            "Stubbed queue_build constructs a real BuildQueuedPayload before logging",
        ],
        swap_point_note="Establishes the grep anchors required by DDR-009. Test TASK-J002-021 asserts the grep-count invariant.",
    ),
    Task(
        id="TASK-J002-008",
        title="Implement read_file tool",
        task_type="feature",
        complexity=4,
        wave=2,
        dependencies=["TASK-J002-001", "TASK-J002-004"],
        implementation_mode="task-work",
        estimated_minutes=60,
        description=(
            "Read-only filesystem access scoped to config.workspace_root. Rejects path "
            "traversal, symlinks out, null-byte paths, non-UTF-8 bytes, and files over 1 MiB. "
            "Never raises — all errors are structured strings per ADR-ARCH-021."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/general.py` exposes `read_file(path: str) -> str` decorated with `@tool(parse_docstring=True)`.",
            "Docstring matches API-tools.md §1.1 byte-for-byte (it IS the contract per DDR-005 precedent).",
            "Resolves `path` relative to `config.workspace_root`; rejects paths whose `os.path.realpath` resolves outside workspace with `ERROR: path_traversal — path resolves outside workspace: <resolved>`.",
            "Rejects paths containing embedded null bytes (`\\x00`) with `ERROR: path_traversal — ...` (ASSUM-003: same category, no new one).",
            "Rejects symlinks whose resolved target lies outside workspace with `ERROR: path_traversal — ...` (ASSUM-002).",
            "Returns `ERROR: not_found — ...` for non-existent paths; `ERROR: not_a_file — ...` for directories; `ERROR: too_large — ...` for files > 1 MiB (boundary: exactly 1 MiB = accept; 1 MiB + 1 byte = reject); `ERROR: encoding — ...` for non-UTF-8 bytes.",
            "Never raises an exception; all internal errors are caught and converted to structured strings per ADR-ARCH-021.",
            "Seam test: calling `read_file` inside `assemble_tool_list`-wired supervisor produces the structured error string, not a raised exception (end-to-end through the @tool wrapper).",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Reading a UTF-8 text file inside the workspace returns its contents",
            "read_file enforces the one megabyte file size limit",
            "Reading a path outside the workspace returns a path traversal error",
            "Reading a path that does not exist returns a not-found error",
            "Reading a directory instead of a file returns a not-a-file error",
            "Reading a file with invalid UTF-8 bytes returns an encoding error",
            "read_file rejects paths that evade the workspace guard",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note=None,
    ),
    Task(
        id="TASK-J002-009",
        title="Implement search_web tool",
        task_type="feature",
        complexity=5,
        wave=2,
        dependencies=["TASK-J002-001", "TASK-J002-004"],
        implementation_mode="task-work",
        estimated_minutes=75,
        description=(
            "Web search via langchain-tavily provider. Hostile snippet content is surfaced "
            "verbatim as data per ASSUM-004. DEGRADED return shape for provider unavailability "
            "per ASSUM-005. Never raises."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/general.py` exposes `search_web(query: str, max_results: int = 5) -> str` decorated with `@tool(parse_docstring=True)`.",
            "Docstring matches API-tools.md §1.2 byte-for-byte.",
            "Uses the `langchain-tavily` provider wrapper; returns `ERROR: config_missing — tavily_api_key not set in JarvisConfig` when `config.tavily_api_key is None`.",
            "Rejects empty query with `ERROR: invalid_query — query must be non-empty`.",
            "Rejects `max_results` outside `[1, 10]` with `ERROR: invalid_max_results — must be between 1 and 10, got <n>` (boundaries: 1 and 10 accept; 0 and 11 reject).",
            "On provider non-success response returns `DEGRADED: provider_unavailable — Tavily returned <status>` per ASSUM-005 exact format.",
            "Returns hostile snippet content verbatim in `WebResult.snippet` — no sanitisation (ASSUM-004). No side-effecting tool calls from inside `search_web`.",
            "Returns JSON array of `WebResult` dicts on success.",
            "Never raises.",
            "Seam test: with `fake_tavily_response` fixture, calling via `assemble_tool_list`-wired supervisor returns parseable JSON matching the WebResult shape.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Searching the web with a configured provider returns result summaries",
            "search_web accepts max_results only within its documented range",
            "Searching the web without a configured Tavily key returns a configuration error",
            "Searching the web with an empty query returns an invalid-query error",
            "search_web preserves and surfaces hostile snippet content as data without acting on it",
            "search_web surfaces provider unavailability as a DEGRADED result",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note="Provider abstraction grep anchor: `class TavilyProvider`. A future FEAT can swap providers without docstring change per DDR-006.",
    ),
    Task(
        id="TASK-J002-010",
        title="Implement get_calendar_events tool",
        task_type="feature",
        complexity=2,
        wave=2,
        dependencies=["TASK-J002-004"],
        implementation_mode="direct",
        estimated_minutes=40,
        description=(
            "Phase 2 stub returning an empty CalendarEvent JSON array for any valid window. "
            "Return shape matches the real-provider contract so the FEAT-JARVIS-007 "
            "morning-briefing skill parses identically against stub and real data."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/general.py` exposes `get_calendar_events(window: str = \"today\") -> str` decorated with `@tool(parse_docstring=True)`.",
            "Docstring matches API-tools.md §1.3 byte-for-byte; argument type annotation is `Literal[\"today\",\"tomorrow\",\"this_week\"]`.",
            "Returns JSON `\"[]\"` (Phase 2 stub) for any valid `window`.",
            "Rejects invalid window with `ERROR: invalid_window — must be one of today/tomorrow/this_week, got <value>` listing the allowed windows.",
            "Returned shape is a JSON array of `CalendarEvent`-shaped dicts (even when empty) so FEAT-JARVIS-007's morning-briefing skill parses identically against stub and real data.",
            "Never raises.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Retrieving calendar events in Phase 2 returns an empty list",
            "Requesting calendar events for an unknown window returns an invalid-window error",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note="Stub returns empty list; real provider in v1.5. Grep anchor: `Phase 2 stub` inside get_calendar_events docstring.",
    ),
    Task(
        id="TASK-J002-011",
        title="Implement calculate tool",
        task_type="feature",
        complexity=4,
        wave=2,
        dependencies=["TASK-J002-004"],
        implementation_mode="task-work",
        estimated_minutes=60,
        description=(
            "Safe arithmetic via asteval.Interpreter per DDR-007. Rejects unsafe tokens "
            "(__import__, open, lambda, def). Handles percentage shorthand. Never raises."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/general.py` exposes `calculate(expression: str) -> str` decorated with `@tool(parse_docstring=True)`.",
            "Docstring matches API-tools.md §1.4 byte-for-byte.",
            "Uses `asteval.Interpreter` (DDR-007); disables `__import__`, `open`, `lambda`, function definitions.",
            "Supports operators `+ - * / ** %` + parentheses; functions `sqrt log exp sin cos tan abs min max round`.",
            "Rejects `__import__('os').getcwd`, `open('/etc/passwd')`, `lambda x: x` with `ERROR: unsafe_expression — disallowed token: <token>`.",
            "Returns `ERROR: division_by_zero` for `1/0`-shaped inputs.",
            "Returns `ERROR: overflow — result exceeds float range` for overflow (e.g. `10.0 ** 500`).",
            "Returns `ERROR: parse_error — <detail>` for syntactically malformed input.",
            "Handles `\"15% of 847\"` by preprocessing `X% of Y` → `X/100 * Y`; returns the numeric result as a string.",
            "Never raises; all asteval internal errors are trapped and converted.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Evaluating a supported arithmetic expression returns a numeric result",
            "Calculating an expression that divides by zero returns a structured error",
            "Calculating an expression that exceeds the float range returns an overflow error",
            "Calculator rejects expressions containing unsafe tokens",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note=None,
    ),
    Task(
        id="TASK-J002-012",
        title="Implement list_available_capabilities + refresh + subscribe tools",
        task_type="feature",
        complexity=3,
        wave=2,
        dependencies=["TASK-J002-003", "TASK-J002-006"],
        implementation_mode="task-work",
        estimated_minutes=50,
        description=(
            "Three @tool functions over the closed-over capability registry snapshot. "
            "list_available_capabilities returns a JSON-serialised COPY (snapshot isolation per "
            "ASSUM-006). refresh and subscribe are Phase-2 no-ops returning exact OK strings — "
            "their bodies are the Phase-2→3 swap targets."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/capabilities.py` exposes three `@tool(parse_docstring=True)` functions: `list_available_capabilities() -> str`, `capabilities_refresh() -> str`, `capabilities_subscribe_updates() -> str`.",
            "Docstrings match API-tools.md §2.1–2.3 byte-for-byte.",
            "`list_available_capabilities` returns JSON-serialised copy of the registry list captured at `assemble_tool_list` time. Snapshot isolation invariant (ASSUM-006): the closed-over list is NOT mutated; a subsequent `capabilities_refresh` does not affect an in-flight call.",
            "`capabilities_refresh` returns the exact string `\"OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)\"`.",
            "`capabilities_subscribe_updates` returns the exact string `\"OK: subscribed (stubbed in Phase 2 — no live updates)\"`.",
            "All three never raise; internal errors wrapped as `ERROR: registry_unavailable — <detail>`.",
            "Concurrent test: issuing `list_available_capabilities()` and `capabilities_refresh()` in parallel returns the startup snapshot from the former and the OK string from the latter with no mutation of the snapshot between call start and return.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Listing available capabilities returns the current stub registry",
            "capabilities_refresh and capabilities_subscribe_updates return OK acknowledgements in Phase 2",
            "list_available_capabilities returns a stable snapshot even when refresh is called concurrently",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note="`capabilities_refresh` and `capabilities_subscribe_updates` bodies are the Phase 2→3 swap targets. Grep anchor: `stubbed in Phase 2` inside capabilities.py.",
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT],
    ),
    Task(
        id="TASK-J002-013",
        title="Implement dispatch_by_capability tool",
        task_type="feature",
        complexity=7,
        wave=2,
        dependencies=["TASK-J002-003", "TASK-J002-004", "TASK-J002-005", "TASK-J002-007"],
        implementation_mode="task-work",
        estimated_minutes=110,
        description=(
            "The primary dispatch tool. Resolves tool_name → agent_id against the capability "
            "registry (exact match, then intent_pattern fallback). Constructs real nats-core "
            "CommandPayload + MessageEnvelope. Emits exactly one JARVIS_DISPATCH_STUB log line. "
            "Honours _stub_response_hook for testability. This is the PRIMARY DDR-009 swap point."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/dispatch.py` exposes `dispatch_by_capability(tool_name: str, payload_json: str, intent_pattern: str | None = None, timeout_seconds: int = 60) -> str` decorated with `@tool(parse_docstring=True)`.",
            "Docstring matches API-tools.md §3.1 byte-for-byte.",
            "Resolution: exact `CapabilityToolSummary.tool_name` match wins; else `intent_pattern` substring match on descriptor `role`/`description` with highest-confidence (first match on lexicographic agent_id order for stability); else `ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>`.",
            "Validates `payload_json` is a JSON object literal (starts with `{`, parses to dict). Non-object / non-JSON → `ERROR: invalid_payload — payload_json is not a JSON object literal`.",
            "Validates `timeout_seconds` in `[5, 600]`. Out of range → `ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>`.",
            "Constructs a real `nats_core.events.CommandPayload` with `command=tool_name`, `args=json.loads(payload_json)`, `correlation_id=new_correlation_id()` (uses TASK-J002-005 helper).",
            "Constructs a real `MessageEnvelope(source_id=\"jarvis\", event_type=EventType.COMMAND, correlation_id=..., payload=command.model_dump(mode=\"json\"))`.",
            "Emits exactly one `logger.info` call per invocation with message starting with `LOG_PREFIX_DISPATCH` (= `\"JARVIS_DISPATCH_STUB\"`) and containing `tool_name=<x> agent_id=<y> correlation_id=<z> topic=agents.command.<y> payload_bytes=<n>` in the rendered line.",
            "Honours `_stub_response_hook`: unset → returns canned `ResultPayload` JSON with `success=True, result={\"stub\":True,\"tool_name\":<x>}, correlation_id=<same>`; `timeout` → `TIMEOUT: agent_id=<y> tool_name=<x> timeout_seconds=<n>`; `specialist_error` → `ERROR: specialist_error — agent_id=<y> detail=<reason>`.",
            "No retry inside the tool (DDR-009 §6); error string returned verbatim.",
            "Concurrent dispatches produce distinct correlation IDs; two parallel invocations yield two distinct `JARVIS_DISPATCH_STUB` log lines, each carrying its own correlation_id.",
            "Seam test: dispatches succeed end-to-end through `assemble_tool_list`-wired supervisor fixture; log capture verifies exactly-one log line per call.",
            "Never raises; Pydantic ValidationError on MessageEnvelope construction is caught and returned as `ERROR: validation — <detail>`.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Dispatching by capability resolves a specialist and returns a successful result",
            "dispatch_by_capability accepts timeout_seconds only within 5 to 600",
            "Dispatching by an unknown capability name returns an unresolved error",
            "dispatch_by_capability rejects payloads that are not JSON object literals",
            "Dispatching by capability with a simulated timeout returns a timeout error",
            "Dispatching by capability falls back to intent pattern matching when no exact tool match exists",
            "Stubbed dispatches construct real nats-core payloads before logging",
            "Concurrent dispatch_by_capability calls produce distinct correlation ids and independent log lines",
            "dispatch_by_capability surfaces specialist-side failures as structured errors",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note=(
            "**PRIMARY DDR-009 SWAP POINT.** Grep anchors: `JARVIS_DISPATCH_STUB` (the log-line "
            "prefix), `_stub_response_hook` (the hook attribute). FEAT-JARVIS-004 replaces the "
            "`logger.info` call with `await nats.request(...)` and removes `_stub_response_hook`; "
            "tool docstring and return shape are untouched."
        ),
        consumer_context=[
            CAPABILITY_DESCRIPTOR_CONTRACT,
            CORRELATION_ID_CONTRACT,
            STUB_HOOK_CONTRACT,
        ],
        seam_tests=[STUB_HOOK_CONTRACT],
    ),
    Task(
        id="TASK-J002-014",
        title="Implement queue_build tool",
        task_type="feature",
        complexity=6,
        wave=2,
        dependencies=["TASK-J002-004", "TASK-J002-005", "TASK-J002-007"],
        implementation_mode="task-work",
        estimated_minutes=90,
        description=(
            "The build-queue publisher tool. Validates feature_id / repo / originating_adapter, "
            "constructs a real BuildQueuedPayload + MessageEnvelope, emits one JARVIS_QUEUE_BUILD_STUB "
            "log line, and returns a QueueBuildAck JSON. PRIMARY DDR-009 swap point (FEAT-JARVIS-005)."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/dispatch.py` exposes `queue_build(feature_id: str, feature_yaml_path: str, repo: str, branch: str = \"main\", originating_adapter: str = \"terminal\", correlation_id: str | None = None, parent_request_id: str | None = None) -> str` decorated with `@tool(parse_docstring=True)`.",
            "Docstring matches API-tools.md §3.2 byte-for-byte.",
            "Validates `feature_id` against `^FEAT-[A-Z0-9]{3,12}$`; rejects invalid with `ERROR: invalid_feature_id — must match FEAT-XXX pattern, got <value>`.",
            "Validates `repo` against `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`; rejects invalid with `ERROR: invalid_repo — must be org/name format, got <value>`.",
            "Validates `originating_adapter` in `{terminal, telegram, dashboard, voice-reachy, slack, cli-wrapper}`; rejects other with `ERROR: invalid_adapter — <value> not in allowed list`.",
            "Constructs real `BuildQueuedPayload` with `triggered_by=\"jarvis\"`, `originating_adapter=<value>`, `correlation_id=correlation_id or new_correlation_id()`, `requested_at=now_utc()`, `queued_at=now_utc()`.",
            "Constructs real `MessageEnvelope(source_id=\"jarvis\", event_type=EventType.BUILD_QUEUED, correlation_id=..., payload=...)`.",
            "Emits exactly one `logger.info` call with message starting with `LOG_PREFIX_QUEUE_BUILD` (= `\"JARVIS_QUEUE_BUILD_STUB\"`) and containing `feature_id=<x> repo=<y> correlation_id=<z> topic=pipeline.build-queued.<x> payload_bytes=<n>`.",
            "Returns `QueueBuildAck` JSON: `{\"feature_id\":<x>,\"correlation_id\":<z>,\"queued_at\":<iso>,\"publish_target\":\"pipeline.build-queued.<x>\",\"status\":\"queued\"}`.",
            "Uses `Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)` — singular-topic ADR-SP-016 compliant.",
            "Pydantic ValidationError caught at tool boundary → `ERROR: validation — <pydantic detail>` (ADR-ARCH-021).",
            "Never raises.",
            "Seam test: dispatches succeed end-to-end through `assemble_tool_list`-wired supervisor fixture; payload JSON round-trips through `BuildQueuedPayload.model_validate_json`.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "Queueing a build for a planned feature returns an acknowledgement",
            "queue_build validates feature_id against the documented pattern",
            "queue_build validates repo against the org/name pattern",
            "queue_build restricts originating_adapter to the documented values",
            "Stubbed queue_build constructs a real BuildQueuedPayload before logging",
            "Every tool converts internal errors into structured strings rather than raising",
        ],
        swap_point_note=(
            "**PRIMARY DDR-009 SWAP POINT.** Grep anchor: `JARVIS_QUEUE_BUILD_STUB`. "
            "FEAT-JARVIS-005 replaces the `logger.info` call with "
            "`await js.publish(subject=Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id), payload=envelope.model_dump_json().encode())`. "
            "Tool docstring and return shape untouched."
        ),
        consumer_context=[CORRELATION_ID_CONTRACT, STUB_HOOK_CONTRACT],
        seam_tests=[STUB_HOOK_CONTRACT],
    ),
    Task(
        id="TASK-J002-015",
        title="assemble_tool_list + tools package __init__ re-exports",
        task_type="scaffolding",
        complexity=3,
        wave=3,
        dependencies=[
            "TASK-J002-008", "TASK-J002-009", "TASK-J002-010", "TASK-J002-011",
            "TASK-J002-012", "TASK-J002-013", "TASK-J002-014",
        ],
        implementation_mode="direct",
        estimated_minutes=40,
        description=(
            "Wire the 9 tools into one assemble_tool_list(config, capability_registry) function. "
            "Returns tools in stable alphabetical order. Closure-binds the capability registry "
            "into capability + dispatch tools — this is where snapshot isolation is enforced. "
            "tools/__init__.py re-exports the public surface."
        ),
        acceptance_criteria=[
            "`src/jarvis/tools/__init__.py` re-exports exactly the public surface listed in API-internal.md §1.1 (11 symbols plus `assemble_tool_list` and `load_stub_registry`).",
            "`src/jarvis/tools/__init__.py` exposes `assemble_tool_list(config: JarvisConfig, capability_registry: list[CapabilityDescriptor]) -> list[BaseTool]`.",
            "`assemble_tool_list` returns the 9 tools in stable alphabetical order: `calculate, capabilities_refresh, capabilities_subscribe_updates, dispatch_by_capability, get_calendar_events, list_available_capabilities, queue_build, read_file, search_web`.",
            "`assemble_tool_list` is the **only** place that binds capability_registry into the capability + dispatch tools via closure (snapshot isolation).",
            "No other module imports `jarvis.tools.general`, `jarvis.tools.capabilities`, `jarvis.tools.dispatch` directly — only `jarvis.tools`.",
        ],
        scenarios_covered=[
            "The supervisor is built with all nine Phase 2 tools wired",
        ],
        swap_point_note=None,
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT],
    ),
    Task(
        id="TASK-J002-016",
        title="Extend supervisor_prompt with Tool-Usage section + {available_capabilities}",
        task_type="feature",
        complexity=3,
        wave=2,
        dependencies=["TASK-J002-003"],
        implementation_mode="direct",
        estimated_minutes=45,
        description=(
            "Add a {available_capabilities} placeholder and a Tool Usage preference list to "
            "SUPERVISOR_SYSTEM_PROMPT. Phase 1 content is preserved verbatim (TASK-J001-004 "
            "scope invariant). No mention of deprecated tool names."
        ),
        acceptance_criteria=[
            "`src/jarvis/prompts/supervisor_prompt.py` `SUPERVISOR_SYSTEM_PROMPT` gains a `{available_capabilities}` placeholder inserted after the attended-conversation section and before the Trace Richness section.",
            "Gains a `## Tool Usage` section with the preference list from design §10 (prefer calculate over mental arithmetic; list_available_capabilities at most once per session; prefer dispatch_by_capability over repeating specialist work; queue_build only when feature explicitly named; return structured-error strings as-is).",
            "Phase 1 content is preserved verbatim (TASK-J001-004 scope invariant): attended-conversation posture, identity, model-selection philosophy unchanged; no mention of `call_specialist`, `start_async_task`, `morning-briefing`, named subagents, or skills.",
            "The `{domain_prompt}` placeholder remains at the bottom of the prompt (per existing domain-prompt-injection pattern).",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "The capability catalogue is injected into the supervisor system prompt at session start",
            "Building the supervisor with no registered capabilities renders a safe prompt fallback",
        ],
        swap_point_note=None,
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT],
    ),
    Task(
        id="TASK-J002-017",
        title="Extend build_supervisor signature and lifecycle wiring",
        task_type="feature",
        complexity=4,
        wave=3,
        dependencies=["TASK-J002-015", "TASK-J002-016"],
        implementation_mode="task-work",
        estimated_minutes=70,
        description=(
            "Extend build_supervisor with keyword-only tools and available_capabilities kwargs "
            "(Phase 1 callers unaffected). Wire lifecycle.build_app_state to load the stub "
            "registry, assemble the tool list, and pass both into build_supervisor. AppState "
            "gains a capability_registry field."
        ),
        acceptance_criteria=[
            "`jarvis.agents.supervisor.build_supervisor` gains two keyword-only kwargs: `tools: list[BaseTool] | None = None` and `available_capabilities: list[CapabilityDescriptor] | None = None`. Phase 1 callers (no kwargs) still work.",
            "When `available_capabilities` is None or empty, `{available_capabilities}` is replaced with the exact string `\"No capabilities currently registered.\"` per `.feature` L305.",
            "When non-empty, descriptors are rendered via `CapabilityDescriptor.as_prompt_block()` in deterministic order by `agent_id`, joined with `\"\\n\\n\"`.",
            "When `tools` is None, passes `tools=[]` to `create_deep_agent` (Phase 1 behaviour preserved).",
            "`jarvis.infrastructure.lifecycle.build_app_state` gains steps: `capability_registry = load_stub_registry(config.stub_capabilities_path)`, `tool_list = assemble_tool_list(config, capability_registry)`, then passes both into `build_supervisor(config, tools=tool_list, available_capabilities=capability_registry)`.",
            "`AppState` gains `capability_registry: list[CapabilityDescriptor]` field.",
            "Startup still completes in under 2 seconds with the 4-entry stub registry (no network).",
            "Seam test: calling `build_app_state(test_config)` returns an `AppState` whose `supervisor` has 9 tools wired and `capability_registry` has 4 entries.",
            "All modified files pass project-configured lint/format checks with zero errors.",
        ],
        scenarios_covered=[
            "The supervisor is built with all nine Phase 2 tools wired",
            "The capability catalogue is injected into the supervisor system prompt at session start",
            "Building the supervisor with no registered capabilities renders a safe prompt fallback",
        ],
        swap_point_note=(
            "`assemble_tool_list` and `load_stub_registry` are the two lifecycle seams rewritten "
            "in FEAT-JARVIS-004. Grep anchors: `assemble_tool_list`, `load_stub_registry`."
        ),
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT, TOOL_LIST_CONTRACT],
    ),
    Task(
        id="TASK-J002-018",
        title="Unit tests for tool types (types.py + capabilities.py models)",
        task_type="testing",
        complexity=3,
        wave=4,
        dependencies=["TASK-J002-003", "TASK-J002-004"],
        implementation_mode="direct",
        estimated_minutes=45,
        description=(
            "pytest suite exercising Pydantic validation on every model in types.py and "
            "capabilities.py, including the as_prompt_block byte-equal assertion."
        ),
        acceptance_criteria=[
            "`tests/test_tools_types.py` added with at least 12 tests covering Pydantic validation for CapabilityDescriptor (valid + invalid agent_id pattern + unknown risk_level), CapabilityToolSummary, WebResult (score bounds), CalendarEvent (end>=start validator), DispatchError (category literal).",
            "`as_prompt_block` byte-equal assertion against DM-tool-types.md §\"Prompt-block shape\" example.",
            "All tests use `pytest` + `unittest.mock` per .claude/CLAUDE.md rules.",
            "No tests require network or filesystem beyond `tmp_path`.",
        ],
        scenarios_covered=[
            "Listing available capabilities returns the current stub registry",
            "Building the supervisor with no registered capabilities renders a safe prompt fallback",
        ],
        swap_point_note=None,
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT],
    ),
    Task(
        id="TASK-J002-019",
        title="Unit tests for general tools",
        task_type="testing",
        complexity=5,
        wave=4,
        dependencies=["TASK-J002-008", "TASK-J002-009", "TASK-J002-010", "TASK-J002-011"],
        implementation_mode="task-work",
        estimated_minutes=90,
        description=(
            "pytest suite exercising every general-tool scenario in the .feature: read_file "
            "(9 scenarios), search_web (6), get_calendar_events (2), calculate (4). Uses "
            "fake_tavily_response fixture — no real network."
        ),
        acceptance_criteria=[
            "`tests/test_tools_general.py` exercises every Group-A / Group-B / Group-C / Group-D / Group-E scenario in the `.feature` file that targets a general tool.",
            "`read_file`: happy path + 1MB-boundary table + traversal + null-byte + symlink + not-found + not-a-file + too-large + encoding (9 scenarios).",
            "`search_web`: happy path + max_results table + missing key + empty query + DEGRADED + hostile-snippet-passthrough (6 scenarios).",
            "`get_calendar_events`: stub empty + invalid_window (2 scenarios).",
            "`calculate`: happy path + division_by_zero + overflow + unsafe tokens table (4 scenarios).",
            "Uses `fake_tavily_response` fixture (monkeypatched Tavily client). No real network.",
            "Each @tool's `Every tool converts internal errors into structured strings rather than raising` coverage row is asserted.",
        ],
        scenarios_covered=["all Group-A/B/C/D general-tool scenarios listed in TASK-J002-008/009/010/011"],
        swap_point_note=None,
    ),
    Task(
        id="TASK-J002-020",
        title="Unit tests for capability tools + snapshot isolation",
        task_type="testing",
        complexity=4,
        wave=4,
        dependencies=["TASK-J002-006", "TASK-J002-012"],
        implementation_mode="direct",
        estimated_minutes=70,
        description=(
            "pytest suite covering the stub registry loader and the three capability @tools, "
            "including the ASSUM-006 snapshot-isolation concurrency test."
        ),
        acceptance_criteria=[
            "`tests/test_tools_capabilities.py` covers: stub YAML loads into 4 descriptors; `list_available_capabilities` returns JSON of 4 descriptors; refresh/subscribe OK acks; startup-fatal on missing YAML; startup-fatal on malformed YAML (invalid agent_id uppercase); snapshot isolation (concurrent `list_available_capabilities` + `capabilities_refresh` via `concurrent.futures` — both succeed, snapshot unchanged).",
            "Byte-equal check on the `OK:` strings from refresh and subscribe.",
            "Duplicate-agent_id YAML is rejected by loader.",
        ],
        scenarios_covered=[
            "Listing available capabilities returns the current stub registry",
            "Starting Jarvis with a missing stub capabilities file fails fast at startup",
            "Starting Jarvis with a malformed stub capabilities file fails fast at startup",
            "capabilities_refresh and capabilities_subscribe_updates return OK acknowledgements in Phase 2",
            "list_available_capabilities returns a stable snapshot even when refresh is called concurrently",
        ],
        swap_point_note=None,
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT],
    ),
    Task(
        id="TASK-J002-021",
        title="Unit tests for dispatch tools + swap-point grep invariant",
        task_type="testing",
        complexity=6,
        wave=4,
        dependencies=["TASK-J002-007", "TASK-J002-013", "TASK-J002-014"],
        implementation_mode="task-work",
        estimated_minutes=110,
        description=(
            "pytest suite for dispatch_by_capability and queue_build, including the grep-invariant "
            "test that guards the DDR-009 swap-point anchors. Uses fake_dispatch_stub to flip "
            "_stub_response_hook between success / timeout / specialist_error modes."
        ),
        acceptance_criteria=[
            "`tests/test_tools_dispatch.py` covers every dispatch-targeted scenario in `.feature`.",
            "`dispatch_by_capability`: happy path resolves `run_architecture_session` → `architect-agent`; intent-pattern fallback; timeout_seconds table (5, 60, 600, 4, 601); invalid JSON payload table; unresolved; simulated timeout via `_stub_response_hook`; specialist_error via `_stub_response_hook`; concurrent dispatch produces distinct UUIDs (ThreadPoolExecutor with 2 parallel calls, assert `{id_a} != {id_b}`, assert 2 log lines with matching correlation_ids).",
            "`queue_build`: happy path; feature_id table (FEAT-AB1, FEAT-JARVIS-EXAMPLE01 accept; FEAT-AB, feat-jarvis-002, BUG-JARVIS-001 reject); repo table (accept/reject per Gherkin); originating_adapter table (accept/reject per Gherkin).",
            "Asserts log lines match exact format: `JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y> correlation_id=<z> topic=agents.command.<y> payload_bytes=<n>`; same format pattern for `JARVIS_QUEUE_BUILD_STUB`.",
            "Asserts real `CommandPayload` and `BuildQueuedPayload` instances (not dicts) are constructed — `isinstance` check on captured object.",
            "**Swap-point grep invariant test:** a helper runs `grep -rn \"JARVIS_DISPATCH_STUB\\|JARVIS_QUEUE_BUILD_STUB\" src/jarvis/` and asserts the result contains exactly the expected lines (2 constants + 2 usages = 4 lines minimum, all in `src/jarvis/tools/dispatch.py`). Test fails if anchor leaks to another module or anchor name drifts.",
            "Uses `fake_dispatch_stub` fixture to flip `_stub_response_hook` between modes.",
        ],
        scenarios_covered=[
            "Dispatching by capability resolves a specialist and returns a successful result",
            "Queueing a build for a planned feature returns an acknowledgement",
            "dispatch_by_capability accepts timeout_seconds only within 5 to 600",
            "queue_build validates feature_id against the documented pattern",
            "queue_build validates repo against the org/name pattern",
            "queue_build restricts originating_adapter to the documented values",
            "Dispatching by an unknown capability name returns an unresolved error",
            "dispatch_by_capability rejects payloads that are not JSON object literals",
            "Dispatching by capability with a simulated timeout returns a timeout error",
            "Dispatching by capability falls back to intent pattern matching when no exact tool match exists",
            "Stubbed dispatches construct real nats-core payloads before logging",
            "Stubbed queue_build constructs a real BuildQueuedPayload before logging",
            "Concurrent dispatch_by_capability calls produce distinct correlation ids and independent log lines",
            "dispatch_by_capability surfaces specialist-side failures as structured errors",
        ],
        swap_point_note=(
            "Contains the **grep-invariant test** that guards DDR-009. If this test fails, a "
            "swap-point anchor has drifted and FEAT-JARVIS-004/005 will lose its landmark."
        ),
        consumer_context=[STUB_HOOK_CONTRACT],
    ),
    Task(
        id="TASK-J002-022",
        title="Integration test: supervisor-with-tools + nine-tool wiring + prompt injection",
        task_type="testing",
        complexity=5,
        wave=5,
        dependencies=[
            "TASK-J002-017", "TASK-J002-018", "TASK-J002-019",
            "TASK-J002-020", "TASK-J002-021",
        ],
        implementation_mode="task-work",
        estimated_minutes=80,
        description=(
            "Final-wave integration test: build_app_state produces a supervisor with exactly 9 "
            "tools in alphabetical order and a prompt containing the capability block. Phase 1 "
            "tests still green. Coverage of src/jarvis/tools/ ≥ 80%."
        ),
        acceptance_criteria=[
            "`tests/test_supervisor_with_tools.py` creates `test_config` + 4-entry `capability_registry` fixtures; calls `build_app_state(test_config)`.",
            "Asserts the compiled `supervisor` graph exposes exactly the 9 tool names in alphabetical order: `calculate, capabilities_refresh, capabilities_subscribe_updates, dispatch_by_capability, get_calendar_events, list_available_capabilities, queue_build, read_file, search_web`.",
            "Asserts the rendered system prompt contains the `{available_capabilities}` block built from 4 descriptors (each `as_prompt_block()` substring appears verbatim).",
            "Asserts empty-registry path: `build_supervisor(test_config, tools=[], available_capabilities=[])` renders the `\"No capabilities currently registered.\"` sentinel.",
            "No LLM call is made (FakeListChatModel or equivalent); no network.",
            "Phase 1 test modules (`tests/test_supervisor.py`, `tests/test_supervisor_no_llm_call.py`, `tests/test_sessions.py`, `tests/test_config.py`, `tests/test_infrastructure.py`, `tests/test_prompts.py`) all still pass unchanged.",
            "Coverage of `src/jarvis/tools/` ≥ 80%.",
        ],
        scenarios_covered=[
            "The supervisor is built with all nine Phase 2 tools wired",
            "The capability catalogue is injected into the supervisor system prompt at session start",
            "Building the supervisor with no registered capabilities renders a safe prompt fallback",
        ],
        swap_point_note=None,
        consumer_context=[CAPABILITY_DESCRIPTOR_CONTRACT, TOOL_LIST_CONTRACT],
    ),
    Task(
        id="TASK-J002-023",
        title="pyproject + dependency management",
        task_type="scaffolding",
        complexity=2,
        wave=1,
        dependencies=[],
        implementation_mode="direct",
        estimated_minutes=25,
        description=(
            "Add Phase-2 runtime dependencies (langchain-tavily, asteval, nats-core, pyyaml). "
            "Deliberately DOES NOT add nats-py — Phase 2 scope invariant forbids a live NATS "
            "client. Phase 1 dependencies are untouched."
        ),
        acceptance_criteria=[
            "`pyproject.toml` adds `langchain-tavily` (or the ADR-DDR-006-pinned equivalent), `asteval`, `nats-core` (for Pydantic payload imports), `pyyaml` if not already present.",
            "`nats-py` (the NATS client library) is NOT added — Phase 2 scope invariant.",
            "`uv lock` is regenerated; `uv sync` completes clean.",
            "Phase 1 dependencies are untouched.",
        ],
        scenarios_covered=[],
        swap_point_note=None,
    ),
]


# --------------------------------------------------------------------------
# FILE GENERATION
# --------------------------------------------------------------------------

def _yaml_quote(s: str) -> str:
    """Escape a string for safe YAML double-quoted scalar."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _slug_from_title(title: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-")


def _consumer_context_yaml(entries: list[dict]) -> str:
    if not entries:
        return ""
    lines = ["consumer_context:"]
    for e in entries:
        lines.append(f'  - task: {e["task"]}')
        lines.append(f'    consumes: "{_yaml_quote(e["consumes"])}"')
        lines.append(f'    framework: "{_yaml_quote(e["framework"])}"')
        lines.append(f'    driver: "{_yaml_quote(e["driver"])}"')
        lines.append(f'    format_note: "{_yaml_quote(e["format_note"])}"')
    return "\n".join(lines) + "\n"


def _seam_tests_section(seam_tests: list[dict], task_id: str) -> str:
    if not seam_tests:
        return ""
    blocks = [
        "## Seam Tests",
        "",
        "The following seam test(s) validate the integration contract(s) with the producer "
        "task(s). Implement before integration.",
        "",
    ]
    for contract in seam_tests:
        artifact_name = contract["consumes"]
        producer = contract["task"]
        fmt_note = contract["format_note"]
        # snake-case the first word of the artifact for the test name
        test_tok = artifact_name.split()[0].lower().replace("-", "_")
        blocks.extend([
            "```python",
            f'"""Seam test: verify {artifact_name} contract from {producer}."""',
            "import pytest",
            "",
            "",
            f'@pytest.mark.seam',
            f'@pytest.mark.integration_contract("{artifact_name}")',
            f"def test_{test_tok}_contract():",
            f'    """Verify {artifact_name} matches the expected format.',
            "",
            f"    Contract: {fmt_note}",
            f"    Producer: {producer}",
            '    """',
            "    # Producer side: acquire the artifact.",
            "    # e.g.: from jarvis.tools.dispatch import _stub_response_hook, LOG_PREFIX_DISPATCH",
            "    # Consumer side: verify format matches contract.",
            "    # e.g.: assert LOG_PREFIX_DISPATCH == \"JARVIS_DISPATCH_STUB\"",
            "    raise NotImplementedError(\"Implement the seam assertion derived from the contract above.\")",
            "```",
            "",
        ])
    return "\n".join(blocks)


def _render_task(task: Task) -> str:
    deps = ", ".join(f'"{d}"' for d in task.dependencies) if task.dependencies else ""
    deps_line = f"[{deps}]" if task.dependencies else "[]"
    scenarios = "\n".join(f'  - "{_yaml_quote(s)}"' for s in task.scenarios_covered)
    ac_lines = "\n".join(f"- [ ] {c}" for c in task.acceptance_criteria)
    cc_block = _consumer_context_yaml(task.consumer_context)
    seam_block = _seam_tests_section(task.seam_tests, task.id)

    fm = [
        "---",
        f"id: {task.id}",
        f'title: "{_yaml_quote(task.title)}"',
        f"task_type: {task.task_type}",
        "status: backlog",
        f"created: {CREATED_AT}",
        f"updated: {CREATED_AT}",
        "priority: high",
        f"complexity: {task.complexity}",
        f"wave: {task.wave}",
        f"implementation_mode: {task.implementation_mode}",
        f"estimated_minutes: {task.estimated_minutes}",
        f"dependencies: {deps_line}",
        f"parent_review: {PARENT_REVIEW}",
        f"feature_id: {FEATURE_ID}",
        "tags: [phase-2, jarvis, feat-jarvis-002]",
        "scenarios_covered:",
    ]
    if scenarios:
        fm.append(scenarios)
    else:
        fm.append("  []")
    if cc_block:
        fm.append(cc_block.rstrip())
    if task.swap_point_note:
        fm.append(f'swap_point_note: "{_yaml_quote(task.swap_point_note)}"')
    fm.extend([
        "test_results:",
        "  status: pending",
        "  coverage: null",
        "  last_run: null",
        "---",
        "",
    ])

    body_parts = [
        f"# {task.title}",
        "",
        f'**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"',
        (
            f"**Wave:** {task.wave} | **Mode:** {task.implementation_mode} | "
            f"**Complexity:** {task.complexity}/10 | **Est.:** {task.estimated_minutes} min"
        ),
        (
            f"**Parent review:** [{PARENT_REVIEW}]"
            f"(../../in_review/{PARENT_REVIEW}-plan-core-tools-and-dispatch.md)"
        ),
        "",
        "## Description",
        "",
        task.description,
        "",
        "## Acceptance Criteria",
        "",
        ac_lines,
        "",
        "## Scenarios Covered",
        "",
    ]
    if task.scenarios_covered:
        body_parts.extend(f"- {s}" for s in task.scenarios_covered)
    else:
        body_parts.append("_No direct scenario coverage — supporting task._")
    if task.swap_point_note:
        body_parts.extend(["", "## Swap-Point Note", "", task.swap_point_note])
    if seam_block:
        body_parts.extend(["", seam_block.rstrip()])
    body_parts.extend([
        "",
        "## Test Execution Log",
        "",
        "_Populated by `/task-work` during implementation._",
        "",
    ])
    return "\n".join(fm) + "\n".join(body_parts)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for task in TASKS:
        slug = _slug_from_title(task.title)
        fname = f"{task.id}-{slug}.md"
        path = OUT_DIR / fname
        path.write_text(_render_task(task), encoding="utf-8")
        print(f"wrote {path}")

    print(f"\nGenerated {len(TASKS)} task files in {OUT_DIR}")


if __name__ == "__main__":
    main()
