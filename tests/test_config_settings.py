"""Tests for FEAT-JARVIS-004 JarvisConfig extensions (TASK-J004-003).

Covers acceptance criteria:
  AC-001: Nine new fields added to JarvisConfig with documented defaults.
  AC-002: Field(ge=, le=) constraints applied per DDR-016 / DDR-020 /
          DDR-021/heartbeat (out-of-range values raise ValidationError).
  AC-003: ``jarvis_agent_version`` defaults to ``"0.4.0"`` and rejects
          non-semver values via the embedded regex pattern.
  AC-005: Env-prefix resolution (``JARVIS_NATS_URL`` → ``nats_url``);
          defaults applied when env vars absent.
  AC-006: settings.py imports neither ``nats-py`` nor ``graphiti-core``.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args, get_type_hints
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError


# ---------------------------------------------------------------------------
# AC-001: Nine new fields exist with documented defaults
# ---------------------------------------------------------------------------
class TestAC001NewFieldsAndDefaults:
    """Each FEAT-JARVIS-004 field is declared with the contracted default."""

    def test_default_nats_url_is_localhost(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.nats_url == "nats://localhost:4222"

    def test_default_nats_credentials_path_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.nats_credentials_path is None

    def test_default_heartbeat_interval_is_30s(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.heartbeat_interval_seconds == 30

    def test_default_graphiti_endpoint_is_none(self) -> None:
        """``None`` triggers the DDR-019 soft-fail path."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.graphiti_endpoint is None

    def test_default_graphiti_api_key_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.graphiti_api_key is None

    def test_default_jarvis_traces_dir_is_home_dot_jarvis_traces(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.jarvis_traces_dir == Path.home() / ".jarvis" / "traces"

    def test_default_specialist_dispatch_timeout_is_60s(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.specialist_dispatch_timeout_seconds == 60

    def test_default_dispatch_concurrent_cap_is_8(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.dispatch_concurrent_cap == 8

    def test_default_jarvis_agent_version_is_0_4_0(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.jarvis_agent_version == "0.4.0"

    def test_field_types_match_contract(self) -> None:
        """Type hints match docs/design/FEAT-JARVIS-004/contracts/API-internal.md §8."""
        from jarvis.config.settings import JarvisConfig

        hints = get_type_hints(JarvisConfig)
        assert hints["nats_url"] is str
        assert Path in get_args(hints["nats_credentials_path"])
        assert type(None) in get_args(hints["nats_credentials_path"])
        assert hints["heartbeat_interval_seconds"] is int
        assert str in get_args(hints["graphiti_endpoint"])
        assert type(None) in get_args(hints["graphiti_endpoint"])
        assert SecretStr in get_args(hints["graphiti_api_key"])
        assert type(None) in get_args(hints["graphiti_api_key"])
        assert hints["jarvis_traces_dir"] is Path
        assert hints["specialist_dispatch_timeout_seconds"] is int
        assert hints["dispatch_concurrent_cap"] is int
        assert hints["jarvis_agent_version"] is str


# ---------------------------------------------------------------------------
# AC-002: ge / le constraints reject out-of-range values
# ---------------------------------------------------------------------------
class TestAC002RangeConstraints:
    """Field(ge=, le=) constraints raise ValidationError on out-of-range input."""

    # ---- DDR-016: timeout 5..600 -----------------------------------------
    def test_dispatch_timeout_below_floor_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(specialist_dispatch_timeout_seconds=4)

    def test_dispatch_timeout_above_ceiling_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(specialist_dispatch_timeout_seconds=601)

    @pytest.mark.parametrize("value", [5, 60, 600])
    def test_dispatch_timeout_in_range_accepted(self, value: int) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(specialist_dispatch_timeout_seconds=value)
        assert cfg.specialist_dispatch_timeout_seconds == value

    # ---- DDR-020: cap 1..64 ----------------------------------------------
    def test_dispatch_cap_zero_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(dispatch_concurrent_cap=0)

    def test_dispatch_cap_above_ceiling_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(dispatch_concurrent_cap=65)

    @pytest.mark.parametrize("value", [1, 8, 64])
    def test_dispatch_cap_in_range_accepted(self, value: int) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(dispatch_concurrent_cap=value)
        assert cfg.dispatch_concurrent_cap == value

    # ---- DDR-021/heartbeat: 5..300 ---------------------------------------
    def test_heartbeat_below_floor_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(heartbeat_interval_seconds=4)

    def test_heartbeat_above_ceiling_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(heartbeat_interval_seconds=301)

    @pytest.mark.parametrize("value", [5, 30, 300])
    def test_heartbeat_in_range_accepted(self, value: int) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(heartbeat_interval_seconds=value)
        assert cfg.heartbeat_interval_seconds == value


# ---------------------------------------------------------------------------
# AC-003: jarvis_agent_version semver pattern validator
# ---------------------------------------------------------------------------
class TestAC003JarvisAgentVersionSemver:
    """``jarvis_agent_version`` rejects non-semver strings via the regex pattern."""

    @pytest.mark.parametrize(
        "value",
        [
            "0.4.0",
            "1.2.3",
            "10.20.30",
            "0.4.0-rc1",
            "0.4.0-alpha.1",
            "1.0.0-beta.2",
        ],
    )
    def test_valid_semver_accepted(self, value: str) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(jarvis_agent_version=value)
        assert cfg.jarvis_agent_version == value

    @pytest.mark.parametrize(
        "value",
        [
            "0.4",
            "v0.4.0",
            "0.4.0.0",
            "not-a-version",
            "",
            "1.2.3-UPPER",  # uppercase pre-release rejected by [a-z0-9.]+
        ],
    )
    def test_invalid_semver_raises(self, value: str) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(jarvis_agent_version=value)


# ---------------------------------------------------------------------------
# AC-005: Env-prefix resolution and default-when-unset
# ---------------------------------------------------------------------------
class TestAC005EnvPrefixResolution:
    """``JARVIS_<NAME>`` env vars resolve to the corresponding field."""

    def test_jarvis_nats_url_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_NATS_URL": "nats://test:4222"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.nats_url == "nats://test:4222"

    def test_jarvis_nats_credentials_path_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_NATS_CREDENTIALS_PATH": "/etc/jarvis/nats.creds"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.nats_credentials_path == Path("/etc/jarvis/nats.creds")

    def test_jarvis_heartbeat_interval_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_HEARTBEAT_INTERVAL_SECONDS": "60"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.heartbeat_interval_seconds == 60

    def test_jarvis_graphiti_endpoint_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_GRAPHITI_ENDPOINT": "http://graphiti.local:8000"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.graphiti_endpoint == "http://graphiti.local:8000"

    def test_jarvis_graphiti_api_key_env_var_is_secret(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_GRAPHITI_API_KEY": "graphiti-secret"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert isinstance(cfg.graphiti_api_key, SecretStr)
        assert cfg.graphiti_api_key.get_secret_value() == "graphiti-secret"
        # SecretStr must mask the value in str/repr output.
        assert "graphiti-secret" not in str(cfg)

    def test_jarvis_traces_dir_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_TRACES_DIR": "/var/lib/jarvis/traces"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.jarvis_traces_dir == Path("/var/lib/jarvis/traces")

    def test_jarvis_specialist_dispatch_timeout_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_SPECIALIST_DISPATCH_TIMEOUT_SECONDS": "120"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.specialist_dispatch_timeout_seconds == 120

    def test_jarvis_dispatch_concurrent_cap_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_DISPATCH_CONCURRENT_CAP": "16"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.dispatch_concurrent_cap == 16

    def test_jarvis_agent_version_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_AGENT_VERSION": "0.5.0"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.jarvis_agent_version == "0.5.0"

    def test_defaults_applied_when_env_unset(self) -> None:
        """With no FEAT-J004 env vars, every new field falls back to its default."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.nats_url == "nats://localhost:4222"
        assert cfg.nats_credentials_path is None
        assert cfg.heartbeat_interval_seconds == 30
        assert cfg.graphiti_endpoint is None
        assert cfg.graphiti_api_key is None
        assert cfg.jarvis_traces_dir == Path.home() / ".jarvis" / "traces"
        assert cfg.specialist_dispatch_timeout_seconds == 60
        assert cfg.dispatch_concurrent_cap == 8
        assert cfg.jarvis_agent_version == "0.4.0"


# ---------------------------------------------------------------------------
# AC-006: settings.py imports neither nats-py nor graphiti-core
# ---------------------------------------------------------------------------
class TestAC006SettingsModuleDependencyFree:
    """``jarvis.config.settings`` must not import nats-py or graphiti-core."""

    def test_settings_source_does_not_import_nats(self) -> None:
        from jarvis.config import settings as settings_module

        source = Path(settings_module.__file__).read_text(encoding="utf-8")
        # Allow ``nats://`` URL strings; reject any actual import.
        assert "import nats" not in source
        assert "from nats" not in source

    def test_settings_source_does_not_import_graphiti(self) -> None:
        from jarvis.config import settings as settings_module

        source = Path(settings_module.__file__).read_text(encoding="utf-8")
        assert "import graphiti" not in source
        assert "from graphiti" not in source
