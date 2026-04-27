# Tool docstrings are reproduced *byte-for-byte* from
# docs/design/FEAT-JARVIS-002/contracts/API-tools.md. The contract uses
# Unicode en-dashes; the reasoning model reads docstrings verbatim, so we
# deliberately preserve those characters rather than substitute ASCII
# hyphens. The project-wide RUF002 silence is pinned in pyproject.toml's
# `[tool.ruff.lint.per-file-ignores]` for `src/jarvis/**` (FEAT-J002F-001).
"""General-purpose tools for the Jarvis supervisor.

Hosts the four ``general`` tools consumed by the reasoning model via the
``jarvis.tools.assemble_tool_list`` factory:

* :func:`read_file` (TASK-J002-008) — implemented in this module
* :func:`search_web` (TASK-J002-009) — implemented in this module
* ``get_calendar_events`` (TASK-J002-010) — lands separately
* ``calculate`` (TASK-J002-011) — implemented in this module

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
import re
from pathlib import Path
from typing import Any, Final, Literal

from asteval import Interpreter  # type: ignore[import-untyped]
from langchain_core.tools import tool

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


__all__ = [
    "MAX_FILE_BYTES",
    "TavilyProvider",
    "calculate",
    "configure",
    "get_calendar_events",
    "read_file",
    "search_web",
]


# ---------------------------------------------------------------------------
# Module-level configuration consumed by :func:`search_web`.
#
# ``assemble_tool_list`` (TASK-J002-015) and tests write here via
# :func:`configure`. The tool reads it on each call so a re-configured
# value takes effect without re-decorating.
# ---------------------------------------------------------------------------
_config: JarvisConfig | None = None


def configure(config: JarvisConfig | None) -> None:
    """Inject (or clear) the active :class:`JarvisConfig`.

    ``assemble_tool_list`` (TASK-J002-015) calls this once at supervisor
    build time. Tests call this in setup/teardown to swap a test config
    in and out. Passing ``None`` clears the active config — useful for
    isolating the ``config_missing`` branch in tests.
    """
    global _config
    _config = config


# ---------------------------------------------------------------------------
# DDR-006 swap-point grep anchor: ``class TavilyProvider``.
#
# A future FEAT replacing the provider edits exactly this class (and the
# module-level ``_provider_factory`` reference below) without changing
# the :func:`search_web` docstring or the returned ``WebResult`` shape.
# ---------------------------------------------------------------------------
class TavilyProvider:
    """Web-search provider wrapping the ``langchain-tavily`` client.

    The :func:`search_web` tool depends on this class only — it never
    imports from ``langchain_tavily`` directly. To swap providers (e.g.
    Bing, SerpAPI), implement the same ``search`` method on a
    replacement class and rebind ``_provider_factory`` to it.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, max_results: int) -> dict[str, Any]:
        """Run a Tavily search and return the raw response dict.

        Raises whatever the underlying client raises on failure; the
        tool boundary in :func:`search_web` converts every exception
        into the structured ``DEGRADED:`` error string per ADR-ARCH-021.

        Args:
            query: Non-empty search query.
            max_results: Maximum number of results, already validated
                against the documented [1, 10] range by the caller.

        Returns:
            The provider's raw response dict — typically with a
            ``"results"`` key holding a list of result dicts.
        """
        # Imported lazily so test fixtures can monkeypatch
        # ``_provider_factory`` without paying the langchain-tavily
        # import cost at module-load time.
        from langchain_tavily import TavilySearch

        client = TavilySearch(
            tavily_api_key=self._api_key,
            max_results=max_results,
        )
        response = client.invoke({"query": query})
        if not isinstance(response, dict):
            raise RuntimeError(f"non-dict response: {type(response).__name__}")
        return response


# ---------------------------------------------------------------------------
# Provider factory indirection so tests can monkeypatch a fake provider
# without touching the network. Default callable returns a real
# :class:`TavilyProvider`. Tests assign a stub callable to this name.
# ---------------------------------------------------------------------------
_provider_factory: Any = TavilyProvider


def _resolve_api_key(config: JarvisConfig | None) -> str | None:
    """Return the configured Tavily API key, or ``None`` if absent.

    ``JarvisConfig.tavily_api_key`` is typed as ``SecretStr | None`` so
    after the early ``None`` return the only remaining branch is the
    SecretStr unwrap. (Earlier revisions kept a ``str`` fallback arm,
    but the config schema has narrowed since — strict mypy flagged it
    as unreachable. Removed in FEAT-J002F-001.)
    """
    if config is None:
        return None
    raw = config.tavily_api_key
    if raw is None:
        return None
    secret = raw.get_secret_value()
    return secret or None


def _coerce_results(
    raw_results: list[Any],
    max_results: int,
) -> list[dict[str, Any]]:
    """Convert raw provider result dicts into ``WebResult`` JSON dicts.

    Skips entries that fail validation — e.g. a result with no URL — so
    a single bad row does not poison the whole batch. Hostile content
    in the snippet field is preserved verbatim per ASSUM-004: the tool
    surfaces it as data, never acts on it.
    """
    coerced: list[dict[str, Any]] = []
    for entry in raw_results[:max_results]:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title")
        url = entry.get("url")
        if not isinstance(title, str) or not title:
            continue
        if not isinstance(url, str) or not url:
            continue
        # Tavily returns the textual extract under ``content``; the
        # WebResult API exposes the same field as ``snippet``.
        snippet_raw = entry.get("content")
        if snippet_raw is None:
            snippet_raw = entry.get("snippet", "")
        if not isinstance(snippet_raw, str):
            snippet_raw = str(snippet_raw)
        score_raw = entry.get("score", 0.0)
        try:
            score = float(score_raw) if score_raw is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        # Clamp score into [0.0, 1.0] — providers occasionally emit
        # values just outside the band and WebResult validation would
        # otherwise reject the (otherwise valid) row.
        if score < 0.0:
            score = 0.0
        elif score > 1.0:
            score = 1.0
        try:
            web = WebResult(
                title=title,
                url=url,
                snippet=snippet_raw,
                score=score,
            )
        except Exception:
            # ADR-ARCH-021 — never raise across the tool boundary; skip
            # the malformed row and continue with the remainder.
            continue
        coerced.append(web.model_dump())
    return coerced


@tool(parse_docstring=True)
def search_web(query: str, max_results: int = 5) -> str:
    """Run a web search and return up to N results as JSON.

    Use this tool for factual lookups, recent information, or when the user asks
    you to find something online. Prefer over invoking a subagent for simple
    lookups — the subagent cost and latency are higher. Do NOT use it for
    knowledge already in the conversation or for reasoning tasks.

    Moderate cost (~$0.005/query via Tavily), ~1–3s typical latency.
    Requires TAVILY_API_KEY configured; returns a structured error otherwise.

    Args:
        query: The search query string. Non-empty.
        max_results: Maximum number of results to return (1–10). Default 5.

    Returns:
        JSON array of WebResult objects:
          ``[{"title": str, "url": str, "snippet": str, "score": float}, ...]``
        OR a structured error:
          - ``ERROR: config_missing — tavily_api_key not set in JarvisConfig``
          - ``ERROR: invalid_query — query must be non-empty``
          - ``ERROR: invalid_max_results — must be between 1 and 10, got <n>``
          - ``DEGRADED: provider_unavailable — Tavily returned <status>``
    """
    try:
        # ---- Argument validation (cheapest checks first) -------------------
        if not isinstance(query, str) or not query.strip():
            return "ERROR: invalid_query — query must be non-empty"
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            return f"ERROR: invalid_max_results — must be between 1 and 10, got {max_results!r}"
        if max_results < 1 or max_results > 10:
            return f"ERROR: invalid_max_results — must be between 1 and 10, got {max_results}"

        # ---- Provider configuration ----------------------------------------
        api_key = _resolve_api_key(_config)
        if api_key is None:
            return "ERROR: config_missing — tavily_api_key not set in JarvisConfig"

        # ---- Provider call (every exception becomes DEGRADED) --------------
        try:
            provider = _provider_factory(api_key)
            response = provider.search(query, max_results)
        except Exception as exc:
            # ADR-ARCH-021 — provider exceptions become structured errors.
            logger.warning("search_web provider error: %s", exc)
            return f"DEGRADED: provider_unavailable — Tavily returned {exc}"

        # ---- Provider response shape checks --------------------------------
        if not isinstance(response, dict):
            return (
                "DEGRADED: provider_unavailable — Tavily returned "
                f"non-dict response ({type(response).__name__})"
            )
        if "error" in response and response["error"] is not None:
            return f"DEGRADED: provider_unavailable — Tavily returned {response['error']}"
        explicit_status = response.get("status")
        if explicit_status not in (None, "success", 200, "ok", "OK"):
            return f"DEGRADED: provider_unavailable — Tavily returned {explicit_status}"

        raw_results = response.get("results")
        if raw_results is None:
            return "DEGRADED: provider_unavailable — Tavily returned no results"
        if not isinstance(raw_results, list):
            return (
                "DEGRADED: provider_unavailable — Tavily returned "
                f"malformed results ({type(raw_results).__name__})"
            )

        coerced = _coerce_results(raw_results, max_results)
        return json.dumps(coerced)

    except Exception as exc:
        # ADR-ARCH-021 last-line never-raise guard.
        logger.exception("search_web unexpected failure: %s", exc)
        return f"DEGRADED: provider_unavailable — Tavily returned {exc}"


# ---------------------------------------------------------------------------
# ``calculate`` — safe expression evaluation (TASK-J002-011 / DDR-007)
# ---------------------------------------------------------------------------
# Each entry pairs a regular expression with the canonical token label that
# appears in the structured error string. Order matters: the more specific
# patterns (e.g. ``__import__``) come before broader ones (e.g. ``__``) so
# the most informative label wins when two patterns start at the same offset.
# A label of ``None`` means "echo the matched substring back to the caller"
# — useful for the dunder pattern where reporting the actual ``__import__``
# / ``__class__`` text is more informative than a generic ``__`` placeholder.
_UNSAFE_PATTERNS: Final[tuple[tuple[re.Pattern[str], str | None], ...]] = (
    # Newlines: multi-line input is rejected outright (DDR-007 §Decision-1).
    (re.compile(r"\n"), "\\n"),
    # Dunder access (covers ``__import__``, ``__class__``, ``_x.__y__`` etc.).
    # ``None`` echoes the matched substring back so ``__import__('os')``
    # reports ``disallowed token: __import__``.
    (re.compile(r"__\w+__?"), None),
    # Reserved keywords that must never appear in an arithmetic expression.
    (re.compile(r"\blambda\b"), "lambda"),
    (re.compile(r"\bdef\b"), "def"),
    (re.compile(r"\bclass\b"), "class"),
    (re.compile(r"\bimport\b"), "import"),
    # ``open(...)`` / bare ``open`` — the only built-in callable name we
    # care about that the asteval symbol table does not strip but whose
    # mere appearance in a user-visible expression should be flagged.
    (re.compile(r"\bopen\s*\("), "open"),
    # Bare assignment ``=`` that isn't part of ``==``, ``!=``, ``>=``, ``<=``.
    (re.compile(r"(?<![=!<>])=(?!=)"), "="),
)


# ``X% of Y`` shorthand → ``(X/100 * Y)``. The pattern is intentionally
# narrow — the modulo operator (``X % Y`` with no "of") is unaffected.
_PERCENT_OF_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*of\s+(\d+(?:\.\d+)?)",
    flags=re.IGNORECASE,
)


def _detect_unsafe_token(expression: str) -> str | None:
    """Return the canonical label of the first disallowed token, else ``None``.

    Scans every pattern in :data:`_UNSAFE_PATTERNS` and returns the label
    whose match starts earliest in the source. Ties are broken by the order
    of declaration (most specific first), so dunder access is reported as
    ``__import__`` / ``__class__`` rather than ``=`` for inputs like
    ``"x.__class__"``.

    A pattern's label may be ``None`` to indicate "report the matched
    substring itself", which keeps the structured error informative for
    families of tokens (every dunder name is reported verbatim).
    """
    earliest: tuple[int, str] | None = None
    for pattern, label in _UNSAFE_PATTERNS:
        match = pattern.search(expression)
        if match is None:
            continue
        token = label if label is not None else match.group(0)
        # Trim trailing punctuation (e.g. the ``(`` from ``open(``) so the
        # error string mentions the offending name only.
        token = token.rstrip("(").rstrip()
        if earliest is None or match.start() < earliest[0]:
            earliest = (match.start(), token)
    return None if earliest is None else earliest[1]


def _normalise_percent_of(expression: str) -> str:
    """Rewrite ``X% of Y`` as ``(X/100 * Y)`` (case-insensitive).

    Returns the input unchanged when the pattern is not present so the
    modulo operator and unrelated whitespace survive untouched.
    """
    return _PERCENT_OF_PATTERN.sub(r"(\1/100 * \2)", expression)


def _format_calculate_result(value: object) -> str:
    """Render the ``asteval`` result as a clean numeric string.

    Per DDR-007 §Decision-6: integers use :func:`repr` (the bare decimal
    form); floats use ``f"{value:g}"`` to drop IEEE-754 trailing-zero
    noise. Booleans (a subclass of ``int``) are coerced to ``"True"`` /
    ``"False"`` via :func:`str`.
    """
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return repr(value)
    if isinstance(value, float):
        if value != value:  # NaN — keep distinguishable from a number
            return "nan"
        return f"{value:g}"
    return str(value)


def _evaluate_expression(expression: str) -> str:
    """Safely evaluate ``expression`` and return a contract-compliant string.

    Pre-filters unsafe tokens, normalises ``X% of Y`` shorthand, evaluates
    via :class:`asteval.Interpreter`, and converts every failure mode into
    one of the four canonical error strings documented in API-tools.md
    §1.4. Never raises — the public :func:`calculate` tool relies on this
    invariant to honour ADR-ARCH-021.
    """
    stripped = expression.strip()
    if not stripped:
        return "ERROR: parse_error — empty expression"

    token = _detect_unsafe_token(expression)
    if token is not None:
        return f"ERROR: unsafe_expression — disallowed token: {token}"

    normalised = _normalise_percent_of(stripped)

    # ``asteval.Interpreter()`` ships with the math allow-list pre-populated
    # (sqrt, log, exp, sin, cos, tan, abs, min, max, round, plus the
    # operators we need). ``no_print=True`` suppresses any stray ``print``
    # output the user expression might attempt.
    interp = Interpreter(no_print=True)

    try:
        result = interp(normalised, show_errors=False, raise_errors=False)
    except Exception as exc:  # pragma: no cover — asteval should not raise
        # Defensive: ADR-ARCH-021 forbids propagation across the boundary.
        logger.warning("asteval raised unexpectedly for %r: %s", expression, exc)
        return f"ERROR: parse_error — {type(exc).__name__}: {exc}"

    # asteval reports every error via ``interp.error`` (a list of
    # ``ExceptionHolder``). The first entry carries the originating
    # exception class and message.
    if interp.error:
        first = interp.error[0]
        exc_cls = getattr(first, "exc", None)
        msg = getattr(first, "msg", "") or ""
        if exc_cls is ZeroDivisionError:
            return "ERROR: division_by_zero"
        if exc_cls is OverflowError:
            return "ERROR: overflow — result exceeds float range"
        text = str(msg).strip()
        if text:
            detail = text.splitlines()[0]
        elif exc_cls is not None:
            detail = exc_cls.__name__
        else:
            detail = "unknown error"
        return f"ERROR: parse_error — {detail}"

    if result is None:
        # No reported error and no value: treat as an unparseable input.
        return "ERROR: parse_error — expression produced no value"

    # Boundary-trap arithmetic explosions that ``asteval`` did not surface
    # via ``interp.error`` (e.g. ``float('inf')`` slipping through).
    if isinstance(result, float) and (result == float("inf") or result == float("-inf")):
        return "ERROR: overflow — result exceeds float range"

    return _format_calculate_result(result)


@tool(parse_docstring=True)
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely and return the result.

    Use this tool for ANY arithmetic — percentages, unit conversion, compound
    calculations. You are bad at arithmetic; the tool is not. Do NOT use it for
    symbolic manipulation, calculus, or anything that requires an algebra
    system — those return a structured error.

    Near-zero cost, <10ms latency. No network I/O.

    Args:
        expression: A mathematical expression. Supported operators: + - * / ** % and parentheses. Supported functions: sqrt, log, exp, sin, cos, tan, abs, min, max, round. Variables are NOT supported.

    Returns:
        The result as a string (numeric or truthy), OR a structured error:
          - ``ERROR: unsafe_expression — disallowed token: <token>``
          - ``ERROR: parse_error — <detail>``
          - ``ERROR: division_by_zero``
          - ``ERROR: overflow — result exceeds float range``
    """  # noqa: E501 — Args line must be one line for parse_docstring=True
    # The tool boundary MUST NOT raise (ADR-ARCH-021). Every failure mode is
    # converted to a structured string inside ``_evaluate_expression``; the
    # ``except`` here is a last-resort backstop in case the evaluator itself
    # misbehaves — diagnostic only and never expected on the happy path.
    try:
        return _evaluate_expression(expression)
    except Exception as exc:
        logger.exception("calculate(%r) failed unexpectedly", expression)
        return f"ERROR: parse_error — {type(exc).__name__}: {exc}"


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
            return "ERROR: path_traversal — path contains embedded null byte"

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
            return f"ERROR: path_traversal — path resolves outside workspace: {resolved}"

        if not resolved.exists():
            return f"ERROR: not_found — path does not exist: {path}"

        if not resolved.is_file():
            return f"ERROR: not_a_file — path is a directory or special file: {path}"

        size = resolved.stat().st_size
        if size > MAX_FILE_BYTES:
            return f"ERROR: too_large — file exceeds 1MB, refusing to read: {path}"

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
    except Exception as exc:
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
    # Defensive runtime guard. The Literal annotation already constrains
    # the JSON schema exposed to the reasoning model, but a direct Python
    # caller may still pass an out-of-domain value. Per ADR-ARCH-021 we
    # never raise; we always return a structured ERROR string.
    try:
        if window not in _ALLOWED_WINDOWS:
            return f"ERROR: invalid_window — must be one of today/tomorrow/this_week, got {window}"
        # Phase 2 stub — real provider lands in v1.5.
        return json.dumps([])
    except Exception as exc:
        # Belt-and-braces last-resort guard. The body above contains no
        # raising operation, but the catch-all keeps the never-raises
        # invariant (AC-006) airtight against future edits.
        logger.exception("Unexpected error in get_calendar_events")
        return (
            "ERROR: invalid_window — must be one of "
            f"today/tomorrow/this_week, got {window!r} "
            f"(internal: {type(exc).__name__})"
        )
