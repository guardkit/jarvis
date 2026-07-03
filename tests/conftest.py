"""Root conftest — shared fixtures for the Jarvis test suite.

This is the standard approach for src-layout projects: pytest discovers this
conftest.py at startup and prepends ``<project-root>/src`` to ``sys.path`` so
that ``import jarvis`` resolves to the local source tree regardless of whether
the package has been installed in the active environment.

Fixtures provided:

- :func:`_isolate_dotenv` (autouse) — chdirs to a tmp dir so ``JarvisConfig``'s
  ``env_file=".env"`` cannot pick up the operator's real ``.env`` during test
  runs
- :func:`fake_llm` — deterministic ``FakeListChatModel`` (no network)
- :func:`test_config` — ``JarvisConfig`` with sensible defaults and a fake endpoint
- :func:`in_memory_store` — fresh ``InMemoryStore``, cleared after each test
- :func:`app_state` — placeholder for composed application state (future)
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Inject src/ into sys.path so tests can ``from jarvis import ...`` even
# when running bare ``pytest`` without an editable install.
# ---------------------------------------------------------------------------
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


# ---------------------------------------------------------------------------
# Pre-seed a stub OPENAI_API_KEY at conftest module load so the OpenAI SDK
# does not crash during test collection.
#
# DDR-012 mandates that ``jarvis_reasoner`` compile its LangGraph at module
# import time, which calls ``init_chat_model("openai:jarvis-reasoner")``,
# which constructs ``ChatOpenAI(...)``, which raises ``openai.OpenAIError``
# if ``OPENAI_API_KEY`` is not in the process environment. Test modules
# that import anything from ``jarvis.agents.subagents`` (directly or via
# the package ``__init__``) trigger that import chain during pytest's
# collection phase — *before* any fixture, autouse or otherwise, has had
# a chance to run.
#
# Setting it here (at conftest module load, which pytest evaluates before
# collecting any test module) is the only safe place to pre-seed the stub.
# The value is obviously fake so it cannot be confused with a real key, and
# no test in this suite makes a real network call against the production
# OpenAI endpoint (fakes are routed via ``FakeListChatModel`` or the
# ``http://fake-endpoint/v1`` base URL). Production environments inject
# real keys via ``.env``; ``langgraph dev`` continues to fail loudly when
# the operator has not configured one (DDR-012's "fail fast" promise — the
# fix is scoped to the test environment only).
#
# Use ``setdefault`` so a real key in the developer's shell environment
# (e.g. someone debugging a single test against the live SDK) is not
# clobbered. The autouse ``_isolate_dotenv`` fixture below then re-asserts
# the stub per-test via ``monkeypatch.setenv`` so individual tests start
# from a known stub value, while still honouring per-test ``patch.dict``
# overrides (which wrap the test body and therefore win for that test).
# ---------------------------------------------------------------------------
_OPENAI_API_KEY_TEST_STUB = "stub-for-tests-no-real-calls-do-not-use-in-prod"
os.environ.setdefault("OPENAI_API_KEY", _OPENAI_API_KEY_TEST_STUB)


# ---------------------------------------------------------------------------
# Autouse: isolate every test from the operator's real ``.env`` file.
#
# ``JarvisConfig`` is a ``pydantic_settings.BaseSettings`` subclass with
# ``env_file=".env"``, resolved relative to the current working directory.
# When pytest runs from the project root and the operator has populated
# ``.env`` with their live provider credentials, every ``JarvisConfig()``
# call silently absorbs those values — breaking tests that assert
# missing-config failure paths (e.g. ``TestAC005ValidateProviderKeys``).
#
# ``monkeypatch.chdir(tmp_path)`` resolves pydantic's relative ``.env``
# lookup to a nonexistent file for the duration of each test, restoring the
# original cwd on teardown. Tests that need a specific file layout (subprocess
# tests in ``test_build_system.py`` / ``test_developer_surface.py``) either
# pass ``cwd=str(ROOT)`` explicitly or use absolute path constants, so chdir
# does not disturb them.
#
# The fixture also re-asserts the stub ``OPENAI_API_KEY`` per-test via
# ``monkeypatch.setenv`` so individual tests start from a known stub value
# even after a previous test cleared the env. See the module-level
# ``setdefault`` block above for the rationale; per-test ``patch.dict``
# overrides still win because they wrap the test body and the inner
# clear-and-replace runs after fixture setup.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", _OPENAI_API_KEY_TEST_STUB)


# ---------------------------------------------------------------------------
# Autouse: snapshot + restore the dispatch module's DDR-014 Layer-2 hooks
# around every test (TASK-J003-FIX-001).
#
# ``lifecycle.build_app_state`` now assigns ``dispatch._current_session_hook``
# and ``dispatch._async_subagent_frame_hook`` to close the FEAT-JARVIS-003
# review's Finding F1 ("Layer 2 dormant in production"). Tests that exercise
# ``build_app_state`` (e.g. ``tests/test_lifecycle_startup_phase3.py``)
# therefore mutate module-level state on the import-shared
# ``jarvis.tools.dispatch`` module — without a per-test save/restore the
# hooks bleed into downstream test modules whose Layer-1 assertions assume
# the dormant default (e.g. ``tests/test_escalate_to_frontier.py``).
#
# Per-file fixtures (``reset_layer2_hooks``) cover the modules that wire
# hooks intentionally; this autouse fixture covers every other test by
# default so a future ``build_app_state``-using test does not silently
# poison sibling modules. Cost is two attribute reads + two writes per
# test, which is negligible.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _restore_dispatch_layer2_hooks() -> Generator[None, None, None]:
    from jarvis.tools import dispatch as _dispatch

    original_session_hook = _dispatch._current_session_hook
    original_frame_hook = _dispatch._async_subagent_frame_hook
    original_nats = _dispatch._nats_client
    original_writer = _dispatch._routing_history_writer
    original_sem = _dispatch._dispatch_semaphore
    yield
    _dispatch._current_session_hook = original_session_hook
    _dispatch._async_subagent_frame_hook = original_frame_hook
    _dispatch._nats_client = original_nats
    _dispatch._routing_history_writer = original_writer
    _dispatch._dispatch_semaphore = original_sem


# ---------------------------------------------------------------------------
# Autouse: short-circuit ``NATSClient.connect`` to ``None`` by default.
#
# TASK-J004-013 wired ``build_app_state`` to call ``NATSClient.connect`` on
# every startup. nats-py's default ``connect()`` blocks for tens of seconds
# (or hangs entirely) when no broker is reachable on ``nats://localhost:4222``
# — every existing lifecycle test that does not explicitly patch the seam
# would stall under the new wiring.
#
# Returning ``None`` here mirrors the DDR-021 soft-fail: lifecycle falls back
# to ``StubCapabilitiesRegistry`` and ``fleet_heartbeat_task = None`` — the
# behaviour the pre-J004-013 tests implicitly assumed (NATS untouched). Tests
# that need to exercise the NATS-up path opt in by wrapping their body in an
# inner ``patch("jarvis.infrastructure.lifecycle.NATSClient.connect", ...)``
# block — the inner ``patch`` shadows this autouse stub for the duration.
#
# The fleet-memory seam gets the same treatment so unit tests never attempt
# a live NATS memory publish (the seam is pure-stub by default).
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stub_nats_and_memory_connect_seams() -> Generator[None, None, None]:
    from unittest.mock import AsyncMock as _AsyncMock
    from unittest.mock import patch as _patch

    with (
        _patch(
            "jarvis.infrastructure.lifecycle._connect_nats",
            new=_AsyncMock(return_value=None),
        ),
        _patch(
            "jarvis.infrastructure.lifecycle._connect_memory",
            new=_AsyncMock(return_value=None),
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# fake_llm — deterministic chat model for unit tests
# ---------------------------------------------------------------------------
@pytest.fixture()
def fake_llm() -> Any:
    """Return a ``FakeListChatModel`` with canned responses.

    The model cycles through a predefined list of responses without making
    any network calls.  Useful for testing agent logic deterministically.

    Returns:
        A ``FakeListChatModel`` instance that returns ``"Canned response 1"``
        on the first invocation and ``"Canned response 2"`` on subsequent ones.
    """
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    return FakeListChatModel(
        responses=[
            "Canned response 1",
            "Canned response 2",
            "Canned response 3",
        ],
    )


# ---------------------------------------------------------------------------
# test_config — JarvisConfig with safe defaults (no real provider keys)
# ---------------------------------------------------------------------------
@pytest.fixture()
def test_config() -> Any:
    """Return a ``JarvisConfig`` with sensible test defaults.

    The default ``llama_swap_base_url`` already satisfies the ``openai:``
    provider routing path (ADR-ARCH-001 — local-first inference). No
    cloud credentials are required for ``validate_provider_keys()`` to
    pass on the default ``openai:jarvis-reasoner`` supervisor model.

    Returns:
        A ``JarvisConfig`` instance that validates cleanly.
    """
    from jarvis.config.settings import JarvisConfig

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            llama_swap_base_url="http://fake-endpoint",
        )
    # Validate provider keys to ensure no ConfigurationError
    cfg.validate_provider_keys()
    return cfg


# ---------------------------------------------------------------------------
# in_memory_store — fresh LangGraph InMemoryStore per test
# ---------------------------------------------------------------------------
@pytest.fixture()
def in_memory_store() -> Generator[Any, None, None]:
    """Yield a fresh ``InMemoryStore`` and clear it after the test.

    Provides test isolation: each test gets its own empty store that is
    cleaned up on teardown.
    """
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    yield store
    # InMemoryStore has no explicit close; the reference is simply dropped.


# ---------------------------------------------------------------------------
# app_state — placeholder for composed application state
# ---------------------------------------------------------------------------
@pytest.fixture()
def app_state() -> dict[str, Any]:
    """Return a placeholder ``AppState`` dict.

    This fixture will be expanded when the full application state model
    is implemented.  For now it returns a minimal dictionary that downstream
    tests can extend.
    """
    return {
        "config": None,
        "store": None,
    }


# ---------------------------------------------------------------------------
# Canonical NATS provisioning helper — mirrors what
# ``nats-infrastructure/streams/provision-streams.sh`` and
# ``nats-infrastructure/kv/provision-kv.sh`` do at infra deploy time.
#
# The in-process broker the ``nats_test_server`` fixture spins up starts
# completely bare. Before TASK-FRR-001 jarvis (via nats_core) used
# ``js.create_key_value(bucket=...)`` which silently auto-created the
# ``agent-registry`` bucket on first use — so a bare broker was fine.
# Switching to lookup-only (so jarvis interoperates with the canonical
# infra without a config-mismatch BadRequestError) made the contract
# direction explicit: the bucket / streams MUST be pre-provisioned. The
# fixture mirrors that production contract by calling this helper once
# at setup so existing tests (test_fleet_registration_integration,
# test_capabilities_real, etc.) keep their original semantics.
#
# Provisioning is idempotent — tests that re-assert the canonical config
# from inside the test body (test_lifecycle_nats_subscriptions) succeed
# because nats-py treats matching-config (re)creates as no-ops.
# ---------------------------------------------------------------------------
async def _provision_canonical_streams_and_buckets(client: Any) -> None:
    """Provision the canonical agent-registry KV + PIPELINE stream.

    Mirrors:
    * ``nats-infrastructure/kv/kv-definitions.json`` (agent-registry:
      ``history=5``, ``max_value_size=256KB``, ``storage=file``,
      ``replicas=1``).
    * ``nats-infrastructure/streams/stream-definitions.json`` (PIPELINE:
      ``subjects=["pipeline.>"]``, ``retention=workqueue``, ``storage=file``).

    Args:
        client: A connected :class:`NATSClient` whose ``.client``
            attribute exposes the underlying nats-py async connection.
    """
    from nats.js.api import (
        KeyValueConfig,
        RetentionPolicy,
        StorageType,
        StreamConfig,
    )

    js = client.client.jetstream()
    await js.create_key_value(
        config=KeyValueConfig(
            bucket="agent-registry",
            history=5,
            max_value_size=256 * 1024,
            storage=StorageType.FILE,
            replicas=1,
        )
    )
    await js.add_stream(
        config=StreamConfig(
            name="PIPELINE",
            subjects=["pipeline.>"],
            retention=RetentionPolicy.WORK_QUEUE,
            storage=StorageType.FILE,
            num_replicas=1,
        )
    )


# ---------------------------------------------------------------------------
# nats_test_server — in-process JetStream-enabled NATS broker for integration
# tests (TASK-J004-014, FEAT-JARVIS-004 Phase 3 floor capability).
#
# Each test gets a fresh ``nats-server -p <free> -js`` subprocess bound to
# a tmp_path JetStream store directory and a lifecycle-managed
# :class:`NATSClient` wired against it. The fixture skips with a clear
# operator message when the ``nats-server`` CLI is not on PATH so the suite
# remains green on developer machines without the binary installed —
# CI/operators install ``nats-server`` (e.g. ``brew install nats-server``)
# to exercise the integration path.
#
# Function-scoped (the default) so each test starts from a clean KV bucket
# state — survives ``pytest-randomly --randomly-seed=0`` because no fixture
# state outlives a single test.
# ---------------------------------------------------------------------------
@pytest.fixture()
def nats_server_binary() -> str:
    """Resolve the ``nats-server`` CLI or skip the test cleanly.

    Returns:
        Absolute path to the ``nats-server`` executable.
    """
    import shutil as _shutil

    binary = _shutil.which("nats-server")
    if binary is None:
        pytest.skip("install nats-server CLI for integration tests")
    return binary


@pytest.fixture()
def _free_tcp_port() -> int:
    """Return a TCP port that is currently free on localhost.

    There is an inherent TOCTOU race between closing the discovery socket
    and the subprocess binding to the same port; the integration tests
    accept that risk because pytest-randomly seeds make collisions rare and
    a flake here surfaces as a connect-timeout, not a silent corruption.
    """
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest_asyncio.fixture()
async def nats_test_server(
    nats_server_binary: str,
    _free_tcp_port: int,
    tmp_path: Path,
) -> Any:
    """Yield a connected :class:`NATSClient` against an in-process broker.

    Steps:
      1. Spawn ``nats-server -p <port> -js -sd <tmp_path>``.
      2. Poll-connect until the server accepts traffic (5s budget).
      3. Build a :class:`NATSClient` via ``NATSClient.connect`` so the
         production wrapper exercises the same connect path as the
         supervisor lifecycle.
      4. Yield the wrapper to the test.
      5. On teardown drain the wrapper, terminate the subprocess, and wait
         (SIGKILL after 5s if the broker fails to exit cleanly).

    The ``-sd`` flag points JetStream's storage at ``tmp_path`` so each
    test gets an isolated KV state without polluting the working directory.
    """
    import asyncio as _asyncio
    import subprocess as _subprocess
    import time as _time

    import nats as _nats

    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.nats_client import NATSClient

    # Keep stdio attached to /dev/null so a long-running pytest does not
    # eventually fill the kernel pipe buffer and block the broker.
    process = _subprocess.Popen(
        [
            nats_server_binary,
            "-p",
            str(_free_tcp_port),
            "-a",
            "127.0.0.1",
            "-js",
            "-sd",
            str(tmp_path / "jetstream"),
        ],
        stdout=_subprocess.DEVNULL,
        stderr=_subprocess.DEVNULL,
    )

    nats_url = f"nats://127.0.0.1:{_free_tcp_port}"
    client: NATSClient | None = None
    try:
        # Poll-connect until the server is ready (or budget exhausted).
        deadline = _time.monotonic() + 5.0
        last_error: Exception | None = None
        while _time.monotonic() < deadline:
            # Bail early if the broker died before accepting traffic.
            if process.poll() is not None:
                raise RuntimeError(
                    f"nats-server exited prematurely with code {process.returncode}"
                )
            try:
                probe = await _nats.connect(nats_url, connect_timeout=1)
                await probe.close()
                break
            except Exception as exc:  # broker not ready yet — keep polling
                last_error = exc
                await _asyncio.sleep(0.1)
        else:
            raise RuntimeError(
                f"nats-server at {nats_url} did not accept connections "
                f"within 5s: {type(last_error).__name__}: {last_error}"
            )

        config = JarvisConfig(
            llama_swap_base_url="http://fake-endpoint",
            nats_url=nats_url,
        )
        client = await NATSClient.connect(config)
        if client is None:
            raise RuntimeError(
                f"NATSClient.connect returned None for {nats_url} — "
                "in-process broker handshake failed"
            )

        # Pre-provision the canonical streams / KV that ``nats-infrastructure``
        # provisions in production (TASK-FRR-001). nats_core's
        # ``NATSKVManifestRegistry.create`` is now lookup-only against the
        # ``agent-registry`` bucket and the canonical PIPELINE stream is
        # ``retention=workqueue``; a bare in-process broker has neither, so
        # tests that exercise those paths would surface ``BucketNotFoundError``
        # / ``StreamNotFoundError`` instead of the production failure modes.
        # Provisioning here is idempotent — tests that re-assert the same
        # config (e.g. ``test_lifecycle_nats_subscriptions``) succeed; tests
        # that don't touch these surfaces (e.g. ``test_routing_e2e``) pay only
        # the negligible cost of the two creates.
        await _provision_canonical_streams_and_buckets(client)

        yield client
    finally:
        # Best-effort drain: a flaky broker should not mask the test result.
        if client is not None:
            try:
                await client.drain(timeout=2.0)
            except Exception:
                # Drain failure during teardown is not actionable; the
                # subprocess termination below cleans up regardless.
                pass

        process.terminate()
        try:
            process.wait(timeout=5.0)
        except _subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
