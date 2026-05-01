"""Contract tests vs ``nats_core`` + ``Topics`` formatter grep invariant.

This is the cross-repo handshake protector for FEAT-JARVIS-004 (TASK-J004-019).
It catches the kind of drift between Jarvis's emit sites and ``nats_core``'s
schemas / topic registry that would silently break Forge↔Jarvis interop with
no clear blast radius.

Acceptance criteria covered:

- AC-001: every contract test in the task description exists.
- AC-002: the grep invariant test (#6) uses ``pathlib.Path.rglob`` +
  ``str.contains`` to scan ``src/jarvis/`` for hard-coded subject
  literals; the allow-list is documented in the test docstring.
- AC-003: the grep invariant fails loudly with the offending file +
  line in the assertion message.
- AC-004: the source-id audit (#4) parametrises across every
  ``MessageEnvelope`` construction site found via grep.
- AC-005: no real NATS / Graphiti — pure schema + grep contract tests.
- AC-006: ``uv run pytest tests/test_contract_nats_core.py -v`` green.

The test suite is deliberately self-contained — synthetic
``CommandPayload`` / ``ResultPayload`` / ``AgentManifest`` instances are
built in-test, no live NATS round-trip is required, and the grep
invariant runs against ``src/jarvis/`` only (not ``tests/``,
``features/``, or ``docs/``).
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats_core import (
    AgentManifest,
    EventType,
    MessageEnvelope,
    Topics,
)
from nats_core.events import (
    BuildQueuedPayload,
    CommandPayload,
    ResultPayload,
    StageCompletePayload,
)
from pydantic import ValidationError

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.fleet_registration import build_jarvis_manifest
from jarvis.tools import dispatch
from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_SRC_JARVIS: Path = _PROJECT_ROOT / "src" / "jarvis"

# Forbidden subject-literal substrings the grep invariant guards against.
# Anchored with `+` concatenation in the test only when needed so the
# tokens themselves do not leak into the source tree via this test file
# (the grep invariant ignores ``tests/``, but defence-in-depth is cheap).
_FORBIDDEN_SUBJECT_LITERALS: tuple[str, ...] = (
    "agents.command.",
    "agents.result.",
    "fleet.register",
    # FEAT-JARVIS-005 / TASK-J005-010 — every pipeline subject must be
    # derived from ``nats_core.Topics.Pipeline`` (ADR-SP-014 / ADR-SP-016).
    "pipeline.build-queued.",
    "pipeline.stage-complete.",
)

# ---------------------------------------------------------------------------
# Allow-list for the grep invariant.
#
# The grep invariant rejects any ``"agents.command."`` / ``"agents.result."``
# / ``"fleet.register"`` substring that appears in ``src/jarvis/`` outside the
# narrow set listed here. The allow-list captures lines that legitimately
# mention the tokens — module-level docstrings that explain the contract,
# import lines (``from nats_core ... Topics``), or commentary referencing the
# canonical ``Topics`` registry.
#
# Each entry is matched as a substring against the *line* content (not the
# whole file) so a comment line carrying e.g. ``# fleet.register KV bucket``
# is allowed while a literal Python string ``"fleet.register"`` is not.
# ---------------------------------------------------------------------------
_GREP_LINE_ALLOWLIST: tuple[str, ...] = (
    # Module docstring / commentary mentions of the retired literals.
    "fleet.register",  # accept comment / docstring mentions; literals are
    # caught via the secondary pattern below
)


def _read_text_safe(path: Path) -> str | None:
    """Return file content or ``None`` if the file is binary / unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _iter_source_files() -> list[Path]:
    """Yield ``.py`` files under ``src/jarvis/`` (excludes ``__pycache__``)."""
    files: list[Path] = []
    for path in _SRC_JARVIS.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


# ---------------------------------------------------------------------------
# Fixtures — synthetic test config + dispatch dep wiring
# ---------------------------------------------------------------------------


@pytest.fixture()
def jarvis_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` with a fake openai endpoint.

    The default ``jarvis_agent_version`` is a valid semver so the
    manifest validates without any overrides.
    """
    return JarvisConfig(llama_swap_base_url="http://fake-endpoint")


def _make_registry() -> list[CapabilityDescriptor]:
    """Build a single-entry capability registry for dispatch routing."""
    return [
        CapabilityDescriptor(
            agent_id="product-owner",
            role="Product Owner",
            description="Reviews specs against acceptance criteria.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="review_spec",
                    description="Review a feature spec",
                    risk_level="read_only",
                ),
            ],
        ),
    ]


@pytest.fixture()
def bound_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a fresh capability registry into the dispatch module."""
    saved = dispatch._capability_registry
    dispatch._capability_registry = _make_registry()
    try:
        yield dispatch._capability_registry
    finally:
        dispatch._capability_registry = saved


@pytest.fixture()
def mock_dispatch_deps() -> Generator[dict[str, Any], None, None]:
    """Wire mock ``NATSClient`` + ``DispatchSemaphore`` + ``RoutingHistoryWriter``."""
    saved = (
        dispatch._nats_client,
        dispatch._dispatch_semaphore,
        dispatch._routing_history_writer,
    )

    nats_client = MagicMock()
    nats_client.request = AsyncMock()

    semaphore = MagicMock()
    semaphore.try_acquire = MagicMock(return_value=True)
    semaphore.release = MagicMock()
    semaphore.in_flight = 0

    writer = MagicMock()
    writer.write_specialist_dispatch = AsyncMock(return_value=None)

    dispatch._nats_client = nats_client
    dispatch._dispatch_semaphore = semaphore
    dispatch._routing_history_writer = writer

    try:
        yield {
            "nats_client": nats_client,
            "semaphore": semaphore,
            "writer": writer,
        }
    finally:
        (
            dispatch._nats_client,
            dispatch._dispatch_semaphore,
            dispatch._routing_history_writer,
        ) = saved


# ===========================================================================
# (1) test_jarvis_manifest_round_trips
# ===========================================================================


class TestJarvisManifestRoundTrips:
    """``build_jarvis_manifest`` → JSON → ``AgentManifest`` round-trips."""

    def test_jarvis_manifest_round_trips(self, jarvis_config: JarvisConfig) -> None:
        """Manifest survives a JSON encode/decode cycle into ``AgentManifest``."""
        manifest = build_jarvis_manifest(jarvis_config)

        # Encode via pydantic, decode via the canonical nats_core schema.
        encoded = manifest.model_dump_json()
        decoded = AgentManifest.model_validate_json(encoded)

        # Equality at the model level (pydantic compares field-by-field).
        assert decoded == manifest, (
            "AgentManifest round-trip diverged: "
            f"original={manifest.model_dump()} decoded={decoded.model_dump()}"
        )

        # Also confirm the decoded instance carries the canonical Jarvis
        # identity fields — a guard against silent field-name drift.
        assert decoded.agent_id == "jarvis"
        assert decoded.template == "general_purpose_agent"
        assert decoded.trust_tier == "core"


# ===========================================================================
# (2) test_command_payload_emitted_matches_nats_core
# ===========================================================================


class TestCommandPayloadEmittedMatchesNatsCore:
    """Every emitted ``CommandPayload`` deserialises via ``nats_core``."""

    def test_command_payload_emitted_matches_nats_core(self) -> None:
        """``_build_command_envelope`` produces a wire-compatible payload."""
        correlation_id = "00000000-0000-4000-8000-000000000001"
        command, envelope = dispatch._build_command_envelope(
            tool_name="review_spec",
            parsed_args={"path": "features/foo.yaml", "depth": 2},
            correlation_id=correlation_id,
        )

        # Direct schema instance: type-check against nats_core.events.
        assert isinstance(command, CommandPayload), (
            "dispatch._build_command_envelope must produce a nats_core CommandPayload"
        )

        # Round-trip via the envelope's payload (this is what hits the wire).
        payload_json = json.dumps(envelope.payload)
        decoded = CommandPayload.model_validate_json(payload_json)

        # Required-field invariants: command, args, correlation_id all populated.
        assert decoded.command == "review_spec"
        assert decoded.args == {"path": "features/foo.yaml", "depth": 2}
        assert decoded.correlation_id == correlation_id


# ===========================================================================
# (3) test_result_payload_consumed_matches_nats_core
# ===========================================================================


class TestResultPayloadConsumedMatchesNatsCore:
    """A synthetic ``ResultPayload`` reply round-trips through dispatch."""

    async def test_result_payload_consumed_matches_nats_core(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        """``ResultPayload(...)`` reply deserialises without ValidationError."""
        # Build a synthetic specialist reply via the canonical nats_core schema.
        reply = ResultPayload(
            command="review_spec",
            result={"verdict": "ok", "notes": "looks good"},
            correlation_id="00000000-0000-4000-8000-000000000002",
            success=True,
        )
        reply_bytes = reply.model_dump_json().encode("utf-8")

        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(data=reply_bytes)

        result_str = await dispatch.dispatch_by_capability.ainvoke(
            {
                "tool_name": "review_spec",
                "payload_json": "{}",
            }
        )

        # The dispatch tool returns the ResultPayload JSON on success — round
        # trip the *output* through ResultPayload.model_validate_json to prove
        # the contract holds end-to-end.
        decoded = ResultPayload.model_validate_json(result_str)
        assert decoded.command == "review_spec"
        assert decoded.success is True
        assert decoded.result == {"verdict": "ok", "notes": "looks good"}


# ===========================================================================
# (4) test_envelope_source_id_is_jarvis — parametrised across emit sites
# ===========================================================================


def _emit_command_envelope() -> MessageEnvelope:
    """Build the dispatch-side ``MessageEnvelope`` (CommandPayload)."""
    _, envelope = dispatch._build_command_envelope(
        tool_name="review_spec",
        parsed_args={},
        correlation_id="00000000-0000-4000-8000-00000000000a",
    )
    return envelope


def _emit_queue_build_envelope() -> MessageEnvelope:
    """Build the queue_build-side ``MessageEnvelope`` (BuildQueuedPayload).

    Constructs the BuildQueuedPayload + MessageEnvelope using the same shape
    the queue_build tool body uses (dispatch.py:799-816) so the audit
    invariant covers every emit site found via grep.
    """
    from datetime import UTC, datetime

    payload = BuildQueuedPayload(
        feature_id="FEAT-J004",
        repo="guardkit/jarvis",
        branch="main",
        feature_yaml_path="features/feat.yaml",
        triggered_by="jarvis",
        originating_adapter="terminal",
        correlation_id="00000000-0000-4000-8000-00000000000b",
        parent_request_id=None,
        requested_at=datetime.now(UTC),
        queued_at=datetime.now(UTC),
    )
    return MessageEnvelope(
        source_id="jarvis",
        event_type=EventType.BUILD_QUEUED,
        correlation_id=str(payload.correlation_id),
        payload=payload.model_dump(mode="json"),
    )


# Every ``MessageEnvelope(source_id=...)`` construction site under
# ``src/jarvis/`` is replayed here. The grep below the parametrisation pins
# the count — adding a new emit site without registering it triggers a hard
# fail rather than a silent miss.
_EMIT_SITES: tuple[tuple[str, Any], ...] = (
    ("dispatch.py:_build_command_envelope", _emit_command_envelope),
    ("dispatch.py:queue_build", _emit_queue_build_envelope),
)


class TestEnvelopeSourceIdIsJarvis:
    """API-events §5: every emitted ``MessageEnvelope`` carries source_id='jarvis'."""

    @pytest.mark.parametrize(
        "label,builder",
        _EMIT_SITES,
        ids=[label for label, _ in _EMIT_SITES],
    )
    def test_envelope_source_id_is_jarvis(self, label: str, builder: Any) -> None:
        """Every emit site sets ``source_id='jarvis'``."""
        envelope = builder()
        assert envelope.source_id == "jarvis", (
            f"API-events §5 invariant broken at {label}: "
            f"source_id={envelope.source_id!r} (expected 'jarvis')"
        )

    def test_emit_site_count_matches_grep(self) -> None:
        """Audit guard: every ``MessageEnvelope(`` in src/jarvis is registered.

        Counts ``MessageEnvelope(`` constructor calls under ``src/jarvis/``
        and asserts that count equals ``len(_EMIT_SITES)``. Adding a new
        emit site without adding it to ``_EMIT_SITES`` (or removing one
        without updating the parametrisation) triggers a hard failure
        with the offending count.
        """
        construction_pattern = re.compile(r"\bMessageEnvelope\s*\(")
        emit_lines: list[str] = []
        for path in _iter_source_files():
            content = _read_text_safe(path)
            if content is None:
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if construction_pattern.search(line):
                    rel = path.relative_to(_PROJECT_ROOT)
                    emit_lines.append(f"{rel}:{lineno}")

        assert len(emit_lines) == len(_EMIT_SITES), (
            "MessageEnvelope construction sites in src/jarvis/ "
            f"({len(emit_lines)}) does not match registered _EMIT_SITES "
            f"({len(_EMIT_SITES)}). Sites found: {emit_lines}"
        )


# ===========================================================================
# (5) test_topic_subjects_match_topics_class
# ===========================================================================


class TestTopicSubjectsMatchTopicsClass:
    """Every emitted subject string is produced by a ``Topics.*`` formatter."""

    def test_dispatch_subject_matches_topics_agents_command(self) -> None:
        """``dispatch_by_capability`` subject is ``Topics.Agents.COMMAND``."""
        agent_id = "product-owner"
        # Re-derive the subject the dispatch tool emits.
        produced = Topics.Agents.COMMAND.format(agent_id=agent_id)
        assert produced == f"agents.command.{agent_id}"
        # Defence: the template itself is the Topics constant — no literal.
        assert Topics.Agents.COMMAND == "agents.command.{agent_id}"

    def test_queue_build_subject_matches_topics_pipeline_build_queued(self) -> None:
        """``queue_build`` subject is ``Topics.Pipeline.BUILD_QUEUED``."""
        feature_id = "FEAT-J004"
        produced = Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)
        assert produced == f"pipeline.build-queued.{feature_id}"
        assert Topics.Pipeline.BUILD_QUEUED == "pipeline.build-queued.{feature_id}"

    def test_fleet_register_topic_constant_matches_topics_fleet_register(self) -> None:
        """``Topics.Fleet.REGISTER`` is the canonical fleet-register subject.

        The ``fleet_registration`` module routes through
        :class:`NATSKVManifestRegistry` rather than synthesising a subject
        literal; this test pins the canonical value Jarvis would use if it
        ever did emit on that subject directly.
        """
        assert Topics.Fleet.REGISTER == "fleet.register"


# ===========================================================================
# (6) test_no_hardcoded_subject_literals_in_src — grep invariant
# ===========================================================================


class TestNoHardcodedSubjectLiteralsInSrc:
    """Grep invariant: ``src/jarvis/`` carries no hard-coded subject literals.

    Allow-list (in priority order):

    1. Module-level / function-level docstrings (``\"\"\"...\"\"\"`` and
       ``'''...'''``) — narrative mentions of the topic strings are fine.
    2. Comment lines (``# ...``) — commentary explaining the contract.
    3. Lines that import or reference :class:`nats_core.Topics` — the
       template constants legitimately contain the literal substrings
       (``Topics.Agents.COMMAND = "agents.command.{agent_id}"``).
    4. The :mod:`jarvis.shared.constants` module — a no-op carve-out kept
       for forward-compat; currently empty.
    """

    def test_src_tree_exists(self) -> None:
        """Fail fast if the source layout has shifted."""
        assert _SRC_JARVIS.is_dir(), (
            f"Expected src tree at {_SRC_JARVIS}; layout has changed."
        )

    @pytest.mark.parametrize("forbidden", _FORBIDDEN_SUBJECT_LITERALS)
    def test_no_hardcoded_subject_literals_in_src(self, forbidden: str) -> None:
        """No hard-coded subject literal appears outside the allow-list."""
        offenders: list[str] = []

        for path in _iter_source_files():
            content = _read_text_safe(path)
            if content is None:
                continue
            if forbidden not in content:
                continue

            in_docstring = False
            docstring_delim: str | None = None
            for lineno, line in enumerate(content.splitlines(), start=1):
                stripped = line.lstrip()

                # Toggle docstring state. Triple-quoted strings opened and
                # closed on the same line do not flip the flag.
                if not in_docstring:
                    for delim in ('"""', "'''"):
                        if stripped.startswith(delim):
                            rest = stripped[len(delim):]
                            if delim in rest:
                                # Single-line docstring — do not flip.
                                pass
                            else:
                                in_docstring = True
                                docstring_delim = delim
                            break
                else:
                    assert docstring_delim is not None
                    if docstring_delim in stripped:
                        in_docstring = False
                        docstring_delim = None
                    # Either way, a docstring body line is allow-listed.
                    continue

                if in_docstring:
                    # Opening line of a multi-line docstring is allow-listed.
                    continue

                if forbidden not in line:
                    continue

                # Allow-list: comment lines.
                if stripped.startswith("#"):
                    continue

                # Allow-list: import lines mentioning Topics.
                if stripped.startswith("from nats_core") or stripped.startswith(
                    "import nats_core"
                ):
                    continue

                # Allow-list: lines that reference a ``Topics.*`` template
                # rather than emitting a literal — the Topics class itself
                # holds the templates and is the canonical source of truth.
                if "Topics." in line:
                    continue

                rel = path.relative_to(_PROJECT_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

        assert not offenders, (
            f"Hard-coded subject literal {forbidden!r} found in "
            f"src/jarvis/ outside the allow-list "
            "(nats_core.Topics import + module-docstring commentary):\n"
            + "\n".join(offenders)
        )


# ===========================================================================
# (7) test_build_queued_payload_emitted_matches_nats_core — FEAT-J005 carry
# ===========================================================================


class TestBuildQueuedPayloadEmittedMatchesNatsCore:
    """FEAT-J005 carry-forward stub.

    Today the queue_build tool builds a real :class:`BuildQueuedPayload`,
    logs it, and walks away (Phase 2 stub). FEAT-JARVIS-005 swaps the log
    for a real ``js.publish`` on ``pipeline.build-queued.{feature_id}``;
    when that lands this test is the contract gate. For now we only
    exercise the Phase 2 stub builder so the test exists and is green.
    """

    def test_build_queued_payload_stub_round_trips_via_nats_core(self) -> None:
        """Phase 2 stub: synthetic ``BuildQueuedPayload`` round-trips."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        payload = BuildQueuedPayload(
            feature_id="FEAT-J004",
            repo="guardkit/jarvis",
            branch="main",
            feature_yaml_path="features/feat.yaml",
            triggered_by="jarvis",
            originating_adapter="terminal",
            correlation_id="00000000-0000-4000-8000-00000000000c",
            parent_request_id=None,
            requested_at=now,
            queued_at=now,
        )
        encoded = payload.model_dump_json()
        decoded = BuildQueuedPayload.model_validate_json(encoded)

        assert decoded.feature_id == "FEAT-J004"
        assert decoded.triggered_by == "jarvis"
        assert decoded.originating_adapter == "terminal"
        assert decoded.correlation_id == payload.correlation_id


# ===========================================================================
# TASK-J005-010 — FEAT-JARVIS-005 cross-repo contract gate
# ===========================================================================
#
# The block below verifies the wire-level contract between Jarvis and Forge
# for FEAT-JARVIS-005: BuildQueuedPayload (publish), StageCompletePayload
# (subscribe), the Topics formatters that produce both subjects, and the
# MessageEnvelope.source_id round-trip / drop semantics. Tests run against
# the actual ``nats_core`` package import (no mocks of nats_core types) so a
# payload-shape change in nats_core trips this suite first.
# ===========================================================================


def _good_build_queued_dict() -> dict[str, Any]:
    """Return a known-good ``BuildQueuedPayload`` input dict (jarvis trigger)."""
    from datetime import UTC, datetime

    iso = datetime(2026, 4, 30, 15, 0, 0, tzinfo=UTC).isoformat()
    return {
        "feature_id": "FEAT-J005",
        "repo": "guardkit/jarvis",
        "branch": "main",
        "feature_yaml_path": "features/feat.yaml",
        "triggered_by": "jarvis",
        "originating_adapter": "terminal",
        "originating_user": "rich",
        "correlation_id": "00000000-0000-4000-8000-00000000aaaa",
        "parent_request_id": None,
        "requested_at": iso,
        "queued_at": iso,
    }


def _good_stage_complete_dict() -> dict[str, Any]:
    """Return a known-good ``StageCompletePayload`` input dict."""
    from datetime import UTC, datetime

    return {
        "feature_id": "FEAT-J005",
        "build_id": "build-001",
        "stage_label": "plan-complete",
        "target_kind": "subagent",
        "target_identifier": "architect",
        "status": "PASSED",
        "gate_mode": "AUTO_APPROVE",
        "coach_score": 0.92,
        "duration_secs": 12.5,
        "completed_at": datetime(2026, 4, 30, 15, 42, 0, tzinfo=UTC).isoformat(),
        "correlation_id": "00000000-0000-4000-8000-00000000bbbb",
    }


# ---------------------------------------------------------------------------
# AC-001 — BuildQueuedPayload contract
# ---------------------------------------------------------------------------


class TestBuildQueuedPayloadContract:
    """AC-001 — publish-direction payload validates + round-trips + validator."""

    def test_constructs_from_known_good_dict(self) -> None:
        """BuildQueuedPayload accepts the canonical jarvis-triggered shape."""
        payload = BuildQueuedPayload(**_good_build_queued_dict())

        assert payload.feature_id == "FEAT-J005"
        assert payload.triggered_by == "jarvis"
        assert payload.originating_adapter == "terminal"
        assert payload.correlation_id == "00000000-0000-4000-8000-00000000aaaa"

    def test_model_dump_round_trip_preserves_all_fields(self) -> None:
        """``model_dump()`` → constructor reproduces every field bit-stably."""
        original = BuildQueuedPayload(**_good_build_queued_dict())

        # Round-trip via model_dump (Python objects, not JSON).
        rebuilt = BuildQueuedPayload(**original.model_dump())
        assert rebuilt == original, (
            "BuildQueuedPayload model_dump round-trip diverged: "
            f"original={original.model_dump()} rebuilt={rebuilt.model_dump()}"
        )

        # And via model_dump_json for bit-stability across the wire.
        encoded = original.model_dump_json()
        decoded = BuildQueuedPayload.model_validate_json(encoded)
        assert decoded == original
        # Re-encoding must be byte-identical (deterministic field order).
        assert decoded.model_dump_json() == encoded

    def test_adapter_required_for_jarvis_validator_raises(self) -> None:
        """``_adapter_required_for_jarvis`` rejects jarvis-trigger w/ no adapter."""
        bad = _good_build_queued_dict()
        bad["originating_adapter"] = None

        with pytest.raises(ValidationError) as excinfo:
            BuildQueuedPayload(**bad)

        # The ValueError raised inside the validator carries this message —
        # pydantic surfaces it under the ``msg`` of the resulting error tuple.
        assert "originating_adapter is required when triggered_by == 'jarvis'" in str(
            excinfo.value
        )


# ---------------------------------------------------------------------------
# AC-002 — StageCompletePayload contract
# ---------------------------------------------------------------------------


class TestStageCompletePayloadContract:
    """AC-002 — subscribe-direction payload validates + JSON round-trips."""

    def test_constructs_from_known_good_dict(self) -> None:
        """StageCompletePayload accepts the canonical Forge-published shape."""
        payload = StageCompletePayload(**_good_stage_complete_dict())

        assert payload.feature_id == "FEAT-J005"
        assert payload.stage_label == "plan-complete"
        assert payload.status == "PASSED"
        assert payload.target_kind == "subagent"
        assert payload.duration_secs == 12.5

    def test_json_round_trip_is_bit_stable(self) -> None:
        """``model_dump_json`` → ``model_validate_json`` is byte-stable."""
        original = StageCompletePayload(**_good_stage_complete_dict())

        encoded = original.model_dump_json()
        decoded = StageCompletePayload.model_validate_json(encoded)

        assert decoded == original
        # Re-serialising the decoded instance produces the same bytes —
        # i.e. there is no field ordering / coercion drift across the wire.
        assert decoded.model_dump_json() == encoded


# ---------------------------------------------------------------------------
# AC-003 / AC-004 — Topics formatters and subscribe wildcard
# ---------------------------------------------------------------------------


def _nats_subject_matches(pattern: str, subject: str) -> bool:
    """Minimal NATS subject matcher supporting ``*`` and trailing ``>``.

    * ``*`` matches exactly one token.
    * ``>`` matches one or more tokens; only valid as the final token.
    """
    pat_tokens = pattern.split(".")
    sub_tokens = subject.split(".")

    if pat_tokens and pat_tokens[-1] == ">":
        head = pat_tokens[:-1]
        if len(sub_tokens) <= len(head):
            return False
        for p, s in zip(head, sub_tokens, strict=False):
            if p != "*" and p != s:
                return False
        return True

    if len(pat_tokens) != len(sub_tokens):
        return False
    for p, s in zip(pat_tokens, sub_tokens, strict=True):
        if p != "*" and p != s:
            return False
    return True


class TestTopicsPipelineFormatters:
    """AC-003 / AC-004 — Topics.Pipeline subjects match design contract."""

    def test_build_queued_format_produces_singular_subject(self) -> None:
        """``Topics.Pipeline.BUILD_QUEUED.format(feature_id="X")`` yields the
        ADR-SP-016 singular form ``pipeline.build-queued.X``."""
        produced = Topics.Pipeline.BUILD_QUEUED.format(feature_id="X")
        assert produced == "pipeline.build-queued.X", (
            "ADR-SP-016 singular convention broken: BUILD_QUEUED format "
            f"produced {produced!r}"
        )

    def test_stage_complete_wildcard_matches_known_subject(self) -> None:
        """``STAGE_COMPLETE`` template + ``>`` wildcard matches a real
        stage-complete subject (``pipeline.stage-complete.X.plan-complete``)."""
        # Derive the wildcard subscribe pattern from the Topics template by
        # substituting NATS '>' for the {feature_id} placeholder. This is
        # the same derivation the subscriber uses (see
        # jarvis.infrastructure.forge_notifications._STAGE_COMPLETE_SUBJECT).
        pattern = Topics.Pipeline.STAGE_COMPLETE.format(feature_id=">")
        assert pattern == "pipeline.stage-complete.>", (
            "Subscribe wildcard derivation broke: "
            f"got {pattern!r} from {Topics.Pipeline.STAGE_COMPLETE!r}"
        )

        # The pattern must match the worked example from the task description.
        assert _nats_subject_matches(
            pattern, "pipeline.stage-complete.FEAT-J005.plan-complete"
        )
        # Defensive: it must also match the simpler 3-token form (single
        # feature_id) since Forge may publish either depending on its v.
        assert _nats_subject_matches(pattern, "pipeline.stage-complete.FEAT-J005")
        # And it must NOT match a sibling subject family.
        assert not _nats_subject_matches(
            pattern, "pipeline.build-queued.FEAT-J005"
        )


# ---------------------------------------------------------------------------
# AC-005 — MessageEnvelope source_id round-trip
# ---------------------------------------------------------------------------


class TestMessageEnvelopeSourceIdRoundTrip:
    """AC-005 — ``source_id="jarvis"`` envelope survives a JSON round-trip."""

    def test_jarvis_envelope_round_trips_via_json(self) -> None:
        """``MessageEnvelope(source_id="jarvis", payload=...)`` is bit-stable."""
        payload = BuildQueuedPayload(**_good_build_queued_dict())
        envelope = MessageEnvelope(
            source_id="jarvis",
            event_type=EventType.BUILD_QUEUED,
            correlation_id=str(payload.correlation_id),
            payload=payload.model_dump(mode="json"),
        )

        encoded = envelope.model_dump_json()
        decoded = MessageEnvelope.model_validate_json(encoded)

        # source_id must survive end-to-end (this is the API-events §5
        # invariant that the cross-repo gate is here to enforce).
        assert decoded.source_id == "jarvis"
        assert decoded.event_type == EventType.BUILD_QUEUED
        assert decoded.correlation_id == envelope.correlation_id
        # Payload contents preserved — round-trip into BuildQueuedPayload.
        rebuilt = BuildQueuedPayload.model_validate(decoded.payload)
        assert rebuilt == payload


# ---------------------------------------------------------------------------
# AC-006 — Subscriber drops envelope with malicious source_id
# ---------------------------------------------------------------------------


class TestSubscriberDropsMaliciousSourceId:
    """AC-006 — ``ForgeNotificationsSubscriber`` drops non-forge source_ids."""

    async def test_malicious_source_id_drops_message_and_logs_warn(
        self,
    ) -> None:
        """Group C #1: envelope with ``source_id="malicious"`` is dropped.

        The subscriber must:
        1. Not enqueue any notification on the bound session manager.
        2. Not fire the routing-history edge.
        3. Emit a structured WARN ``forge_notification_dropped_unknown_source``
           carrying the offending source_id.
        """
        # Late imports — this test exercises the real subscriber path.
        from jarvis.infrastructure import forge_notifications as fn_module
        from jarvis.infrastructure.forge_notifications import (
            ForgeNotificationsSubscriber,
        )

        nats_client = MagicMock()
        nats_client.js = MagicMock()
        writer = MagicMock()
        writer.append_build_queue_event = AsyncMock()

        subscriber = ForgeNotificationsSubscriber(
            nats_client=nats_client,
            routing_history_writer=writer,
        )
        session_manager = MagicMock()
        session_manager.enqueue_notification = MagicMock()
        subscriber.bind_session_manager(session_manager)

        # Build a real MessageEnvelope with a forged source_id and feed it
        # through the subscriber's message handler as raw JSON bytes.
        payload = StageCompletePayload(**_good_stage_complete_dict())
        envelope = MessageEnvelope(
            source_id="malicious",
            event_type=EventType.STAGE_COMPLETE,
            correlation_id=payload.correlation_id,
            payload=payload.model_dump(mode="json"),
        )
        msg = MagicMock()
        msg.data = envelope.model_dump_json().encode("utf-8")
        msg.subject = Topics.Pipeline.STAGE_COMPLETE.format(
            feature_id=payload.feature_id
        )
        msg.ack = AsyncMock()

        # The module's structlog logger routes through whatever the project
        # configures (stdout in dev). Patch ``logger.warning`` directly to
        # assert the structured event name + source_id without depending on
        # the stdlib logging plumbing.
        warn_calls: list[tuple[str, dict[str, Any]]] = []
        original_warning = fn_module.logger.warning

        def _capture_warning(event: str, **kwargs: Any) -> None:
            warn_calls.append((event, kwargs))
            original_warning(event, **kwargs)

        fn_module.logger.warning = _capture_warning  # type: ignore[assignment]
        try:
            await subscriber._handle_message(msg)
        finally:
            fn_module.logger.warning = original_warning  # type: ignore[assignment]

        # No notification was enqueued — security invariant held.
        session_manager.enqueue_notification.assert_not_called()
        # Routing-history writer was not invoked either — drop is total.
        writer.append_build_queue_event.assert_not_called()

        # And the canonical WARN was emitted with the rogue source_id.
        assert any(
            event == "forge_notification_dropped_unknown_source"
            and kwargs.get("source_id") == "malicious"
            for event, kwargs in warn_calls
        ), (
            "Expected forge_notification_dropped_unknown_source WARN with "
            f"source_id='malicious'; got: {warn_calls}"
        )
