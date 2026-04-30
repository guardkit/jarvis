"""Forge stage-complete notification schema + subscriber.

TASK-J005-002 landed the Pydantic v2 declarative schema for the in-process
Forge stage-complete notification surface (``ForgeNotification`` and
``BuildCorrelation``).

TASK-J005-003 (this revision) appends the subscriber, the in-memory LRU
correlation map, and the in-process router from
``pipeline.stage-complete.>`` to per-session pending notifications, per
design.md §8 and DDR-026 / DDR-027 / DDR-028 / DDR-030.

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

import asyncio
import contextlib
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from nats.aio.msg import Msg
    from nats.js import JetStreamContext

    from jarvis.infrastructure.nats_client import NATSClient
    from jarvis.infrastructure.routing_history import RoutingHistoryWriter
    from jarvis.sessions.manager import SessionManager


logger = structlog.get_logger(__name__)

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
# §3 — ForgeNotificationsSubscriber (TASK-J005-003)
# ---------------------------------------------------------------------------

# Subscribe wildcard derived lazily from the canonical
# ``nats_core.Topics.Pipeline.STAGE_COMPLETE`` template
# (``pipeline.stage-complete.{feature_id}``) by substituting the NATS ``>``
# wildcard for ``{feature_id}``. The derivation is wrapped in
# :func:`_get_stage_complete_subject` rather than evaluated at import time
# so this module continues to satisfy the schema-import-isolation invariant
# checked by ``tests/test_forge_notification_schema.py`` while still
# pulling the canonical subject from :class:`nats_core.Topics` (cross-repo
# contract test ``tests/test_contract_nats_core.py`` AC-007).

# DDR-027: ephemeral push consumer with deliver_policy=NEW. We avoid a top-
# level import of the nats.js.api so the schema-only import of this module
# (e.g. from a unit test that only exercises ``ForgeNotification``) does not
# pay the nats-py import cost. ``_get_deliver_policy_new`` lazy-loads the
# enum on the start path.

# DDR-027 §"Consequences": no replay on restart in v1. Backfill is out of
# scope; the subscriber drops on the floor anything published while Jarvis
# was down.

# DDR-028 default cap. ``register_correlation`` evicts the oldest entry once
# the map is at capacity and emits one WARN per eviction.
_DEFAULT_CORRELATION_CAP = 1000


def _get_deliver_policy_new() -> Any:
    """Lazy-load ``nats.js.api.DeliverPolicy.NEW``.

    Schema-only consumers of this module never import ``nats``; the
    subscriber start path is the only call site that needs the enum.
    Keeping the import lazy stops cold imports of the schema from
    transitively pulling in the full ``nats-py`` JetStream surface.
    """
    from nats.js.api import DeliverPolicy

    return DeliverPolicy.NEW


def _get_stage_complete_subject() -> str:
    """Lazy-derive the subscribe wildcard from ``nats_core.Topics``.

    Returns the wildcard subject Jarvis subscribes to for stage-complete
    events: ``pipeline.stage-complete.>`` derived from
    ``Topics.Pipeline.STAGE_COMPLETE`` (``pipeline.stage-complete.{feature_id}``)
    by substituting NATS ``>`` for the ``{feature_id}`` placeholder.

    Imported lazily — same rationale as :func:`_get_deliver_policy_new`,
    plus the schema-import-isolation invariant in
    ``tests/test_forge_notification_schema.py`` forbids top-level
    ``from nats_core`` / ``from nats`` statements in this module.
    """
    from nats_core import Topics

    return Topics.Pipeline.STAGE_COMPLETE.format(feature_id=">")


class ForgeNotificationsSubscriber:
    """In-process subscriber for ``pipeline.stage-complete.>``.

    Maintains a bounded LRU map from ``correlation_id`` to
    :class:`BuildCorrelation`, decodes each delivered envelope into a
    :class:`ForgeNotification`, fire-and-forgets a Graphiti edge via
    :meth:`RoutingHistoryWriter.append_build_queue_event` (DDR-029), and
    enqueues the notification on the originating session's FIFO via
    :meth:`SessionManager.enqueue_notification` (DDR-030).

    Behaviour invariants per design.md §8 / DDR-026 — DDR-028 / DDR-030:

    * Ephemeral push consumer on ``pipeline.stage-complete.>`` with
      ``deliver_policy=NEW``; auto-ack (DDR-027). No replay on restart.
    * ``start()`` is idempotent — a second call is a no-op.
    * ``stop()`` cancels the subscription and returns within ``stop_timeout``
      seconds even if the broker is unresponsive (Group D #14).
    * Unknown ``source_id`` / unknown ``correlation_id`` / malformed envelope
      → drop with structured log line (or silent for unknown correlations);
      never raises out of the message handler (DDR-026).
    * ``bind_session_manager`` is late-bound from
      ``lifecycle.build_app_state``. A defensive re-bind raises (programmer
      error). Notifications received before the session manager is bound are
      dropped with one WARN per drop per design.md §8.
    """

    __slots__ = (
        "_nats_client",
        "_routing_history_writer",
        "_queue_cap",
        "_correlation_cap",
        "_correlations",
        "_session_manager",
        "_subscription",
        "_started",
        "_stop_timeout",
    )

    def __init__(
        self,
        nats_client: NATSClient,
        routing_history_writer: RoutingHistoryWriter,
        *,
        queue_cap: int = 100,
        correlation_cap: int = _DEFAULT_CORRELATION_CAP,
        stop_timeout: float = 5.0,
    ) -> None:
        """Construct the subscriber.

        Args:
            nats_client: A connected :class:`NATSClient` whose ``js``
                property exposes the JetStream context. The subscriber
                does not own the connection — lifecycle wiring drains it
                via ``NATSClient.drain``.
            routing_history_writer: The fire-and-forget writer used to
                append a Graphiti edge per matched stage-complete event
                (DDR-029).
            queue_cap: Per-session FIFO cap (forwarded to
                lifecycle.build_app_state for the session manager). Not
                consumed directly by the subscriber; kept for API
                symmetry with the wiring contract per AC-001.
            correlation_cap: Bound on the LRU correlation map (DDR-028).
                Defaults to 1000 entries per ``JarvisConfig``.
            stop_timeout: Maximum seconds :meth:`stop` will wait for the
                consumer to unsubscribe before returning unconditionally
                (ASSUM-011 / Group D #14).
        """
        self._nats_client = nats_client
        self._routing_history_writer = routing_history_writer
        self._queue_cap = queue_cap
        self._correlation_cap = correlation_cap
        self._stop_timeout = stop_timeout
        # OrderedDict gives O(1) move_to_end on lookup and popitem(last=False)
        # for oldest-first eviction. The map is single-loop (ASSUM-003) so a
        # plain dict suffices for thread-safety; OrderedDict is for ordering.
        self._correlations: OrderedDict[str, BuildCorrelation] = OrderedDict()
        self._session_manager: SessionManager | None = None
        self._subscription: Any = None  # nats.js.JetStreamContext.PushSubscription
        self._started: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Subscribe to ``pipeline.stage-complete.>`` (idempotent).

        DDR-027: ephemeral push consumer with ``deliver_policy=NEW``.
        Auto-ack — the subscriber does not call ``msg.ack()`` because
        ``manual_ack=False`` is the default and the JetStream context
        will ack each delivery once the callback returns.
        """
        if self._started:
            return

        js: JetStreamContext = self._nats_client.js
        deliver_policy_new = _get_deliver_policy_new()
        stage_complete_subject = _get_stage_complete_subject()

        self._subscription = await js.subscribe(
            stage_complete_subject,
            cb=self._on_message,
            ordered_consumer=False,
            deliver_policy=deliver_policy_new,
        )
        self._started = True
        logger.info(
            "forge_notifications_subscribed",
            subject=stage_complete_subject,
            correlation_cap=self._correlation_cap,
        )

    async def stop(self) -> None:
        """Unsubscribe within ``stop_timeout``; never raises (ASSUM-011).

        Bounded by ``asyncio.wait_for`` so an unresponsive broker cannot
        wedge the supervisor shutdown path (Group D #14). Any exception
        from the underlying ``unsubscribe`` is logged at WARN and
        swallowed — shutdown must be best-effort.
        """
        if not self._started:
            return

        sub = self._subscription
        self._started = False
        self._subscription = None

        if sub is None:
            return

        try:
            await asyncio.wait_for(
                sub.unsubscribe(), timeout=self._stop_timeout
            )
        except TimeoutError:
            logger.warning(
                "forge_notifications_stop_timeout",
                timeout=self._stop_timeout,
            )
        except Exception as exc:  # noqa: BLE001 — never raise on shutdown
            logger.warning(
                "forge_notifications_stop_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Late binding (TASK-J005-008 lifecycle wiring)
    # ------------------------------------------------------------------

    def bind_session_manager(self, session_manager: SessionManager) -> None:
        """Bind the :class:`SessionManager` for in-process routing.

        Called once from ``lifecycle.build_app_state`` after the session
        manager has been constructed (the dependency is unidirectional —
        the subscriber is created before the session manager so the
        latter can hold a reference back to it). Re-binding is a
        programming error and raises ``RuntimeError``.
        """
        if self._session_manager is not None:
            msg = (
                "ForgeNotificationsSubscriber.bind_session_manager called "
                "twice — session manager binding must be set exactly once "
                "from lifecycle.build_app_state."
            )
            raise RuntimeError(msg)
        self._session_manager = session_manager

    # ------------------------------------------------------------------
    # Correlation map (DDR-028 LRU)
    # ------------------------------------------------------------------

    def register_correlation(
        self,
        correlation_id: str,
        session_id: str | None,
        adapter: str,
        queued_at: datetime,
        feature_id: str,
    ) -> None:
        """Insert a correlation into the LRU map; evict oldest at cap.

        Entry point used by :func:`jarvis.tools.queue_build` (TASK-J005-005)
        once the BUILD_QUEUED publish has been accepted. Re-registering the
        same ``correlation_id`` is silently overwritten (idempotent register —
        per DDR-028 §Consequences).

        DDR-028 eviction policy:

        * When the map is at capacity AND ``correlation_id`` is not already
          present, ``popitem(last=False)`` discards the oldest entry.
        * Each eviction emits exactly one WARN
          ``forge_correlation_evicted`` log line carrying the evicted
          correlation's diagnostics (Group B #3–#4).
        """
        existing = self._correlations.pop(correlation_id, None)
        if existing is None and len(self._correlations) >= self._correlation_cap:
            evicted_id, evicted = self._correlations.popitem(last=False)
            logger.warning(
                "forge_correlation_evicted",
                correlation_id=evicted_id,
                feature_id=evicted.feature_id,
                session_id=evicted.session_id,
                adapter=evicted.adapter,
                cap=self._correlation_cap,
            )

        self._correlations[correlation_id] = BuildCorrelation(
            correlation_id=correlation_id,
            feature_id=feature_id,
            session_id=session_id,
            adapter=adapter,
            queued_at=queued_at,
        )

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    async def _on_message(self, msg: Msg) -> None:
        """JetStream callback — never raises (DDR-026).

        Validates the envelope, enforces ``source_id == "forge"``, looks
        up the correlation, and:

        1. Fires the routing-history edge (fire-and-forget — DDR-029).
        2. Enqueues a :class:`ForgeNotification` on the session FIFO.

        Drop conditions (per design.md §8 / DDR-026):

        * Malformed envelope (bad JSON, missing required fields) → WARN
          ``forge_notification_dropped_malformed``.
        * Unknown source_id (not ``"forge"``) → WARN
          ``forge_notification_dropped_unknown_source``.
        * Unknown correlation_id (evicted or never registered) → silent
          drop (no log line — Group C #2).
        * Malformed StageCompletePayload → WARN
          ``forge_notification_dropped_bad_payload``.
        * Session manager unbound → WARN
          ``forge_notification_dropped_unbound_session_manager`` and
          drop the message (design.md §8 chooses drop over buffer).
        """
        try:
            await self._handle_message(msg)
        except Exception as exc:  # noqa: BLE001 — never raise out of cb
            # Defensive backstop. Every legitimate drop path inside
            # ``_handle_message`` already logs and returns; this catch
            # only fires on a genuine programming error and ensures the
            # JetStream loop keeps draining the next message.
            logger.warning(
                "forge_notification_dropped_handler_error",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _handle_message(self, msg: Msg) -> None:
        """Inner message-routing path. Never raises."""
        # Local imports keep the schema-only consumers of this module
        # free of nats_core's payload classes (and the transitive nats
        # import chain).
        from nats_core import MessageEnvelope
        from nats_core.events import StageCompletePayload

        # --- 1. Decode envelope --------------------------------------------
        try:
            envelope = MessageEnvelope.model_validate_json(msg.data)
        except (ValidationError, ValueError) as exc:
            # Bad JSON or missing/invalid envelope fields. Group D #7 +
            # Group D #8 (extra unknown fields) are both handled here:
            # ``MessageEnvelope`` declares ``extra="ignore"``, so unknown
            # fields land in this branch only when JSON shape is broken,
            # not when extra keys are present.
            logger.warning(
                "forge_notification_dropped_malformed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            return

        # --- 2. Source-ID gate (ASSUM-006 / API-events §3) -----------------
        if envelope.source_id != "forge":
            logger.warning(
                "forge_notification_dropped_unknown_source",
                source_id=envelope.source_id,
                correlation_id=envelope.correlation_id,
            )
            return

        # --- 3. Decode payload ---------------------------------------------
        try:
            payload = StageCompletePayload.model_validate(envelope.payload)
        except ValidationError as exc:
            logger.warning(
                "forge_notification_dropped_bad_payload",
                error_class=type(exc).__name__,
                error=str(exc),
                correlation_id=envelope.correlation_id,
            )
            return

        correlation_id = payload.correlation_id

        # --- 4. Correlation lookup -----------------------------------------
        correlation = self._correlations.get(correlation_id)
        if correlation is None:
            # Group C #2 — silent drop. The correlation was either evicted
            # from the DDR-028 bounded map or never registered (e.g. an
            # event published after a Jarvis restart).
            return

        # LRU touch — accessing this correlation moves it to the freshest
        # end so a long-running build doesn't get evicted underneath an
        # in-flight stream of stage-complete events.
        self._correlations.move_to_end(correlation_id)

        # --- 5. Routing-history edge (DDR-029, fire-and-forget) ------------
        # The writer is itself fire-and-forget; we await the *submission*
        # so a writer-side exception lands in the WARN-only branch rather
        # than escaping the JetStream callback. ``append_build_queue_event``
        # never raises (DDR-019) so the suppress is a defensive belt-and-
        # braces for future writer evolutions.
        edge_payload = payload.model_dump(mode="json")
        with contextlib.suppress(Exception):
            await self._routing_history_writer.append_build_queue_event(
                correlation_id, edge_payload
            )

        # --- 6. Build the in-process notification --------------------------
        try:
            completed_at_dt = _parse_completed_at(payload.completed_at)
        except ValueError as exc:
            logger.warning(
                "forge_notification_dropped_bad_completed_at",
                error_class=type(exc).__name__,
                error=str(exc),
                correlation_id=correlation_id,
            )
            return

        try:
            notification = ForgeNotification(
                correlation_id=correlation_id,
                feature_id=payload.feature_id,
                stage_label=payload.stage_label,
                status=payload.status,
                target_kind=payload.target_kind,
                target_identifier=payload.target_identifier,
                completed_at=completed_at_dt,
                duration_secs=payload.duration_secs,
            )
        except ValidationError as exc:
            logger.warning(
                "forge_notification_dropped_projection_failed",
                error_class=type(exc).__name__,
                error=str(exc),
                correlation_id=correlation_id,
            )
            return

        # --- 7. Enqueue on session FIFO ------------------------------------
        if self._session_manager is None:
            logger.warning(
                "forge_notification_dropped_unbound_session_manager",
                correlation_id=correlation_id,
            )
            return

        if correlation.session_id is None:
            # The correlation was registered without a session
            # (sessionless test path). The trace edge is still useful;
            # we simply have no FIFO to enqueue on.
            return

        # SessionManager.enqueue_notification is idempotent on missing /
        # ended sessions and bounds the per-session FIFO at queue_cap
        # internally — no try/except needed here.
        self._session_manager.enqueue_notification(
            correlation.session_id, notification
        )


def _parse_completed_at(value: str | datetime) -> datetime:
    """Normalize ``StageCompletePayload.completed_at`` to ``datetime``.

    The wire payload declares ``completed_at: str`` (ISO 8601). Defensively
    accept an already-parsed ``datetime`` so the same helper is reusable
    from the in-process projection paths once contract tests start
    emitting datetime objects directly.
    """
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "BuildCorrelation",
    "ForgeNotification",
    "ForgeNotificationsSubscriber",
]
