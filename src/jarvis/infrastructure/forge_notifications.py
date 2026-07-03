"""Forge stage-complete notification schema and subscriber.

This module owns the in-process Forge stage-complete notification surface
for Jarvis. It declares two Pydantic v2 models — :class:`ForgeNotification`
(the projection of ``nats_core.events.StageCompletePayload`` onto Jarvis's
adapter-rendering layer) and :class:`BuildCorrelation` (one element of the
in-memory correlation map) — and the
:class:`ForgeNotificationsSubscriber` that routes deliveries from
``pipeline.stage-complete.>`` to the originating session's pending
notifications FIFO. Together they realise the cross-adapter rendering
contract that downstream features (CLI today; Telegram and the live
dashboard tomorrow) consume verbatim.

Origin
------
Group A.2 of FEAT-JARVIS-005 — the Forge stage-complete notification
pipeline. This module is the in-process landing zone; the canonical NATS
wire shape lives in ``nats_core.events.StageCompletePayload`` and is
imported lazily from the subscriber so schema-only consumers do not pay
the ``nats-py`` import cost.

References
----------
* Design document:
  ``docs/design/FEAT-JARVIS-005/design.md`` (§8 — stage-complete
  routing, drop policy, and shutdown ordering).
* Data model:
  ``docs/design/FEAT-JARVIS-005/models/DM-forge-notification.md`` —
  authoritative field definitions, regex patterns, ``Literal`` members,
  and the ``render_line()`` shape contract.
* ``docs/design/FEAT-JARVIS-005/decisions/DDR-026-forge-notifications-module-location.md``
  — why this surface lives under ``jarvis.infrastructure``.
* ``docs/design/FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md``
  — ephemeral push consumer with ``deliver_policy=NEW``; no replay on
  restart.
* ``docs/design/FEAT-JARVIS-005/decisions/DDR-028-correlation-map-in-memory-bounded.md``
  — bounded LRU correlation map; oldest-first eviction at capacity.
* ``docs/design/FEAT-JARVIS-005/decisions/DDR-029-stage-complete-as-append-only-edges.md``
  — fire-and-forget routing-history edge per matched event.
* ``docs/design/FEAT-JARVIS-005/decisions/DDR-030-cli-notifications-between-prompts.md``
  — canonical render shape consumed by the CLI.
* ``docs/design/FEAT-JARVIS-005/decisions/DDR-031-originating-adapter-from-session.md``
  — adapter resolution captured at queue time for diagnostics.

Notes
-----
* Both models are ``frozen=True`` — once constructed, never mutated. Any
  future enrichment (e.g. adding a ``coach_score`` quintile bucket) is a
  new optional field plus an updated ``render_line()`` body, not an
  in-place edit.
* ``extra="ignore"`` lets future fields land non-breakingly when a
  follow-up feature promotes ``ForgeNotification`` to a real wire payload
  on ``jarvis.notification.{adapter}``.
* The schema declarations do not import ``nats_core`` / ``nats`` at
  module top level; the subscriber lazy-loads those modules so unit
  tests that only exercise the Pydantic models stay free of the
  JetStream import chain.
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
    itself is performed inside the subscriber's message handler.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    event_type: Literal[
        "stage_complete", "build_started", "build_complete", "build_failed"
    ] = Field(
        default="stage_complete",
        description=(
            "Discriminator for the rendered line shape. Defaults to "
            "``stage_complete`` so existing call sites that build a "
            "ForgeNotification with the stage-complete fields continue "
            "to render the canonical DDR-030 stage line. Per "
            "TASK-FRR-F010D, the subscriber widened to the full "
            "pipeline namespace (``Topics.Pipeline.ALL``) and now "
            "projects build-started, build-complete and build-failed "
            "envelopes onto this same model with the "
            "stage-complete-specific fields left as None."
        ),
    )
    correlation_id: str = Field(
        min_length=1,
        description=(
            "BuildQueuedPayload.correlation_id — used to thread back "
            "to the originating routing-history entry. For "
            "stage_complete events this is the payload's own "
            "correlation_id; for the three build-lifecycle event "
            "types (which carry no payload-level correlation_id) it "
            "is sourced from MessageEnvelope.correlation_id (forge "
            "threads it on outbound envelopes per "
            "TASK-FORGE-FRR-F010C)."
        ),
    )
    feature_id: str = Field(
        pattern=r"^FEAT-[A-Z0-9]{3,12}$",
        description="The Forge feature identifier (matches BuildQueuedPayload).",
    )
    stage_label: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Reasoning-model-chosen stage label (emergent per "
            "ADR-ARCH-016). Examples: 'plan-complete', 'autobuild-complete', "
            "'task-review-complete'. Only populated for "
            "``event_type='stage_complete'``; None for the three "
            "build-lifecycle event types."
        ),
    )
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"] | None = Field(
        default=None,
        description=(
            "Stage outcome from StageCompletePayload. Only populated "
            "for ``event_type='stage_complete'``."
        ),
    )
    target_kind: Literal["local_tool", "fleet_capability", "subagent"] | None = (
        Field(
            default=None,
            description=(
                "Which kind of executor ran the stage on Forge's side. "
                "Surfaced on the rendered line so Rich can see whether "
                "a stage was internal-tool work, fleet-dispatch, or "
                "subagent-driven. Only populated for "
                "``event_type='stage_complete'``."
            ),
        )
    )
    target_identifier: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Concrete identifier of the executor "
            "(tool name / agent_id:tool_name / subagent name). Only "
            "populated for ``event_type='stage_complete'``."
        ),
    )
    completed_at: datetime = Field(
        description=(
            "When Forge published the event. For stage-complete events "
            "this is parsed from StageCompletePayload.completed_at "
            "(ISO 8601 string). For the three build-lifecycle event "
            "types (whose payloads carry no completed_at field) this "
            "is sourced from MessageEnvelope.timestamp. "
            "Timezone-aware UTC datetime per DM-forge-notification §1."
        ),
    )
    duration_secs: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Stage duration in seconds — surfaced on the rendered "
            "line. Only populated for ``event_type='stage_complete'``."
        ),
    )
    failure_reason: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Failure reason from BuildFailedPayload.failure_reason. "
            "Only populated for ``event_type='build_failed'``; "
            "rendered in parens on the canonical line per the "
            "FEAT-JARVIS-INTERNAL-001 first-real-run runbook §7.1 "
            "shape ``[HH:MM] Forge FEAT-XXX: build-failed (path "
            "outside allowlist)``."
        ),
    )

    def render_line(self) -> str:
        """Render the canonical CLI line per DDR-030 / DM-forge-notification §1.

        Shapes (one per ``event_type`` discriminator member; FEAT-J006 /
        FEAT-J009 reuse all four verbatim — the cross-adapter rendering
        contract is the union of these four lines)::

            [HH:MM] Forge {feature_id}: stage {stage_label} ({status})
            [HH:MM] Forge {feature_id}: build-started (RUNNING)
            [HH:MM] Forge {feature_id}: build-complete (PASSED)
            [HH:MM] Forge {feature_id}: build-failed ({failure_reason})

        Examples::

            [15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete (PASSED)
            [15:44] Forge FEAT-JARVIS-INTERNAL-001: stage autobuild-complete (PASSED)
            [15:42] Forge FEAT-43DE: build-started (RUNNING)
            [15:50] Forge FEAT-43DE: build-complete (PASSED)
            [15:48] Forge FEAT-43DE: build-failed (path outside allowlist)

        Time is the local-time portion of :attr:`completed_at` rendered
        as ``HH:MM`` (no seconds, no timezone offset). When
        ``completed_at`` is timezone-aware UTC, ``astimezone()`` shifts
        it into the host's local zone before formatting; naive datetimes
        fall through ``strftime`` unchanged.
        """
        local_completed_at = (
            self.completed_at.astimezone()
            if self.completed_at.tzinfo is not None
            else self.completed_at
        )
        hhmm = local_completed_at.strftime("%H:%M")
        prefix = f"[{hhmm}] Forge {self.feature_id}:"

        if self.event_type == "stage_complete":
            # Existing DDR-030 shape — preserved verbatim for the
            # cross-adapter contract (FEAT-J006 / FEAT-J009 consumers).
            return f"{prefix} stage {self.stage_label} ({self.status})"
        if self.event_type == "build_started":
            return f"{prefix} build-started (RUNNING)"
        if self.event_type == "build_complete":
            return f"{prefix} build-complete (PASSED)"
        # build_failed — failure_reason rendered in parens per runbook
        # §7.1; defensive fallback if unset (should never happen given
        # the projection in _handle_message always sets it).
        reason = self.failure_reason or "unknown"
        return f"{prefix} build-failed ({reason})"


# ---------------------------------------------------------------------------
# §2 — BuildCorrelation (DM-forge-notification §2)
# ---------------------------------------------------------------------------


class BuildCorrelation(BaseModel):
    """One element of the in-memory correlation map.

    Stored in ``ForgeNotificationsSubscriber._correlations`` (DDR-028 —
    LRU bounded at ``correlation_cap``, default 1000). Lost on Jarvis
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


# ---------------------------------------------------------------------------
# §3 — ForgeNotificationsSubscriber
# ---------------------------------------------------------------------------

# Subscribe wildcards derived lazily from the canonical
# ``nats_core.Topics.Pipeline`` templates by substituting the NATS ``>``
# wildcard for ``{feature_id}``. TASK-FRR-F010Db (2026-05-04) narrowed
# the filter from ``Topics.Pipeline.ALL`` (``pipeline.>``, the Option A
# choice from TASK-FRR-F010D) to the explicit four-subject lifecycle
# list returned by :func:`_get_lifecycle_subjects` because
# ``pipeline.>`` overlaps with forge-serve's ``pipeline.build-queued.>``
# consumer on the workqueue PIPELINE stream and JetStream rejects the
# bind with ``err_code=10100 'filtered consumer not unique on workqueue
# stream'``. The four lifecycle subjects are disjoint from
# ``pipeline.build-queued.>`` by construction.
#
# The derivation is wrapped in :func:`_get_lifecycle_subjects` rather
# than evaluated at import time so this module continues to satisfy the
# schema-import-isolation invariant checked by
# ``tests/test_forge_notification_schema.py`` while still pulling the
# canonical subjects from :class:`nats_core.Topics` (cross-repo contract
# test ``tests/test_contract_nats_core.py`` AC-007).

# DDR-027 (revised 2026-05-01 per TASK-FRR-001): ephemeral push consumer
# with deliver_policy=ALL. The canonical PIPELINE stream provisioned by
# ``nats-infrastructure`` is ``retention=workqueue`` (per
# ``streams/stream-definitions.json``); workqueue retention requires
# ``deliver_policy=all`` on consumers and rejects ``deliver_policy=new``
# with ``BadRequestError code=10101 consumer must be deliver all on
# workqueue stream``. The original DDR-027 ``DeliverPolicy.NEW`` choice
# assumed PIPELINE was a LimitsPolicy stream, which the canonical infra
# has not been since FEAT-JARVIS-INTERNAL-001 surfaced the contract drift.
#
# The "no replay-on-restart UX surprise" property the original DDR-027
# rationale was after is preserved structurally rather than via the
# delivery policy:
#   * Workqueue retention deletes a message once any consumer acks it.
#     Jarvis's only filter on this stream is ``pipeline.stage-complete.>``,
#     and auto-ack drains every delivery the moment the callback returns —
#     so the consumer's slice is empty in steady state.
#   * The DDR-028 in-memory correlation map is lost on Jarvis restart.
#     Any backlog drained at restart with deliver_policy=all hits a
#     "correlation_id not found" silent drop in ``_handle_message`` and
#     the message is gone (workqueue + auto-ack).
# Net effect: the operator never sees replay UX, just like before.
#
# We avoid a top-level import of nats.js.api so the schema-only import of
# this module (e.g. from a unit test that only exercises
# ``ForgeNotification``) does not pay the nats-py import cost.
# ``_get_deliver_policy_all`` lazy-loads the enum on the start path.

# DDR-027 §"Consequences": no replay on restart in v1. Backfill is out of
# scope; the subscriber drops on the floor anything published while Jarvis
# was down.

# DDR-028 default cap. ``register_correlation`` evicts the oldest entry once
# the map is at capacity and emits one WARN per eviction.
_DEFAULT_CORRELATION_CAP = 1000


def _get_deliver_policy_all() -> Any:
    """Lazy-load ``nats.js.api.DeliverPolicy.ALL``.

    Schema-only consumers of this module never import ``nats``; the
    subscriber start path is the only call site that needs the enum.
    Keeping the import lazy stops cold imports of the schema from
    transitively pulling in the full ``nats-py`` JetStream surface.

    DDR-027 (revised): the canonical PIPELINE stream is a workqueue —
    only ``DeliverPolicy.ALL`` is accepted on attached consumers
    (``code=10101`` otherwise). The no-replay-on-restart UX is preserved
    by workqueue retention + auto-ack + DDR-028 correlation-map loss
    (see the module-level rationale block above).
    """
    from nats.js.api import DeliverPolicy

    return DeliverPolicy.ALL


def _get_lifecycle_subjects() -> list[str]:
    """Lazy-derive the four lifecycle subject wildcards from ``nats_core.Topics``.

    Returns the explicit four-subject lifecycle filter list Jarvis
    binds on the canonical PIPELINE stream:

    * ``pipeline.build-started.>``
    * ``pipeline.stage-complete.>``
    * ``pipeline.build-complete.>``
    * ``pipeline.build-failed.>``

    These are exactly the runbook §7.1 envelope types Jarvis renders.

    Why this list (and not the wider ``Topics.Pipeline.ALL`` —
    ``pipeline.>``)? PIPELINE is workqueue-retention; workqueue policy
    forbids overlapping subject filters across consumers. The forge
    daemon's ``forge-serve`` consumer already filters
    ``pipeline.build-queued.>``, so any consumer Jarvis attaches must
    use a filter disjoint from that. ``pipeline.>`` is a superset of
    ``pipeline.build-queued.>`` and JetStream rejects the bind with
    ``err_code=10100 'filtered consumer not unique on workqueue
    stream'``. The four lifecycle subjects above are disjoint from
    ``pipeline.build-queued.>`` by construction (TASK-FRR-F010Db, the
    correction to TASK-FRR-F010D's Option A widening). Jarvis's own
    ``pipeline.build-queued.*`` self-publishes never reach
    ``_handle_message`` at the wire level; the
    ``source_id != "forge"`` gate inside ``_handle_message`` is kept
    as defence-in-depth against future publishers that mis-set
    ``source_id``.

    Imported lazily — same rationale as :func:`_get_deliver_policy_all`,
    plus the schema-import-isolation invariant in
    ``tests/test_forge_notification_schema.py`` forbids top-level
    ``from nats_core`` / ``from nats`` statements in this module.

    The ``replace("{feature_id}", ">")`` substitution mirrors the
    pre-TASK-FRR-F010D derivation pattern; the templates themselves
    are validated against the cross-repo contract by
    ``tests/test_contract_nats_core.py``.
    """
    from nats_core import Topics

    pipeline = Topics.Pipeline
    return [
        pipeline.BUILD_STARTED.replace("{feature_id}", ">"),
        pipeline.STAGE_COMPLETE.replace("{feature_id}", ">"),
        pipeline.BUILD_COMPLETE.replace("{feature_id}", ">"),
        pipeline.BUILD_FAILED.replace("{feature_id}", ">"),
    ]


class ForgeNotificationsSubscriber:
    """In-process subscriber for ``pipeline.stage-complete.>``.

    Maintains a bounded LRU map from ``correlation_id`` to
    :class:`BuildCorrelation`, decodes each delivered envelope into a
    :class:`ForgeNotification`, fire-and-forgets a memory edge via
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
        "_correlation_cap",
        "_correlations",
        "_nats_client",
        "_queue_cap",
        "_routing_history_writer",
        "_session_manager",
        "_started",
        "_stop_timeout",
        "_subscription",
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
                append a memory edge per matched stage-complete event
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
        """Subscribe to the four lifecycle subjects (idempotent).

        TASK-FRR-F010Db (2026-05-04, late afternoon): subject filter
        narrowed from ``Topics.Pipeline.ALL`` (``pipeline.>``, the
        Option A choice from TASK-FRR-F010D) to the explicit four-
        subject lifecycle list returned by
        :func:`_get_lifecycle_subjects` (Option B). The Option A
        catch-all overlapped with forge-serve's existing
        ``pipeline.build-queued.>`` consumer on the workqueue PIPELINE
        stream and JetStream rejected the bind on every boot with
        ``err_code=10100 'filtered consumer not unique on workqueue
        stream'``. The four lifecycle subjects are disjoint from
        ``pipeline.build-queued.>`` by construction. See
        :func:`_get_lifecycle_subjects` for the workqueue-overlap
        rationale.

        TASK-FRR-F010D (2026-05-04, morning): the subscriber is
        responsible for all four runbook §7.1 lifecycle envelope types
        (``build-started`` / ``stage-complete`` / ``build-complete`` /
        ``build-failed``); the ``source_id != "forge"`` gate in
        ``_handle_message`` is preserved as defence-in-depth.

        DDR-027 (revised 2026-05-01 / TASK-FRR-001): ephemeral push
        consumer with ``deliver_policy=ALL``. Workqueue retention on the
        canonical PIPELINE stream rejects ``DeliverPolicy.NEW`` with
        ``code=10101 consumer must be deliver all on workqueue stream``;
        the no-replay-on-restart UX the original DDR-027 wanted is
        preserved structurally instead — see the module-level rationale
        block by ``_get_deliver_policy_all``.

        Auto-ack — the subscriber does not call ``msg.ack()`` because
        ``manual_ack=False`` is the default and the JetStream context
        will ack each delivery once the callback returns.

        Implementation note: the multi-subject filter is passed via
        ``nats.js.api.ConsumerConfig.filter_subjects`` (the plural
        form). When ``filter_subjects`` is set on the config,
        :meth:`nats.js.JetStreamContext.subscribe` ignores the
        positional ``subject`` arg for filter purposes (it is still
        used for stream lookup) — see the ``subscribe`` source in
        ``nats.js.client`` (``if not config.filter_subjects:
        config.filter_subject = subject``). We pass the first
        lifecycle subject as the positional lookup hint so
        ``find_stream_name_by_subject`` resolves the canonical
        PIPELINE stream without needing to hard-code its name.
        """
        if self._started:
            return

        # Lazy import — keeps ``nats.js.api`` out of the module's top-
        # level import chain (same rationale as
        # :func:`_get_deliver_policy_all`).
        from nats.js.api import ConsumerConfig

        js: JetStreamContext = self._nats_client.js
        deliver_policy_all = _get_deliver_policy_all()
        lifecycle_subjects = _get_lifecycle_subjects()

        self._subscription = await js.subscribe(
            lifecycle_subjects[0],
            cb=self._on_message,
            config=ConsumerConfig(filter_subjects=list(lifecycle_subjects)),
            ordered_consumer=False,
            deliver_policy=deliver_policy_all,
        )
        self._started = True
        logger.info(
            "forge_notifications_subscribed",
            subjects=lifecycle_subjects,
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
        except Exception as exc:
            logger.warning(
                "forge_notifications_stop_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Late binding (lifecycle wiring)
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

        Entry point used by :func:`jarvis.tools.queue_build` once the
        BUILD_QUEUED publish has been accepted. Re-registering the
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
        except Exception as exc:
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
        """Inner message-routing path. Never raises.

        Per TASK-FRR-F010D, dispatches on ``envelope.event_type`` after
        the source-id gate so the four runbook §7.1 lifecycle envelope
        types each route to their type-specific projection. The
        ``stage_complete`` branch preserves the original DDR-029
        routing-history edge plus DDR-030 enqueue path verbatim; the
        three build-lifecycle branches share a single light projector
        that skips the DDR-029 edge (the routing-history writer's
        ``append_build_queue_event`` is keyed on stage-complete
        payloads — broadening it is out of scope for this fix) and
        enqueues directly on the session FIFO.
        """
        # Local imports keep the schema-only consumers of this module
        # free of nats_core's payload classes (and the transitive nats
        # import chain).
        from nats_core import MessageEnvelope

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

        # --- 3. Dispatch on event_type -------------------------------------
        # Per TASK-FRR-F010D the subscription is the canonical
        # ``pipeline.>`` catch-all; dispatch to the right projection.
        event_type = envelope.event_type
        if event_type == "stage_complete":
            await self._handle_stage_complete(envelope)
            return
        if event_type in ("build_started", "build_complete", "build_failed"):
            await self._handle_build_lifecycle(envelope, event_type)
            return
        # Other pipeline.* events (build_queued, build_progress,
        # build_paused, build_resumed, build_cancelled, feature_planned,
        # feature_ready_for_build, stage_gated) are intentionally not
        # rendered as CLI between-prompt notifications today. Drop with
        # a debug log; consumers needing those types will be added by a
        # follow-up task.
        logger.debug(
            "forge_notification_dropped_unsupported_event_type",
            event_type=str(event_type),
            correlation_id=envelope.correlation_id,
        )

    async def _handle_stage_complete(self, envelope: Any) -> None:
        """Stage-complete projection (original DDR-029 + DDR-030 path).

        Preserved verbatim from the pre-TASK-FRR-F010D implementation —
        decodes ``StageCompletePayload``, fires the routing-history edge,
        and enqueues a stage-shaped :class:`ForgeNotification`. Routing
        key is ``payload.correlation_id`` because StageCompletePayload
        carries one of its own (the three build-lifecycle payloads do
        not).
        """
        from nats_core.events import StageCompletePayload

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

        # Routing-history edge (DDR-029, fire-and-forget). The writer is
        # itself fire-and-forget; we await the *submission* so a
        # writer-side exception lands in the WARN-only branch rather
        # than escaping the JetStream callback. ``append_build_queue_event``
        # never raises (DDR-019) so the suppress is a defensive belt-
        # and-braces for future writer evolutions.
        edge_payload = payload.model_dump(mode="json")
        with contextlib.suppress(Exception):
            await self._routing_history_writer.append_build_queue_event(
                correlation_id, edge_payload
            )

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
                event_type="stage_complete",
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

        self._enqueue_for_correlation(correlation, notification)

    async def _handle_build_lifecycle(
        self,
        envelope: Any,
        event_type: str,
    ) -> None:
        """Project a build-lifecycle envelope onto a ForgeNotification.

        Handles the three runbook §7.1 lifecycle types whose payloads do
        not carry a ``correlation_id`` of their own:

        * ``build_started``  → BuildStartedPayload
        * ``build_complete`` → BuildCompletePayload
        * ``build_failed``   → BuildFailedPayload (failure_reason
          captured for the rendered line)

        Routing key is ``envelope.correlation_id`` (forge threads the
        inbound build-queued correlation onto outbound envelopes per
        TASK-FORGE-FRR-F010C). ``completed_at`` is sourced from
        ``envelope.timestamp`` since the lifecycle payloads have no
        completed_at field.
        """
        from nats_core.events import (
            BuildCompletePayload,
            BuildFailedPayload,
            BuildStartedPayload,
        )

        correlation_id = envelope.correlation_id
        if not correlation_id:
            # Forge envelopes pre-TASK-FORGE-FRR-F010C may have
            # correlation_id=null on rejection-published failures; drop
            # with a structured WARN so operators can spot the missing
            # threading.
            logger.warning(
                "forge_notification_dropped_missing_envelope_correlation",
                event_type=event_type,
            )
            return

        # Validate the payload against the right model. A bad payload
        # mirrors the stage-complete branch's ``dropped_bad_payload``
        # WARN shape so diagnostic tooling can grep one log key for
        # both.
        payload_model: type[Any]
        if event_type == "build_started":
            payload_model = BuildStartedPayload
        elif event_type == "build_complete":
            payload_model = BuildCompletePayload
        else:  # build_failed
            payload_model = BuildFailedPayload

        try:
            payload = payload_model.model_validate(envelope.payload)
        except ValidationError as exc:
            logger.warning(
                "forge_notification_dropped_bad_payload",
                error_class=type(exc).__name__,
                error=str(exc),
                event_type=event_type,
                correlation_id=correlation_id,
            )
            return

        correlation = self._correlations.get(correlation_id)
        if correlation is None:
            # Same silent-drop semantics as stage-complete (Group C #2).
            return
        self._correlations.move_to_end(correlation_id)

        # ``isinstance`` narrows the union — only BuildFailedPayload
        # carries ``failure_reason``; the other two branches keep it None
        # and the renderer falls through to its non-failure shapes.
        failure_reason: str | None = (
            payload.failure_reason
            if isinstance(payload, BuildFailedPayload)
            else None
        )

        try:
            notification = ForgeNotification(
                event_type=event_type,  # type: ignore[arg-type]
                correlation_id=correlation_id,
                feature_id=payload.feature_id,
                completed_at=envelope.timestamp,
                failure_reason=failure_reason,
            )
        except ValidationError as exc:
            logger.warning(
                "forge_notification_dropped_projection_failed",
                error_class=type(exc).__name__,
                error=str(exc),
                event_type=event_type,
                correlation_id=correlation_id,
            )
            return

        self._enqueue_for_correlation(correlation, notification)

    def _enqueue_for_correlation(
        self,
        correlation: BuildCorrelation,
        notification: ForgeNotification,
    ) -> None:
        """Common FIFO enqueue path shared by all event-type branches.

        Drops on unbound session manager (DDR-030) and skips the enqueue
        when the correlation has no session (sessionless test path).
        """
        if self._session_manager is None:
            logger.warning(
                "forge_notification_dropped_unbound_session_manager",
                correlation_id=notification.correlation_id,
            )
            return

        if correlation.session_id is None:
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
