"""Declarative AgentManifest factory for the Jarvis NATS chat gateway.

This module is the schema half of FEAT-JARVIS-006 (NATS chat gateway):
it produces the :class:`AgentManifest` advertised on the
``agent-registry`` KV bucket so the rest of the fleet can discover the
single ``chat`` ToolCapability and the natural-language
``general.*`` IntentCapability that Jarvis exposes.

Origin
------

Introduced as part of **FEAT-JARVIS-006 — NATS Chat Gateway**.  The
full feature design lives at
``features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md``
and the per-task spec is
``tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-001-manifest-factory.md``.

Public surface
--------------

- :func:`build_manifest` — pure manifest factory.

Design notes
------------

- ``agent_id`` is the literal ``"jarvis"`` so this factory's output is
  byte-compatible with the existing
  :func:`jarvis.infrastructure.fleet_registration.build_jarvis_manifest`
  identifier — both modules publish under the same fleet name (Risk #5
  guard: no double registration with a different id).
- The single :class:`ToolCapability` ``chat`` documents the
  ``CommandPayload.args`` schema consumed by the gateway: ``message``
  (required, str), ``conversation_history`` (optional, list — ignored
  by the chat handler), and ``adapter`` (optional, str).  Schema shape
  mirrors ``study-tutor``'s proven adapter manifest (referenced from
  the implementation guide §9).
- The single :class:`IntentCapability` ``general.*`` advertises the
  natural-language chat route for the supervisor.  ``signals`` is
  populated with non-empty keywords as a Bug #5 regression guard:
  ``InMemoryManifestRegistry.register`` rejects manifests with empty
  intents arrays and downstream routers ignore intents with empty
  signals.
- ``version`` is sourced from ``config.jarvis_agent_version``, matching
  the existing ``fleet_registration`` convention so both factories emit
  the same semver string.
"""

from __future__ import annotations

from nats_core.manifest import AgentManifest, IntentCapability, ToolCapability

from jarvis.config.settings import JarvisConfig

__all__ = ["build_manifest"]


# ---------------------------------------------------------------------------
# Static manifest fields — kept in module scope so unit tests can pin them
# without reaching into the factory body.
# ---------------------------------------------------------------------------
_JARVIS_AGENT_ID: str = "jarvis"
_JARVIS_AGENT_NAME: str = "Jarvis"
_JARVIS_TEMPLATE: str = "general_purpose_agent"


def _build_chat_tool() -> ToolCapability:
    """Build the single ``chat`` :class:`ToolCapability`.

    Parameter schema documents the three fields the fleet-gateway pipe
    function publishes inside ``CommandPayload.args``:

    - ``message``: natural-language user message (required, string).
    - ``conversation_history``: optional inbound history (list);
      deliberately ignored by the chat handler since the per-gateway
      Session is the canonical history store.
    - ``adapter``: optional adapter identifier (string) for the
      gateway publishing the command (e.g. ``"openwebui"``).

    Returns:
        A :class:`ToolCapability` ready to be embedded in the manifest.
    """
    return ToolCapability(
        name="chat",
        description=(
            "Conversational entry point for natural-language requests "
            "delivered on the jarvis chat-command NATS subject (see "
            "nats_core Topics.Agents). Returns the supervisor reply "
            "text plus any drained forge notifications."
        ),
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": (
                        "Natural-language user message handed straight to "
                        "the supervisor (required, non-empty)."
                    ),
                },
                "conversation_history": {
                    "type": "array",
                    "description": (
                        "Optional inbound history. Deliberately ignored "
                        "by the chat handler — the per-gateway Session is "
                        "the canonical history store."
                    ),
                    "items": {"type": "object"},
                },
                "adapter": {
                    "type": "string",
                    "description": (
                        "Optional adapter identifier of the gateway "
                        "publishing the command (e.g. 'openwebui')."
                    ),
                },
            },
            "required": ["message"],
        },
        returns=(
            "ResultPayload with response text, tools_called list, and any "
            "drained forge notifications."
        ),
        risk_level="mutating",
        async_mode=False,
    )


def _build_general_intent() -> IntentCapability:
    """Build the single ``general.*`` :class:`IntentCapability`.

    ``signals`` is populated with a non-empty keyword set as a Bug #5
    regression guard — the study-tutor template proved that downstream
    routers (and ``InMemoryManifestRegistry.register``) reject empty
    intent arrays / empty signal lists.

    Returns:
        An :class:`IntentCapability` describing natural-language chat
        routing.
    """
    return IntentCapability(
        pattern="general.*",
        signals=[
            "chat",
            "hello",
            "hi",
            "help",
            "ask",
            "question",
            "talk",
            "general",
        ],
        confidence=0.5,
        description=(
            "Natural-language chat routing for general-purpose "
            "conversational requests handled by the Jarvis supervisor."
        ),
    )


def build_manifest(config: JarvisConfig) -> AgentManifest:
    """Build the Jarvis :class:`AgentManifest` for the NATS chat gateway.

    Pure function — no network, no filesystem.  The returned manifest
    carries:

    - ``agent_id = "jarvis"`` (matches the existing
      ``fleet_registration`` convention so a single fleet entry is
      shared across both factories).
    - Exactly one :class:`ToolCapability` named ``"chat"`` whose
      parameter schema documents ``message`` (required, str),
      ``conversation_history`` (optional, list), and ``adapter``
      (optional, str).
    - Exactly one :class:`IntentCapability` (``general.*``) with a
      non-empty ``signals`` list (Bug #5 guard).
    - ``version`` sourced from ``config.jarvis_agent_version`` — same
      convention used by
      :func:`jarvis.infrastructure.fleet_registration.build_jarvis_manifest`.

    Args:
        config: The validated :class:`JarvisConfig` instance.  Only
            ``config.jarvis_agent_version`` is read.

    Returns:
        A fully validated :class:`AgentManifest` ready for
        :func:`jarvis.infrastructure.fleet_registration.register_on_fleet`.

    Raises:
        pydantic.ValidationError: If ``config.jarvis_agent_version``
            fails the semver pattern enforced by AgentManifest.  The
            pydantic settings layer normally rejects malformed versions
            earlier; this function does not perform additional
            validation.
    """
    return AgentManifest(
        agent_id=_JARVIS_AGENT_ID,
        name=_JARVIS_AGENT_NAME,
        version=config.jarvis_agent_version,
        template=_JARVIS_TEMPLATE,
        intents=[_build_general_intent()],
        tools=[_build_chat_tool()],
        max_concurrent=1,
        status="ready",
        trust_tier="core",
    )
