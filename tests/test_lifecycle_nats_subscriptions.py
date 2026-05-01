"""Integration tests reconciling jarvis NATS subscriptions with canonical provisioning.

TASK-FRR-001 / FEAT-JARVIS-INTERNAL-001-FRR.

The 2026-05-01 first real run on GB10 surfaced three startup-time NATS
errors that all trace to a config mismatch between what jarvis (via
``nats_core``) asserts against the broker and what
``nats-infrastructure/streams/stream-definitions.json`` and
``nats-infrastructure/kv/kv-definitions.json`` provision:

1. ``jarvis_fleet_register_failed`` — ``code=10058 stream name already in
   use with a different configuration``. The fleet-register hop binds the
   ``agent-registry`` KV bucket via
   :meth:`nats_core.NATSKVManifestRegistry.create`, which delegates to
   nats-py's ``js.create_key_value(bucket=...)``. With no further config
   that asserts nats-py defaults (history=1, unlimited size); the canonical
   bucket is provisioned with ``history=5`` and ``max_value_size=256KB`` so
   the assertion mismatches.
2. ``jarvis_live_capabilities_registry_failed`` — same root cause as (1),
   surfaced one log line later because
   :meth:`LiveCapabilitiesRegistry.create` routes through the same helper.
3. ``jarvis_forge_subscriber_start_failed`` — ``code=10101 consumer must
   be deliver all on workqueue stream``. ``ForgeNotificationsSubscriber.start``
   calls ``js.subscribe(..., deliver_policy=DeliverPolicy.NEW)`` against the
   canonical PIPELINE stream, which is provisioned with
   ``retention=workqueue``; workqueue retention only accepts
   ``deliver_policy=all``.

These tests provision the canonical streams + KV bucket on the in-process
``nats_test_server`` broker BEFORE driving the relevant jarvis-side
lifecycle code, so the assertion is "jarvis interoperates with the
canonical infra", not "jarvis happens to work on a fresh broker where
defaults haven't been contradicted yet".

The TDD red phase commits these tests against the current ``main``; all
three fail. The TDD green phase commits the fixes (lookup-only KV bind in
nats_core, ``deliver_policy=all`` in ``forge_notifications``) and the
tests turn green.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.capabilities_registry import LiveCapabilitiesRegistry
from jarvis.infrastructure.fleet_registration import (
    build_jarvis_manifest,
    register_on_fleet,
)
from jarvis.infrastructure.forge_notifications import ForgeNotificationsSubscriber
from jarvis.shared.exceptions import NATSConnectionError

LIFECYCLE_LOGGER = "jarvis.infrastructure.lifecycle"
FORGE_NOTIFICATIONS_LOGGER = "jarvis.infrastructure.forge_notifications"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _stub_yaml_path() -> Path:
    return _project_root() / "src" / "jarvis" / "config" / "stub_capabilities.yaml"


def _build_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` valid for manifest construction."""
    return JarvisConfig(
        openai_base_url="http://fake-endpoint/v1",
        stub_capabilities_path=_stub_yaml_path(),
    )


async def _assert_canonical_provisioning_present(client: Any) -> None:
    """Sanity-check the canonical streams / KV are on the broker.

    The conftest ``nats_test_server`` fixture provisions the canonical
    PIPELINE workqueue stream and ``agent-registry`` KV bucket on every
    setup (mirroring ``nats-infrastructure/kv/provision-kv.sh`` and
    ``streams/provision-streams.sh``). This helper exists so the tests
    document that they DEPEND on canonical provisioning rather than
    silently relying on a fixture detail — the assertion makes the
    contract direction loud at the test body.
    """
    js = client.client.jetstream()
    # Both lookups raise on absence — the test fails loud here rather
    # than later inside the production code under test.
    await js.key_value(bucket="agent-registry")
    await js.stream_info(name="PIPELINE")


# ---------------------------------------------------------------------------
# AC-1 — fleet register against canonical KV bucket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fleet_register_against_canonical_kv_bucket_succeeds(
    nats_test_server: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``register_on_fleet`` must not raise against canonical agent-registry.

    Red phase: ``nats_core.NATSKVManifestRegistry.create`` calls
    ``js.create_key_value(bucket="agent-registry")`` (no config) which asserts
    nats-py defaults — these mismatch the canonical history=5 / 256KB shape
    and surface as ``BadRequestError code=10058``. ``register_on_fleet``
    wraps that as :class:`NATSConnectionError`.

    Green phase: nats_core uses ``js.key_value(bucket=...)`` (lookup-only)
    so the bucket's canonical config is honoured untouched.
    """
    await _assert_canonical_provisioning_present(nats_test_server)

    config = _build_config()
    manifest = build_jarvis_manifest(config)

    caplog.set_level(logging.WARNING, logger=LIFECYCLE_LOGGER)

    # Must not raise. The lifecycle wrapper would convert this into a
    # ``jarvis_fleet_register_failed`` WARN; the absence of that warning
    # is asserted via caplog below as a belt-and-braces check.
    await register_on_fleet(nats_test_server, manifest)

    fleet_failed = [
        r
        for r in caplog.records
        if r.message and "jarvis_fleet_register_failed" in r.message
    ]
    assert fleet_failed == [], (
        "fleet register against canonical agent-registry KV bucket emitted "
        f"a *_failed warning: {[r.getMessage() for r in fleet_failed]}"
    )


# ---------------------------------------------------------------------------
# AC-2 — LiveCapabilitiesRegistry KV bind against canonical bucket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capabilities_registry_kv_bind_against_canonical_bucket_succeeds(
    nats_test_server: Any,
) -> None:
    """``LiveCapabilitiesRegistry.create`` must not raise against canonical KV.

    Red phase: same root cause as AC-1 — the registry's ``_resolve_registry``
    helper also routes through ``NATSKVManifestRegistry.create`` →
    ``js.create_key_value(bucket=...)`` with no config, hits ``code=10058``,
    surfaces as :class:`NATSConnectionError`.

    Green phase: lookup-only bind in nats_core honours the canonical config;
    the registry warms up cleanly and ``capabilities_mode`` reports ``"live"``
    rather than the DDR-021 stub fallback.
    """
    await _assert_canonical_provisioning_present(nats_test_server)

    # The registry must successfully bind + warm up. Any failure to bind
    # raises NATSConnectionError, which is what the lifecycle catches and
    # converts into the ``jarvis_live_capabilities_registry_failed`` WARN.
    registry = await LiveCapabilitiesRegistry.create(nats_test_server)
    try:
        snapshot = registry.snapshot()
        # An empty registry is fine; the bind succeeded and a snapshot is
        # callable. The point is that no NATSConnectionError fired.
        assert isinstance(snapshot, list)
    finally:
        await registry.close()


# ---------------------------------------------------------------------------
# AC-3 — forge subscriber attach against canonical PIPELINE workqueue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forge_subscriber_attach_against_canonical_workqueue_succeeds(
    nats_test_server: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``ForgeNotificationsSubscriber.start`` must not raise against workqueue.

    Red phase: the subscriber attaches with ``DeliverPolicy.NEW`` (DDR-027
    as written) but the canonical PIPELINE stream has ``retention=workqueue``;
    nats-py rejects with ``BadRequestError code=10101 consumer must be
    deliver all on workqueue stream``. The lifecycle catches this and emits
    ``jarvis_forge_subscriber_start_failed``.

    Green phase: the subscriber uses ``DeliverPolicy.ALL`` so the consumer
    create succeeds. The workqueue + auto-ack + in-memory correlation map
    combination preserves the no-replay-on-restart UX the original DDR-027
    rationale was after — see DDR-027 (revised).
    """
    await _assert_canonical_provisioning_present(nats_test_server)

    # RoutingHistoryWriter is not load-bearing for the consumer create
    # path — pass a None and rely on the start() code never reaching the
    # writer in this test. ``ForgeNotificationsSubscriber`` accepts any
    # object satisfying its narrow attribute use; the start path only
    # touches the JetStream context.
    class _NoOpRoutingHistoryWriter:
        async def append_build_queue_event(
            self, *args: Any, **kwargs: Any
        ) -> None:
            return None

    subscriber = ForgeNotificationsSubscriber(
        nats_client=nats_test_server,
        routing_history_writer=_NoOpRoutingHistoryWriter(),  # type: ignore[arg-type]
        queue_cap=10,
        correlation_cap=10,
        stop_timeout=2.0,
    )

    caplog.set_level(logging.WARNING, logger=FORGE_NOTIFICATIONS_LOGGER)

    try:
        # Must not raise. nats-py raises ``BadRequestError`` directly out
        # of ``js.subscribe`` — the subscriber does not wrap it, so any
        # leak surfaces here as the test failure.
        await subscriber.start()
    finally:
        await subscriber.stop()


# ---------------------------------------------------------------------------
# AC-4 — combined: all three subscriptions against full canonical provisioning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_canonical_provisioning_emits_no_failed_warnings(
    nats_test_server: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """End-to-end: canonical streams + KV → all three jarvis subscribers clean.

    The original 2026-05-01 GB10 first-real-run runbook recorded all three
    failures in a single ``jarvis chat`` boot. This test reproduces that
    boot order against the in-process broker pre-provisioned with the
    canonical streams/KV and asserts the structured log emits zero of the
    three ``*_failed`` warnings.
    """
    # Canonical PIPELINE workqueue + agent-registry KV are provisioned by
    # the conftest fixture; assert they're present so a fixture regression
    # surfaces here loudly rather than as a downstream production error.
    await _assert_canonical_provisioning_present(nats_test_server)

    config = _build_config()
    manifest = build_jarvis_manifest(config)

    caplog.set_level(logging.WARNING)

    # 1. Fleet register.
    await register_on_fleet(nats_test_server, manifest)

    # 2. LiveCapabilitiesRegistry KV bind.
    registry = await LiveCapabilitiesRegistry.create(nats_test_server)

    # 3. Forge subscriber attach.
    class _NoOpRoutingHistoryWriter:
        async def append_build_queue_event(
            self, *args: Any, **kwargs: Any
        ) -> None:
            return None

    subscriber = ForgeNotificationsSubscriber(
        nats_client=nats_test_server,
        routing_history_writer=_NoOpRoutingHistoryWriter(),  # type: ignore[arg-type]
        queue_cap=10,
        correlation_cap=10,
        stop_timeout=2.0,
    )
    try:
        await subscriber.start()
    finally:
        await subscriber.stop()
        await registry.close()

    # Assert none of the three ``*_failed`` event names appear in the
    # captured log records. We grep on the structured event name as it
    # appears in the rendered message because structlog's stdlib bridge
    # collapses the event into the message body.
    bad_event_names = (
        "jarvis_fleet_register_failed",
        "jarvis_live_capabilities_registry_failed",
        "jarvis_forge_subscriber_start_failed",
    )
    offenders = [
        (r.name, r.getMessage())
        for r in caplog.records
        if any(event in r.getMessage() for event in bad_event_names)
    ]
    assert offenders == [], (
        "Canonical provisioning emitted *_failed warnings on jarvis "
        f"startup: {offenders}"
    )


# ---------------------------------------------------------------------------
# Belt-and-braces — make the NATSConnectionError → wrapping path explicit so
# a future refactor that drops the wrapper still trips a test.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fleet_register_does_not_raise_natsconnectionerror_on_canonical(
    nats_test_server: Any,
) -> None:
    """Documents that the canonical-bucket path no longer raises wrapping.

    Red phase: ``register_on_fleet`` wraps the underlying ``BadRequestError``
    as :class:`NATSConnectionError`. This test asserts the wrapping branch
    is no longer hit — i.e. the underlying call returns cleanly.
    """
    await _assert_canonical_provisioning_present(nats_test_server)

    config = _build_config()
    manifest = build_jarvis_manifest(config)

    try:
        await register_on_fleet(nats_test_server, manifest)
    except NATSConnectionError as exc:  # pragma: no cover - red phase only
        pytest.fail(
            "register_on_fleet wrapped a config mismatch as "
            f"NATSConnectionError against canonical agent-registry: {exc}"
        )


# ---------------------------------------------------------------------------
# AC-6 — capabilities_mode reports "live" once the KV bind succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_app_state_reports_capabilities_mode_live_against_canonical(
    nats_test_server: Any,
    fake_llm: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``capabilities_mode == "live"`` once the canonical KV bind succeeds.

    The TASK-FRR-001 acceptance criteria call out an explicit assertion of
    ``capabilities_mode == "live"`` (not the DDR-021 stub fallback) once
    the KV bind no longer fails against canonical provisioning. Drives
    ``build_app_state`` end-to-end against the canonical broker fixture
    with the autouse ``_connect_nats`` stub overridden so the production
    capabilities-bind branch (``LiveCapabilitiesRegistry.create``) actually
    runs.

    Capture path: ``configure()`` clears the stdlib root logger handlers
    and installs its own JSON-rendering ``StreamHandler(sys.stderr)``,
    which means pytest's ``caplog`` (which attaches at the root) is
    cleared mid-test. We capture stderr via ``capsys`` instead and assert
    the rendered JSON event by substring, which is robust to renderer
    field-ordering tweaks.
    """
    from unittest.mock import AsyncMock, patch

    from jarvis.infrastructure.lifecycle import build_app_state, shutdown

    config = _build_config()

    with (
        patch(
            "jarvis.infrastructure.lifecycle._connect_nats",
            new=AsyncMock(return_value=nats_test_server),
        ),
        patch(
            "jarvis.infrastructure.lifecycle._connect_graphiti",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ),
    ):
        state = await build_app_state(config)
        try:
            stderr = capsys.readouterr().err
            # structlog's JSON renderer emits the event as a flat
            # ``"capabilities_mode": "live"`` field on the
            # ``jarvis_startup_complete`` record. Substring-assert against
            # both halves of the expected log line so a mode flip from
            # ``live`` → ``stub`` (the DDR-021 fallback) trips this test
            # immediately rather than at production-runtime triage.
            assert "jarvis_startup_complete" in stderr, (
                "lifecycle did not emit jarvis_startup_complete on stderr — "
                "capabilities_mode field cannot be asserted"
            )
            assert '"capabilities_mode": "live"' in stderr, (
                "Expected capabilities_mode=live with canonical KV bound; "
                f"stderr did not contain it. Last 2KB:\n{stderr[-2048:]}"
            )
        finally:
            await shutdown(state)
