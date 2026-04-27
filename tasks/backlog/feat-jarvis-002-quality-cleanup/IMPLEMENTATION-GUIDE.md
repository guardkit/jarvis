# FEAT-J002F — Implementation Guide

> **Generated:** 2026-04-26 via `/task-review FEAT-JARVIS-002` → `[I]mplement`
> **Estimated total:** 40-60 minutes (parallelisable)

## Execution Strategy

Both subtasks are **direct-mode** and **parallel-safe**. They touch
disjoint surfaces:

- TASK-J002F-001 modifies `src/jarvis/tools/*.py` and (optionally)
  `pyproject.toml`. No task-file moves.
- TASK-J002F-002 moves task markdown files between `tasks/backlog/`,
  `tasks/design_approved/`, and `tasks/completed/`. No source code.

Either order works. If running through Conductor:

| Wave | Task | Workspace |
|---|---|---|
| 1 | TASK-J002F-001 | `feat-jarvis-002-quality-cleanup-wave1-1` |
| 1 | TASK-J002F-002 | `feat-jarvis-002-quality-cleanup-wave1-2` |

Otherwise: do them sequentially in either order; merge in one commit
or two.

## Wave 1 (parallel)

### TASK-J002F-001 — ruff + mypy clean

**Goal**: zero ruff errors and zero mypy errors over the J002 module
surface. Behavioural code unchanged.

**Approach**:

1. Run `.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py`.
2. For each rule:
   - **RUF022** (`__all__` not sorted in `tools/__init__.py:64`) —
     either accept isort sort, or add `# noqa: RUF022` with a
     comment explaining the deliberate category grouping. Pick
     whichever matches existing project style.
   - **UP037** (`tools/__init__.py:90` stringified `"JarvisConfig"`) —
     remove quotes and lift the import out of `TYPE_CHECKING` if it's
     in there, or vice versa. The forward-reference is unnecessary at
     module level.
   - **UP042** (`tools/dispatch_types.py:39 FrontierTarget(str, Enum)`)
     — convert to `class FrontierTarget(StrEnum)`. Verify nothing
     downstream relies on `str.__mro__` ordering.
   - **I001** import sorting — auto-fixable with `ruff check --fix`.
   - **RUF002** ambiguous en/em-dashes in docstrings — pin
     `[tool.ruff.lint.per-file-ignores]` for `"src/jarvis/**" = ["RUF002"]`
     in `pyproject.toml`. Em-dash prose is intentional and pervasive
     across the codebase; converting them all to ASCII `-` would harm
     readability.
3. Run `.venv/bin/mypy src/jarvis/tools`. For each error:
   - **`unreachable`** in `general.py:187`, `dispatch.py:359,944` —
     these are defensive `else` arms after exhaustive narrowing.
     Either remove them (if truly dead) or suppress per-line with
     `# type: ignore[unreachable]` and a one-line comment explaining
     the defensive intent.
   - **`Subclass of "str" and "ResultPayload"`** at `dispatch.py:349,356`
     — narrow the union before the comparison; an explicit
     `isinstance(value, str)` guard typically fixes it.
   - **`arg-type`** at `dispatch.py:661,678` — widen the
     `_emit_frontier_log` outcome literal to include
     `"attended_only"`, or split the call site into a separate
     specialised emitter.
4. Re-run both gates plus the full pytest suite to confirm no
   regressions. Target outcome: `0` ruff errors, `0` mypy errors,
   `1585 passed, 2 skipped`.

**Files likely touched**:

- `src/jarvis/tools/__init__.py`
- `src/jarvis/tools/dispatch.py`
- `src/jarvis/tools/dispatch_types.py`
- `src/jarvis/tools/general.py`
- `pyproject.toml` (only if pinning the RUF002 per-file ignore)

**Validation**:

```bash
.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py
.venv/bin/mypy src/jarvis/tools
.venv/bin/pytest -q
```

All three commands must exit 0 (with the pytest summary line showing
`1585 passed, 2 skipped`).

### TASK-J002F-002 — kanban hygiene

**Goal**: every J002 task lives at exactly one path, under
`tasks/completed/feat-jarvis-002-core-tools-and-dispatch/`. Orphan
copies in `tasks/backlog/` and `tasks/design_approved/` removed.

**Approach**:

1. List the three current locations and identify the canonical copy
   for each task ID:
   - Primary: `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-*.md`
     (21 files; missing 013, 014)
   - Loose backlog: `tasks/backlog/TASK-J002-*.md` (13 files)
   - Design approved: `tasks/design_approved/TASK-J002-*.md` (10
     files; **includes** 013 and 014)
2. For each `TASK-J002-NNN`:
   - If only one copy exists, that's canonical.
   - If multiple copies exist, prefer the one with the populated
     `autobuild_state.turns` array and `status: in_review` — that's
     the version `/task-work` wrote during AutoBuild.
   - Update each canonical copy's frontmatter: `status: completed`,
     add `completed_at: 2026-04-25T...` (use the timestamp from
     `.guardkit/features/FEAT-J002.yaml`'s per-task `completed_at`).
3. `git mv` (or `mv`) the canonical copies into
   `tasks/completed/feat-jarvis-002-core-tools-and-dispatch/`.
4. `git rm` the duplicate copies.
5. Update the `IMPLEMENTATION-GUIDE.md` and `README.md` paths in the
   subfolder if they point to old locations (they shouldn't —
   relative paths inside the subfolder remain valid after the move).

**Validation**:

```bash
test $(find tasks/backlog -name "TASK-J002-*" | wc -l) -eq 0
test $(find tasks/design_approved -name "TASK-J002-*" | wc -l) -eq 0
test $(find tasks/completed -name "TASK-J002-*" | wc -l) -eq 23
```

All three commands must exit 0.

**Note**: The cleanup task files (TASK-J002F-001 and TASK-J002F-002
themselves) live under `tasks/backlog/feat-jarvis-002-quality-cleanup/`
and are NOT moved by this task — they live in backlog until they
themselves complete, then move to `tasks/completed/feat-jarvis-002-quality-cleanup/`
in the normal way.

## Final Verification

After both subtasks complete:

```bash
# Quality gates
.venv/bin/ruff check src/jarvis/
.venv/bin/mypy src/jarvis/
.venv/bin/pytest -q
# expected: 0 errors, 0 errors, "1585 passed, 2 skipped"

# Kanban truth
find tasks/backlog -name "TASK-J002-[0-9]*"  # expected: empty
find tasks/design_approved -name "TASK-J002-*"  # expected: empty
find tasks/completed -name "TASK-J002-*" | wc -l  # expected: 23
```

Then mark `.guardkit/features/FEAT-J002.yaml`'s task entries
`status: completed` if they aren't already, and the FEAT-JARVIS-002
loop closes cleanly for Phase 3 to inherit.
