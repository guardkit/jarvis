"""Forge stage-complete notification schema (declarative-only).

TASK-J005-002 lands the Pydantic v2 declarative schema for the in-process
Forge stage-complete notification surface — no subscriber, no NATS imports,
no I/O. The subscriber, correlation map, and the
``pipeline.stage-complete.>`` JetStream subscription land in TASK-J005-003.

References
----------
* :doc:`docs/design/FEAT-JARVIS-005/models/DM-forge-notification.md` —
  authoritative field definitions, regex patterns, ``Literal`` members,
  and the ``render_line()`` shape contract.
* `DDR-030 — CLI notifications between prompts
  <../../../docs/design/FEAT-JARVIS-005/decisions/DDR-030-cli-notifications-between-prompts.md>`_
  — the canonical render shape consumed by ``cli/main.py`` (TASK-J005-007).
* `DDR-027 — Correlation map is in-memory, lost on restart
  <../../../docs/design/FEAT-JARVIS-005/decisions/DDR-027-correlation-map-in-memory.md>`_.
* `DDR-028 — Correlation map LRU cap
  <../../../docs/design/FEAT-JARVIS-005/decisions/DDR-028-correlation-map-lru-cap.md>`_.
* `DDR-031 — Adapter resolution at queue time
  <../../../docs/design/FEAT-JARVIS-005/decisions/DDR-031-adapter-at-queue-time.md>`_.

Notes
-----
* Both models are ``frozen=True`` — once constructed, never mutated. Any
  future enrichment (e.g. adding a ``coach_score`` quintile bucket) is a
  new optional field plus an updated ``render_line()`` body, not an
  in-place edit.
* ``extra="ignore"`` lets future fields land non-breakingly when
  FEAT-J006 promotes ``ForgeNotification`` to a real wire payload on
  ``jarvis.notification.{adapter}``.
* This module deliberately imports nothing from ``nats_core`` /
  ``nats`` — the projection from ``StageCompletePayload`` lands in
  TASK-J005-003 alongside the subscriber.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# §1 — ForgeNotification (DM-forge-notification §1)
# ---------------------------------------------------------------------------


class ForgeNotification(BaseModel):
    """In-process notification routed from ``pipeline.stage-complete.*`` to
    the originating session's CLI rendering surface.

    Frozen — once constructed, never mutated. Any future enrichment
    (e.g. adding a ``coach_score`` quintile bucket) is a new optional
    field plus an updated :meth:`render_line` body, not an in-place edit.

    The canonical NATS wire shape is ``nats_core.events.StageCompletePayload``;
    ``ForgeNotification`` is the projection of that payload onto Jarvis's
    adapter-rendering layer (DM-forge-notification §1). The projection
    itself (``from_stage_complete``) lands with the subscriber in
    TASK-J005-003 — this task is schema-only.
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
            "StageCompletePayload.completed_at (ISO 8601 string). "
            "Timezone-aware UTC datetime per DM-forge-notification §1."
        ),
    )
    duration_secs: float = Field(
        ge=0.0,
        description="Stage duration in seconds — surfaced on the rendered line.",
    )

    def render_line(self) -> str:
        """Render the canonical CLI line per DDR-030 / DM-forge-notification §1.

        Shape::

            [HH:MM] Forge {feature_id}: stage {stage_label} ({status})

        Examples::

            [15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete (PASSED)
            [15:44] Forge FEAT-JARVIS-INTERNAL-001: stage autobuild-complete (PASSED)
            [15:45] Forge FEAT-JARVIS-INTERNAL-001: stage task-review (FAILED)

        Time is the local-time portion of :attr:`completed_at` rendered
        as ``HH:MM`` (no seconds, no timezone offset). When
        ``completed_at`` is timezone-aware UTC, ``astimezone()`` shifts
        it into the host's local zone before formatting; naive datetimes
        fall through ``strftime`` unchanged.

        FEAT-J006 (Telegram) reuses this method verbatim for the
        notification body; FEAT-J009 (Dashboard) reuses it for the
        live-trace viewport's per-stage line. The shape is the
        cross-adapter rendering contract.
        """
        local_completed_at = (
            self.completed_at.astimezone()
            if self.completed_at.tzinfo is not None
            else self.completed_at
        )
        hhmm = local_completed_at.strftime("%H:%M")
        return (
            f"[{hhmm}] Forge {self.feature_id}: "
            f"stage {self.stage_label} ({self.status})"
        )


# ---------------------------------------------------------------------------
# §2 — BuildCorrelation (DM-forge-notification §2)
# ---------------------------------------------------------------------------


class BuildCorrelation(BaseModel):
    """One element of the in-memory correlation map.

    Stored in ``ForgeNotificationsSubscriber._correlations`` (DDR-028 —
    LRU bounded at ``correlation_cap``, default 1000). Lost on Jarvis
    restart per DDR-027.

    The subscriber + correlation-map land in TASK-J005-003; this task
    only ships the schema.
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


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "BuildCorrelation",
    "ForgeNotification",
]
