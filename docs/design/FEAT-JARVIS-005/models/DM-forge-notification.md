# DM-forge-notification — ForgeNotification, BuildCorrelation

> **Owner:** [FEAT-JARVIS-005 design §4](../design.md)
> **Status:** Authoritative for FEAT-JARVIS-005's in-process notification surface. FEAT-J006 (Telegram) promotes the wire surface to `jarvis.notification.{adapter}`; this Pydantic shape becomes the canonical wire payload at that point.

This module defines the **in-process** types FEAT-JARVIS-005 introduces between the `pipeline.stage-complete.>` subscriber and the per-session CLI rendering surface. Neither type appears on the wire in v1 — they are projection / correlation types only. The canonical NATS wire shape is `nats_core.events.StageCompletePayload`; `ForgeNotification` is the projection of that payload onto Jarvis's adapter-rendering layer.

---

## 1. `ForgeNotification` — in-process notification

```python
class ForgeNotification(BaseModel):
    """In-process notification routed from `pipeline.stage-complete.*` to
    the originating session's CLI rendering surface.

    Frozen — once constructed, never mutated. Any future enrichment
    (e.g. adding a coach_score quintile bucket) is a new optional field
    plus an updated `format_one_line` body, not an in-place edit.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    correlation_id: str = Field(
        min_length=1,
        description=(
            "BuildQueuedPayload.correlation_id — used to thread back "
            "to the originating routing-history entry."
        ),
    )
    feature_id: str = Field(
        pattern=r"^FEAT-[A-Z0-9]{3,12}$",
        description="The Forge feature identifier (matches BuildQueuedPayload).",
    )
    stage_label: str = Field(
        min_length=1,
        max_length=128,
        description=(
            "Reasoning-model-chosen stage label (emergent per "
            "ADR-ARCH-016). Examples: 'plan-complete', 'autobuild-complete', "
            "'task-review-complete'."
        ),
    )
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"] = Field(
        description="Stage outcome from StageCompletePayload.",
    )
    target_kind: Literal["local_tool", "fleet_capability", "subagent"] = Field(
        description=(
            "Which kind of executor ran the stage on Forge's side. "
            "Surfaced on the rendered line so Rich can see whether a "
            "stage was internal-tool work, fleet-dispatch, or "
            "subagent-driven."
        ),
    )
    target_identifier: str = Field(
        min_length=1,
        description=(
            "Concrete identifier of the executor "
            "(tool name / agent_id:tool_name / subagent name)."
        ),
    )
    completed_at: datetime = Field(
        description=(
            "When Forge published the stage-complete event. Parsed from "
            "StageCompletePayload.completed_at (ISO 8601 string)."
        ),
    )
    duration_secs: float = Field(
        ge=0.0,
        description="Stage duration in seconds — surfaced on the rendered line.",
    )

    @classmethod
    def from_stage_complete(
        cls,
        payload: StageCompletePayload,
        correlation: BuildCorrelation,
    ) -> ForgeNotification:
        """Project a Forge stage-complete payload onto the in-process shape.

        Pure function — no I/O. Suitable for direct unit testing.
        Uses the correlation entry's feature_id (rather than the
        payload's feature_id) only as a defensive cross-check;
        in normal operation they're equal.
        """
        # implementation omitted — straightforward field copy + isoparse

    def format_one_line(self) -> str:
        """Render the canonical CLI line.

        Shape:
            [HH:MM] Forge {feature_id}: stage {stage_label} ({status})

        Examples:
            [15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete (PASSED)
            [15:44] Forge FEAT-JARVIS-INTERNAL-001: stage autobuild-complete (PASSED)
            [15:45] Forge FEAT-JARVIS-INTERNAL-001: stage task-review (FAILED)

        Time is the local-time portion of completed_at.

        FEAT-J006 (Telegram) reuses this method verbatim for the
        notification body; FEAT-J009 (Dashboard) reuses it for the
        live-trace viewport's per-stage line. The shape is the
        cross-adapter rendering contract.
        """
```

### Field invariants

- `correlation_id` MUST match an entry in the subscriber's correlation map at the moment the notification is constructed. The subscriber drops un-matched events silently per design §8.
- `completed_at` is timezone-aware UTC datetime — `StageCompletePayload.completed_at` is an ISO-8601 string, parsed once at projection time.
- `duration_secs ≥ 0.0`. Forge guarantees non-negative; the constraint is defensive against malformed payloads.

---

## 2. `BuildCorrelation` — correlation map entry

```python
class BuildCorrelation(BaseModel):
    """One element of the in-memory correlation map.

    Stored in `ForgeNotificationsSubscriber._correlations` (DDR-028 —
    LRU bounded at `correlation_cap`, default 1000). Lost on Jarvis
    restart per DDR-027.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    correlation_id: str = Field(
        min_length=1,
        description="The BuildQueuedPayload.correlation_id Jarvis published.",
    )
    feature_id: str = Field(
        pattern=r"^FEAT-[A-Z0-9]{3,12}$",
        description="The feature_id that was queued — primarily for diagnostics.",
    )
    session_id: str | None = Field(
        default=None,
        description=(
            "The Session.session_id that originated the queue. None for "
            "tests / sessionless paths where queue_build was invoked "
            "without an active session — events for those correlations "
            "are still bridged to the routing-history writer for the "
            "trace edge but are not enqueued anywhere (no session)."
        ),
    )
    adapter: str = Field(
        min_length=1,
        description=(
            "Resolved Session.adapter at queue time (DDR-031). Captured "
            "for diagnostic logging when correlations are evicted; not "
            "load-bearing for routing."
        ),
    )
    queued_at: datetime = Field(
        description="When queue_build accepted the publish (UTC).",
    )
```

---

## 3. Per-session notification queue

The queue itself is a plain Python `collections.deque` held in `SessionManager`:

```python
class SessionManager:
    def __init__(self, ...):
        ...
        self._notification_queues: dict[str, deque[ForgeNotification]] = {}
```

### Invariants

1. **Per-session isolation** — `dict` keyed on `session_id`. Notifications for session A never surface on session B's `pending_notifications`.
2. **FIFO order** — `deque.append` for enqueue, `deque.popleft` (drain) for read. The `pending_notifications` reader returns the contents in arrival order.
3. **Bounded depth** — every queue is constructed with `maxlen=cap` (DDR-030, default 100). `deque.maxlen` discards the oldest entry on overflow; the WARN fires from a wrapper that detects overflow by checking length-before vs cap.
4. **Cleared on `end_session`** — the per-session entry is `del`-ed from the dict and a structured log records the count cleared.
5. **Atomic drain** — `pending_notifications` returns `list(deque)` then clears the deque, in one critical section. A concurrent `enqueue_notification` from the subscriber lands in a fresh deque (or a deque just-cleared) — no entries lost.
6. **Idempotent on missing/ended sessions** — enqueueing to an unknown or ended session is a no-op with `DEBUG forge_notification_dropped`. Reading from an unknown session returns `[]`.

### Threading note

`SessionManager` runs on a single asyncio event loop (single Jarvis process per ADR-ARCH-026). The deque operations are atomic at the Python interpreter level for single-loop access. No additional locking is required.

---

## 4. Validation tests anchor

The `tests/test_forge_notifications_unit.py` suite asserts:

1. `ForgeNotification.from_stage_complete` populates every field correctly across all `status ∈ {PASSED, FAILED, GATED, SKIPPED}` values and `target_kind ∈ {local_tool, fleet_capability, subagent}` values.
2. `format_one_line()` produces the canonical shape; specifically:
   - `[15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete (PASSED)`
   - Time is local HH:MM (no seconds, no timezone offset).
   - `feature_id`, `stage_label`, `status` echo verbatim.
3. `BuildCorrelation.session_id is None` is permitted (sessionless test paths).
4. `frozen=True` — both types are immutable post-construction.
5. The per-session queue:
   - 100 enqueues all surface on `pending_notifications` in FIFO order; queue is empty after drain.
   - 101st enqueue evicts the oldest; final queue length is 100; `WARN forge_notification_queue_overflow` was emitted exactly once.
   - `end_session(sid)` clears the queue; subsequent `pending_notifications(sid)` returns `[]`.
   - `enqueue_notification` to an unknown `session_id` returns silently with DEBUG log.

---

## 5. Schema-version markers

This is an in-process type in v1. When FEAT-J006 promotes `jarvis.notification.forge-stage-complete.{correlation_id}` to a real wire subject, the `ForgeNotification` Pydantic class becomes the wire payload — at that point a `schema_version` field may land per the same convention as DDR-018 establishes for `JarvisRoutingHistoryEntry` (additions append-only via append-only DDR; renames or type changes require a `schema_version` marker at the change point).

Until then, `extra="ignore"` lets future fields land non-breakingly.

---

*"Project the wire payload onto the adapter rendering layer once, at the bridge boundary. Never let the reasoning model see it."* — [phase3-fleet-integration-scope.md §FEAT-005](../../../research/ideas/phase3-fleet-integration-scope.md)
