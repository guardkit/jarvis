"""Single callsite for dispatch-path correlation IDs (per ASSUM-001).

This module is the **single, canonical callsite** for generating correlation
IDs used by Jarvis dispatch-path tooling (``dispatch_by_capability``,
``queue_build``, and any future dispatch-style tools that emit log lines or
trace events). Per ASSUM-001 in
``docs/architecture/assumptions.yaml``, every dispatch invocation is tagged
with a fresh UUID4 produced by :func:`new_correlation_id` so concurrent
dispatches are isolated by construction — there is no shared state, no
counter, no lock, and no module-level mutability that could cross-contaminate
two in-flight dispatches.

Concurrency safety
------------------
``uuid.uuid4()`` reads from the operating system's CSPRNG and constructs a
fresh ``UUID`` object on each call. No module-level state is mutated, so the
function is safe to call from many threads (or many asyncio tasks) without
any synchronisation. The contract enforced by AC-004 is that 100 threads x
100 calls each must produce 10,000 distinct strings.

Why a dedicated module
----------------------
Centralising the primitive here lets us grep for a single import to audit
**all** dispatch-path correlation-ID generation across the codebase, and lets
us swap the implementation (e.g. to a structured ID prefixed with the request
source) in exactly one place if ASSUM-001 is ever revised.
"""

import uuid


def new_correlation_id() -> str:
    """Return a fresh UUID4 string suitable for a dispatch correlation ID.

    Returns:
        The string representation of a freshly generated random UUID
        (RFC 4122 variant 1, version 4) — for example
        ``"f47ac10b-58cc-4372-a567-0e02b2c3d479"``.
    """
    return str(uuid.uuid4())
