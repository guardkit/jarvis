# DM-routing-history — JarvisRoutingHistoryEntry, DispatchOutcome, RedirectAttempt

> **Owner:** [FEAT-JARVIS-004 design §4](../design.md)
> **Status:** Authoritative for v1+ per [DDR-018](../decisions/DDR-018-routing-history-schema-authoritative.md). Future additions are append-only via ADR-FLEET-00X.
> **Source:** [ADR-FLEET-001 — Trace-Richness by Default](../../../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md) base schema + Jarvis-specific extensions.
> **Resolves:** JA1 (architecture-deferred — exact Pydantic shape for `jarvis_routing_history`).

This module defines the wire types Jarvis writes to the `jarvis_routing_history` Graphiti group. Every successful, failed, redirected, or timed-out dispatch (specialist via `dispatch_by_capability` *and* — by FEAT-JARVIS-005 reuse — Forge build queueing via `queue_build`) writes one entry. Stage-complete events arriving on `pipeline.stage-complete.*` (FEAT-J005) **append edges** to the original entry rather than overwriting fields.

---

## 1. `DispatchOutcome` — closed Literal

```python
DispatchOutcome = Literal[
    "success",                # Specialist replied with success=True on first attempt.
    "redirected",             # Specialist replied with success=True after >=1 retry-with-redirect.
    "timeout",                # Specialist did not reply within timeout_seconds; no redirect attempted.
    "specialist_error",       # Specialist replied with success=False; no redirect attempted.
    "exhausted",              # All retry-with-redirect attempts (1 redirect = 2 attempts) failed.
    "transport_unavailable",  # NATS soft-fail (DDR-021) — connection failed at dispatch time.
    "unresolved",             # _resolve_agent_id returned None on the first attempt (no capability match).
]
```

Closed enum. Adding a member is **non-breaking** for the schema (new members are forward-compatible) but requires an append-only DDR per DDR-018.

---

## 2. `RedirectAttempt` — element of `alternatives_considered`

```python
class RedirectAttempt(BaseModel):
    """One attempt within a dispatch_by_capability invocation."""

    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(
        pattern=r"^[a-z][a-z0-9-]*$",
        description="The specialist agent_id this attempt targeted.",
    )
    attempt_index: int = Field(
        ge=0,
        description="0-indexed position within the dispatch (0 = original, 1 = first redirect).",
    )
    reason_skipped: Literal["timeout", "specialist_error", "transport_error"] = Field(
        description="Why this attempt didn't succeed.",
    )
    detail: str | None = Field(
        default=None,
        max_length=512,
        description="Truncated, redaction-processed detail. None for timeouts.",
    )
    duration_ms: int = Field(
        ge=0,
        description="Wall-clock time the supervisor spent on this attempt.",
    )
```

---

## 3. `JarvisRoutingHistoryEntry` — full schema

```python
class JarvisRoutingHistoryEntry(BaseModel):
    """ADR-FLEET-001-shaped trace record for one Jarvis dispatch decision.

    Authoritative for v1+ per DDR-018. Additions are append-only via
    ADR-FLEET-00X — never overwrite or rename existing fields.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    # ── §1 Decision identity (ADR-FLEET-001 §"Required fields" #1) ────────
    decision_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        description="UUIDv4 — unique per decision.",
    )
    surface: Literal["jarvis"] = "jarvis"
    session_id: str = Field(
        min_length=1,
        description="Session correlation ID — Session.session_id (FEAT-J003 review F5).",
    )
    timestamp: datetime = Field(
        description="ISO 8601, UTC, timezone-aware.",
    )

    # ── §2 Reasoning context ──────────────────────────────────────────────
    supervisor_tool_call_sequence: list[ToolCallRecord] | TraceRef = Field(
        description=(
            "Inline list of {tool_name, args, result_summary} dicts when "
            "JSON-encoded payload is <=16KB; TraceRef pointing to "
            "~/.jarvis/traces/{date}/{decision_id}.json otherwise. "
            "ADR-FLEET-001 §'Large traces' filesystem offload."
        ),
    )
    priors_retrieved: list[str] = Field(
        default_factory=list,
        description=(
            "Graphiti entity IDs retrieved into the system prompt at "
            "decision time. Empty list in v1 (learning isn't reading); "
            "populated when FEAT-JARVIS-008 lands."
        ),
    )
    capability_snapshot_hash: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 of the {available_capabilities} prompt block as "
            "rendered at decision time. Lets future analyses "
            "reconstruct the catalogue Jarvis saw without storing the "
            "full block per record."
        ),
    )

    # ── §3 Subagent delegation ────────────────────────────────────────────
    subagent_type: Literal[
        "specialist",          # dispatch_by_capability path
        "forge_build_queue",   # queue_build path (FEAT-J005)
        "jarvis_reasoner",     # local AsyncSubAgent dispatch (future trace-capture)
    ]
    subagent_task_id: str = Field(
        min_length=1,
        description=(
            "For specialist: nats-core correlation_id. "
            "For forge_build_queue: BuildQueuedPayload.correlation_id. "
            "For jarvis_reasoner: thread_id."
        ),
    )
    subagent_trace_ref: TraceRef | None = Field(
        default=None,
        description=(
            "Optional reference to LangSmith trace or NATS dispatch ref. "
            "When the inline payload exceeds 16KB it points to the "
            "filesystem offload path."
        ),
    )
    subagent_final_state: Literal["success", "error", "timeout", "cancelled"]

    # ── §4 Resource cost ──────────────────────────────────────────────────
    model_calls: list[ModelCallRecord] = Field(
        default_factory=list,
        description=(
            "Reasoning-side model calls during dispatch (excluding the "
            "specialist's own internal model usage — that's their trace)."
        ),
    )
    wall_clock_ms: int = Field(
        ge=0,
        description="End-to-end time the supervisor spent on this decision.",
    )
    total_cost_usd: float = Field(
        ge=0.0,
        description=(
            "Summed cost of model_calls. 0.0 for pure-local dispatches "
            "(no cloud LLM use)."
        ),
    )

    # ── §5 Outcome ────────────────────────────────────────────────────────
    outcome_type: DispatchOutcome
    outcome_detail: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured outcome metadata. Free-shape dict — keys vary by "
            "outcome_type. e.g. for 'redirected': "
            "{'final_attempt_index': 1, 'final_agent_id': 'product-owner'}."
        ),
    )

    # ── §6 Human response (populated later if Rich redirects) ─────────────
    human_response_type: (
        Literal["confirm", "reject", "redirect", "ignore", "override"] | None
    ) = None
    human_response_text: str | None = Field(
        default=None,
        max_length=4096,
        description=(
            "Free-text response when Rich engages mid-conversation. "
            "Captured as-is per ADR-FLEET-001 §6, redaction processor "
            "applied at write time per ADR-ARCH-029."
        ),
    )
    human_response_latency_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Time from notification/pause to Rich's response. "
            "None for unattended/dispatch-only flows."
        ),
    )

    # ── §7 Environmental context ──────────────────────────────────────────
    project_id: str | None = Field(
        default=None,
        description=(
            "Pulled from session metadata when the session is "
            "project-scoped; None for general-purpose chat sessions."
        ),
    )
    local_time_of_day: str = Field(
        pattern=r"^\d{2}:\d{2}$",
        description="Local HH:MM, used for time-pattern detection.",
    )
    recent_session_refs: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Last 10 session_id references (sequence-pattern detection).",
    )
    concurrent_workload: ConcurrentWorkloadSnapshot = Field(
        description=(
            "{in_flight_dispatches: int, in_flight_watchers: int, "
            "in_flight_subagents: int} at decision time. Helps diagnose "
            "degraded-mode edge cases (e.g. semaphore overflow)."
        ),
    )

    # ── Jarvis-specific extensions (per ADR-FLEET-001 'per-group' clause) ──
    chosen_specialist_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]*$",
        description=(
            "agent_id of the specialist that ultimately replied (or None "
            "for unresolved/exhausted/transport_unavailable). "
            "Distinct from subagent_task_id which is the correlation."
        ),
    )
    chosen_subagent_name: str | None = Field(
        default=None,
        description=(
            "When subagent_type='jarvis_reasoner', the AsyncSubAgent name "
            "('jarvis-reasoner'); None otherwise. Reserved for future use."
        ),
    )
    alternatives_considered: list[CapabilityDescriptorRef] = Field(
        default_factory=list,
        description=(
            "Capability descriptors the supervisor saw in the catalogue "
            "but didn't pick. Each is a {agent_id, role, "
            "tool_name_match: bool, intent_pattern_match: bool} ref. "
            "Joins on chosen_specialist_id give the full picture."
        ),
    )
    attempts: list[RedirectAttempt] = Field(
        default_factory=list,
        description=(
            "Ordered list of redirect attempts. Length 0 on first-attempt "
            "success; length 1+ when retry-with-redirect fired."
        ),
    )
    supervisor_reasoning_summary: str = Field(
        max_length=1024,
        description=(
            "The supervisor's own rationale for the dispatch — a "
            "summary extracted from the tool-call sequence. Truncated to "
            "1024 chars; redaction-processed."
        ),
    )
```

---

## 4. Helper types

### 4.1 `TraceRef` — filesystem offload pointer

```python
class TraceRef(BaseModel):
    """Pointer to an oversized trace component on the filesystem.

    ADR-FLEET-001 §'Large traces' / DDR-018: when a trace component
    exceeds 16KB JSON-encoded, it lands in
    ~/.jarvis/traces/{date}/{decision_id}.json and the entity stores
    only this ref + a content hash.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    path: str = Field(
        description="Absolute path to the trace file.",
    )
    content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the file contents at write time.",
    )
    size_bytes: int = Field(ge=0)
```

### 4.2 `ToolCallRecord`

```python
class ToolCallRecord(BaseModel):
    """One supervisor tool-call within the decision sequence."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    tool_name: str = Field(min_length=1)
    args_summary: str = Field(
        max_length=512,
        description="Truncated, redaction-processed args summary.",
    )
    result_summary: str = Field(
        max_length=512,
        description="Truncated, redaction-processed result summary.",
    )
    duration_ms: int = Field(ge=0)
```

### 4.3 `ModelCallRecord`

```python
class ModelCallRecord(BaseModel):
    """One supervisor-side model invocation during dispatch."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    model_id: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
```

### 4.4 `CapabilityDescriptorRef`

```python
class CapabilityDescriptorRef(BaseModel):
    """Lightweight reference to a CapabilityDescriptor seen but not chosen."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    agent_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    role: str = Field(min_length=1)
    tool_name_match: bool = Field(
        description="True if the descriptor's capability_list contained the requested tool_name.",
    )
    intent_pattern_match: bool = Field(
        description="True if the descriptor's role/description matched the intent_pattern (when provided).",
    )
```

### 4.5 `ConcurrentWorkloadSnapshot`

```python
class ConcurrentWorkloadSnapshot(BaseModel):
    """Workload at decision time — feeds DDR-020 capacity diagnostics."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    in_flight_dispatches: int = Field(ge=0, description="Held by dispatch_semaphore.")
    in_flight_watchers: int = Field(ge=0, description="Pattern B watchers.")
    in_flight_subagents: int = Field(ge=0, description="AsyncSubAgent invocations.")
```

---

## 5. Filesystem offload — large-trace path layout

Per ADR-FLEET-001 §"Large traces" + DDR-018:

```
~/.jarvis/traces/
└── 2026-04-30/                      ← date in operator's local timezone
    ├── 7e4f1b2c-…json               ← decision_id.json
    ├── 5a93c0e1-…json
    └── …
```

Each file is the JSON-encoded payload of the offloaded field (`supervisor_tool_call_sequence` and/or `subagent_trace_ref`). The Graphiti entity stores a `TraceRef` with the absolute path and the content SHA-256. Meta-reasoning (FEAT-JARVIS-008 v1.5) reads via `cat`, `grep`, `ls` — no Graphiti round-trip required for high-volume scans (the Meta-Harness pattern).

**Retention** — 12 months rolling per ADR-FLEET-001; FEAT-JARVIS-011 (`jarvis purge-traces`) lands the GDPR-clean delete path in v1.1.

**Privacy** — `structlog` redaction processor runs at the **write boundary** (inside `RoutingHistoryWriter.write(...)`), not at the Pydantic-validation level. The redactor strips API keys, JWT tokens, NATS credentials, email addresses before either inline or filesystem write. ADR-ARCH-029 holds.

---

## 6. Schema-version markers

Per DDR-018 (authoritative-from-here):

- The class has no explicit `schema_version` field in v1 — adding fields is non-breaking, and consumers (`jarvis.learning` in v1.5) tolerate missing optional fields per Pydantic's `extra="ignore"`.
- Future **renames** or **type changes** to existing fields require an append-only ADR-FLEET-00X *and* a `schema_version` field at that point. Until then, the absence of the field implicitly tags the record as `v1`.
- The Graphiti group itself is not versioned. Per ADR-FLEET-001 §"Do-not-reopen", reducing trace richness needs an explicit ADR.

---

## 7. Validation tests anchor

The `tests/test_routing_history_schema.py` suite asserts:

1. Every field above is populated in a happy-path `JarvisRoutingHistoryEntry.model_validate(...)` round-trip.
2. Timeout / redirect / exhausted scenarios populate `attempts` correctly with monotonic `attempt_index`.
3. JSON-encoded payload >16KB triggers the filesystem offload — `TraceRef` substituted, file present at the path, hash matches.
4. Inline payload <=16KB stays inline — no filesystem write.
5. `extra="ignore"` survives unknown fields without raising (forward-compat for ADR-FLEET-00X additions).
6. Redaction processor runs before write — assert that a synthetic `OPENAI_API_KEY=sk-…` token in `human_response_text` lands as `***REDACTED***` in the persisted entity.
7. `frozen=True` — entries are immutable post-construction. Updates from FEAT-J005 stage-complete events go on the **edges**, not the entry.

---

*"The schema is authoritative for the rest of v1 and beyond. Retrofits are expensive."* — [phase3-fleet-integration-scope.md §JA1 resolution](../../../research/ideas/phase3-fleet-integration-scope.md)
