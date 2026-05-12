"""Chat command handler for the ``agents.command.jarvis`` NATS topic.

This module owns the single-command business logic for the
``CommandPayload`` envelopes delivered to Jarvis on
``agents.command.jarvis`` (FEAT-JARVIS-006). It is the gateway-side
counterpart to study-tutor's
:mod:`study_tutor.adapters.command_router`, simplified for Jarvis's
single verb (``chat``):

* No ``_command_map`` (one verb only).
* No alias resolution (``tool_to_command``) — the fleet talks to
  Jarvis exclusively via the canonical ``chat`` command, not an MCP
  tool name.
* No adapter-readiness gate — the session manager is constructed in
  ``lifecycle.build_app_state`` before the NATS subscription is
  registered, so the handler is wired only after the supervisor is
  ready (the early-bind invariant is enforced by lifecycle
  composition, not by a runtime check inside the handler).

The handler is closure-free: every dependency arrives as an explicit
keyword argument so the unit tests can inject mocks without
monkey-patching module globals. The public surface is exactly one
function — :func:`handle_chat_command` — which is the callback
registered with :meth:`NATSClient.subscribe_with_reply` by
``lifecycle.build_app_state``.

Origin
------

Group B of FEAT-JARVIS-006 — the NATS chat gateway. See
``tasks/design_approved/TASK-J006-003-chat-handler.md`` for the per-task
spec and ``features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md``
for the design rationale (Bug #1 dual-publish, Bug #4 flat subjects,
Risk #3 forge-notification drain).

Behaviour invariants
--------------------

1. **Single verb.** The handler always treats the inbound envelope as a
   ``chat`` command. ``CommandPayload.command`` is logged for diagnostics
   but not branched on — alternative verbs are routed by separate
   subscriptions (none exist today).
2. **Inbound ``conversation_history`` is ignored** — the per-gateway
   :class:`Session` is the canonical history store (resolves ASSUM from
   the scope doc). The inbound field is documented in the manifest
   (TASK-J006-001) as accepted-but-ignored for backwards compatibility.
3. **Empty / missing message rejected.** If ``args["message"]`` is
   missing, not a string, or whitespace-only, the handler short-circuits
   with a structured ``ResultPayload`` (``success=False``,
   ``result["error"]`` set) and skips :meth:`SessionManager.invoke`.
   The structured-error reply still travels the full dual-publish
   path so the requester's NATS request/reply future resolves.
4. **No exceptions escape.** Any exception raised by
   :meth:`SessionManager.invoke` is caught at the boundary and
   converted to ``ResultPayload(success=False, ...)``. The wrapper
   :meth:`NATSClient.subscribe_with_reply` already logs+absorbs
   handler exceptions (so the subscription's reader task survives
   bugs), but the chat handler exists upstream of that backstop and
   takes its own responsibility for the dual-publish contract — the
   wrapper backstop would otherwise drop the reply silently and the
   requester's future would never resolve (Bug #1 regression).
5. **Notification drain after invoke.** Any forge stage-complete
   notifications accumulated on the session's FIFO during the
   supervisor turn are drained via
   :meth:`SessionManager.pending_notifications` and appended to the
   reply text (Risk #3 mitigation — include rather than ignore).
6. **Dual-publish (Bug #1 fix).** The final ``ResultPayload`` is
   published to BOTH:

   * The raw ``reply_to`` inbox via ``nats_client.client.publish``
     so the requester's :meth:`NATSClient.request` future resolves
     with the actual payload (not the JetStream PubAck).
   * The canonical ``agents.result.jarvis`` envelope topic via the
     same client, wrapped in a :class:`MessageEnvelope` so
     event-stream consumers see every result.

   Both publishes use flat subjects only (Bug #4 — no wildcard
   tokens; the canonical subject is resolved via
   :meth:`Topics.resolve` which validates identifiers).

7. **Structured logs.** Three events bracket every invocation:
   ``chat_invoke_start``, ``chat_invoke_complete``, and
   ``chat_invoke_error`` (the latter for both the empty-message
   short-circuit and the invoke-exception branch). All three carry
   ``correlation_id`` so log streams can be threaded against the
   inbound envelope.

References
----------
* ``study-tutor/src/study_tutor/adapters/command_router.py`` — proven
  ``_safe_invoke`` + ``_publish_result`` pattern (11 May 2026).
* ``nats_core.envelope.MessageEnvelope`` — canonical wire envelope.
* ``nats_core.events._agent.CommandPayload`` / ``ResultPayload`` —
  inbound and outbound payload schemas.
* ``nats_core.topics.Topics.Agents.RESULT`` — canonical result topic
  template (resolves to ``agents.result.{agent_id}``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events._agent import CommandPayload, ResultPayload
from nats_core.topics import Topics

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.infrastructure.nats_client import NATSClient
    from jarvis.sessions.manager import SessionManager
    from jarvis.sessions.session import Session

__all__ = ["handle_chat_command"]


logger = structlog.get_logger(__name__)

# The canonical command verb. Used as ``ResultPayload.command`` on every
# reply so downstream observers can filter the result stream by verb
# without re-parsing the inbound envelope. Single-source-of-truth at
# module scope so unit tests can pin the value without poking the
# handler body.
_CHAT_COMMAND: str = "chat"


async def handle_chat_command(
    payload: CommandPayload,
    reply_to: str,
    *,
    session_manager: SessionManager,
    session: Session,
    nats_client: NATSClient,
    agent_id: str,
) -> None:
    """Handle one inbound ``chat`` command envelope.

    This is the callback registered with
    :meth:`NATSClient.subscribe_with_reply` for
    ``agents.command.jarvis``. The wrapper has already decoded the raw
    bytes into a :class:`CommandPayload` and forwarded the raw
    ``msg.reply`` inbox as ``reply_to`` (empty string when the inbound
    message was fire-and-forget).

    Behaviour summary (see module docstring for full invariants):

    1. Extract ``args["message"]`` from the inbound payload. Reject
       missing / non-string / whitespace-only values with a structured
       error reply (dual-published) and return.
    2. Await :meth:`SessionManager.invoke`. Any exception is caught at
       the boundary and converted to ``ResultPayload(success=False)``.
    3. Drain forge stage-complete notifications via
       :meth:`SessionManager.pending_notifications` and append them to
       the reply text (Risk #3).
    4. Build the success ``ResultPayload`` with
       ``{"response", "tools_called", "correlation_id"}``.
    5. Dual-publish to ``reply_to`` (raw bytes) AND
       ``agents.result.{agent_id}`` (envelope-wrapped) — Bug #1.

    Args:
        payload: The decoded inbound command payload.
            ``payload.args["message"]`` is the natural-language user
            text fed to the supervisor; ``payload.args["conversation_history"]``
            is accepted but ignored (the per-gateway Session is the
            canonical history store).
        reply_to: The raw NATS reply inbox the requester set on the
            inbound message. Empty string means fire-and-forget — the
            raw-publish leg is skipped but the canonical envelope leg
            still fires so event-stream consumers see the result.
        session_manager: The supervisor's
            :class:`~jarvis.sessions.manager.SessionManager`. The
            handler calls :meth:`invoke` and
            :meth:`pending_notifications` on it; nothing else.
        session: The pre-created :class:`~jarvis.sessions.session.Session`
            owned by this gateway. The same session is reused across
            every command so the supervisor's thread keeps its
            checkpoint state.
        nats_client: The connected :class:`NATSClient`. The handler
            uses its raw ``.client.publish`` surface for both publish
            legs.
        agent_id: The Jarvis fleet identifier (typically ``"jarvis"``).
            Used as ``source_id`` on the outbound envelope and to
            resolve the canonical result subject.

    Returns:
        ``None``. The result is delivered via the dual-publish; the
        return value is not consumed by the
        :meth:`NATSClient.subscribe_with_reply` wrapper.
    """
    correlation_id = payload.correlation_id

    logger.info(
        "chat_invoke_start",
        correlation_id=correlation_id,
        agent_id=agent_id,
        session_id=session.session_id,
        command=payload.command,
    )

    # ------------------------------------------------------------------
    # 1. Extract + validate message
    # ------------------------------------------------------------------
    message_raw: Any = payload.args.get("message")
    if not isinstance(message_raw, str) or not message_raw.strip():
        logger.warning(
            "chat_invoke_error",
            correlation_id=correlation_id,
            agent_id=agent_id,
            session_id=session.session_id,
            error_type="MissingMessage",
            reason="empty_or_missing_message",
        )
        error_result = ResultPayload(
            command=_CHAT_COMMAND,
            result={
                "error": (
                    "Missing or empty 'message' field in command args; "
                    "the chat verb requires a non-empty natural-language "
                    "message."
                ),
                "error_type": "MissingMessage",
                "correlation_id": correlation_id,
            },
            correlation_id=correlation_id,
            success=False,
        )
        await _dual_publish(
            nats_client=nats_client,
            reply_to=reply_to,
            result_payload=error_result,
            correlation_id=correlation_id,
            agent_id=agent_id,
        )
        return

    message: str = message_raw

    # Note: ``payload.args.get("conversation_history")`` is intentionally
    # *not* consulted here. The per-gateway Session is the canonical
    # history store (resolves ASSUM from the scope doc); inbound history
    # is documented in the manifest as accepted-but-ignored.

    # ------------------------------------------------------------------
    # 2. Invoke supervisor (boundary catch — no exceptions escape)
    # ------------------------------------------------------------------
    try:
        reply_text = await session_manager.invoke(session, message)
    except Exception as exc:
        logger.exception(
            "chat_invoke_error",
            correlation_id=correlation_id,
            agent_id=agent_id,
            session_id=session.session_id,
            error_class=type(exc).__name__,
        )
        error_result = ResultPayload(
            command=_CHAT_COMMAND,
            result={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "correlation_id": correlation_id,
            },
            correlation_id=correlation_id,
            success=False,
        )
        await _dual_publish(
            nats_client=nats_client,
            reply_to=reply_to,
            result_payload=error_result,
            correlation_id=correlation_id,
            agent_id=agent_id,
        )
        return

    # ------------------------------------------------------------------
    # 3. Drain pending forge notifications (Risk #3 mitigation)
    # ------------------------------------------------------------------
    # ``pending_notifications`` returns ``[]`` for unknown / ended
    # sessions per DM-forge-notification §3 #6, so no defensive guard
    # is needed here. Each rendered line is wrapped in a ``try`` so a
    # single malformed notification (e.g. one introduced by a future
    # ForgeNotification field migration) does not lose the entire
    # supervisor reply — the bad notification is dropped with a WARN
    # log line and the remaining notifications still reach the user.
    pending = session_manager.pending_notifications(session.session_id)
    rendered_lines: list[str] = []
    for notification in pending:
        try:
            rendered_lines.append(notification.render_line())
        except Exception as exc:
            logger.warning(
                "chat_notification_render_failed",
                correlation_id=correlation_id,
                session_id=session.session_id,
                notification_correlation_id=getattr(notification, "correlation_id", None),
                error_class=type(exc).__name__,
                error=str(exc),
            )
    response_text = reply_text + "\n" + "\n".join(rendered_lines) if rendered_lines else reply_text

    # ------------------------------------------------------------------
    # 4. Build success ResultPayload
    # ------------------------------------------------------------------
    # ``tools_called`` is currently an empty list — the supervisor does
    # not surface its tool-invocation trace in the reply text yet
    # (the field is reserved for a follow-up that threads
    # ``supervisor.tool_calls`` through). Keeping the key present at
    # ``[]`` lets downstream consumers (OpenWebUI adapter) build
    # against the stable shape today.
    success_result = ResultPayload(
        command=_CHAT_COMMAND,
        result={
            "response": response_text,
            "tools_called": [],
            "correlation_id": correlation_id,
        },
        correlation_id=correlation_id,
        success=True,
    )

    logger.info(
        "chat_invoke_complete",
        correlation_id=correlation_id,
        agent_id=agent_id,
        session_id=session.session_id,
        notifications_drained=len(pending),
        response_length=len(response_text),
    )

    # ------------------------------------------------------------------
    # 5. Dual-publish (Bug #1)
    # ------------------------------------------------------------------
    await _dual_publish(
        nats_client=nats_client,
        reply_to=reply_to,
        result_payload=success_result,
        correlation_id=correlation_id,
        agent_id=agent_id,
    )


async def _dual_publish(
    *,
    nats_client: NATSClient,
    reply_to: str,
    result_payload: ResultPayload,
    correlation_id: str | None,
    agent_id: str,
) -> None:
    """Publish ``result_payload`` to BOTH ``reply_to`` AND ``agents.result.{agent_id}``.

    This is the Bug #1 fix surface. The two publishes are intentionally
    not collapsed into a single helper inside ``NATSClient`` because the
    semantics differ:

    * The ``reply_to`` publish carries the **bare** ``ResultPayload``
      JSON (no envelope wrapper) — this is the shape
      :meth:`NATSClient.request` expects when its future resolves. A
      :class:`MessageEnvelope` wrapper here would break the
      requester-side decode.
    * The canonical ``agents.result.{agent_id}`` publish carries the
      **envelope-wrapped** payload so subject-domain consumers (the
      ``agents.result.>`` watchers) see the same wire format every
      other agent publishes.

    The canonical publish is *always* taken — even when ``reply_to`` is
    set — so event-stream consumers never miss a result. A
    fire-and-forget inbound (empty ``reply_to``) still emits the
    canonical envelope.

    Bug #4 (flat subjects): :meth:`Topics.resolve` validates
    ``agent_id`` against the identifier allowlist and rejects any
    embedded ``*`` / ``>`` tokens; the produced subject is guaranteed
    flat. The ``reply_to`` inbox supplied by the requester is opaque
    to us and forwarded verbatim — the nats-py client side of the
    request/reply protocol always allocates a flat ``_INBOX.<nuid>``
    subject so this is structurally safe.

    Args:
        nats_client: The connected client (``.client.publish`` is the
            underlying nats-py call).
        reply_to: The raw reply inbox. Empty string skips the raw leg.
        result_payload: The :class:`ResultPayload` to publish.
        correlation_id: Threaded into the canonical envelope so
            downstream tooling can correlate.
        agent_id: Resolved into the canonical subject and used as
            ``source_id`` on the envelope.
    """
    # --- Leg 1: raw publish to reply_to inbox (Bug #1 first publish) ---
    if reply_to:
        await nats_client.client.publish(
            reply_to,
            result_payload.model_dump_json().encode(),
        )

    # --- Leg 2: envelope-wrapped publish to canonical subject ---------
    # Topics.resolve enforces the flat-subject contract (Bug #4) by
    # validating ``agent_id`` against the identifier allowlist; an
    # invalid agent_id would raise ValueError at resolve time, well
    # before any bytes hit the wire.
    canonical_subject = Topics.resolve(Topics.Agents.RESULT, agent_id=agent_id)

    envelope = MessageEnvelope(
        source_id=agent_id,
        event_type=EventType.RESULT,
        correlation_id=correlation_id,
        payload=result_payload.model_dump(mode="json"),
    )
    await nats_client.client.publish(
        canonical_subject,
        envelope.model_dump_json().encode(),
    )
