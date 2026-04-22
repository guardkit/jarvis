"""Tests for TASK-J001-011: developer surface — .env.example, README Quickstart, .gitignore audit.

Covers all four acceptance criteria:
  AC-001: .env.example exists with required variables and comments
  AC-002: git check-ignore .env prints .env (it IS ignored)
  AC-003: git check-ignore .env.example exits non-zero (it is NOT ignored)
  AC-004: README.md contains Quickstart section; no FEAT-002/003/004 content
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
GITIGNORE = ROOT / ".gitignore"
README = ROOT / "README.md"


# ===================================================================
# AC-001: .env.example exists with required variables and comments
# ===================================================================


class TestAC001EnvExample:
    """.env.example exists and includes required variables with comments."""

    def test_env_example_exists(self) -> None:
        """`.env.example` file exists at project root."""
        assert ENV_EXAMPLE.exists(), ".env.example must exist at project root"

    def test_env_example_is_not_empty(self) -> None:
        """`.env.example` is not an empty file."""
        content = ENV_EXAMPLE.read_text()
        assert len(content.strip()) > 0, ".env.example must not be empty"

    @pytest.mark.parametrize(
        "var_name",
        [
            "JARVIS_SUPERVISOR_MODEL",
            "JARVIS_OPENAI_BASE_URL",
            "JARVIS_LOG_LEVEL",
            "JARVIS_MEMORY_STORE_BACKEND",
        ],
    )
    def test_required_variable_present(self, var_name: str) -> None:
        """Each required environment variable appears in .env.example."""
        content = ENV_EXAMPLE.read_text()
        # Match either as an assignment (VAR=value) or as a commented-out
        # reference (# VAR=...) — the key must appear somewhere.
        assert var_name in content, (
            f"{var_name} must appear in .env.example"
        )

    @pytest.mark.parametrize(
        "var_name",
        [
            "JARVIS_SUPERVISOR_MODEL",
            "JARVIS_OPENAI_BASE_URL",
            "JARVIS_LOG_LEVEL",
            "JARVIS_MEMORY_STORE_BACKEND",
        ],
    )
    def test_required_variable_has_assignment(self, var_name: str) -> None:
        """Each required variable has an actual VAR=value assignment (not just in comments)."""
        content = ENV_EXAMPLE.read_text()
        lines = content.splitlines()
        assignment_lines = [
            line for line in lines
            if not line.strip().startswith("#") and f"{var_name}=" in line
        ]
        assert len(assignment_lines) >= 1, (
            f"{var_name} must have an uncommented assignment in .env.example"
        )

    def test_has_comments(self) -> None:
        """`.env.example` contains explanatory comments."""
        content = ENV_EXAMPLE.read_text()
        comment_lines = [
            line for line in content.splitlines()
            if line.strip().startswith("#") and len(line.strip()) > 1
        ]
        assert len(comment_lines) >= 4, (
            ".env.example should have at least 4 comment lines with explanations"
        )

    def test_supervisor_model_has_default_value(self) -> None:
        """JARVIS_SUPERVISOR_MODEL has a sensible default value."""
        content = ENV_EXAMPLE.read_text()
        # Should contain provider:model format
        match = re.search(r"^JARVIS_SUPERVISOR_MODEL=(.+)$", content, re.MULTILINE)
        assert match is not None, "JARVIS_SUPERVISOR_MODEL must have an assignment"
        value = match.group(1).strip()
        assert ":" in value, (
            f"JARVIS_SUPERVISOR_MODEL must use provider:model format, got {value!r}"
        )

    def test_log_level_has_valid_default(self) -> None:
        """JARVIS_LOG_LEVEL has a valid log level default."""
        content = ENV_EXAMPLE.read_text()
        match = re.search(r"^JARVIS_LOG_LEVEL=(.+)$", content, re.MULTILINE)
        assert match is not None, "JARVIS_LOG_LEVEL must have an assignment"
        value = match.group(1).strip()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        assert value in valid_levels, f"JARVIS_LOG_LEVEL default must be valid, got {value!r}"

    def test_memory_store_backend_has_valid_default(self) -> None:
        """JARVIS_MEMORY_STORE_BACKEND has a valid backend default."""
        content = ENV_EXAMPLE.read_text()
        match = re.search(r"^JARVIS_MEMORY_STORE_BACKEND=(.+)$", content, re.MULTILINE)
        assert match is not None, "JARVIS_MEMORY_STORE_BACKEND must have an assignment"
        value = match.group(1).strip()
        valid_backends = {"in_memory", "file", "graphiti"}
        assert value in valid_backends, (
            f"JARVIS_MEMORY_STORE_BACKEND default must be valid, got {value!r}"
        )


# ===================================================================
# AC-002: git check-ignore .env prints .env (it IS ignored)
# ===================================================================


class TestAC002EnvIgnored:
    """`.env` is git-ignored so secrets cannot be accidentally committed."""

    def test_gitignore_exists(self) -> None:
        """.gitignore exists at project root."""
        assert GITIGNORE.exists(), ".gitignore must exist at project root"

    def test_env_in_gitignore_content(self) -> None:
        """`.env` appears as a standalone pattern in .gitignore."""
        content = GITIGNORE.read_text()
        lines = [line.strip() for line in content.splitlines()]
        assert ".env" in lines, ".env must be a standalone pattern in .gitignore"

    def test_git_check_ignore_env(self) -> None:
        """``git check-ignore .env`` prints .env (exit 0)."""
        result = subprocess.run(
            ["git", "check-ignore", ".env"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"git check-ignore .env should exit 0 (ignored), got {result.returncode}"
        )
        assert ".env" in result.stdout.strip(), (
            f"git check-ignore .env should print '.env', got {result.stdout!r}"
        )


# ===================================================================
# AC-003: git check-ignore .env.example exits non-zero (NOT ignored)
# ===================================================================


class TestAC003EnvExampleNotIgnored:
    """`.env.example` is NOT git-ignored so it can be committed and shared."""

    def test_env_example_not_in_gitignore_patterns(self) -> None:
        """`.env.example` does not appear as a standalone pattern in .gitignore."""
        content = GITIGNORE.read_text()
        lines = [line.strip() for line in content.splitlines()]
        assert ".env.example" not in lines, (
            ".env.example must NOT be in .gitignore"
        )

    def test_git_check_ignore_env_example_exits_nonzero(self) -> None:
        """``git check-ignore .env.example`` exits non-zero (not ignored)."""
        result = subprocess.run(
            ["git", "check-ignore", ".env.example"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(ROOT),
        )
        assert result.returncode != 0, (
            f"git check-ignore .env.example should exit non-zero (not ignored), "
            f"got {result.returncode}. stdout={result.stdout!r}"
        )


# ===================================================================
# AC-004: README.md Quickstart section; no FEAT-002/003/004 content
# ===================================================================


class TestAC004ReadmeQuickstart:
    """README.md contains a Quickstart section with the right commands."""

    def test_readme_exists(self) -> None:
        """README.md exists at project root."""
        assert README.exists(), "README.md must exist at project root"

    def test_readme_has_quickstart_heading(self) -> None:
        """README.md contains a '## Quickstart' heading."""
        content = README.read_text()
        assert re.search(r"^## Quickstart", content, re.MULTILINE), (
            "README.md must contain a '## Quickstart' section heading"
        )

    @pytest.mark.parametrize(
        "command_fragment",
        [
            "pip install",
            ".env.example",
            "pytest",
        ],
    )
    def test_quickstart_contains_command(self, command_fragment: str) -> None:
        """Quickstart section references key commands."""
        content = README.read_text()
        # Extract the Quickstart section (from heading to next ## heading or end)
        match = re.search(
            r"## Quickstart\n(.+?)(?=\n## |\Z)",
            content,
            re.DOTALL,
        )
        assert match is not None, "Could not find Quickstart section"
        quickstart_text = match.group(1)
        assert command_fragment in quickstart_text, (
            f"Quickstart section must mention '{command_fragment}'"
        )

    def test_quickstart_mentions_venv(self) -> None:
        """Quickstart section includes virtual environment setup."""
        content = README.read_text()
        match = re.search(
            r"## Quickstart\n(.+?)(?=\n## |\Z)",
            content,
            re.DOTALL,
        )
        assert match is not None, "Could not find Quickstart section"
        quickstart_text = match.group(1)
        assert "venv" in quickstart_text, (
            "Quickstart section must mention virtual environment setup"
        )

    def test_quickstart_mentions_cp_env_example(self) -> None:
        """Quickstart section instructs user to copy .env.example to .env."""
        content = README.read_text()
        match = re.search(
            r"## Quickstart\n(.+?)(?=\n## |\Z)",
            content,
            re.DOTALL,
        )
        assert match is not None, "Could not find Quickstart section"
        quickstart_text = match.group(1)
        assert "cp .env.example .env" in quickstart_text, (
            "Quickstart must include 'cp .env.example .env' command"
        )

    @pytest.mark.parametrize(
        "forbidden_pattern",
        [
            "FEAT-002",
            "FEAT-003",
            "FEAT-004",
        ],
    )
    def test_no_feat_002_003_004_content(self, forbidden_pattern: str) -> None:
        """README.md does not mention FEAT-002, FEAT-003, or FEAT-004 (scope invariant)."""
        content = README.read_text()
        assert forbidden_pattern not in content, (
            f"README.md must not contain {forbidden_pattern} content (scope invariant)"
        )

    def test_readme_still_has_project_title(self) -> None:
        """README.md retains the project title (we didn't break existing content)."""
        content = README.read_text()
        assert "# Jarvis" in content, "README.md must retain the project title"
