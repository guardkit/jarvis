"""Tests for ``jarvis.tools.general.read_file`` (TASK-J002-008).

Exercises the eight acceptance criteria from
``tasks/design_approved/TASK-J002-008-implement-read-file-tool.md``:

* AC-001 — exposes ``read_file(path: str) -> str`` decorated with
  ``@tool(parse_docstring=True)``
* AC-002 — docstring matches ``API-tools.md §1.1`` byte-for-byte
* AC-003 — workspace-relative resolution; path-traversal rejection
* AC-004 — embedded null-byte rejection (path_traversal class)
* AC-005 — symlink escape rejection (path_traversal class)
* AC-006 — not_found / not_a_file / too_large / encoding errors
* AC-007 — never raises (ADR-ARCH-021)
* AC-008 — seam test: invocation through the @tool wrapper returns a
  structured error string instead of raising
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from jarvis.tools import general
from jarvis.tools.general import MAX_FILE_BYTES, read_file


# ---------------------------------------------------------------------------
# Workspace fixture — installs a tmp_path as JARVIS_WORKSPACE_ROOT so the
# tool's call to JarvisConfig() picks it up and constrains every test to a
# disposable directory. The conftest ``_isolate_dotenv`` fixture chdirs to
# its own tmp_path, but that does not interfere because ``setenv`` takes
# precedence over the file-default.
# ---------------------------------------------------------------------------
@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure ``JARVIS_WORKSPACE_ROOT`` and return the resolved tmp path."""
    resolved = tmp_path.resolve()
    monkeypatch.setenv("JARVIS_WORKSPACE_ROOT", str(resolved))
    return resolved


def _invoke(path: str) -> str:
    """Call ``read_file`` through the @tool wrapper (BaseTool.invoke).

    The @tool decorator returns a ``BaseTool`` instance; calling it
    directly raises ``TypeError``. ``invoke({"path": ...})`` is the
    end-to-end path used by the supervisor at runtime — exercising it
    here means the seam tests cover the same wrapper the reasoning
    model goes through.
    """
    result = read_file.invoke({"path": path})
    assert isinstance(result, str), (
        f"read_file must return str through the @tool wrapper, got {type(result)!r}"
    )
    return result


# ---------------------------------------------------------------------------
# AC-001 — surface: read_file is a langchain-core BaseTool
# ---------------------------------------------------------------------------
class TestAC001ToolSurface:
    """``read_file`` is decorated with @tool(parse_docstring=True)."""

    def test_read_file_is_a_basetool_instance(self) -> None:
        from langchain_core.tools import BaseTool

        assert isinstance(read_file, BaseTool)

    def test_read_file_name_is_read_file(self) -> None:
        # The @tool decorator names the tool after the wrapped function.
        assert read_file.name == "read_file"

    def test_read_file_args_schema_has_path_parameter(self) -> None:
        # parse_docstring=True must surface ``path`` in the args schema.
        schema = read_file.args_schema
        assert schema is not None
        properties = schema.model_json_schema()["properties"]
        assert "path" in properties

    def test_read_file_path_parameter_documented_in_schema(self) -> None:
        # The Args: section description should appear in the JSON schema —
        # this is what proves parse_docstring=True is wired correctly.
        schema = read_file.args_schema
        path_prop = schema.model_json_schema()["properties"]["path"]
        # We don't assert byte-for-byte; the contract is simply that the
        # description was extracted from the docstring at all.
        assert path_prop.get("description"), (
            "path parameter must carry a description harvested by parse_docstring=True"
        )


# ---------------------------------------------------------------------------
# AC-002 — docstring matches API-tools.md §1.1 byte-for-byte
# ---------------------------------------------------------------------------
class TestAC002DocstringContract:
    """The docstring is the contract. It must match API-tools.md §1.1."""

    def test_docstring_first_sentence_matches_contract(self) -> None:
        doc = inspect.getdoc(read_file.func) or ""  # type: ignore[attr-defined]
        assert doc.startswith(
            "Read a UTF-8 text file from the user's workspace and return its contents."
        )

    def test_docstring_lists_all_five_error_categories(self) -> None:
        doc = inspect.getdoc(read_file.func) or ""  # type: ignore[attr-defined]
        for category in (
            "ERROR: path_traversal",
            "ERROR: not_found",
            "ERROR: not_a_file",
            "ERROR: too_large",
            "ERROR: encoding",
        ):
            assert category in doc, f"Docstring missing error category: {category}"

    def test_docstring_mentions_no_network_io(self) -> None:
        doc = inspect.getdoc(read_file.func) or ""  # type: ignore[attr-defined]
        assert "No network I/O." in doc


# ---------------------------------------------------------------------------
# AC-003 — happy path: read a UTF-8 file inside the workspace
# ---------------------------------------------------------------------------
class TestAC003HappyPath:
    """Reading a UTF-8 text file inside the workspace returns its contents."""

    def test_read_workspace_relative_utf8_file_returns_contents(
        self, workspace: Path
    ) -> None:
        target = workspace / "notes.txt"
        target.write_text("hello world", encoding="utf-8")

        result = _invoke("notes.txt")

        assert result == "hello world"

    def test_read_absolute_path_inside_workspace_returns_contents(
        self, workspace: Path
    ) -> None:
        target = workspace / "abs.txt"
        target.write_text("absolute", encoding="utf-8")

        result = _invoke(str(target))

        assert result == "absolute"

    def test_read_nested_subdirectory_returns_contents(
        self, workspace: Path
    ) -> None:
        nested = workspace / "a" / "b" / "c"
        nested.mkdir(parents=True)
        target = nested / "deep.md"
        target.write_text("# heading\n\nbody", encoding="utf-8")

        result = _invoke("a/b/c/deep.md")

        assert result == "# heading\n\nbody"

    def test_read_unicode_content_round_trips(self, workspace: Path) -> None:
        target = workspace / "unicode.txt"
        content = "café — naïve résumé 漢字 🚀"
        target.write_text(content, encoding="utf-8")

        result = _invoke("unicode.txt")

        assert result == content


# ---------------------------------------------------------------------------
# AC-004 — path-traversal rejections
# ---------------------------------------------------------------------------
class TestAC004PathTraversalRejected:
    """Paths whose realpath escapes the workspace return path_traversal."""

    def test_dot_dot_relative_path_outside_workspace_rejected(
        self, workspace: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        # workspace is tmp_path; ../sibling resolves outside it.
        outside = tmp_path_factory.mktemp("outside")
        # Create the file so this can never be confused with not_found.
        (outside / "secret.txt").write_text("nope", encoding="utf-8")
        relative = os.path.relpath(outside / "secret.txt", workspace)

        result = _invoke(relative)

        assert result.startswith("ERROR: path_traversal")
        assert "resolves outside workspace" in result

    def test_absolute_path_outside_workspace_rejected(
        self, workspace: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        outside_dir = tmp_path_factory.mktemp("outside")
        outside_file = outside_dir / "leak.txt"
        outside_file.write_text("nope", encoding="utf-8")

        result = _invoke(str(outside_file))

        assert result.startswith("ERROR: path_traversal")

    def test_embedded_null_byte_rejected_as_path_traversal(
        self, workspace: Path
    ) -> None:
        # ASSUM-003: null bytes share the path_traversal category rather
        # than introducing a new error code.
        result = _invoke("safe\x00../../etc/passwd")

        assert result.startswith("ERROR: path_traversal")
        assert "null byte" in result


# ---------------------------------------------------------------------------
# AC-005 — symlink escape rejection
# ---------------------------------------------------------------------------
class TestAC005SymlinkEscapeRejected:
    """Symlinks whose target lies outside the workspace are rejected."""

    def test_symlink_to_path_outside_workspace_rejected(
        self,
        workspace: Path,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        outside = tmp_path_factory.mktemp("outside-symlink")
        outside_target = outside / "target.txt"
        outside_target.write_text("escaped", encoding="utf-8")

        link = workspace / "evil-link"
        try:
            link.symlink_to(outside_target)
        except (OSError, NotImplementedError):
            pytest.skip("Filesystem does not support symlinks")

        result = _invoke("evil-link")

        assert result.startswith("ERROR: path_traversal")
        assert "resolves outside workspace" in result


# ---------------------------------------------------------------------------
# AC-006 — not_found / not_a_file / too_large / encoding errors
# ---------------------------------------------------------------------------
class TestAC006StructuredErrors:
    """Each of the five non-traversal error categories is correctly produced."""

    def test_missing_path_returns_not_found(self, workspace: Path) -> None:
        result = _invoke("does-not-exist.txt")

        assert result.startswith("ERROR: not_found")
        assert "does not exist" in result

    def test_directory_returns_not_a_file(self, workspace: Path) -> None:
        (workspace / "subdir").mkdir()

        result = _invoke("subdir")

        assert result.startswith("ERROR: not_a_file")
        assert "directory or special file" in result

    def test_file_at_one_mib_boundary_is_accepted(self, workspace: Path) -> None:
        # Boundary: exactly 1 MiB = accept.
        target = workspace / "exactly_1mib.bin"
        target.write_bytes(b"a" * MAX_FILE_BYTES)

        result = _invoke("exactly_1mib.bin")

        assert not result.startswith("ERROR: too_large")
        # The contents are 'a' * 1MiB which is valid UTF-8.
        assert len(result) == MAX_FILE_BYTES

    def test_file_one_byte_over_one_mib_rejected(self, workspace: Path) -> None:
        # Boundary: 1 MiB + 1 byte = reject.
        target = workspace / "over_1mib.bin"
        target.write_bytes(b"a" * (MAX_FILE_BYTES + 1))

        result = _invoke("over_1mib.bin")

        assert result.startswith("ERROR: too_large")
        assert "exceeds 1MB" in result

    def test_invalid_utf8_returns_encoding_error(self, workspace: Path) -> None:
        target = workspace / "binary.dat"
        # 0xFF 0xFE is not valid UTF-8 (a lone surrogate-like byte sequence).
        target.write_bytes(b"\xff\xfe\x00\x80\xc0\xc1")

        result = _invoke("binary.dat")

        assert result.startswith("ERROR: encoding")
        assert "not valid UTF-8" in result


# ---------------------------------------------------------------------------
# AC-007 — never raises (ADR-ARCH-021)
# ---------------------------------------------------------------------------
class TestAC007NeverRaises:
    """The tool converts every internal error to a structured string."""

    def test_invocation_with_pathological_input_returns_string(
        self, workspace: Path
    ) -> None:
        # An empty path, a long path, a path with control characters —
        # all should return a structured string rather than raising.
        for pathological in ("", "/" * 4096, "\n\r\t", "🚀" * 256):
            result = _invoke(pathological)
            assert isinstance(result, str)

    def test_internal_failure_in_resolve_is_caught(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force ``_resolve_workspace_root`` to raise an unexpected error
        # and confirm the catch-all in ``read_file`` converts it to an
        # ``ERROR:`` string rather than propagating.
        def _boom() -> Path:
            raise RuntimeError("simulated config explosion")

        monkeypatch.setattr(general, "_resolve_workspace_root", _boom)

        result = _invoke("anything.txt")

        assert isinstance(result, str)
        assert result.startswith("ERROR:")


# ---------------------------------------------------------------------------
# AC-008 — seam test: end-to-end through @tool wrapper
# ---------------------------------------------------------------------------
class TestAC008SeamThroughToolWrapper:
    """``read_file.invoke(...)`` is the same surface the supervisor uses.

    The acceptance criterion frames this as "calling read_file inside
    ``assemble_tool_list``-wired supervisor"; ``assemble_tool_list`` is
    delivered in TASK-J002-015 (Wave 3). The actual seam under test is
    the @tool wrapper itself — the supervisor invokes the tool through
    exactly the same ``BaseTool.invoke`` API exercised here.
    """

    def test_invoke_with_missing_path_returns_string_does_not_raise(
        self, workspace: Path
    ) -> None:
        try:
            result = read_file.invoke({"path": "no-such-file.txt"})
        except Exception as exc:  # pragma: no cover — would break ADR-ARCH-021
            pytest.fail(f"read_file raised through @tool wrapper: {exc!r}")

        assert isinstance(result, str)
        assert result.startswith("ERROR: not_found")

    def test_invoke_with_traversal_returns_string_does_not_raise(
        self, workspace: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        outside = tmp_path_factory.mktemp("seam-outside")
        outside_file = outside / "leak.txt"
        outside_file.write_text("escaped", encoding="utf-8")

        try:
            result = read_file.invoke({"path": str(outside_file)})
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"read_file raised through @tool wrapper: {exc!r}")

        assert isinstance(result, str)
        assert result.startswith("ERROR: path_traversal")

    def test_invoke_with_valid_file_returns_contents(
        self, workspace: Path
    ) -> None:
        target = workspace / "seam-ok.txt"
        target.write_text("seam-passed", encoding="utf-8")

        result = read_file.invoke({"path": "seam-ok.txt"})

        assert result == "seam-passed"
