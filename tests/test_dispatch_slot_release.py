"""Regression for the slot-release invariant — TASK-J004-017.

Pins the 5-row Scenario Outline at
``features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/
feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature`` line 352:

    Scenario Outline: The concurrent dispatch slot is released on every
                      dispatch outcome
        Examples:
          | outcome                |
          | success                |
          | timeout                |
          | specialist error       |
          | transport unavailable  |
          | unresolved             |

This is the canonical regression that protects DDR-020's
``DispatchSemaphore`` from silent slot-leak bugs across the closed
``DispatchOutcome`` set reachable from ``dispatch_by_capability`` —
specifically the five members (``success``, ``timeout``,
``specialist_error``, ``transport_unavailable``, ``unresolved``) for
which slot-release is the test's sole responsibility. The
``redirected`` and ``exhausted`` outcomes are owned by TASK-J004-015's
redirect matrix and are intentionally not exercised here.

Test shape per the task brief (Description §1–5):

1. Construct ``DispatchSemaphore(cap=2)`` so we can detect leaks via
   slot count.
2. Pre-acquire 1 slot — ``in_flight = 1`` going into the dispatch.
3. Trigger a dispatch matching the row's outcome.
4. Assert the dispatch returned the expected outcome string / error.
5. Assert ``semaphore.in_flight == 1`` at the end — only the
   pre-acquired slot remains, the dispatch released its own slot.

If a future regression silently drops the ``finally: release()`` from
``jarvis.tools.dispatch.dispatch_by_capability``, exactly one of these
five rows fails — pointing at the leaked outcome path.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats_core.events import ResultPayload

from jarvis.infrastructure.dispatch_semaphore import DispatchSemaphore
from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools import dispatch
from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary


# ---------------------------------------------------------------------------
# Helpers — encoded ResultPayload bodies for the in-process NATS substitute
# ---------------------------------------------------------------------------


def _success_result_bytes(*, command: str, correlation_id: str | None) -> bytes:
    """Encode a ``ResultPayload(success=True)`` for the happy-path row."""
    payload = ResultPayload(
        command=command,
        result={"verdict": "ok"},
        correlation_id=correlation_id,
        success=True,
    )
    return payload.model_dump_json().encode("utf-8")


def _failure_result_bytes(*, command: str, correlation_id: str | None) -> bytes:
    """Encode a ``ResultPayload(success=False)`` for the specialist-error row.

    The error text lives at ``result.error`` so
    :func:`jarvis.tools.dispatch._extract_specialist_error` finds it on its
    first key probe (matching the nats-core specialists' convention).
    """
    payload = ResultPayload(
        command=command,
        result={"error": "specialist refused — capacity exceeded"},
        correlation_id=correlation_id,
        success=False,
    )
    return payload.model_dump_json().encode("utf-8")


def _solo_specialist_registry() -> list[CapabilityDescriptor]:
    """Single-specialist registry — no redirect candidate available.

    The Outline rows that should produce ``specialist_error`` and
    ``timeout`` outcomes deliberately register exactly one specialist so
    the retry-with-redirect loop has nothing to fall back to. After the
    first failed attempt the loop's second iteration resolves to
    ``None`` and the call exits via the ``exhausted`` branch — the
    user-facing string is ``TIMEOUT: ... exhausted attempts=1``.
    """
    return [
        CapabilityDescriptor(
            agent_id="solo-specialist",
            role="Solo Specialist",
            description="Single registered specialist for slot-release tests.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="review_spec",
                    description="Review a feature spec.",
                    risk_level="read_only",
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Fixture — real DispatchSemaphore(cap=2) + stubbed NATS / writer / registry
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_dispatch_deps() -> Generator[dict[str, Any], None, None]:
    """Wire a *real* :class:`DispatchSemaphore` and stub everything else.

    The semaphore is real (not mocked) so ``in_flight`` reports the live
    counter — that's the property under test. The NATS client and
    routing-history writer are mocks so each Scenario Outline row can
    drive a specific outcome path through ``dispatch_by_capability``.

    The autouse ``_restore_dispatch_layer2_hooks`` fixture in
    ``tests/conftest.py`` already snapshots ``_nats_client``,
    ``_routing_history_writer`` and ``_dispatch_semaphore``; we
    additionally save/restore ``_capability_registry`` since the
    unresolved row mutates it.
    """
    saved_registry = dispatch._capability_registry

    semaphore = DispatchSemaphore(cap=2)

    nats_client = MagicMock()
    nats_client.request = AsyncMock()

    writer = MagicMock()
    writer.write_specialist_dispatch = AsyncMock(return_value=None)

    dispatch._nats_client = nats_client
    dispatch._dispatch_semaphore = semaphore
    dispatch._routing_history_writer = writer
    dispatch._capability_registry = _solo_specialist_registry()

    try:
        yield {
            "nats_client": nats_client,
            "semaphore": semaphore,
            "writer": writer,
        }
    finally:
        dispatch._capability_registry = saved_registry


async def _ainvoke(**kwargs: Any) -> str:
    """Invoke the @tool-wrapped async ``dispatch_by_capability``."""
    return await dispatch.dispatch_by_capability.ainvoke(kwargs)


# ---------------------------------------------------------------------------
# Per-row arrange callables — keep the parametrised body uniform
# ---------------------------------------------------------------------------


def _arrange_success(deps: dict[str, Any]) -> None:
    """Mock specialist replies success=True (row 1)."""
    nats_client = deps["nats_client"]

    async def _reply(subject: str, payload: bytes, *, timeout: float) -> Any:
        envelope = json.loads(payload.decode("utf-8"))
        cid = envelope["payload"]["correlation_id"]
        return MagicMock(
            data=_success_result_bytes(command="review_spec", correlation_id=cid)
        )

    nats_client.request.side_effect = _reply


def _arrange_timeout(deps: dict[str, Any]) -> None:
    """No reply ever — every NATS attempt raises TimeoutError (row 2)."""
    deps["nats_client"].request.side_effect = TimeoutError()


def _arrange_specialist_error(deps: dict[str, Any]) -> None:
    """Mock specialist replies success=False; no redirect candidate (row 3)."""
    nats_client = deps["nats_client"]

    async def _reply(subject: str, payload: bytes, *, timeout: float) -> Any:
        envelope = json.loads(payload.decode("utf-8"))
        cid = envelope["payload"]["correlation_id"]
        return MagicMock(
            data=_failure_result_bytes(command="review_spec", correlation_id=cid)
        )

    nats_client.request.side_effect = _reply


def _arrange_transport_unavailable(deps: dict[str, Any]) -> None:
    """``NATSClient.request`` raises ``NATSConnectionError`` (row 4)."""
    deps["nats_client"].request.side_effect = NATSConnectionError("broker down")


def _arrange_unresolved(deps: dict[str, Any]) -> None:
    """Stub ``_capability_registry`` to an empty list (row 5)."""
    dispatch._capability_registry = []


# ---------------------------------------------------------------------------
# Per-row outcome predicates — what the user-facing return string must be
# ---------------------------------------------------------------------------


def _is_success_payload(result: str) -> bool:
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return False
    return parsed.get("success") is True and parsed.get("command") == "review_spec"


def _is_timeout_string(result: str) -> bool:
    # Both the timeout row and the specialist-error row exit via the
    # ``exhausted`` branch, which surfaces as ``TIMEOUT: ... exhausted
    # attempts=N``. The slot-release invariant is what's under test, not
    # the exact wording — predicate stays minimal.
    return result.startswith("TIMEOUT:") and "exhausted" in result


def _is_transport_unavailable_string(result: str) -> bool:
    return result == "DEGRADED: transport_unavailable — NATS connection failed"


def _is_unresolved_string(result: str) -> bool:
    return result.startswith("ERROR: unresolved")


# ---------------------------------------------------------------------------
# The Scenario Outline regression — one parametrised test, five rows
# ---------------------------------------------------------------------------


class TestSlotReleasedOnEveryDispatchOutcome:
    """Scenario Outline: The concurrent dispatch slot is released on every
    dispatch outcome (.feature line 352, FEAT-JARVIS-004 Group E).

    Rows (closed five-set):

      | row | outcome              | setup                                        |
      | --- | -------------------- | -------------------------------------------- |
      |  1  | success              | mock specialist replies success=True         |
      |  2  | timeout              | NATSClient.request raises TimeoutError       |
      |  3  | specialist_error     | mock specialist replies success=False        |
      |  4  | transport_unavailable| NATSClient.request raises NATSConnectionError|
      |  5  | unresolved           | _capability_registry empty — no match        |

    AC-001 — one parametrised test with 5 rows.
    AC-002 — every row asserts ``in_flight == 1`` after the dispatch.
    AC-003 — no row uses ``pytest.xfail`` or ``pytest.skip``.
    AC-004 — ``redirected`` / ``exhausted`` are NOT covered (TASK-J004-015).
    AC-005 — ``uv run pytest tests/test_dispatch_slot_release.py -v`` green.
    """

    @pytest.mark.parametrize(
        ("outcome_label", "arrange", "is_expected_result"),
        [
            ("success", _arrange_success, _is_success_payload),
            ("timeout", _arrange_timeout, _is_timeout_string),
            ("specialist_error", _arrange_specialist_error, _is_timeout_string),
            (
                "transport_unavailable",
                _arrange_transport_unavailable,
                _is_transport_unavailable_string,
            ),
            ("unresolved", _arrange_unresolved, _is_unresolved_string),
        ],
        ids=[
            "row1-success",
            "row2-timeout",
            "row3-specialist_error",
            "row4-transport_unavailable",
            "row5-unresolved",
        ],
    )
    async def test_slot_released_on_every_dispatch_outcome(
        self,
        patched_dispatch_deps: dict[str, Any],
        outcome_label: str,
        arrange: Callable[[dict[str, Any]], None],
        is_expected_result: Callable[[str], bool],
    ) -> None:
        # Arrange — configure the row-specific outcome path, then pre-acquire
        # one slot so ``in_flight = 1`` going into the dispatch (cap=2 leaves
        # exactly one slot for the dispatch itself; a leak would drop the
        # cap-2 ceiling to 1 and surface here).
        arrange(patched_dispatch_deps)

        semaphore: DispatchSemaphore = patched_dispatch_deps["semaphore"]
        assert semaphore.try_acquire() is True
        assert semaphore.in_flight == 1, "pre-condition: one slot held"

        # Act — dispatch a request that will route through this row's
        # outcome path. The minimum legal ``timeout_seconds`` is 5 (the
        # tool-boundary validator rejects values < 5); the row 2 mock
        # raises TimeoutError synchronously so wall-clock duration is
        # negligible regardless.
        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=5,
        )

        # Assert — outcome string matches expectation AND the slot was
        # released. Slot release is the regression invariant — assert it
        # explicitly with a row-tagged message so a leak points at the
        # exact outcome path that broke.
        assert is_expected_result(result), (
            f"row '{outcome_label}' produced unexpected result: {result!r}"
        )
        assert semaphore.in_flight == 1, (
            f"slot leaked on '{outcome_label}' — "
            f"in_flight={semaphore.in_flight}, expected 1 "
            f"(pre-acquired slot only; dispatch must release its own)"
        )


# ---------------------------------------------------------------------------
# Type-level guard — keep the import / typing surface honest
# ---------------------------------------------------------------------------

_AwaitableSetup = Callable[[dict[str, Any]], None]
_AwaitableInvoke = Callable[..., Awaitable[str]]
__all__: list[str] = [
    "TestSlotReleasedOnEveryDispatchOutcome",
]
