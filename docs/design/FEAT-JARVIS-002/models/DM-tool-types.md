# DM-tool-types — Tool-Layer Pydantic Models

> Models live in [`src/jarvis/tools/types.py`](../../../../src/jarvis/tools/types.py) (+ `capabilities.py` for `CapabilityDescriptor` because that module owns the registry). All models validate at construction per fleet-wide D22 / ADR-ARCH-021 (Pydantic 2 at every boundary).

---

## 1. `CapabilityDescriptor` — `jarvis.tools.capabilities`

The supervisor-facing projection of an agent's `nats_core.AgentManifest`. Deliberately a subset of the manifest — the reasoning model reads this; not every manifest field is useful to the model, and some (e.g. `container_id`) leak infrastructure.

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityToolSummary(BaseModel):
    """A single tool exposed by a fleet agent, as surfaced to Jarvis.

    Attributes:
        tool_name: Maps 1:1 to ``nats_core.ToolCapability.name``.
        description: Human-readable description the reasoning model reads
                     at decision time.
        risk_level: Risk classification for approval gating.
    """

    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["read_only", "mutating", "destructive"] = "read_only"


class CapabilityDescriptor(BaseModel):
    """A fleet agent's capabilities as rendered into Jarvis's context.

    Attributes:
        agent_id: Kebab-case identifier. Matches ``AgentManifest.agent_id``.
        role: Human-readable role name (e.g. "Architect", "Product Owner").
              Derived from ``AgentManifest.name`` in Phase 3+.
        description: One-paragraph description of what this agent does best —
                     surfaces in ``{available_capabilities}`` prompt block.
        capability_list: The ToolCapability summaries Jarvis can dispatch to.
        cost_signal: Human-readable cost indicator (e.g. "low", "~$0.10/call").
        latency_signal: Human-readable latency indicator (e.g. "5-30s", "sub-second").
        last_heartbeat_at: Timestamp of last heartbeat received. None in Phase 2
                           (no heartbeats yet); populated in Phase 3.
        trust_tier: Trust classification, mapped from ``AgentManifest.trust_tier``.
    """

    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Kebab-case agent identifier",
    )
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capability_list: list[CapabilityToolSummary] = Field(default_factory=list)
    cost_signal: str = Field(default="unknown")
    latency_signal: str = Field(default="unknown")
    last_heartbeat_at: datetime | None = None
    trust_tier: Literal["core", "specialist", "extension"] = "specialist"

    def as_prompt_block(self) -> str:
        """Render this descriptor as a prompt-friendly text block.

        The supervisor's ``{available_capabilities}`` placeholder is filled
        by joining these blocks with double newlines.
        """
        ...  # implementation returns deterministic, token-cheap text
```

### Prompt-block shape (deterministic)

Example rendering (exact format — tests assert byte-equal):

```
### architect-agent — Architect (trust: specialist, cost: moderate, latency: 5-30s)

Produces architecture sessions, C4 diagrams, and ADRs for features. Prefers
evidence-based decisions grounded in the existing ARCHITECTURE.md.

Tools:
  - run_architecture_session (read_only) — Drive a full /system-arch
    session end-to-end from a scope document.
  - draft_adr (mutating) — Produce a new ADR file given context + decision.
```

### Compatibility with `nats_core.AgentManifest`

| `CapabilityDescriptor` field | Source in `AgentManifest` | Notes |
|---|---|---|
| `agent_id` | `agent_id` | 1:1 |
| `role` | `name` | Human-friendly mapping |
| `description` | `metadata["jarvis_description"]` OR first-paragraph of a convention field — **settled here for Phase 3:** use `metadata["jarvis_description"]`, fall back to `f"{name} ({template})"` if absent. This keeps the `AgentManifest` contract un-touched and gives Jarvis a dedicated field to negotiate on. |
| `capability_list` | `tools[*]` mapped to `CapabilityToolSummary` | 1:1 per entry |
| `cost_signal` | `metadata["cost_signal"]` | Free-form |
| `latency_signal` | `metadata["latency_signal"]` | Free-form |
| `last_heartbeat_at` | `AgentHeartbeatPayload.timestamp` (last received) | `None` in Phase 2 |
| `trust_tier` | `trust_tier` | 1:1 |

`metadata["jarvis_description"]`, `metadata["cost_signal"]`, `metadata["latency_signal"]` are **conventions** the fleet adopts for Jarvis consumption; they sit inside `AgentManifest.metadata` (which is designed for exactly this kind of extension). No `nats-core` schema change is required.

---

## 2. `WebResult` — `jarvis.tools.types`

```python
class WebResult(BaseModel):
    """A single web-search result surfaced by ``search_web``.

    Attributes:
        title: Page title from the search result.
        url: Fully-qualified URL.
        snippet: Short extract or description from the search provider.
        score: Relevance score (0.0–1.0) if the provider supplies one; 0.0 otherwise.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    snippet: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
```

---

## 3. `CalendarEvent` — `jarvis.tools.types`

```python
class CalendarEvent(BaseModel):
    """A single calendar event surfaced by ``get_calendar_events``.

    Phase 2 only constructs these in tests — the real provider lands in v1.5.

    Attributes:
        id: Stable event identifier from the source provider.
        title: Event title.
        start: Event start time (UTC).
        end: Event end time (UTC). Must be >= start.
        location: Optional physical / virtual location string.
        description: Optional free-text body.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _end_must_not_precede_start(self) -> "CalendarEvent":
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self
```

---

## 4. `DispatchError` — `jarvis.tools.types`

Structured-error sentinel used internally by `dispatch.py` and `capabilities.py`. **Not** surfaced over the tool boundary — tools convert it into an `ERROR: <category> — <detail>` string per ADR-ARCH-021. Kept as a Pydantic model so tests can match on fields rather than on error-string regex.

```python
class DispatchError(BaseModel):
    """Internal structured representation of a dispatch failure.

    Attributes:
        category: One of unresolved | invalid_payload | invalid_timeout |
                  timeout | specialist_error | transport_stub.
        detail: Human-readable context.
        agent_id: Resolved agent if known; None if resolution failed.
        tool_name: Requested tool_name if set.
        correlation_id: Correlation ID assigned even on failure so the event
                        is traceable.
    """

    model_config = ConfigDict(extra="ignore")

    category: Literal[
        "unresolved",
        "invalid_payload",
        "invalid_timeout",
        "timeout",
        "specialist_error",
        "transport_stub",
    ]
    detail: str = Field(min_length=1)
    agent_id: str | None = None
    tool_name: str | None = None
    correlation_id: str

    def to_tool_string(self) -> str:
        """Render the ADR-ARCH-021-compliant single-line error string."""
        ...
```

---

## 5. Invariants

- All models set `ConfigDict(extra="ignore")` — forward-compatible with new fields published by evolving manifests.
- `datetime` fields are UTC-aware; serialization goes through Pydantic's default ISO-8601 encoder.
- No model imports from `jarvis.agents.*`, `jarvis.infrastructure.*`, or `jarvis.cli.*` — the tools package is a leaf per ADR-ARCH-002 (clean hexagonal).
- Models are hashable by value only where mutation is never needed — `CapabilityDescriptor` sits inside lists that are rebuilt on refresh rather than mutated in place.
