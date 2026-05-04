"""Schema-conformance gate for ``ForgeNotification`` / ``BuildCorrelation``
(TASK-J005-002 — DM-forge-notification §1+§2).

This is the schema *authority gate* for the FEAT-JARVIS-005 in-process
notification surface. It fails loudly if any later task accidentally
renames a field, drops a section, or weakens a validator on either
``ForgeNotification`` or ``BuildCorrelation``.

Coverage (mapped to TASK-J005-002 acceptance criteria):

* AC-001 — ``forge_notifications`` exports both models via explicit
  ``__all__``.
* AC-002 — both models declare
  ``model_config = ConfigDict(extra="ignore", frozen=True)``.
* AC-003 — ``ForgeNotification.render_line()`` produces the canonical
  CLI shape per DM-forge-notification §1, with ``completed_at``
  rendered as local ``HH:MM``.
* AC-004 — Field validators / regex / ``max_length`` match
  DM-forge-notification verbatim — every ``Literal`` member, every
  ``min_length`` / ``max_length`` / ``ge`` / ``pattern`` is asserted.
* AC-005 — no NATS / subscriber imports leak into the schema module.

This task does *not* test ``from_stage_complete`` or the per-session
queue — those depend on the subscriber (TASK-J005-003) and the
SessionManager queue (TASK-J005-006) and land alongside their
respective implementations.

Notes
-----
* No mocks: Pydantic models are pure-data; tests construct real
  instances.
* No ``pytest.xfail`` / ``pytest.skip`` — every assertion is live
  against TASK-J005-002's authoritative schema.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, get_args

import pytest
from pydantic import ValidationError

import jarvis.infrastructure.forge_notifications as forge_notifications_module
from jarvis.infrastructure.forge_notifications import (
    BuildCorrelation,
    ForgeNotification,
)

# ============================================================================
# Helpers
# ============================================================================


_VALID_CORRELATION_ID = "corr-7e4f1b2c1a2b4c3d9e8f"
# Per DM-forge-notification §1 the pattern is ``^FEAT-[A-Z0-9]{3,12}$``
# — strict alphanumerics, no hyphens in the body. Use ``FEAT-J005`` rather
# than ``FEAT-JARVIS-005`` so the fixture is regex-clean.
_VALID_FEATURE_ID = "FEAT-J005"
_VALID_STAGE_LABEL = "plan-complete"
_VALID_TARGET_IDENTIFIER = "internal-tools:queue_build"
_VALID_ADAPTER = "cli"
_VALID_COMPLETED_AT = datetime(2026, 4, 28, 15, 42, 0, tzinfo=UTC)
_VALID_QUEUED_AT = datetime(2026, 4, 28, 15, 41, 0, tzinfo=UTC)


def _valid_notification_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a fully-populated valid ``ForgeNotification`` kwargs dict."""
    kwargs: dict[str, Any] = {
        "correlation_id": _VALID_CORRELATION_ID,
        "feature_id": _VALID_FEATURE_ID,
        "stage_label": _VALID_STAGE_LABEL,
        "status": "PASSED",
        "target_kind": "local_tool",
        "target_identifier": _VALID_TARGET_IDENTIFIER,
        "completed_at": _VALID_COMPLETED_AT,
        "duration_secs": 1.25,
    }
    kwargs.update(overrides)
    return kwargs


def _valid_correlation_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a fully-populated valid ``BuildCorrelation`` kwargs dict."""
    kwargs: dict[str, Any] = {
        "correlation_id": _VALID_CORRELATION_ID,
        "feature_id": _VALID_FEATURE_ID,
        "session_id": "sess-abc",
        "adapter": _VALID_ADAPTER,
        "queued_at": _VALID_QUEUED_AT,
    }
    kwargs.update(overrides)
    return kwargs


def _literal_members(annotation: Any) -> set[Any]:
    """Recover the closed-set members of a ``Literal[...]`` field annotation.

    TASK-FRR-F010D made several formerly-required Literal fields
    Optional (``Literal[...] | None``) so the same ``ForgeNotification``
    model can carry build-lifecycle event types whose payloads do not
    carry those fields. ``get_args`` on ``Literal[...] | None`` returns
    ``(Literal[...], NoneType)`` — the inner Literal is one element of
    the union, not the strings themselves.

    Strip the ``| None`` wrapper if present and return the Literal's
    closed-set string members.
    """
    union_members = get_args(annotation)
    if not union_members:
        # Already a bare Literal[...] — return its members directly.
        return set(get_args(annotation)) or set()  # pragma: no cover
    if type(None) in union_members:
        # Optional[Literal[...]] — find the non-None inner type and
        # recurse one level to peel its Literal members.
        inner = next(m for m in union_members if m is not type(None))
        return set(get_args(inner))
    # Bare Literal[...] — get_args already returned the members.
    return set(union_members)


# ============================================================================
# AC-001 — explicit __all__ exports
# ============================================================================


class TestExports:
    """AC-001 — ``forge_notifications`` exports both models via ``__all__``."""

    def test_module_exports_forge_notification_via_dunder_all(self) -> None:
        assert "ForgeNotification" in forge_notifications_module.__all__

    def test_module_exports_build_correlation_via_dunder_all(self) -> None:
        assert "BuildCorrelation" in forge_notifications_module.__all__

    def test_schema_module_keeps_nats_imports_lazy(self) -> None:
        """Schema imports must remain top-level-clean.

        TASK-J005-002 AC-005 originally enforced ``no NATS imports at all``
        because the subscriber lived in a future sibling module. TASK-J005-003
        co-locates the subscriber in this same file, so the asserted shape
        is now: ``nats`` / ``nats_core`` may be referenced for typing or
        inside function bodies, but MUST NOT appear at module top-level
        (so a schema-only consumer of ``ForgeNotification`` /
        ``BuildCorrelation`` does not pay the nats-py import cost).
        """
        source = forge_notifications_module.__file__ or ""
        with open(source, encoding="utf-8") as handle:
            lines = handle.readlines()

        # Track block depth — we only flag bare top-level imports.
        in_type_checking = False
        for raw in lines:
            stripped = raw.lstrip()
            indent = len(raw) - len(stripped)
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("if TYPE_CHECKING"):
                in_type_checking = True
                continue
            # Leaving the TYPE_CHECKING block: any dedent to col 0 ends it.
            if in_type_checking and indent == 0 and stripped:
                in_type_checking = False
            if indent != 0:
                continue
            # Top-level statement.
            assert not stripped.startswith("import nats"), (
                f"top-level 'import nats*' leaks into schema module: {raw!r}"
            )
            assert not stripped.startswith("from nats"), (
                f"top-level 'from nats*' leaks into schema module: {raw!r}"
            )


# ============================================================================
# AC-002 — model_config: frozen + extra="ignore"
# ============================================================================


class TestModelConfig:
    """AC-002 — both models declare ConfigDict(extra="ignore", frozen=True)."""

    def test_forge_notification_is_frozen(self) -> None:
        notification = ForgeNotification(**_valid_notification_kwargs())
        with pytest.raises(ValidationError):
            notification.status = "FAILED"  # type: ignore[misc]

    def test_build_correlation_is_frozen(self) -> None:
        correlation = BuildCorrelation(**_valid_correlation_kwargs())
        with pytest.raises(ValidationError):
            correlation.session_id = "different"  # type: ignore[misc]

    def test_forge_notification_ignores_unknown_extras(self) -> None:
        kwargs = _valid_notification_kwargs(unknown_field="should-be-dropped")
        notification = ForgeNotification(**kwargs)
        assert not hasattr(notification, "unknown_field")

    def test_build_correlation_ignores_unknown_extras(self) -> None:
        kwargs = _valid_correlation_kwargs(future_field="ignored")
        correlation = BuildCorrelation(**kwargs)
        assert not hasattr(correlation, "future_field")

    def test_forge_notification_config_flags(self) -> None:
        config = ForgeNotification.model_config
        assert config.get("frozen") is True
        assert config.get("extra") == "ignore"

    def test_build_correlation_config_flags(self) -> None:
        config = BuildCorrelation.model_config
        assert config.get("frozen") is True
        assert config.get("extra") == "ignore"


# ============================================================================
# AC-003 — render_line() canonical shape
# ============================================================================


class TestRenderLine:
    """AC-003 — render_line() emits the canonical CLI shape (DDR-030)."""

    def test_render_line_canonical_shape_passed(self) -> None:
        # Pin via a fixed-offset zone so the local-time render is
        # deterministic regardless of host TZ.
        local = timezone(timedelta(hours=0))
        completed_at = datetime(2026, 4, 28, 15, 42, 0, tzinfo=local)
        notification = ForgeNotification(
            **_valid_notification_kwargs(
                feature_id="FEAT-J005",
                stage_label="plan-complete",
                status="PASSED",
                completed_at=completed_at,
            )
        )
        # In the host's local zone the formatted hour may differ from
        # 15 (if the host TZ != UTC); the rest of the shape must match
        # verbatim.
        rendered = notification.render_line()
        assert rendered.startswith("[")
        assert (
            "] Forge FEAT-J005: stage plan-complete (PASSED)"
            in rendered
        )

    def test_render_line_failed_status_is_echoed_verbatim(self) -> None:
        notification = ForgeNotification(
            **_valid_notification_kwargs(
                stage_label="task-review",
                status="FAILED",
            )
        )
        assert "stage task-review (FAILED)" in notification.render_line()

    def test_render_line_uses_hhmm_no_seconds(self) -> None:
        notification = ForgeNotification(**_valid_notification_kwargs())
        rendered = notification.render_line()
        # The bracketed prefix has exactly one ':' — i.e. HH:MM, no seconds.
        prefix = rendered.split("]", 1)[0]
        assert prefix.startswith("[")
        assert prefix.count(":") == 1
        # Hours and minutes are 2 digits each.
        hh, mm = prefix[1:].split(":")
        assert len(hh) == 2 and hh.isdigit()
        assert len(mm) == 2 and mm.isdigit()

    def test_render_line_local_time_matches_explicit_strftime(self) -> None:
        notification = ForgeNotification(**_valid_notification_kwargs())
        expected_hhmm = (
            notification.completed_at.astimezone().strftime("%H:%M")
        )
        rendered = notification.render_line()
        assert rendered.startswith(f"[{expected_hhmm}] Forge ")

    def test_render_line_returns_str(self) -> None:
        notification = ForgeNotification(**_valid_notification_kwargs())
        assert isinstance(notification.render_line(), str)


# ============================================================================
# AC-004 — Field validators match DM-forge-notification verbatim
# ============================================================================


class TestForgeNotificationFieldValidators:
    """AC-004 — validators on ``ForgeNotification`` match DM verbatim."""

    # ---- correlation_id: min_length=1 -------------------------------------

    def test_correlation_id_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(correlation_id="")
            )

    # ---- feature_id: pattern=^FEAT-[A-Z0-9]{3,12}$ ------------------------

    @pytest.mark.parametrize(
        "feature_id",
        [
            "FEAT-J005",
            "FEAT-JARVIS005",
            "FEAT-ABC",
            "FEAT-AB12CD34EF56",  # 12-char body
        ],
    )
    def test_feature_id_accepts_canonical_shapes(
        self, feature_id: str
    ) -> None:
        notification = ForgeNotification(
            **_valid_notification_kwargs(feature_id=feature_id)
        )
        assert notification.feature_id == feature_id

    @pytest.mark.parametrize(
        "feature_id",
        [
            "feat-J005",  # lower-case prefix
            "FEAT-jarvis",  # lower-case body
            "FEAT-AB",  # body too short (<3)
            "FEAT-AB12CD34EF567",  # body too long (>12)
            "BUG-J005",  # wrong prefix
            "FEAT_J005",  # underscore separator
            "",
        ],
    )
    def test_feature_id_rejects_invalid_shapes(
        self, feature_id: str
    ) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(feature_id=feature_id)
            )

    # ---- stage_label: min_length=1, max_length=128 ------------------------

    def test_stage_label_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(stage_label="")
            )

    def test_stage_label_accepts_max_length(self) -> None:
        notification = ForgeNotification(
            **_valid_notification_kwargs(stage_label="x" * 128)
        )
        assert len(notification.stage_label) == 128

    def test_stage_label_rejects_over_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(stage_label="x" * 129)
            )

    # ---- status: closed Literal -------------------------------------------

    @pytest.mark.parametrize(
        "status", ["PASSED", "FAILED", "GATED", "SKIPPED"]
    )
    def test_status_accepts_every_literal_member(
        self, status: str
    ) -> None:
        notification = ForgeNotification(
            **_valid_notification_kwargs(status=status)
        )
        assert notification.status == status

    def test_status_rejects_unknown_member(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(status="UNKNOWN")
            )

    def test_status_literal_members_match_dm_section_1(self) -> None:
        """The closed Literal must contain exactly the four DM members.

        TASK-FRR-F010D made ``status`` Optional (``Literal[...] | None``)
        because the three new build-lifecycle event types — ``build_started``,
        ``build_complete``, ``build_failed`` — do not carry a status
        field. Unwrap the union to recover the inner Literal and assert
        its closed-set membership unchanged from DM-forge-notification §1.
        """
        members = _literal_members(
            ForgeNotification.model_fields["status"].annotation
        )
        assert members == {"PASSED", "FAILED", "GATED", "SKIPPED"}

    # ---- target_kind: closed Literal --------------------------------------

    @pytest.mark.parametrize(
        "target_kind", ["local_tool", "fleet_capability", "subagent"]
    )
    def test_target_kind_accepts_every_literal_member(
        self, target_kind: str
    ) -> None:
        notification = ForgeNotification(
            **_valid_notification_kwargs(target_kind=target_kind)
        )
        assert notification.target_kind == target_kind

    def test_target_kind_rejects_unknown_member(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(target_kind="frontier")
            )

    def test_target_kind_literal_members_match_dm_section_1(self) -> None:
        """TASK-FRR-F010D parity with status: ``target_kind`` is now
        ``Literal[...] | None`` because the build-lifecycle event types
        do not carry it."""
        members = _literal_members(
            ForgeNotification.model_fields["target_kind"].annotation
        )
        assert members == {"local_tool", "fleet_capability", "subagent"}

    # ---- target_identifier: min_length=1 ----------------------------------

    def test_target_identifier_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(target_identifier="")
            )

    # ---- duration_secs: ge=0.0 --------------------------------------------

    def test_duration_secs_accepts_zero(self) -> None:
        notification = ForgeNotification(
            **_valid_notification_kwargs(duration_secs=0.0)
        )
        assert notification.duration_secs == 0.0

    def test_duration_secs_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            ForgeNotification(
                **_valid_notification_kwargs(duration_secs=-0.001)
            )


class TestBuildCorrelationFieldValidators:
    """AC-004 — validators on ``BuildCorrelation`` match DM verbatim."""

    # ---- correlation_id: min_length=1 -------------------------------------

    def test_correlation_id_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            BuildCorrelation(
                **_valid_correlation_kwargs(correlation_id="")
            )

    # ---- feature_id: pattern=^FEAT-[A-Z0-9]{3,12}$ ------------------------

    @pytest.mark.parametrize(
        "feature_id",
        ["FEAT-J005", "FEAT-AB12CD34EF56"],
    )
    def test_feature_id_accepts_canonical_shapes(
        self, feature_id: str
    ) -> None:
        correlation = BuildCorrelation(
            **_valid_correlation_kwargs(feature_id=feature_id)
        )
        assert correlation.feature_id == feature_id

    @pytest.mark.parametrize(
        "feature_id",
        ["feat-J005", "FEAT-AB", "FEAT-AB12CD34EF567", "BUG-J005", ""],
    )
    def test_feature_id_rejects_invalid_shapes(
        self, feature_id: str
    ) -> None:
        with pytest.raises(ValidationError):
            BuildCorrelation(
                **_valid_correlation_kwargs(feature_id=feature_id)
            )

    # ---- session_id: optional, default None -------------------------------

    def test_session_id_default_is_none(self) -> None:
        kwargs = _valid_correlation_kwargs()
        kwargs.pop("session_id")
        correlation = BuildCorrelation(**kwargs)
        assert correlation.session_id is None

    def test_session_id_accepts_string(self) -> None:
        correlation = BuildCorrelation(
            **_valid_correlation_kwargs(session_id="sess-abc")
        )
        assert correlation.session_id == "sess-abc"

    # ---- adapter: min_length=1 --------------------------------------------

    def test_adapter_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            BuildCorrelation(**_valid_correlation_kwargs(adapter=""))


# ============================================================================
# AC-004 — Round-trip JSON serialization
# ============================================================================


class TestJsonRoundTrip:
    """``model_dump_json()`` round-trips both models."""

    def test_forge_notification_round_trips_via_json(self) -> None:
        original = ForgeNotification(**_valid_notification_kwargs())
        encoded = original.model_dump_json()
        # Sanity — the JSON is parseable.
        decoded = json.loads(encoded)
        assert decoded["correlation_id"] == _VALID_CORRELATION_ID
        # Restore through the canonical loader.
        restored = ForgeNotification.model_validate_json(encoded)
        assert restored == original

    def test_build_correlation_round_trips_via_json(self) -> None:
        original = BuildCorrelation(**_valid_correlation_kwargs())
        encoded = original.model_dump_json()
        decoded = json.loads(encoded)
        assert decoded["correlation_id"] == _VALID_CORRELATION_ID
        assert decoded["session_id"] == "sess-abc"
        restored = BuildCorrelation.model_validate_json(encoded)
        assert restored == original

    def test_build_correlation_round_trips_with_none_session(self) -> None:
        original = BuildCorrelation(
            **_valid_correlation_kwargs(session_id=None)
        )
        restored = BuildCorrelation.model_validate_json(
            original.model_dump_json()
        )
        assert restored == original
        assert restored.session_id is None
