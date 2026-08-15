"""The bounded store of worked examples behind a spec digest card.

It holds one thing — the spec's own text — between the moment the card is
posted and a tap on "Show the worked examples". These tests pin the bounds and
the honest degrade: it is in-process memory, it never grows without limit, and
a miss is a miss (the caller then says so on the surface).
"""

from __future__ import annotations

import pytest

from jarvis.infrastructure import spec_texts
from jarvis.infrastructure.spec_texts import SpecTextRegistry


class TestHoldingAndReading:
    def test_what_goes_in_comes_out(self) -> None:
        store = SpecTextRegistry()
        store.record(request_id="req-1", feature="version-endpoint", spec_text="Feature: v")
        record = store.get("req-1")
        assert record is not None
        assert record.feature == "version-endpoint"
        assert record.spec_text == "Feature: v"

    def test_a_card_never_held_reads_as_a_miss(self) -> None:
        assert SpecTextRegistry().get("req-unknown") is None

    @pytest.mark.parametrize("request_id", ("", None))
    def test_a_falsy_key_is_ignored_both_ways(self, request_id: str) -> None:
        store = SpecTextRegistry()
        store.record(request_id=request_id, feature="f", spec_text="x")  # type: ignore[arg-type]
        assert store.get(request_id) is None  # type: ignore[arg-type]

    def test_re_rendering_a_card_replaces_what_is_held(self) -> None:
        store = SpecTextRegistry()
        store.record(request_id="req-1", feature="f", spec_text="first")
        store.record(request_id="req-1", feature="f", spec_text="second")
        assert store.get("req-1").spec_text == "second"  # type: ignore[union-attr]


class TestTheBounds:
    def test_the_eldest_recording_is_evicted_first(self) -> None:
        store = SpecTextRegistry(max_entries=2)
        store.record(request_id="a", feature="f", spec_text="1")
        store.record(request_id="b", feature="f", spec_text="2")
        store.record(request_id="c", feature="f", spec_text="3")
        assert store.get("a") is None
        assert store.get("b") is not None
        assert store.get("c") is not None

    def test_re_recording_moves_a_card_to_the_back_of_the_queue(self) -> None:
        store = SpecTextRegistry(max_entries=2)
        store.record(request_id="a", feature="f", spec_text="1")
        store.record(request_id="b", feature="f", spec_text="2")
        store.record(request_id="a", feature="f", spec_text="1 again")
        store.record(request_id="c", feature="f", spec_text="3")
        assert store.get("a") is not None
        assert store.get("b") is None

    def test_an_expired_hold_reads_as_a_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = {"now": 1000.0}
        monkeypatch.setattr(spec_texts, "_monotonic", lambda: clock["now"])
        store = SpecTextRegistry(ttl_seconds=60.0)
        store.record(request_id="req-1", feature="f", spec_text="x")
        clock["now"] = 1059.0
        assert store.get("req-1") is not None
        clock["now"] = 1061.0
        assert store.get("req-1") is None
