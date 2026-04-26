"""Tests for :class:`jarvis.adapters.llamaswap.LlamaSwapAdapter`.

Covers TASK-J003-007 acceptance criteria:

- AC-001: ``LlamaSwapAdapter`` exposes the test-seam constructor
  ``__init__(self, base_url: str, *, _stub_response=None)`` where
  ``_stub_response`` is keyword-only.
- AC-002: ``get_status`` defaults to a ``loaded`` snapshot
  (``eta_seconds=0``, ``source="stub"``) when no stub is supplied.
- AC-003: when ``_stub_response`` is supplied, its return value is
  forwarded unchanged — the adapter does not interpret the ETA.
- AC-004: ``get_status`` is pure / idempotent. Repeated calls for the
  same alias return equivalent values; no internal counter mutation.
- AC-005: ``jarvis.adapters`` re-exports ``LlamaSwapAdapter``.
- AC-006: no ``httpx`` / ``requests`` symbol is referenced at runtime;
  importing the module triggers no outbound HTTP.
- AC-007: docstring names the live ``/running`` and ``/log`` endpoint
  paths so FEAT-JARVIS-004 can grep for them at swap time.
"""

from __future__ import annotations

import inspect
import pathlib
import sys

import pytest

from jarvis.adapters.llamaswap import LlamaSwapAdapter
from jarvis.adapters.types import SwapStatus

# ---------------------------------------------------------------------------
# AC-001 — constructor signature
# ---------------------------------------------------------------------------


class TestAC001ConstructorSignature:
    """``__init__(self, base_url: str, *, _stub_response=None)``."""

    def test_construct_with_only_base_url_succeeds(self) -> None:
        adapter = LlamaSwapAdapter("http://promaxgb10-41b1:9000")

        assert adapter.base_url == "http://promaxgb10-41b1:9000"

    def test_stub_response_is_keyword_only(self) -> None:
        sig = inspect.signature(LlamaSwapAdapter.__init__)
        param = sig.parameters["_stub_response"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY

    def test_stub_response_default_is_none(self) -> None:
        sig = inspect.signature(LlamaSwapAdapter.__init__)
        assert sig.parameters["_stub_response"].default is None

    def test_passing_stub_response_positionally_raises_type_error(self) -> None:
        def stub(_alias: str) -> SwapStatus:
            return SwapStatus(loaded_model=_alias, eta_seconds=0, source="stub")

        with pytest.raises(TypeError):
            # Keyword-only — positional must fail.
            LlamaSwapAdapter("http://x", stub)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-002 — default get_status returns loaded snapshot
# ---------------------------------------------------------------------------


class TestAC002DefaultGetStatusReturnsLoadedSnapshot:
    """Without ``_stub_response`` the adapter assumes the alias is loaded."""

    def test_default_get_status_returns_eta_zero_stub_source(self) -> None:
        adapter = LlamaSwapAdapter("http://promaxgb10-41b1:9000")

        result = adapter.get_status("qwen3-coder")

        assert result == SwapStatus(loaded_model="qwen3-coder", eta_seconds=0, source="stub")

    def test_default_get_status_loaded_model_matches_requested_alias(self) -> None:
        adapter = LlamaSwapAdapter("http://x:9000")

        result = adapter.get_status("some-other-alias")

        assert result.loaded_model == "some-other-alias"
        assert result.eta_seconds == 0
        assert result.source == "stub"

    def test_default_get_status_returns_swapstatus_instance(self) -> None:
        adapter = LlamaSwapAdapter("http://x:9000")

        result = adapter.get_status("alias-1")

        assert isinstance(result, SwapStatus)


# ---------------------------------------------------------------------------
# AC-003 — _stub_response forwarded unchanged
# ---------------------------------------------------------------------------


class TestAC003StubResponseForwardedUnchanged:
    """The adapter forwards the test-seam value verbatim — no ETA logic."""

    def test_high_eta_stub_returned_unchanged(self) -> None:
        sentinel = SwapStatus(loaded_model="qwen3-coder", eta_seconds=180, source="stub")
        adapter = LlamaSwapAdapter("http://x:9000", _stub_response=lambda _alias: sentinel)

        result = adapter.get_status("qwen3-coder")

        # Equivalence by value (frozen Pydantic models hash by field tuple).
        assert result == sentinel
        assert result.eta_seconds == 180

    def test_stub_response_alias_is_forwarded_to_callable(self) -> None:
        captured: list[str] = []

        def stub(alias: str) -> SwapStatus:
            captured.append(alias)
            return SwapStatus(loaded_model=alias, eta_seconds=42, source="stub")

        adapter = LlamaSwapAdapter("http://x:9000", _stub_response=stub)
        adapter.get_status("alias-A")
        adapter.get_status("alias-B")

        assert captured == ["alias-A", "alias-B"]

    def test_stub_response_live_source_propagates(self) -> None:
        # FEAT-JARVIS-004 will swap the stub for a live probe — when the
        # injected callable returns ``source="live"`` the adapter must not
        # rewrite it back to ``"stub"``.
        live = SwapStatus(loaded_model="x", eta_seconds=5, source="live")
        adapter = LlamaSwapAdapter("http://x:9000", _stub_response=lambda _: live)

        result = adapter.get_status("x")

        assert result.source == "live"


# ---------------------------------------------------------------------------
# AC-004 — pure / idempotent reads
# ---------------------------------------------------------------------------


class TestAC004PureIdempotentReads:
    """Repeated reads for the same alias return equivalent values."""

    def test_repeated_default_reads_for_same_alias_are_equivalent(self) -> None:
        adapter = LlamaSwapAdapter("http://x:9000")

        first = adapter.get_status("qwen3-coder")
        second = adapter.get_status("qwen3-coder")
        third = adapter.get_status("qwen3-coder")

        assert first == second == third

    def test_repeated_stub_reads_for_same_alias_are_equivalent(self) -> None:
        # The stub itself is pure — adapter must not introduce mutation
        # on top of that.
        def stub(alias: str) -> SwapStatus:
            return SwapStatus(loaded_model=alias, eta_seconds=120, source="stub")

        adapter = LlamaSwapAdapter("http://x:9000", _stub_response=stub)

        snapshots = [adapter.get_status("alias-1") for _ in range(5)]

        assert all(snap == snapshots[0] for snap in snapshots)

    def test_no_internal_counter_mutates_across_reads(self) -> None:
        # Reading should not bump any attribute on the adapter — the
        # adapter is a thin transport seam, not a stateful supervisor.
        adapter = LlamaSwapAdapter("http://x:9000")

        before = dict(adapter.__dict__)
        for _ in range(10):
            adapter.get_status("alias-1")
        after = dict(adapter.__dict__)

        assert before == after


# ---------------------------------------------------------------------------
# AC-005 — jarvis.adapters re-exports LlamaSwapAdapter
# ---------------------------------------------------------------------------


class TestAC005PackageReExport:
    """``from jarvis.adapters import LlamaSwapAdapter`` succeeds."""

    def test_package_attribute_resolves_to_class(self) -> None:
        import jarvis.adapters as adapters_pkg

        assert adapters_pkg.LlamaSwapAdapter is LlamaSwapAdapter

    def test_package_all_lists_llamaswap_adapter(self) -> None:
        import jarvis.adapters as adapters_pkg

        all_exports = getattr(adapters_pkg, "__all__", ())
        assert "LlamaSwapAdapter" in all_exports


# ---------------------------------------------------------------------------
# AC-006 — no outbound HTTP at runtime
# ---------------------------------------------------------------------------


class TestAC006NoOutboundHttp:
    """The adapter must not import ``httpx`` / ``requests`` at runtime."""

    def test_module_does_not_pull_httpx_into_sys_modules(self) -> None:
        # Force a fresh import-graph snapshot.  ``httpx`` is not in the
        # base dependency set — we don't want anything in this module to
        # start dragging it in transitively.
        before = set(sys.modules.keys())
        import jarvis.adapters.llamaswap  # noqa: F401  (import for side effect)

        new = set(sys.modules.keys()) - before

        forbidden = {"httpx", "requests"}
        leaked = forbidden & {m.split(".")[0] for m in new}
        assert leaked == set(), f"adapter pulled forbidden HTTP libs: {leaked}"

    def test_module_source_does_not_import_http_clients(self) -> None:
        # AST-level guard so we catch top-level imports even when the
        # forbidden lib happens to already be present in sys.modules
        # because some other test pulled it.
        import jarvis.adapters.llamaswap as mod

        source = pathlib.Path(mod.__file__ or "").read_text(encoding="utf-8")
        for forbidden in ("import httpx", "from httpx", "import requests", "from requests"):
            assert forbidden not in source, (
                f"adapter source must not contain {forbidden!r} in Phase 2"
            )


# ---------------------------------------------------------------------------
# AC-007 — docstring names live endpoints
# ---------------------------------------------------------------------------


class TestAC007DocstringNamesLiveEndpoints:
    """Docstring lists ``/running`` and ``/log`` for FEAT-JARVIS-004 grep."""

    def test_class_docstring_mentions_running_endpoint(self) -> None:
        assert LlamaSwapAdapter.__doc__ is not None
        assert "/running" in LlamaSwapAdapter.__doc__

    def test_class_docstring_mentions_log_endpoint(self) -> None:
        assert LlamaSwapAdapter.__doc__ is not None
        assert "/log" in LlamaSwapAdapter.__doc__
