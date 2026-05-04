---
id: TASK-JAR-FORK-PIN
title: Pin graphiti-core to guardkit/graphiti fork (pyproject only)
status: backlog
created: 2026-05-04T00:00:00Z
updated: 2026-05-04T00:00:00Z
priority: medium
task_type: feature
complexity: 1
estimated_minutes: 10
execution_location: any
tags: [graphiti, fork, pyproject]
parent_task: graphiti/TASK-FORK-PATCH (cross-repo follow-up)
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Pin graphiti-core to the guardkit/graphiti fork

**WHY**: TASK-FORK-PATCH landed bug-fix patches in [`guardkit/graphiti`](https://github.com/guardkit/graphiti) at tag `v0.29.5-guardkit.1`. Jarvis's routing-history writer (DDR-019) writes to graphiti via the `graphiti` extra. To exercise the fork patches, the pin needs to switch from PyPI to the fork tag.

This is a low-priority follow-up — Jarvis runs in production but the routing-history writer is a fire-and-forget non-load-bearing path. Lower priority than guardkit's pin (which feeds the live MCP container).

## What needs to change

`pyproject.toml` line 81:

```diff
 graphiti = [
-    "graphiti-core>=0.9,<1",
+    "graphiti-core @ git+https://github.com/guardkit/graphiti.git@v0.29.5-guardkit.1",
 ]
```

**Note**: the fork's `pyproject.toml` is at the repo root (the package name `graphiti-core` is declared there), so no `#subdirectory=` qualifier is needed.

The `>=0.9,<1` range is replaced rather than augmented because the fork is a single-tag pin, not a range.

## Steps

```bash
cd ~/Projects/appmilla_github/jarvis
# 1. Edit pyproject.toml line 81
# 2. Refresh venv
uv sync --extra graphiti
# 3. Verify import resolves to fork
.venv/bin/python -c "import graphiti_core; print(graphiti_core.__file__)"
# Expect: a path under .venv/.../site-packages/graphiti_core/__init__.py
# whose origin is the git clone (not PyPI cache). uv stashes git-installed
# packages with a hash in the path.
# 4. Run jarvis test suite to make sure nothing broke
uv run pytest -x
# 5. Commit
git add pyproject.toml uv.lock
git commit -m "pin: graphiti-core → guardkit/graphiti @ v0.29.5-guardkit.1 (fork)"
```

## Acceptance Criteria

- [ ] `pyproject.toml` line 81 pins to the fork tag.
- [ ] `uv sync --extra graphiti` succeeds and updates `uv.lock` to reflect the git pin.
- [ ] `.venv/bin/python -c "import graphiti_core"` works and the resolved path is from a git install (not PyPI).
- [ ] `uv run pytest -x` passes (no graphiti-core regressions in jarvis's own tests).
- [ ] Single commit with message `pin: graphiti-core → guardkit/graphiti @ v0.29.5-guardkit.1 (fork)`.

## Cross-references

- Parent (graphiti repo): [TASK-FORK-PATCH](../../graphiti/tasks/backlog/TASK-FORK-PATCH-apply-appmilla-bug-fix-patches.md)
- Sibling cross-repo: guardkit TASK-GK-FORK-PIN (the larger one — drives the live MCP container)
- Blocks: [graphiti TASK-FPA-009](../../graphiti/tasks/blocked/fork-patch-application/TASK-FPA-009-end-to-end-verification.md) — though only loosely; jarvis isn't directly exercised by FPA-009's verification suite, but pinning to the fork keeps Jarvis consistent with the wider rollout

## Notes

- This task can be done from any machine; doesn't require GB10. If you do it on the Mac, the GB10 will see the change once jarvis is re-deployed there (separate concern).
- Jarvis's routing-history writer is fire-and-forget — degraded graphiti calls don't break Jarvis's main flow. Even if the fork pin temporarily breaks ingestion, it won't surface as a Jarvis-side outage. Useful to know during rollout.
