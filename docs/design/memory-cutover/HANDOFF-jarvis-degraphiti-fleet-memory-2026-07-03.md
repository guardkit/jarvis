# HANDOFF — Jarvis de-graphiti → fleet-memory (routing-history writes) — 2026-07-03

Pick-up doc for a **fresh conversation**. Assumes no prior context. This effort
migrated Jarvis's routing-history writes **off Graphiti onto fleet-memory**,
following the pattern guardkit used in FEAT-MEM-09 (see
`../../../../guardkit/docs/design/specs/memory-cutover/HANDOFF-FEAT-MEM-09-W1-and-degraphiti-2026-07-03.md`
§3). **The migration is complete, on `main`, and proven end-to-end against the
live GB10 fleet-memory store.** Everything below is committed + pushed.

---

## 0. Current state (verify first)

- **`HEAD == origin/main == 776f607`.** Two migration commits sit on top of a
  parallel-session commit (`54a17f7`, stub-registry test repair — not ours):
  - `776f607` fix(memory): fail fast on unreachable/unauthorized NATS in the memory publisher
  - `9ddf33d` feat(memory): migrate routing-history writes off Graphiti to fleet-memory
- **Full suite baseline: `2316 passed, 2 skipped`** in default config (no env).
  The 2 skips are: one pre-existing skip, and `test_routing_history_publish_live`
  (the `@pytest.mark.live` proof — skips unless `JARVIS_FLEET_MEMORY_ENABLED=true`).
  Acceptance for any follow-up = "still 2316 passed, zero new failures."
- **Test runner** (pytest.ini `addopts` adds `--tb=short -q`; keep or strip):
  ```
  .venv/bin/python -m pytest tests/ -p no:cacheprovider -o addopts="" -q --tb=line | tail -2
  ```
- **mypy strict + ruff are clean** on all changed/added modules. (There are 3
  PRE-EXISTING ruff findings in `src/jarvis/tools/{capabilities.py,__init__.py}`
  — identical at HEAD, not ours; do not chase.)
- **Live proof: PASSED** (0.66s) from the Mac against `promaxgb10-41b1:4222`
  after the infra was wired (see §4). This is the operator post-merge gate; it's
  green.
- **`.env` is gitignored** — the NATS creds / enable flag live there locally, not
  in the repo. `.env.example` documents the new vars.

---

## 1. What shipped (the two commits)

| Commit | Summary |
|---|---|
| `9ddf33d` | **The migration.** 44 files. New write-only package `src/jarvis/infrastructure/fleet_memory/`; full rename of every `graphiti` symbol → fleet-memory; config `graphiti_endpoint/api_key` → `fleet_memory_enabled/project`; removed the `[graphiti]` extra + `graphiti-core` git-fork (pyproject + uv.lock, which also dropped the orphaned `backoff` transitive); retired `.guardkit/graphiti.yaml` + the graphiti MCP entry; migrated ~20 test files (incl. rename `test_graphiti_unavailable.py` → `test_memory_unavailable.py`); added the §3 two-test contract (boundary + `@pytest.mark.live`) plus mapping/payloads/writer-seam unit tests. |
| `776f607` | **Fail-fast fix** (found by running the live proof). The publisher used nats_core's default `max_reconnect_attempts=60` → a bad/unauthorized broker caused a ~2-minute background retry-storm per fire-and-forget write. Now bounds the connect with `asyncio.wait_for(6s)` + `max_reconnect_attempts=0` and only disconnects if connected. Verified: live-proof runtime 122s → 7s on failure, <1s on success. |

---

## 2. Architecture — the fleet-memory write path

Jarvis is **write-only** to the graph. It writes two kinds of routing-history
record (both fire-and-forget, DDR-019): dispatch-decision **entries** and Forge
**stage-complete edges**. Post-migration these publish as fleet-memory
`document` episodes over NATS; the fleet-memory relay ingests them into
Postgres + embeddings. **There is no read path** (reads are FEAT-JARVIS-008,
future — `priors_retrieved` stays `[]`).

**New package `src/jarvis/infrastructure/fleet_memory/`** (ported from guardkit's
`knowledge/fleet_memory_*` + `memory/harvest_publisher`, trimmed to write-only):

- `client.py` — `FleetMemoryClient`. Keeps the **retired Graphiti client's
  keyword-only `add_episode(*, name, episode_body, source_description,
  reference_time)` surface**, so `RoutingHistoryWriter`'s body did **not** change
  on cutover. Derives the group from `source_description`
  (`"jarvis-routing-history"` → entry, `"jarvis-routing-history-edge"` → edge) →
  `resolve()` → `build_memory_episode()` → `publish_episodes()`. **Fail-open**:
  every error path returns `None`, never raises. Has `enabled` property + async
  no-op `close()` (shutdown parity with the old `aclose()`).
- `mapping.py` — `resolve(group_id)` + `group_for_source(source_description)`.
  Two groups only: `routing_history` → `document` / tags `[routing, dispatch]`;
  `routing_history_edge` → `document` / tags `[routing, stage]`. Both
  `project="jarvis"`, disposition `migrate`.
- `payloads.py` — `build_memory_episode(...)` → `nats_core.events.MemoryEpisodeV1`
  on the **prose/markdown path** (`content_format="markdown"`, `payload_type=None`
  — routing traces are free-shape JSON, not one of the 7 typed payloads). Deterministic
  `episode_id = "document:{project}:{sanitised name}"` (JetStream dedup). Domain
  tags ride in `ingest_hints={"domain_tags": [...]}` for future group-scoped reads.
- `publisher.py` — `publish_episodes(episodes, config, client=None)` → connect-per
  -batch via `nats_core.NATSClient.publish_episode` (the guardkit harvest pattern).
  `build_nats_client(config)` reuses `config.nats_url` + `config.nats_credentials_path`
  (**no new NATS user/password field is introduced** — see §5 gotcha #1). Fail-fast:
  `asyncio.wait_for(connect, 6s)` + `max_reconnect_attempts=0`.

**Renamed production symbols** (grep these if orienting): `MemoryClientProtocol`
(was `GraphitiClientProtocol`, in `routing_history.py`); `lifecycle._connect_memory`
(seam that tests patch); `AppState.memory_client`; `RoutingHistoryWriter._memory_client`;
config `fleet_memory_enabled` / `fleet_memory_project`. Log reasons: `memory_disabled`
(offload), `memory_unavailable` (edge WARN), `memory_error` (offload field).

**Soft-fail / offload (DDR-019, unchanged behaviour, just renamed):**
`_connect_memory` returns `None` when `fleet_memory_enabled=False` or the client
can't be built → the writer holds `memory_client is None` → dispatch-write entries
are offloaded to `<jarvis_traces_dir>/<correlation_id>.json` for later replay; edge
writes emit one `memory_unavailable` WARN. A *runtime* publish failure (client
present) is swallowed fail-open with a WARN — **no** offload (parity with the old
graphiti runtime-failure behaviour).

---

## 3. The reusable test pattern (§3 — reuse for any future consumer work)

Two-test contract, mirrored from guardkit's §3:

1. **Boundary test** — build a **real** `FleetMemoryClient`
   (`fleet_memory_enabled=True`), stub **only** the external publish edge, and
   assert the resolved episode shape reached it. **Patch target is the client
   namespace**, not the publisher module (the name is imported into `client.py`):
   `patch("jarvis.infrastructure.fleet_memory.client.publish_episodes", AsyncMock(...))`.
   The real `group_for_source → resolve → build_memory_episode` chain runs. Assert
   `episode.project_id="jarvis"`, `episode_type="document"`, `content_format="markdown"`,
   decoded `body`, `ingest_hints` tags, and the returned natural key. `publish_episodes`
   is called with **two positional args** `(episodes, config)` → read via
   `mock_pub.call_args.args[0]`. Skip-gate the module on
   `importlib.util.find_spec("nats_core")`.
   - `tests/test_fleet_memory_client.py::TestFleetMemoryClientAddEpisodeBoundary`
   - `tests/test_routing_history_fleet_memory.py` — the strongest evidence: a real
     client wired into `RoutingHistoryWriter`, only the publish edge stubbed, proving
     redaction-before-publish end-to-end.
2. **`@pytest.mark.live` round-trip** — real publish against the live store; `pytest.skip`s
   when `not config.fleet_memory_enabled`. Jarvis is write-only so the proof is a
   successful publish (natural key returned). `tests/test_fleet_memory_client.py::TestFleetMemoryLiveRoundTrip`.
   The `live` marker is registered in `pyproject.toml` `[tool.pytest.ini_options].markers`.

---

## 4. Infra setup that makes the live proof pass (hard-won — document for ops)

The migration was code-complete quickly; the live proof took infra work because
**jarvis had never been a NATS memory publisher** (it was a FalkorDB/Graphiti
consumer, which needs no NATS auth). Getting it green required, in
`../../../../nats-infrastructure`:

1. **A `jarvis` NATS user** in `config/accounts/accounts.conf.template` (commit
   `d4299e7` in nats-infrastructure) with password `${JARVIS_NATS_PASSWORD}`.
2. **`memory.episode.jarvis.>` added to that user's `publish` permissions** — the
   piece that turns auth-success into publish-success. Least-privilege: jarvis's
   own project only. (It already had `$JS.>` + `_INBOX.>` for the JetStream PubAck.)
3. **`JARVIS_NATS_PASSWORD` in `nats-infrastructure/.env`** (envsubst → accounts.conf)
   and a **broker redeploy/reload** on the GB10 so the user + perm go live.
4. **Jarvis client wiring** in `jarvis/.env` (both machines) — jarvis has **no
   password field**, so auth is via URL-embedded creds:
   ```
   JARVIS_FLEET_MEMORY_ENABLED=true
   JARVIS_NATS_URL=nats://jarvis:<JARVIS_NATS_PASSWORD>@promaxgb10-41b1:4222
   ```
   (On the GB10, host is `localhost`. pydantic reads `.env` literally — put the real
   password in the URL, not `${...}`.)

**Live proof command (operator, store up):**
```
JARVIS_FLEET_MEMORY_ENABLED=true .venv/bin/python -m pytest -m live tests/test_fleet_memory_client.py -v
```
→ `1 passed`. (Run on the GB10, or from a machine whose `jarvis/.env` has the
authenticated `JARVIS_NATS_URL`.)

---

## 5. Gotchas / must-knows (save the next session time)

1. **Jarvis has no NATS user/password config field.** `JarvisConfig` exposes only
   `nats_url` and `nats_credentials_path`. The fleet broker uses user/password
   accounts (not NKey `.creds`), so jarvis authenticates via **URL-embedded creds**
   (`nats://user:pass@host`). A bare `JARVIS_NATS_PASSWORD` in `jarvis/.env` is
   **ignored** (extra=ignore). If a cleaner design is wanted later, add
   `nats_user`/`nats_password` (SecretStr) fields + thread them into both the main
   `NATSClient.connect` **and** `fleet_memory/publisher.build_nats_client`
   (`NATSConfig` already supports `user`/`password`). Not required — URL creds work.
2. **`fleet-memory` the PACKAGE is not a jarvis dependency.** Jarvis is write-only;
   the write path uses `nats_core` (base dep) for `MemoryEpisodeV1` + `publish_episode`.
   The `fleet-memory` package is only for *reads* (which jarvis doesn't do). If a
   read path lands (FEAT-JARVIS-008), add `fleet-memory` as an extra, mirroring
   guardkit's `memory` extra + `FleetMemoryClient.search`.
3. **The publisher connects per-episode** (connect → publish → disconnect), off the
   dispatch hot path via `asyncio.create_task`. Heavier than reusing the supervisor's
   long-lived `NATSClient`, but matches guardkit and keeps the memory-write identity
   independent. A future optimisation could reuse the live connection.
4. **The DDR-019 filename keeps its `graphiti` slug** (`DDR-019-graphiti-fire-and-forget-writes.md`)
   — cited in `routing_history.py` docstrings as intentional history. `grep -rni graphiti src/jarvis`
   returns only migration notes + that slug (8 refs, all intentional).
5. **`.guardkit/` + `features/` BDD** were left as historical FEAT-JARVIS-004 artifacts
   where they describe the graphiti era; they're not on the `tests/` path and don't run
   in the suite. `.guardkit/graphiti.yaml` was removed; `.guardkit/.mcp.json` graphiti
   server emptied.
6. **Shared-repo hazard:** a parallel session committed `54a17f7` to local `main`
   mid-effort. Always `git fetch` + `git merge-base --is-ancestor origin/main HEAD`
   before push; stage with **explicit pathspecs** (never `git add -A`) — the
   `.guardkit/autobuild/FEAT-28FF/`, `.guardkit/features/FEAT-28FF.yaml`, and
   `tasks/backlog/jarvis-notification-bridge/` untracked dirs are unrelated WIP and
   must stay out of memory-cutover commits.

---

## 6. What remains / possible next moves

Nothing is blocking; the migration is done and proven. Optional follow-ups:

- **Relay-side ingestion check (ops):** the live proof asserts the *publish* succeeded
  (jarvis's responsibility). Confirming the episode landed in Postgres is the
  fleet-memory relay's domain — query for `document:jarvis:*` records if you want the
  full round-trip evidence.
- **`.env` tidy:** `FALKORDB_HOST` is now dead config (jarvis no longer uses FalkorDB) —
  safe to delete from `jarvis/.env` (and any `.env.example` if present).
- **Read side (FEAT-JARVIS-008):** the learning consumer that *reads* routing history.
  Would add the `fleet-memory` extra + a `search`-style method + a group→payload read
  mapping (mirror guardkit's `FleetMemoryClient.search`).
- **Cleaner NATS auth (optional):** add `nats_user`/`nats_password` config fields (gotcha #1)
  so creds don't live in the URL.
- **Fleet-wide FalkorDB decommission + `qwen-graphiti` LLM removal** from the GB10
  llama-swap — operator-gated, coordinated across the other graph consumers
  (forge/specialist-agent/study-tutor, none of which have migrated yet). See the
  guardkit handoff §3.5.

---

## 7. Key pointers

- **Migration commits:** `git show 9ddf33d 776f607`.
- **New write package:** `src/jarvis/infrastructure/fleet_memory/{client,mapping,payloads,publisher,__init__}.py`.
- **Writer (unchanged body, renamed protocol):** `src/jarvis/infrastructure/routing_history.py`
  (`MemoryClientProtocol`, `RoutingHistoryWriter`).
- **Lifecycle seam + wiring:** `src/jarvis/infrastructure/lifecycle.py`
  (`_connect_memory`, `AppState.memory_client`, shutdown step 6 `memory_client.close()`).
- **Config:** `src/jarvis/config/settings.py` (`fleet_memory_enabled`, `fleet_memory_project`,
  reuses `nats_url` + `nats_credentials_path`).
- **Tests:** `tests/test_fleet_memory_{client,mapping,payloads}.py`,
  `tests/test_routing_history_fleet_memory.py`, `tests/test_memory_unavailable.py`,
  `tests/test_routing_history_{writer,offload}.py`, `tests/test_phase4_dependencies.py`
  (repurposed — now asserts graphiti-core is GONE + nats present).
- **Env vars:** `JARVIS_FLEET_MEMORY_ENABLED` (default false; also honours un-prefixed
  `FLEET_MEMORY_ENABLED`), `JARVIS_FLEET_MEMORY_PROJECT` (default `jarvis`),
  `JARVIS_NATS_URL` (must carry `jarvis:<pw>@host` creds for live writes),
  `JARVIS_TRACES_DIR` (offload dir). Documented in `.env.example`.
- **Infra:** `../nats-infrastructure/config/accounts/accounts.conf.template` (the `jarvis`
  user + `memory.episode.jarvis.>` publish perm); `../nats-infrastructure/.env`
  (`JARVIS_NATS_PASSWORD`).
- **Guardkit reference (the pattern this followed):**
  `../../../../guardkit/guardkit/knowledge/fleet_memory_{client,mapping,payloads}.py`,
  `../../../../guardkit/guardkit/memory/harvest_publisher.py`, and the guardkit handoff §3.
