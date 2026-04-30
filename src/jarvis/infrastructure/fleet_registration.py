"""Fleet registration, heartbeat, and deregistration for the Jarvis agent.

This module owns Jarvis's lifecycle as a NATS fleet citizen: it builds
the :class:`AgentManifest` advertised on the ``agent-registry`` KV
bucket, performs the initial register on startup, runs a background
heartbeat loop that keeps the entry fresh by re-registering on a fixed
cadence, and removes the entry on clean shutdown.  Every operation is
idempotent so retries and double-registration are safe.

Origin
------

Introduced as part of **FEAT-JARVIS-004 — NATS Fleet Registration &
Specialist Dispatch (real transport)**.  The full feature design lives
at ``docs/design/FEAT-JARVIS-004/design.md`` and the public Python
contract for this module is fixed by
``docs/design/FEAT-JARVIS-004/contracts/API-internal.md`` §2.

Public surface
--------------

- :func:`build_jarvis_manifest` — pure manifest factory.
- :func:`register_on_fleet` — idempotent KV register; raises
  :class:`NATSConnectionError` on transport failure.
- :func:`heartbeat_loop` — periodic re-register; survives transient
  failures; cancellation is the normal shutdown path.
- :func:`deregister_from_fleet` — idempotent shutdown; never raises.

Architectural anchors
---------------------

- ``docs/architecture/decisions/ADR-ARCH-004-jarvis-registers-on-fleet-register.md``
  pins the requirement that Jarvis publishes itself on the symmetric
  fleet contract — this module is the implementation of that ADR.
- ``docs/architecture/decisions/ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md``
  fixes NATS as the only transport between fleet members; every I/O
  here flows through that bus.
- ``docs/architecture/decisions/ADR-ARCH-026-no-horizontal-scaling.md``
  underpins the single-instance ``max_concurrent=1`` choice on the
  manifest.

Design decisions
----------------

The soft-fail behaviour of :func:`register_on_fleet` and
:func:`heartbeat_loop` follows
``docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md``:
NATS unavailable at startup must not block Jarvis from starting, and a
transient broker hiccup during the heartbeat loop must not kill the
loop.  :class:`NATSConnectionError` is the typed signal the lifecycle
layer catches to convert a register failure into a startup ``WARN``.

NATS topic discipline
---------------------

Every NATS subject Jarvis emits comes from ``nats_core.Topics`` rather
than literal strings — this module never composes a subject directly.
All KV traffic (register, heartbeat, deregister) is routed through
:class:`nats_core.NATSKVManifestRegistry` against the ``agent-registry``
bucket, so the surrounding code never has to spell ``"fleet.register"``
or ``"fleet.heartbeat..."`` at all.

Client duck-typing
------------------

The ``client`` parameter is duck-typed: it accepts either a raw
``nats.aio.client.Client``, the local ``jarvis.NATSClient`` wrapper
(which exposes the underlying connection on ``.client``), or any object
with a ``jetstream()`` method.  Tests substitute a stub registry by
patching :func:`_resolve_registry` directly, keeping the production
path stable while letting unit tests run without an in-process NATS
broker.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog
from nats_core import (
    AgentManifest,
    IntentCapability,
    NATSKVManifestRegistry,
)

from jarvis.config.settings import JarvisConfig

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Static manifest fields — sourced from API-internal §2 and ADR-ARCH-026.
# ---------------------------------------------------------------------------
JARVIS_AGENT_ID: str = "jarvis"
JARVIS_AGENT_NAME: str = "Jarvis"
JARVIS_TEMPLATE: str = "general_purpose_agent"

# (pattern, description) tuples for the four IntentCapability entries
# Jarvis advertises on the fleet.  Patterns lifted verbatim from
# API-internal §2; descriptions are concise human-readable summaries.
_INTENT_CAPABILITIES: tuple[tuple[str, str], ...] = (
    (
        "conversational.gpa",
        "General-purpose conversational handling on attended adapter surfaces.",
    ),
    (
        "dispatch.by_capability",
        "Dispatch sub-tasks to specialist agents matched by capability.",
    ),
    (
        "meta.dispatch",
        "Meta-routing across multiple specialists for composite requests.",
    ),
    (
        "memory.recall",
        "Recall prior conversational context and routing history.",
    ),
)

# Static metadata published on the manifest.  Both keys MUST stringify —
# AgentManifest enforces ``dict[str, str]``.  ``adapter_set`` enumerates
# the attended adapter ids per ADR-ARCH-016 consumer-surface list.
_METADATA: dict[str, str] = {
    "adapter_set": "telegram,cli,dashboard,reachy",
    "phase": "v1",
}


class NATSConnectionError(Exception):
    """Transport-level NATS failure during fleet registration.

    Raised by :func:`register_on_fleet` when the underlying KV publish
    fails.  The lifecycle bootstrap catches this and converts it to a
    startup WARN per the DDR-021 soft-fail convention — registration
    failure does not block startup.
    """


def build_jarvis_manifest(config: JarvisConfig) -> AgentManifest:
    """Build the Jarvis :class:`AgentManifest` for fleet publication.

    Pure function — no network, no filesystem (apart from a single
    ``os.environ.get("HOSTNAME")`` lookup, which is in-process and
    deterministic).  Output is fully determined by *config* and the
    ``HOSTNAME`` environment variable.

    Args:
        config: The validated :class:`JarvisConfig` instance.  Only
            ``config.jarvis_agent_version`` is read.

    Returns:
        An :class:`AgentManifest` with the four canonical Jarvis intents,
        empty ``tools``, ``max_concurrent=1``, ``status="ready"``,
        ``trust_tier="core"``, and the static
        ``adapter_set`` / ``phase`` metadata.

    Raises:
        pydantic.ValidationError: If ``config.jarvis_agent_version``
            fails the semver pattern enforced by AgentManifest, or any
            other field-level validation rejects the inputs.  The pydantic
            settings layer normally rejects malformed versions earlier;
            this function does not perform additional validation.
    """
    intents = [
        IntentCapability(pattern=pattern, description=description)
        for pattern, description in _INTENT_CAPABILITIES
    ]
    return AgentManifest(
        agent_id=JARVIS_AGENT_ID,
        name=JARVIS_AGENT_NAME,
        version=config.jarvis_agent_version,
        template=JARVIS_TEMPLATE,
        intents=intents,
        tools=[],
        max_concurrent=1,
        status="ready",
        trust_tier="core",
        required_permissions=[],
        # API-internal §2 spec: HOSTNAME first, fall back to None.  An
        # empty-string HOSTNAME (rare in containers) is treated as unset.
        container_id=os.environ.get("HOSTNAME") or None,
        metadata=dict(_METADATA),
    )


async def _resolve_registry(client: Any) -> NATSKVManifestRegistry:
    """Build a :class:`NATSKVManifestRegistry` bound to *client*.

    The local ``jarvis.NATSClient`` wrapper exposes the raw
    ``nats.aio.client.Client`` on a ``.client`` attribute; raw NATS
    clients are passed straight through.  Anything with a
    ``jetstream()`` method satisfies the duck-typed contract that
    :meth:`NATSKVManifestRegistry.create` requires.

    Tests substitute a stub registry by patching this helper directly
    (``monkeypatch.setattr(fleet_registration, "_resolve_registry",
    fake)``) — keeping the production path stable while letting unit
    tests run without an in-process NATS broker.

    Args:
        client: The NATS client (or wrapper) to bind the registry to.

    Returns:
        A registry bound to the ``agent-registry`` KV bucket.
    """
    nc = getattr(client, "client", client)
    return await NATSKVManifestRegistry.create(nc)


async def register_on_fleet(
    client: Any,
    manifest: AgentManifest,
) -> None:
    """Publish *manifest* to the ``agent-registry`` KV bucket.

    Idempotent — :meth:`NATSKVManifestRegistry.register` upserts on
    ``agent_id`` so a second call cleanly replaces the prior entry with
    no exception.

    Args:
        client: A connected NATS client (or local wrapper).
        manifest: The Jarvis manifest produced by
            :func:`build_jarvis_manifest`.

    Raises:
        NATSConnectionError: If the underlying publish fails for any
            reason (broker unreachable, JetStream missing, KV bucket
            unwritable, etc.).  The originating exception is chained as
            ``__cause__``.
    """
    try:
        registry = await _resolve_registry(client)
        await registry.register(manifest)
    except Exception as exc:
        raise NATSConnectionError(
            f"fleet register failed for agent_id={manifest.agent_id!r}: {exc}"
        ) from exc

    logger.info(
        "fleet_register_published",
        agent_id=manifest.agent_id,
        version=manifest.version,
    )


async def heartbeat_loop(
    client: Any,
    manifest: AgentManifest,
    config: JarvisConfig,
) -> None:
    """Periodically re-register *manifest* until cancelled.

    The KV bucket's "register" semantics are upsert-with-refreshed-mtime,
    so re-publishing the same manifest serves as a heartbeat: downstream
    fleet observers reading ``agent-registry`` see Jarvis's entry stay
    fresh.

    Each iteration:

    1. Attempt :meth:`NATSKVManifestRegistry.register`.
    2. On success, log ``DEBUG fleet_heartbeat_published``.
    3. On failure, log ``WARN fleet_heartbeat_failed`` (without
       ``exc_info``) and continue — a transient broker hiccup must not
       kill the loop.
    4. Sleep ``config.heartbeat_interval_seconds``.

    Cancellation is the normal shutdown path: the lifecycle
    ``shutdown(state)`` calls ``state.fleet_heartbeat_task.cancel()`` and
    awaits the task.  This function catches
    :class:`asyncio.CancelledError`, logs ``INFO
    fleet_heartbeat_cancelled``, and re-raises so the asyncio task
    machinery records the cancellation correctly.

    Args:
        client: A connected NATS client (or local wrapper).
        manifest: The manifest to refresh on every tick.
        config: Source of ``heartbeat_interval_seconds``.

    Raises:
        asyncio.CancelledError: Re-raised after a clean INFO log on
            shutdown.  Re-raising preserves Python's asyncio cancellation
            semantics (the task is recorded as cancelled rather than
            completing normally) without emitting a traceback — the log
            line uses no ``exc_info``.
    """
    interval = config.heartbeat_interval_seconds
    try:
        while True:
            try:
                registry = await _resolve_registry(client)
                await registry.register(manifest)
                logger.debug(
                    "fleet_heartbeat_published",
                    agent_id=manifest.agent_id,
                    interval_seconds=interval,
                )
            except asyncio.CancelledError:
                # Cancellation while awaiting the inner I/O — propagate
                # to the outer handler.  Never swallow CancelledError.
                raise
            except Exception as exc:
                logger.warning(
                    "fleet_heartbeat_failed",
                    agent_id=manifest.agent_id,
                    reason=str(exc),
                )
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info(
            "fleet_heartbeat_cancelled",
            agent_id=manifest.agent_id,
        )
        raise


async def deregister_from_fleet(
    client: Any,
    agent_id: str = JARVIS_AGENT_ID,
) -> None:
    """Remove *agent_id* from the ``agent-registry`` KV bucket.

    Idempotent and silent on missing entries —
    :meth:`NATSKVManifestRegistry.deregister` already swallows
    "key not found" failures.  Any unexpected transport failure is
    logged as ``WARN fleet_deregister_failed`` rather than raised, so a
    flaky broker cannot block clean shutdown.

    Args:
        client: A connected NATS client (or local wrapper).
        agent_id: The agent identifier to remove.  Defaults to
            ``"jarvis"``.
    """
    try:
        registry = await _resolve_registry(client)
        await registry.deregister(agent_id)
    except Exception as exc:
        logger.warning(
            "fleet_deregister_failed",
            agent_id=agent_id,
            reason=str(exc),
        )
        return

    logger.info("fleet_deregister_published", agent_id=agent_id)


__all__ = [
    "JARVIS_AGENT_ID",
    "JARVIS_AGENT_NAME",
    "JARVIS_TEMPLATE",
    "NATSConnectionError",
    "build_jarvis_manifest",
    "deregister_from_fleet",
    "heartbeat_loop",
    "register_on_fleet",
]
