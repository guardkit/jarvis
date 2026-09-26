"""The name this process gives the bus for its own connection (E3-j1).

WHY THIS MATTERS, in one paragraph. The containerised estate gives the bus
gateway and the Slack front door the SAME bus account on purpose, so "the
bus holds a connection from the jarvis account" is true while the gateway is
stopped and the front door is up — and a health check built on the account
alone would call a dead gateway healthy. The bus records a name for every
connection if the client sends one and reports it on its monitoring route,
so a name is how one process of an account is told from another. These tests
pin the keyword at the one call site that exists, and pin the default: a
process with no name configured sends no name at all, exactly as before.

Rollout step 1, build item E3-j1, 26 September 2026.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import nats_client as nats_client_module
from jarvis.infrastructure.nats_client import NATSClient


def _make_config(**overrides: Any) -> JarvisConfig:
    base: dict[str, Any] = {
        "nats_url": "nats://localhost:4222",
        "nats_credentials_path": None,
        "startup_connect_timeout_seconds": 1,
    }
    base.update(overrides)
    return JarvisConfig(_env_file=None, **base)  # type: ignore[arg-type]


async def _connect_capturing_kwargs(config: JarvisConfig) -> dict[str, Any]:
    """Run ``NATSClient.connect`` against a fake and return its keywords."""
    captured: dict[str, Any] = {}

    async def fake_connect(**kwargs: Any) -> Any:
        captured.update(kwargs)
        fake = mock.MagicMock()
        fake.is_connected = True
        return fake

    with mock.patch.object(nats_client_module, "_nats_connect", fake_connect):
        await NATSClient.connect(config)
    return captured


# ---------------------------------------------------------------------------
# The default: no name, which is what every jarvis process did until today.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_setting_sends_no_name_at_all() -> None:
    captured = await _connect_capturing_kwargs(_make_config())
    assert "name" not in captured


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
@pytest.mark.asyncio
async def test_a_blank_setting_is_treated_as_unset(blank: str) -> None:
    """A placeholder line in an env file must not become an empty label."""
    captured = await _connect_capturing_kwargs(_make_config(nats_client_name=blank))
    assert "name" not in captured


# ---------------------------------------------------------------------------
# The keyword itself.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_configured_name_reaches_the_connect_call() -> None:
    captured = await _connect_capturing_kwargs(_make_config(nats_client_name="bus-gateway-factory"))
    assert captured["name"] == "bus-gateway-factory"


@pytest.mark.asyncio
async def test_the_name_is_stripped_of_surrounding_space() -> None:
    captured = await _connect_capturing_kwargs(
        _make_config(nats_client_name="  front-door-factory \n")
    )
    assert captured["name"] == "front-door-factory"


@pytest.mark.asyncio
async def test_two_services_of_one_account_send_two_different_names() -> None:
    """The whole point: one account, two names, told apart on the bus."""
    gateway = await _connect_capturing_kwargs(
        _make_config(
            nats_client_name="bus-gateway-factory",
            nats_user="jarvis",
            nats_password="not-a-real-password",
        )
    )
    door = await _connect_capturing_kwargs(
        _make_config(
            nats_client_name="front-door-factory",
            nats_user="jarvis",
            nats_password="not-a-real-password",
        )
    )
    assert gateway["user"] == door["user"] == "jarvis"
    assert gateway["name"] != door["name"]


@pytest.mark.asyncio
async def test_the_name_does_not_disturb_the_other_keywords() -> None:
    """Adding a label must not move the auth or the callbacks."""
    captured = await _connect_capturing_kwargs(
        _make_config(
            nats_client_name="bus-gateway-factory",
            nats_user="jarvis",
            nats_password="not-a-real-password",
        )
    )
    assert captured["servers"] == "nats://localhost:4222"
    assert captured["user"] == "jarvis"
    assert captured["password"] == "not-a-real-password"
    for callback in ("error_cb", "disconnected_cb", "reconnected_cb", "closed_cb"):
        assert callback in captured


# ---------------------------------------------------------------------------
# The library really does take this keyword — the design said to confirm it
# rather than assume it.
# ---------------------------------------------------------------------------


def test_the_client_library_accepts_a_name_keyword() -> None:
    import inspect

    from nats.aio.client import Client

    assert "name" in inspect.signature(Client.connect).parameters
