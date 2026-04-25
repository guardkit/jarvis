"""General-purpose tools for the Jarvis supervisor.

Hosts the four ``general`` tools consumed by the reasoning model via the
``jarvis.tools.assemble_tool_list`` factory:

* :func:`read_file` (TASK-J002-008)
* :func:`search_web` (TASK-J002-009)
* ``get_calendar_events`` (TASK-J002-010)
* ``calculate`` (TASK-J002-011)

Every tool function in this module is decorated with
``@tool(parse_docstring=True)`` and follows the structured-error pattern
defined by ADR-ARCH-021: tools never raise — internal errors are caught
and rendered as ``ERROR: <category> — <detail>`` strings the reasoning
model can read.

The docstrings of the tool functions in this module are the *authoritative*
contract surface (per the API-tools.md preamble): the reasoning model
reads them at decision time, so changes to text or examples constitute a
behaviour change.

Provider abstraction (DDR-006 swap point)
-----------------------------------------
:class:`TavilyProvider` wraps the ``langchain-tavily`` client. The grep
anchor ``class TavilyProvider`` is the single point a future feature
edits to swap to a different web-search provider — the
:func:`search_web` docstring talks about "the configured web-search
provider" and never names Tavily, so a swap does not change routing
behaviour.

Module-level configuration
--------------------------
:func:`search_web` resolves the active
:class:`~jarvis.config.settings.JarvisConfig` via the module-level
``_config`` reference. The wiring contract is:

1. ``jarvis.tools.assemble_tool_list(config, ...)`` (TASK-J002-015)
   calls :func:`configure` once at supervisor build time, before passing
   the tools to ``create_deep_agent``.
2. Test fixtures call :func:`configure` directly to inject a test
   config.
3. The tool reads ``_config`` lazily on each invocation so a
   re-configured value takes effect without re-decorating.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Final, Literal

from langchain_core.tools import tool
from pydantic import SecretStr

from jarvis.config.settings import JarvisConfig
from jarvis.tools.types import WebResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read-file size cap.
#
# The acceptance criterion (TASK-J002-008) defines a 1 MiB boundary:
#   * exactly 1 MiB (1048576 bytes) → accept and read the file
#   * 1 MiB + 1 byte                → reject with ``ERROR: too_large — ...``
#
# Using ``1024 * 1024`` keeps the constant readable and avoids any ambiguity
# between "MB" (decimal) and "MiB" (binary). The contract uses "1MB" in the
# error string only because that is the user-facing wording in API-tools.md
# §1.1; the boundary itself is the binary mebibyte.
# ---------------------------------------------------------------------------
MAX_FILE_BYTES: int = 1024 * 1024


__all__ = ["read_file", "get_calendar_events", "MAX_FILE_BYTES"]


# ---------------------------------------------------------------------------
# Calendar window allow-list — kept in lock-step with the ``Literal`` type
# alias so the docstring, the schema, and the runtime guard cannot drift
# out of sync. The tuple drives the runtime ``invalid_window`` check while
# the ``Literal`` alias drives the public schema (and the tool decorator's
# parse_docstring-derived JSON schema).
# ---------------------------------------------------------------------------
CalendarWindow = Literal["today", "tomorrow", "this_week"]
_ALLOWED_WINDOWS: Final[tuple[str, ...]] = ("today", "tomorrow", "this_week")


def _resolve_workspace_root() -> Path:
    """Return the configured workspace root, fully resolved.

    A fresh :class:`JarvisConfig` is constructed on each call so that
    ``JARVIS_WORKSPACE_ROOT`` env-var changes — including those installed by
    test fixtures via ``monkeypatch.setenv`` — take effect without a
    process restart. ``Path.resolve()`` collapses symlinks and ``..``
    segments so that the workspace boundary check below uses a canonical
    path.
    """
    return Path(JarvisConfig().workspace_root).resolve()


def _is_inside(candidate: Path, workspace: Path) -> bool:
    """Return ``True`` iff ``candidate`` lies at or below ``workspace``.

    ``Path.is_relative_to`` raises ``ValueError`` on some Python versions
    when the two paths share no common prefix; this helper coerces that
    into a plain ``False`` so callers can branch on a single boolean.
    """
    try:
        return candidate.is_relative_to(workspace)
    except ValueError:
        return False


@tool(parse_docstring=True)
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the user's workspace and return its contents.

    Use this tool when the user refers to a file on disk ("summarise /tmp/foo.md",
    "what's in my notes folder") or when you need file contents to answer. Do NOT
    use it for binary files or files outside the configured workspace root — those
    return a structured error.

    Near-zero cost, <100ms typical latency. No network I/O.

    Args:
        path: Absolute or workspace-relative path. Path traversal outside the
              workspace root is rejected.

    Returns:
        The file contents as a string, OR a structured error:
          - ``ERROR: path_traversal — path resolves outside workspace: <resolved>``
          - ``ERROR: not_found — path does not exist: <path>``
          - ``ERROR: not_a_file — path is a directory or special file: <path>``
          - ``ERROR: too_large — file exceeds 1MB, refusing to read: <path>``
          - ``ERROR: encoding — file is not valid UTF-8: <path>``
    """
    try:
        # ------------------------------------------------------------------
        # Reject embedded null bytes BEFORE any os.* call.
        #
        # POSIX paths terminate on NUL; Python's ``open()`` raises
        # ``ValueError("embedded null byte")`` for paths containing
        # ``\x00``. Per ASSUM-003 we treat this as a path-traversal class
        # rejection (rather than introducing a new error category).
        # ------------------------------------------------------------------
        if "\x00" in path:
            return (
                "ERROR: path_traversal — path contains embedded null byte"
            )

        workspace = _resolve_workspace_root()

        # Workspace-relative inputs are joined onto ``workspace``;
        # absolute inputs are accepted as-is and the realpath check
        # below catches any escape attempt.
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = workspace / candidate

        # ``os.path.realpath`` resolves symlinks AND ``..`` segments. This
        # is the single guard against both ``../etc/passwd``-style
        # traversal and symlink escapes (ASSUM-002): if the resolved
        # target lies outside ``workspace`` we reject regardless of how
        # the caller arrived at it.
        resolved = Path(os.path.realpath(candidate))

        if not _is_inside(resolved, workspace):
            return (
                "ERROR: path_traversal — path resolves outside workspace: "
                f"{resolved}"
            )

        if not resolved.exists():
            return f"ERROR: not_found — path does not exist: {path}"

        if not resolved.is_file():
            return (
                f"ERROR: not_a_file — path is a directory or special file: {path}"
            )

        size = resolved.stat().st_size
        if size > MAX_FILE_BYTES:
            return (
                f"ERROR: too_large — file exceeds 1MB, refusing to read: {path}"
            )

        try:
            return resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # The file exists and is the right size, but its bytes are
            # not valid UTF-8. Return the encoding error rather than
            # leaking the raw decode message.
            return f"ERROR: encoding — file is not valid UTF-8: {path}"
    except (PermissionError, OSError) as exc:
        # Permission or OS-level I/O issues are degenerate cases of
        # "we can't read this file" — surface them as not_found so the
        # reasoning model treats the path as unreadable rather than
        # crashing the tool turn.
        logger.warning("read_file OS error for %r: %s", path, exc)
        return f"ERROR: not_found — path does not exist: {path}"
    except Exception as exc:  # noqa: BLE001 — ADR-ARCH-021 catch-all
        # Catch-all per ADR-ARCH-021 / langchain-tool-decorator-specialist:
        # tools must never raise. Log with full stack so operators can
        # diagnose unexpected failures, then return a structured string.
        logger.exception("Unexpected error in read_file")
        return f"ERROR: not_found — read_file failed: {exc}"


@tool(parse_docstring=True)
def get_calendar_events(
    window: Literal["today", "tomorrow", "this_week"] = "today",
) -> str:
    """Return calendar events for a named time window.

    Use this tool when the user asks "what's on today", "do I have time next
    Thursday", or similar calendar-shaped questions. Prefer this over reasoning
    about the calendar from memory — the tool reads live data when a real
    provider is configured.

    STUB in Phase 2: returns an empty list ``[]`` (or a canned list configured
    for tests). Signature is stable — FEAT-JARVIS-007's morning-briefing skill
    depends on this shape. Near-zero cost, <50ms latency.

    Args:
        window: One of "today", "tomorrow", "this_week". Default "today".

    Returns:
        JSON array of CalendarEvent objects:
          ``[{"id": str, "title": str, "start": ISO8601, "end": ISO8601,
              "location": str | null, "description": str | null}, ...]``
        OR a structured error:
          - ``ERROR: invalid_window — must be one of today/tomorrow/this_week, got <value>``
    """
    # Defensive runtime guard. The ``Literal`` annotation already constrains
    # the JSON schema exposed to the reasoning model, but a direct Python
    # caller — or a test that exercises ``.func`` to bypass the pydantic
    # layer — may still pass an out-of-domain value. Per ADR-ARCH-021 we
    # never raise; we always return a structured ``ERROR:`` string.
    try:
        if window not in _ALLOWED_WINDOWS:
            return (
                "ERROR: invalid_window — must be one of "
                f"today/tomorrow/this_week, got {window}"
            )
        # Phase 2 stub — real provider lands in v1.5. The empty list is a
        # JSON array of ``CalendarEvent``-shaped dicts (zero of them, but
        # still an array) so FEAT-JARVIS-007's morning-briefing skill
        # parses identically against stub and real data.
        return json.dumps([])
    except Exception as exc:  # noqa: BLE001 — ADR-ARCH-021 catch-all
        # Belt-and-braces: the body above contains no raising operation,
        # but a defensive catch-all keeps the never-raises invariant
        # (AC-006) airtight against future edits.
        logger.exception("Unexpected error in get_calendar_events")
        return (
            "ERROR: invalid_window — must be one of "
            f"today/tomorrow/this_week, got {window!r} "
            f"(internal: {type(exc).__name__})"
        )
