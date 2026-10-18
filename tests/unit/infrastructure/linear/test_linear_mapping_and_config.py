"""Label, relation and id rules; the door's settings; ``jarvis serve-linear``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from structlog.testing import capture_logs

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.linear.client import (
    LinearIssue,
    LinearIssueRef,
    LinearLabel,
    LinearRelation,
    LinearState,
)
from jarvis.infrastructure.linear.door import door_config
from jarvis.infrastructure.linear.mapping import (
    CORRELATION_ID_RE,
    attempt_of,
    blockers_of,
    check_mission,
    choose_repo,
    correlation_id,
    feature_key,
    mission_labels,
    mission_prefix,
    no_sign_in,
    planning_payload,
    sent_ids_in,
)

from .fake_linear import FAKE_KEY

TODO = LinearState("s1", "Todo", "unstarted")


def _issue(*labels: LinearLabel, relations: tuple[LinearRelation, ...] = ()) -> LinearIssue:
    return LinearIssue(
        id="i1",
        identifier="ENG-12",
        title="A title",
        description="",
        url="https://linear.example/ENG-12",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        state=TODO,
        labels=labels,
        inverse_relations=relations,
    )


# -- labels ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "title"),
    [
        (LinearLabel("L1", "mission: Sharing"), "Sharing"),
        (LinearLabel("L1", "Mission:Sharing notes "), "Sharing notes"),
        (LinearLabel("L1", "MISSION :  Sharing"), "Sharing"),
        (LinearLabel("L1", "Sharing", parent_name="mission"), "Sharing"),
        (LinearLabel("L1", "Sharing", parent_name=" Mission "), "Sharing"),
    ],
)
def test_mission_label_forms(label: LinearLabel, title: str) -> None:
    (found,) = mission_labels(_issue(label))
    assert found.label_id == "L1"
    assert found.title == title


@pytest.mark.parametrize(
    "label",
    [
        LinearLabel("L1", "missions: Sharing"),
        LinearLabel("L1", "our mission: x"),
        LinearLabel("L1", "mission:"),
        LinearLabel("L1", "Sharing", parent_name="Area"),
    ],
)
def test_not_mission_labels(label: LinearLabel) -> None:
    assert mission_labels(_issue(label)) == []


def test_repo_label_group_default_and_missing() -> None:
    assert choose_repo(_issue(LinearLabel("r", "repo: org/name")), "dflt").repo == "org/name"
    assert choose_repo(_issue(LinearLabel("r", "name", parent_name="Repo")), None).repo == "name"
    assert choose_repo(_issue(), "dflt").repo == "dflt"
    missing = choose_repo(_issue(), None)
    assert missing.repo is None and "which repository" in (missing.problem or "")


def test_no_sign_in_label() -> None:
    assert no_sign_in(_issue(LinearLabel("n", "No  Sign-in")))
    assert not no_sign_in(_issue(LinearLabel("n", "sign-in")))


def test_blockers_read_inverse_blocks_relations_only() -> None:
    blocker = LinearIssueRef("b1", "ENG-3", "Done", "completed")
    other = LinearIssueRef("b2", "ENG-4", "Todo", "unstarted")
    issue = _issue(relations=(LinearRelation("blocks", blocker), LinearRelation("related", other)))
    assert blockers_of(issue) == [blocker]


# -- ids ----------------------------------------------------------------------


def test_key_derivation() -> None:
    assert feature_key("ENG-12") == "ENG12"
    assert feature_key("AB-1") == "AB1"


def test_correlation_ids() -> None:
    assert correlation_id("lin-ENG-12-", 1) == "lin-ENG-12-1"
    label_id = "0f8e6a2c-1b3d-4e5f-8a9b-0c1d2e3f4a5b"
    cid = correlation_id(mission_prefix(label_id), 7)
    assert cid == "lin-m-0f8e6a2c1b3d4e5f8a9b0c1d2e3f4a5b-7"
    assert CORRELATION_ID_RE.match(cid)
    assert len(f"{cid}-ABCDEFGHIJKL-a2") <= 128
    with pytest.raises(ValueError):
        correlation_id("lin-bad id-", 1)
    with pytest.raises(ValueError):
        correlation_id("lin-ENG-1-", 0)
    with pytest.raises(ValueError):
        correlation_id("lin-" + "x" * 130 + "-", 1)


def test_attempt_parsing_and_sent_comments() -> None:
    assert attempt_of("lin-ENG-1-3", "lin-ENG-1-") == 3
    assert attempt_of("lin-ENG-12-3", "lin-ENG-1-") is None
    assert attempt_of("lin-ENG-1-x", "lin-ENG-1-") is None
    assert sent_ids_in("Factory: Sent to the factory as `lin-ENG-1-2`") == ["lin-ENG-1-2"]
    assert sent_ids_in("factory: sent to the factory as `lin-ENG-1-2`") == ["lin-ENG-1-2"]
    assert sent_ids_in("Someone: Sent to the factory as `lin-ENG-1-2`") == []


def test_check_mission_mirrors_forges_rules() -> None:
    def command(*features: dict[str, Any]) -> dict[str, Any]:
        return {"verb": "mission", "title": "T", "features": list(features)}

    ok = {"key": "ENG1", "needs": [], "sentence": "x"}
    assert check_mission(command(ok), "lin-m-abc-1") is None
    assert "between 1 and 20" in (check_mission(command(), "c") or "")
    assert "used twice" in (check_mission(command(ok, ok), "c") or "")
    assert "not a usable key" in (
        check_mission(command({"key": "ENGINEERING123", "sentence": "x"}), "c") or ""
    )
    assert "not in this mission" in (
        check_mission(command({"key": "A1", "needs": ["B1"], "sentence": "x"}), "c") or ""
    )
    circle = command(
        {"key": "A1", "needs": ["B1"], "sentence": "x"},
        {"key": "B1", "needs": ["A1"], "sentence": "y"},
    )
    assert "circle" in (check_mission(circle, "c") or "")
    assert "too long" in (check_mission(command(ok), "lin-m-" + "a" * 120 + "-1") or "")


def test_payload_is_the_real_wire_model() -> None:
    payload = planning_payload(
        request_text="Title\n\nBody",
        target_repo="example-repo",
        owner_identity="U0OWNER",
        cid="lin-ENG-1-1",
    )
    assert payload.originating_adapter == "linear"
    assert payload.triggered_by == "jarvis"
    assert payload.parent_request_id is None
    assert payload.originating_user == "U0OWNER"


# -- settings -----------------------------------------------------------------


def test_linear_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    config = JarvisConfig()
    assert config.linear_api_key is None
    assert config.linear_team is None
    assert config.linear_ready_state == "Todo"
    assert config.linear_started_state == "In Progress"
    assert config.linear_done_state == "Done"
    assert config.linear_backlog_state == "Backlog"
    assert config.linear_poll_seconds == 30
    assert config.linear_state_dir == Path("/var/lib/jarvis")
    assert config.linear_forge_db == Path("/forge-state/forge.db")
    assert config.linear_approvers is None


def test_key_from_file_and_owner_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_file = tmp_path / "linear_api_key"
    key_file.write_text(FAKE_KEY + "\n", encoding="utf-8")
    monkeypatch.setenv("JARVIS_LINEAR_API_KEY_FILE", str(key_file))
    monkeypatch.setenv("JARVIS_LINEAR_TEAM", "ENG")
    monkeypatch.setenv("JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID", " U0FIRST , U0SECOND")
    monkeypatch.setenv("JARVIS_LINEAR_STATE_DIR", str(tmp_path))
    config = JarvisConfig()
    assert config.resolve_linear_api_key() == FAKE_KEY
    assert config.resolve_linear_owner_identity() == "U0FIRST"
    resolved = door_config(config)
    assert not isinstance(resolved, str)
    assert resolved.settings.team == "ENG"
    assert resolved.state_path == tmp_path / "linear-door.sqlite3"
    assert FAKE_KEY not in repr(resolved) and FAKE_KEY not in repr(config)

    monkeypatch.setenv("JARVIS_LINEAR_API_KEY", "env-key-wins")
    monkeypatch.setenv("JARVIS_LINEAR_OWNER_IDENTITY", "U0OWNER")
    config = JarvisConfig()
    assert config.resolve_linear_api_key() == "env-key-wins"
    assert config.resolve_linear_owner_identity() == "U0OWNER"


def test_door_config_names_what_is_missing() -> None:
    reason = door_config(JarvisConfig())
    assert isinstance(reason, str)
    assert "JARVIS_LINEAR_API_KEY" in reason and "JARVIS_LINEAR_TEAM" in reason


# -- the command ----------------------------------------------------------------


def test_serve_linear_without_configuration_logs_one_line_and_exits_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jarvis.cli import main as cli

    monkeypatch.setattr(cli, "load_dotenv", lambda **kw: None)
    monkeypatch.setattr(cli, "_configure_default_logging", lambda: None)

    async def no_bus(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("must not connect to the bus when not configured")

    monkeypatch.setattr("jarvis.infrastructure.nats_client.NATSClient.connect", no_bus)
    with capture_logs() as logs:
        result = CliRunner().invoke(cli.main, ["serve-linear"])
    assert result.exit_code == 0, result.output
    assert [entry["event"] for entry in logs] == ["jarvis_serve_linear_not_configured"]


def test_serve_linear_is_listed() -> None:
    from jarvis.cli.main import main

    result = CliRunner().invoke(main, ["--help"])
    assert "serve-linear" in result.output


def test_release_command_says_what_it_is_for_and_needs_a_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis.cli import main as cli

    monkeypatch.setattr(cli, "load_dotenv", lambda **kw: None)
    monkeypatch.setattr(cli, "_configure_default_logging", lambda: None)
    monkeypatch.setenv("JARVIS_LINEAR_API_KEY", FAKE_KEY)
    monkeypatch.setenv("JARVIS_LINEAR_TEAM", "ENG")
    monkeypatch.setenv("JARVIS_LINEAR_OWNER_IDENTITY", "U0OWNER")
    monkeypatch.setenv("JARVIS_LINEAR_STATE_DIR", str(tmp_path / "none"))
    result = CliRunner().invoke(cli.main, ["linear-door", "release", "ENG-1"])
    assert result.exit_code == 1
    assert "refused without filing" in result.output
    assert FAKE_KEY not in result.output
