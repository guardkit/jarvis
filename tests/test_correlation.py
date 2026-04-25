"""Tests for ``jarvis.tools._correlation`` — the dispatch-path correlation ID primitive.

Covers TASK-J002-005 acceptance criteria:

- AC-001: ``new_correlation_id() -> str`` returns ``str(uuid.uuid4())``.
- AC-002: Single dependency — only the stdlib ``uuid`` module.
- AC-003: 10,000 invocations → 10,000 distinct UUID4-formatted strings.
- AC-004: 100 threads x 100 calls each -> 10,000 distinct strings (no
  cross-contamination).
- AC-005: Module docstring names this as the single callsite per ASSUM-001.
"""

from __future__ import annotations

import ast
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jarvis.tools import _correlation
from jarvis.tools._correlation import new_correlation_id

# RFC 4122 / Python ``uuid.uuid4()`` formatted string:
#   8-4-4-4-12 lowercase hex digits, with version nibble == 4 and variant
#   nibble in {8, 9, a, b}.
UUID4_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

MODULE_PATH = Path(_correlation.__file__).resolve()


class TestAC001ReturnTypeAndShape:
    """AC-001: ``new_correlation_id() -> str`` returns ``str(uuid.uuid4())``."""

    def test_new_correlation_id_returns_str(self) -> None:
        result = new_correlation_id()
        assert isinstance(result, str)

    def test_new_correlation_id_returns_uuid4_formatted_string(self) -> None:
        result = new_correlation_id()
        # Must round-trip through uuid.UUID and report version 4.
        parsed = uuid.UUID(result)
        assert parsed.version == 4
        assert UUID4_REGEX.match(result), f"Result {result!r} does not match UUID4 regex"


class TestAC002SingleStdlibDependency:
    """AC-002: Module imports only ``uuid`` from stdlib. No other imports."""

    def test_module_has_only_uuid_import(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                # Any ``from X import Y`` (including ``__future__``) is an
                # additional dependency for the purposes of AC-002.
                module_name = node.module or ""
                imports.append(module_name)

        assert imports == ["uuid"], (
            f"Module must import only stdlib 'uuid'; found imports: {imports}"
        )


class TestAC003UniquenessAndFormat:
    """AC-003: 10,000 invocations → 10,000 distinct UUID4-formatted strings."""

    def test_ten_thousand_invocations_are_all_distinct_and_well_formed(self) -> None:
        ids = [new_correlation_id() for _ in range(10_000)]

        # Distinctness — collision odds for UUID4 over 10k draws are ~1e-32.
        assert len(set(ids)) == 10_000, f"Expected 10,000 distinct IDs; got {len(set(ids))}"

        # Format — every single string matches the UUID4 regex.
        non_matching = [cid for cid in ids if not UUID4_REGEX.match(cid)]
        assert non_matching == [], (
            f"{len(non_matching)} IDs failed UUID4 regex; first: {non_matching[:3]}"
        )


class TestAC004ConcurrentGenerationDoesNotCrossContaminate:
    """AC-004: 100 threads x 100 calls each -> 10,000 distinct strings."""

    def test_100_threads_x_100_calls_yield_10000_distinct_ids(self) -> None:
        def worker(_: int) -> list[str]:
            return [new_correlation_id() for _ in range(100)]

        with ThreadPoolExecutor(max_workers=100) as pool:
            results = list(pool.map(worker, range(100)))

        all_ids = [cid for batch in results for cid in batch]
        assert len(all_ids) == 10_000
        assert len(set(all_ids)) == 10_000, (
            "Concurrent generation produced duplicates — "
            f"{10_000 - len(set(all_ids))} collisions detected"
        )
        # Sanity: every concurrent result is still UUID4-formatted.
        assert all(UUID4_REGEX.match(cid) for cid in all_ids)


class TestAC005ModuleDocstringNamesSingleCallsite:
    """AC-005: Module docstring names this as the single callsite per ASSUM-001."""

    def test_module_docstring_mentions_single_callsite_and_assum_001(self) -> None:
        docstring = _correlation.__doc__ or ""
        lowered = docstring.lower()
        assert "single" in lowered and "callsite" in lowered, (
            "Module docstring must name this as the 'single callsite' for "
            "dispatch-path correlation IDs"
        )
        assert "dispatch" in lowered and "correlation" in lowered, (
            "Module docstring must mention dispatch-path correlation IDs"
        )
        assert "ASSUM-001" in docstring, "Module docstring must reference ASSUM-001"
