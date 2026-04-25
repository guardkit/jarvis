"""Dispatch tool primitives — capability-driven dispatch and build queueing.

This module hosts the two dispatch tools (``dispatch_by_capability`` and
``queue_build``) that connect Jarvis to the NATS event bus. In Phase 2
(FEAT-JARVIS-002) the real publish call is **stubbed**: the dispatch tools
construct real ``nats_core`` envelopes (``CommandPayload`` /
``BuildQueuedPayload`` / ``MessageEnvelope``) and then ``logger.info`` the
envelope contents instead of invoking ``nats.request(...)`` /
``js.publish(...)``. Phase 3 (FEAT-JARVIS-004 and FEAT-JARVIS-005) will
replace those log lines with real NATS round-trips without touching tool
docstrings or return shapes.

SWAP POINT
==========

DDR-009 names this module as the **single seam** through which Phase 3
features replace the stub transport with real NATS round-trips. The seam
has three named anchors that downstream features grep for and replace
verbatim:

1. ``_stub_response_hook`` — a module-level ``Callable`` attribute that
   test fixtures write to in order to simulate ``success`` / ``timeout`` /
   ``specialist_error`` round-trip outcomes. **FEAT-JARVIS-004 replaces
   ``_stub_response_hook`` with a real NATS request/reply round-trip**
   (``await nats.request(...)`` on the ``agents.command.{agent_id}``
   subject), removing the indirection entirely.

2. ``LOG_PREFIX_DISPATCH`` — string constant whose value is the grep
   anchor used by every ``logger.info`` line emitted from
   ``dispatch_by_capability``. FEAT-JARVIS-004 replaces those log calls
   with ``await nats.request(...)``.

3. ``LOG_PREFIX_QUEUE_BUILD`` — string constant whose value is the grep
   anchor used by every ``logger.info`` line emitted from ``queue_build``.
   FEAT-JARVIS-005 replaces those log calls with
   ``await js.publish(...)`` on the ``pipeline.build-queued.{x}`` subject.

Grep invariant (asserted by TASK-J002-021)
------------------------------------------
A grep for the values of ``LOG_PREFIX_DISPATCH`` and
``LOG_PREFIX_QUEUE_BUILD`` rooted at ``src/jarvis/`` returns exactly **two**
lines pre-feature wiring (the two constant definitions in this module) and
exactly **four** lines once TASK-J002-013 and TASK-J002-014 land (the two
constant definitions + one ``logger.info`` usage in each of the two
dispatch tools). Drift in this count signals an unauthorised second swap
point and fails CI.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypeAlias

from nats_core.events import CommandPayload, ResultPayload

# ---------------------------------------------------------------------------
# SWAP POINT — log prefixes (see module docstring).
#
# These two string constants are the DDR-009 grep anchors. Every
# ``logger.info`` call emitted from a dispatch tool MUST use one of these
# constants as the leading literal — never a hard-coded string — so that
# the grep-count invariant (TASK-J002-021) holds across rebases.
# ---------------------------------------------------------------------------
LOG_PREFIX_DISPATCH: str = "JARVIS_DISPATCH_STUB"
LOG_PREFIX_QUEUE_BUILD: str = "JARVIS_QUEUE_BUILD_STUB"


# ---------------------------------------------------------------------------
# SWAP POINT — stub response shape.
#
# ``StubResponse`` is the typed contract returned by ``_stub_response_hook``
# under the Phase 2 stub transport. The three variants are encoded as a
# tagged-tuple union so consumers can pattern-match on the leading literal:
#
#     match hook(command):
#         case ("success", result):    ...
#         case ("timeout",):           ...
#         case ("specialist_error", reason): ...
#
# Phase 3 (FEAT-JARVIS-004) removes the hook entirely; this alias is the
# stub-only contract and disappears with the swap.
# ---------------------------------------------------------------------------
StubResponse: TypeAlias = (
    tuple[Literal["success"], ResultPayload]
    | tuple[Literal["timeout"]]
    | tuple[Literal["specialist_error"], str]
)


# ---------------------------------------------------------------------------
# SWAP POINT — stub response hook (see module docstring).
#
# Default ``None`` means "use the canned ``("success", ResultPayload(...))``
# fallback inside ``dispatch_by_capability``". Test fixtures (and only test
# fixtures) write a callable here to simulate timeouts and specialist
# errors.
#
# FEAT-JARVIS-004 replaces this attribute with a real NATS request/reply
# round-trip and deletes the alias.
# ---------------------------------------------------------------------------
_stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None


__all__ = [
    "LOG_PREFIX_DISPATCH",
    "LOG_PREFIX_QUEUE_BUILD",
    "StubResponse",
    "_stub_response_hook",
]
