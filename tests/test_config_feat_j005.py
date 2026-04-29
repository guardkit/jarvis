"""Tests for FEAT-JARVIS-005 JarvisConfig extensions (TASK-J005-001).

Covers acceptance criteria:
  AC-001: Three fields added to ``JarvisConfig`` with the contracted defaults
          (``pipeline_publish_timeout_seconds=5``,
          ``forge_notifications_queue_cap=100``,
          ``forge_correlation_map_cap=1000``).
  AC-002: Field metadata includes the DDR anchor in ``description=``
          (DDR-025 / DDR-030 / DDR-028).
  AC-003: Env-var overrides follow the FEAT-J004 convention
          (``JARVIS_<UPPER_SNAKE>``).
  AC-004: No other module imports the new fields in this commit.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, get_type_hints
from unittest.mock import patch

from jarvis.config.settings import JarvisConfig


# ---------------------------------------------------------------------------
# AC-001: Three new fields exist with documented defaults
# ---------------------------------------------------------------------------
class TestAC001NewFieldsAndDefaults:
    """FEAT-J005 design.md §7 fields are declared with the contracted defaults."""

    def test_default_pipeline_publish_timeout_seconds_is_5(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.pipeline_publish_timeout_seconds == 5

    def test_default_forge_notifications_queue_cap_is_100(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.forge_notifications_queue_cap == 100

    def test_default_forge_correlation_map_cap_is_1000(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.forge_correlation_map_cap == 1000

    def test_field_types_are_int(self) -> None:
        hints = get_type_hints(JarvisConfig)
        assert hints["pipeline_publish_timeout_seconds"] is int
        assert hints["forge_notifications_queue_cap"] is int
        assert hints["forge_correlation_map_cap"] is int


# ---------------------------------------------------------------------------
# AC-002: Field metadata includes DDR anchor in description=
# ---------------------------------------------------------------------------
class TestAC002FieldDescriptionsContainDDRAnchor:
    """Each new field's ``description=`` references its DDR design anchor."""

    def test_pipeline_publish_timeout_description_references_ddr_025(self) -> None:
        field = JarvisConfig.model_fields["pipeline_publish_timeout_seconds"]
        assert field.description is not None
        assert "DDR-025" in field.description

    def test_forge_notifications_queue_cap_description_references_ddr_030(
        self,
    ) -> None:
        field = JarvisConfig.model_fields["forge_notifications_queue_cap"]
        assert field.description is not None
        assert "DDR-030" in field.description

    def test_forge_correlation_map_cap_description_references_ddr_028(self) -> None:
        field = JarvisConfig.model_fields["forge_correlation_map_cap"]
        assert field.description is not None
        assert "DDR-028" in field.description


# ---------------------------------------------------------------------------
# AC-003: JARVIS_<UPPER_SNAKE> env-var overrides
# ---------------------------------------------------------------------------
class TestAC003EnvVarOverrides:
    """``JARVIS_<NAME>`` env vars resolve to the corresponding new field."""

    def test_jarvis_pipeline_publish_timeout_seconds_env_var(self) -> None:
        with patch.dict(
            "os.environ",
            {"JARVIS_PIPELINE_PUBLISH_TIMEOUT_SECONDS": "12"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.pipeline_publish_timeout_seconds == 12

    def test_jarvis_forge_notifications_queue_cap_env_var(self) -> None:
        with patch.dict(
            "os.environ",
            {"JARVIS_FORGE_NOTIFICATIONS_QUEUE_CAP": "250"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.forge_notifications_queue_cap == 250

    def test_jarvis_forge_correlation_map_cap_env_var(self) -> None:
        with patch.dict(
            "os.environ",
            {"JARVIS_FORGE_CORRELATION_MAP_CAP": "2048"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.forge_correlation_map_cap == 2048

    def test_defaults_applied_when_env_unset(self) -> None:
        """With no FEAT-J005 env vars, every new field falls back to its default."""
        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.pipeline_publish_timeout_seconds == 5
        assert cfg.forge_notifications_queue_cap == 100
        assert cfg.forge_correlation_map_cap == 1000


# ---------------------------------------------------------------------------
# AC-004: Only the design-approved consumers reference the new fields.
#
# The original TASK-J005-001 invariant required the fields to remain
# *declarative-only* in that commit. As TASK-J005-005 (queue_build real
# publish) and TASK-J005-008 (lifecycle wiring for the forge subscriber)
# land, the invariant flips to a *closed allow-list*: each new field has
# exactly one design-approved consumer module beyond ``settings.py``. Any
# reference outside that allow-list is still an offender.
# ---------------------------------------------------------------------------
class TestAC004NoOtherModuleConsumesNewFields:
    """Only the design-approved consumer modules reference the new fields."""

    # Field name → set of relative file paths (under ``src/jarvis``) that
    # are allowed to reference the field after the FEAT-J005 wiring tasks
    # land. ``settings.py`` is always allowed and is filtered separately.
    ALLOWED_CONSUMERS: ClassVar[dict[str, set[str]]] = {
        # TASK-J005-005 — queue_build wraps ``js.publish`` in
        # ``asyncio.wait_for(..., timeout=config.pipeline_publish_timeout_seconds)``.
        "pipeline_publish_timeout_seconds": {
            "tools/dispatch.py",
        },
        # TASK-J005-008 — lifecycle constructs ``ForgeNotificationsSubscriber``
        # with ``queue_cap=config.forge_notifications_queue_cap`` and
        # ``correlation_cap=config.forge_correlation_map_cap``.
        "forge_notifications_queue_cap": {
            "infrastructure/lifecycle.py",
        },
        "forge_correlation_map_cap": {
            "infrastructure/lifecycle.py",
        },
    }

    def test_only_design_approved_consumers_reference_new_fields(self) -> None:
        src_root = Path(__file__).resolve().parent.parent / "src" / "jarvis"
        settings_path = (src_root / "config" / "settings.py").resolve()

        offenders: list[tuple[Path, str]] = []
        for py_file in src_root.rglob("*.py"):
            if py_file.resolve() == settings_path:
                continue
            relative = py_file.resolve().relative_to(src_root).as_posix()
            text = py_file.read_text(encoding="utf-8")
            for name, allowed_paths in self.ALLOWED_CONSUMERS.items():
                if name in text and relative not in allowed_paths:
                    offenders.append((py_file, name))

        assert not offenders, (
            "FEAT-J005 fields may only be consumed by the design-approved "
            f"modules; unexpected references found: {offenders}"
        )
