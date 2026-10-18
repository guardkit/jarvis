-- The tables of Forge's record that the Linear door reads, in their final
-- shape at Forge commit dbd40c7e (main, 18 October 2026).
--
-- Produced by running Forge's own src/forge/lifecycle/schema.sql and
-- schema_v2.sql ... schema_v19.sql in order on an empty database, then the
-- mission DDL of src/forge/lifecycle/missions.py ensure_tables (which also
-- adds builds.mission_id and builds.mission_role), and copying each table's
-- CREATE statement from sqlite_master unchanged. Copied, not read from a Forge
-- checkout, so these tests run without one. Regenerate it the same way when
-- Forge's schema changes.

CREATE TABLE builds (
    build_id TEXT PRIMARY KEY,                       -- build-{feature_id}-{YYYYMMDDHHMMSS}
    feature_id TEXT NOT NULL,
    repo TEXT NOT NULL,
    branch TEXT NOT NULL,
    feature_yaml_path TEXT NOT NULL,
    project TEXT,                                    -- NULL = fleet-wide

    status TEXT NOT NULL CHECK (status IN (
        'QUEUED', 'PREPARING', 'RUNNING', 'PAUSED', 'FINALISING',
        'COMPLETE', 'FAILED', 'INTERRUPTED', 'CANCELLED', 'SKIPPED'
    )),

    triggered_by TEXT NOT NULL CHECK (triggered_by IN (
        'cli', 'jarvis', 'forge-internal', 'notification-adapter'
    )),
    originating_adapter TEXT,
    originating_user TEXT,
    correlation_id TEXT NOT NULL,
    parent_request_id TEXT,                          -- Jarvis dispatch ID

    queued_at TEXT NOT NULL,                         -- ISO 8601 UTC
    started_at TEXT,
    completed_at TEXT,

    worktree_path TEXT,
    pr_url TEXT,
    error TEXT,

    max_turns INTEGER NOT NULL DEFAULT 5,
    sdk_timeout_seconds INTEGER NOT NULL DEFAULT 1800,

    -- Review finding F4: PAUSED-state crash recovery must re-issue the
    -- approval request with the original request_id. Populated only
    -- while status='PAUSED'. Producer side of the
    -- PENDING_APPROVAL_REQUEST_ID integration contract (TASK-PSM-007).
    pending_approval_request_id TEXT
, mode TEXT NOT NULL DEFAULT 'mode-a'
    CHECK (mode IN ('mode-a', 'mode-b', 'mode-c')), profile TEXT, last_coach_score REAL, budget_breach TEXT, task_id TEXT, terminal_class TEXT, merge_branch TEXT, start_commit TEXT, target_branch TEXT, memory_project TEXT, launch_settings TEXT, source_commit TEXT, mission_id TEXT, mission_role TEXT) STRICT;

CREATE TABLE stage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id TEXT NOT NULL REFERENCES builds(build_id),

    stage_label TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK (target_kind IN (
        'local_tool', 'fleet_capability', 'subagent'
    )),
    target_identifier TEXT NOT NULL,

    status TEXT NOT NULL CHECK (status IN (
        'PASSED', 'FAILED', 'GATED', 'SKIPPED'
    )),
    gate_mode TEXT CHECK (gate_mode IN (
        'AUTO_APPROVE', 'FLAG_FOR_REVIEW', 'HARD_STOP', 'MANDATORY_HUMAN_APPROVAL'
    )),

    coach_score REAL,
    threshold_applied REAL,

    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_secs REAL NOT NULL,

    details_json TEXT NOT NULL
) STRICT;

CREATE TABLE "planning_runs" (
    correlation_id TEXT PRIMARY KEY,

    state TEXT NOT NULL CHECK (state IN (
        'QUEUED', 'RUNNING', 'PAUSED', 'FAILED', 'CANCELLED',
        'TIMED_OUT', 'PLANNED_HANDOFF',
        'FEATURE_SPEC', 'FEATURE_PLAN', 'BUILD_QUEUED'
    )),

    originating_user TEXT NOT NULL,
    expected_approver TEXT NOT NULL,
    request_text TEXT NOT NULL,

    target_repo TEXT,
    triggered_by TEXT NOT NULL CHECK (triggered_by IN (
        'cli', 'jarvis', 'forge-internal', 'notification-adapter'
    )),
    originating_adapter TEXT,
    parent_request_id TEXT,

    -- PAUSED-state workflow identifiers
    pending_approval_request_id TEXT,

    -- Escalation counters and timestamps (RT-04 durable escalation state)
    defer_count INTEGER NOT NULL DEFAULT 0,
    paused_at TEXT,
    escalated_at TEXT,

    -- Handoff outputs (populated on PLANNED_HANDOFF terminal)
    handoff_branch TEXT,
    handoff_path TEXT,

    -- Lifecycle timestamps (ISO 8601 UTC)
    queued_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,

    -- Error details (populated on FAILED terminal)
    error TEXT
, start_commit TEXT, target_branch TEXT, memory_project TEXT, launch_settings TEXT) STRICT;

CREATE TABLE planning_run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT NOT NULL REFERENCES planning_runs(correlation_id),

    stage_label TEXT NOT NULL,
    status TEXT NOT NULL,
    gate_mode TEXT,
    coach_score REAL,

    actor_identity TEXT,
    details_json TEXT,

    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE work_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sentence TEXT NOT NULL,
  target_repo TEXT,
  kind TEXT NOT NULL CHECK (kind IN ('feature','fix','question')),
  status TEXT NOT NULL CHECK (status IN ('QUEUED','ADMITTED','DONE','WITHDRAWN','BLOCKED')),
  rank REAL NOT NULL,
  after_id INTEGER REFERENCES work_queue(id),
  originating_user TEXT NOT NULL,
  correlation_id TEXT NOT NULL UNIQUE,
  queued_at TEXT NOT NULL, admitted_at TEXT, closed_at TEXT,
  stale_pinged_at TEXT, keep_count INTEGER NOT NULL DEFAULT 0,
  closed_reason TEXT
) STRICT;

CREATE TABLE work_queue_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_id INTEGER NOT NULL REFERENCES work_queue(id),
  action TEXT NOT NULL, actor_identity TEXT NOT NULL,
  details_json TEXT, recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE publication_records (
    build_id            TEXT PRIMARY KEY,
    feature_id          TEXT,
    repo                TEXT,
    -- Who gave the merge word, and when.
    decided_by          TEXT,
    decided_at          TEXT,
    -- The branch of the remote this work is aimed at, as it was recorded when
    -- the work started. Never chosen at the merge word.
    target_branch       TEXT,
    -- G: where that branch was when the merge word was acted on.
    g_commit            TEXT,
    -- The build's own tip, and J: the commit made by joining it onto G.
    build_tip           TEXT,
    j_commit            TEXT,
    -- Which attempt at the join this record is on.
    attempt             INTEGER NOT NULL DEFAULT 0,
    -- The result word, from the three-name vocabulary. Only
    -- "publication pending" is reachable while publication is switched off.
    result              TEXT,
    -- What the checks produced, and the identity of what was checked, as one
    -- JSON object written by the press.
    checked_json        TEXT,
    -- The lease and the turn number.
    lease_holder        TEXT,
    lease_expires_at    TEXT,
    turn                INTEGER NOT NULL DEFAULT 0,
    -- The lines, oldest first, as a JSON list.
    lines_json          TEXT NOT NULL DEFAULT '[]',
    created_at          TEXT,
    updated_at          TEXT
);

CREATE TABLE missions (id TEXT PRIMARY KEY, title TEXT NOT NULL, target_repo TEXT NOT NULL, branch TEXT NOT NULL UNIQUE, base_commit TEXT, final_commit TEXT, status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'REJECTED', 'NOT_STARTED', 'STARTING', 'RUNNING', 'READY', 'MERGING', 'MERGED', 'NOT_MERGED')), correlation_id TEXT NOT NULL UNIQUE, originating_user TEXT NOT NULL, plan_request_id TEXT, created_at TEXT NOT NULL, approved_at TEXT, approved_by TEXT, closed_at TEXT, closed_reason TEXT, parent_request_id TEXT, originating_adapter TEXT, triggered_by TEXT) STRICT;

CREATE TABLE mission_features (mission_id TEXT NOT NULL REFERENCES missions(id), key TEXT NOT NULL, sentence TEXT NOT NULL, no_sign_in INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (mission_id, key)) STRICT;

CREATE TABLE mission_attempts (mission_id TEXT NOT NULL, key TEXT NOT NULL, attempt INTEGER NOT NULL CHECK (attempt IN (1, 2)), correlation_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL CHECK (status IN ('WAITING', 'ADMITTED', 'LANDED', 'FAILED', 'HELD')), reason TEXT, admitted_at TEXT, closed_at TEXT, PRIMARY KEY (mission_id, key, attempt)) STRICT;

