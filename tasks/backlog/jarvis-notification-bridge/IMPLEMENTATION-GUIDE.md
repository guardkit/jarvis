# Jarvis Notification Bridge (FEAT-UBS-003) — Implementation Guide

**Parent review:** TASK-REV-C951 (forge repo: `../../../../forge/.claude/reviews/TASK-REV-C951-review-report.md`)
**Spec:** forge repo, `../../../../forge/features/jarvis-notification-bridge/` (`.feature`, assumptions YAML, summary)
**Scope:** 16 tasks across two sibling repos — jarvis (12) and forge (4). v1 (TASK-JNB-001..009) is jarvis-only push notifications to Slack; v1.1 (TASK-JNB-101..107) adds the phone reply path (approve/reject) across both repos.

This is the canonical guide for the whole feature. Each task file is self-contained (the jarvis-scoped autobuild worktree cannot read the sibling forge repo), but sequencing, contracts, and gates are defined here.

---

## 1. Data Flow

```mermaid
flowchart LR
    subgraph Writes
        FP["forge pipeline publisher<br/>build-started / stage-complete / build-complete /<br/>build-failed / build-paused / build-resumed"]
        BC["forge publish_build_cancelled<br/>pipeline_publisher.py:272"]
        BPRG["build-progress<br/>(NO LIVE PRODUCER)"]
        QB["jarvis queue_build publish hook<br/>tools/dispatch.py (post-PubAck, fire-and-forget)"]
        ARQ["forge approval-request emit<br/>agents.approval.forge.{build_id}"]
    end
    subgraph Storage
        PIPE[("PIPELINE stream<br/>workqueue retention<br/>exactly ONE ephemeral consumer")]
        AG[("AGENTS stream<br/>limits retention — overlap legal")]
        SQ[("in-process sink queue<br/>bounded asyncio.Queue")]
    end
    subgraph Reads
        SUB["ForgeNotificationsSubscriber<br/>single ephemeral consumer<br/>6-subject filter (was 4; extended in TASK-JNB-005)"]
        WK["SlackNotifier worker<br/>~1 msg/s chat.postMessage, plain_text blocks"]
        CLI["CLI FIFO rendering"]
        CAP["v1.1 jarvis approval capture<br/>agents.approval.forge.> (4-token filter,<br/>never matches .response)"]
        ASUB["forge ApprovalSubscriber<br/>agents.approval.forge.{build_id}.response"]
    end
    ALERT["DISCONNECTION ALERT: no producer emits<br/>build-cancelled in v1 — the jarvis handler is<br/>implemented and unit-validated from day one but<br/>stays silent until TASK-JNB-102 wires the three<br/>CANCELLED transitions in forge"]

    FP --> PIPE
    BC -. "NOT WIRED until TASK-JNB-102" .-> PIPE
    BPRG -. "no live producer" .-> PIPE
    PIPE --> SUB
    SUB --> CLI
    SUB -- "sink.notify() after decode + source gate +<br/>payload validation; correlation-INDEPENDENT" --> SQ
    QB --> SQ
    SQ --> WK
    ARQ --> AG
    AG --> CAP
    AG --> ASUB
    BC --- ALERT
    style BC stroke:#c0392b,color:#c0392b
    style ALERT fill:#fdecea,stroke:#c0392b,color:#c0392b
    linkStyle 1 stroke:#c0392b,stroke-dasharray:6 4
    linkStyle 11 stroke:#c0392b,stroke-dasharray:6 4
```

*Caption: all Slack traffic flows through the single existing PIPELINE ephemeral consumer and an in-process sink queue — the queued event bypasses the stream entirely via the `queue_build` publish hook, and only the AGENTS stream (limits retention) ever gains new consumers.*

## 2. Integration Contract — v1.1 Reply Path

```mermaid
sequenceDiagram
    participant FG as forge gating (wrappers.py)
    participant PIPE as PIPELINE stream
    participant AG as AGENTS stream
    participant SUB as jarvis ForgeNotificationsSubscriber
    participant CAP as jarvis approval capture
    participant SN as jarvis SlackNotifier
    participant PH as Slack (phone)
    participant SM as jarvis Socket Mode client
    participant AS as forge ApprovalSubscriber

    FG->>PIPE: build-paused envelope (BuildPausedPayload carries approval_subject)
    FG->>AG: ApprovalRequestPayload (request_id per build_id)
    PIPE->>SUB: delivery via 6-subject filter
    AG->>CAP: capture request_id into TTL'd pending map (dedup on request_id)
    SUB->>SN: notify(pause projection — approval_subject retained)
    SN->>PH: pause message with Block Kit Approve/Reject buttons<br/>(value JSON: request_id, build_id, correlation_id, approval_subject)
    Note over PH,SM: defer-republish mints a refreshed request_id ->\nchat.update swaps buttons in place (no dead button)
    PH->>SM: block_actions (button click)
    SM->>SM: ack immediately, then gate user.id == JARVIS_SLACK_OPERATOR_USER_ID
    alt unauthorised user
        SM-->>PH: WARN + ephemeral refusal — nothing published
    else authorised operator
        SM->>AG: ApprovalResponsePayload(request_id, decision, decided_by=slack_decided_by)<br/>to approval_subject + '.response', carrying the request's correlation_id
        SM->>PH: chat.update disables buttons (local first-click-wins)
        AG->>AS: response delivery
        AS->>AS: 4-step validation: payload -> decided_by allowlist vs expected_approver<br/>-> correlation_id match -> request_id 300s dedup
        alt approve / override
            AS->>FG: await_response resolves -> mark_resume_pending -> build resumes
        else reject (or REASON_MAX_WAIT / CLI cancel)
            AS->>FG: CANCELLED transition (SQLite authoritative)
            FG->>PIPE: build-cancelled (post-TASK-JNB-102, best-effort per DDR-007)
            PIPE->>SUB: delivery
            SUB->>SN: notify(cancelled)
            SN->>PH: terminal cancelled confirmation on the phone
        end
    end
```

*Caption: window/expiry-race enforcement lives exclusively forge-side, so a reply-vs-expiry race resolves in exactly one place to one outcome; the jarvis operator-id gate is a courtesy filter, the forge 4-step chain is the authority.*

## 3. Task Dependency Graph

```mermaid
graph TD
    J1["TASK-JNB-001 (W1)<br/>SlackNotifier + settings + slack-sdk"]
    J2["TASK-JNB-002 (W1)<br/>sink seam + queued hook"]
    J3["TASK-JNB-003 (W2)<br/>lifecycle wiring"]
    J4["TASK-JNB-004 (W3)<br/>LIVE v1 CHECKPOINT — HARD GATE"]
    J5["TASK-JNB-005 (W4)<br/>pause + cancelled lifecycle"]
    J6["TASK-JNB-006 (W4)<br/>hardening: dedup / throttle / bounds"]
    J7["TASK-JNB-007 (W4)<br/>DDR set"]
    J8["TASK-JNB-008 (W5)<br/>v1 scenario test matrix"]
    J9["TASK-JNB-009 (W6)<br/>LIVE v1 hardening validation"]
    F101["TASK-JNB-101 (W7, forge)<br/>ApprovalSubscriber wiring"]
    J103["TASK-JNB-103 (W7)<br/>approval capture + buttons"]
    F102["TASK-JNB-102 (W8, forge)<br/>build-cancelled emit"]
    J104["TASK-JNB-104 (W8)<br/>Socket Mode reply path"]
    J105["TASK-JNB-105 (W9)<br/>jarvis v1.1 reply tests"]
    F106["TASK-JNB-106 (W9, forge)<br/>forge v1.1 tests"]
    J107["TASK-JNB-107 (W10)<br/>LIVE v1.1 validation"]

    J1 --> J3
    J2 --> J3
    J3 --> J4
    J3 --> J5
    J3 --> J6
    J3 --> J7
    J5 --> J8
    J6 --> J8
    J8 --> J9
    J4 --> F101
    J4 --> J103
    J5 --> J103
    F101 --> F102
    J103 --> J104
    J104 --> J105
    F101 --> F106
    F102 --> F106
    F102 --> J107
    J104 --> J107
    J105 --> J107
    F106 --> J107

    classDef parallel fill:#d5f5d5,stroke:#2e7d32
    classDef handoff fill:#ffe8b3,stroke:#b8860b
    class J1,J2,J5,J6,J7,F101,J103,J105,F106 parallel
    class J4,J9,J107 handoff
```

*Caption: green nodes are parallel-safe within their wave (W1: 001+002, W4: 005+006+007, W7: 101+103, W9: 105+106); amber nodes are the three operator_handoff tasks AutoBuild never attempts.*

## §4 Integration Contracts

Consumers of each contract carry `consumer_context` frontmatter and a `## Seam Tests` section in their task files; producers do not.

### Contract 1 — NOTIFICATION_SINK
| Field | Value |
|---|---|
| Producer | TASK-JNB-001 (`src/jarvis/infrastructure/slack_notifier.py`) |
| Consumers | TASK-JNB-002 (subscriber seam + `queue_build` hook), TASK-JNB-003 (lifecycle binding) |
| Artifact type | Python async protocol, in-process jarvis (`asyncio`) |
| Format constraint | `async notify(ForgeNotification)` must NEVER raise into the caller; failures are WARNING + continue (DDR-007 — the SQLite ledger is authoritative) |
| Validation | `pytest.mark.seam` tests on both consumers: await `notify()` with a Slack client mock raising `SlackApiError` and assert no exception propagates and a WARNING is logged |

### Contract 2 — WIDENED_FORGENOTIFICATION
| Field | Value |
|---|---|
| Producer | TASK-JNB-005 (event_type Literal + optional fields per the frozen-model rule) |
| Consumer | TASK-JNB-103 (button routing) |
| Artifact type | pydantic model (jarvis `ForgeNotification`) |
| Format constraint | pause projection retains `approval_subject`; new fields are optional with `None` defaults so CLI rendering is unaffected |
| Validation | seam test: pause-projected `ForgeNotification` round-trips `approval_subject` and renders with `coach_score` None |

### Contract 3 — BUTTON_METADATA
| Field | Value |
|---|---|
| Producer | TASK-JNB-103 (Block Kit Approve/Reject buttons) |
| Consumer | TASK-JNB-104 (Socket Mode `block_actions` handler) |
| Artifact type | Slack Block Kit interactive buttons over Socket Mode (`slack-sdk` SocketModeClient) |
| Format constraint | button value is JSON `{request_id, build_id, correlation_id, approval_subject}` and must stay within Slack's 2000-char action value limit |
| Validation | seam test: value JSON round-trip including a length assertion < 2000 chars with max-size build/correlation ids |

### Contract 4 — APPROVER_IDENTITY
| Field | Value |
|---|---|
| Producer | TASK-JNB-101 (forge `expected_approver` config) |
| Consumer | TASK-JNB-104 (jarvis `slack_decided_by` config) |
| Artifact type | config string equality: forge `expected_approver` == jarvis `slack_decided_by` (pydantic-settings) |
| Format constraint | exact string match; a mismatch silently refuses every phone approval |
| Validation | seam test: published `ApprovalResponsePayload.decided_by` equals `settings.slack_decided_by` verbatim; named config-alignment AC in both TASK-JNB-101 and TASK-JNB-104; probed live in TASK-JNB-107 |

## 5. Wave-by-Wave Execution Strategy

**Waves 1–6 are v1, entirely in jarvis. Waves 7–10 are v1.1, interleaving jarvis and forge.** Autobuild worktrees are repo-scoped: jarvis tasks are seeded into jarvis `tasks/`, forge tasks into forge's — wave discipline, not worktree scope, is the cross-repo coordination mechanism.

| Wave | Tasks | Notes |
|---|---|---|
| 1 | TASK-JNB-001 ∥ TASK-JNB-002 | Parallel jarvis autobuild. No shared files: 001 owns `slack_notifier.py` + settings; 002 owns the subscriber seam + `tools/dispatch.py` hook. |
| 2 | TASK-JNB-003 | `build_app_state` in `infrastructure/lifecycle.py` constructs the notifier only when `JARVIS_SLACK_BOT_TOKEN` + `JARVIS_SLACK_CHANNEL_ID` are set; logged no-op sink otherwise. |
| 3 | TASK-JNB-004 | **LIVE v1 CHECKPOINT — HARD GATE.** Operator handoff: /invite the bot to #forge-builds, restart jarvis with the JARVIS_SLACK_* env, queue a toy feature from Open WebUI, watch the phone show queued -> running -> terminal exactly once each. **No v1.1 work of any kind starts until this passes.** Checkpoint prerequisites were verified 2026-07-03 but are perishable; this task re-checks them first. Note: dedup lands post-checkpoint (TASK-JNB-006), so one at-least-once double-post during the toy run is cosmetic and expected. |
| 4 | TASK-JNB-005 ∥ TASK-JNB-006 ∥ TASK-JNB-007 | Filter extension 4 -> 6 subjects on the ONE consumer (never a new consumer); hardening; DDR set including the ASSUM-010 v1 acceptance and the correlation-independent fan-out decision (operator sign-off required — config toggle is the rollback lever). |
| 5 | TASK-JNB-008 | v1 scenario test matrix, plain pytest, collect-only count assertion. |
| 6 | TASK-JNB-009 | Operator handoff: live pause-on-phone, burst, restart validation. |
| 7 | TASK-JNB-101 (forge) ∥ TASK-JNB-103 (jarvis) | Different repos, fully parallel. 101 is the highest-uncertainty task (`await_response` has zero production call sites today); slippage delays only v1.1 replies, never the v1 surface. |
| 8 | TASK-JNB-102 (forge) then/∥ TASK-JNB-104 (jarvis) | 102 is serialized after 101 because both edit `gating/wrappers.py`; 104 depends only on 103 and can run alongside 102. |
| 9 | TASK-JNB-105 (jarvis) ∥ TASK-JNB-106 (forge) | Test suites over the production wiring in each repo. |
| 10 | TASK-JNB-107 | Operator handoff: approve and reject from the phone; reject must produce a cancelled confirmation on the phone (ASSUM-010 closed); probes the expected_approver/slack_decided_by alignment live. Requires both repos merged. |

### Feature-YAML gating (operational note)

The v1 feature YAML is generated in jarvis `.guardkit/features` **now**. The v1.1 feature YAMLs (one for jarvis, one for forge) are **deliberately not generated until TASK-JNB-004 passes — that is the gate mechanism.** No YAML, no autobuild dispatch: the hard gate is enforced structurally, not by convention. The v1.1 task frontmatter carries `feature_id: pending-v1.1` for the same reason.

### Step-11 BDD-linking skip (rationale)

The operator chose plain pytest for all test tasks (decision 2026-07-03). Tagging scenarios `@task:` would activate the R2 pytest-bdd oracle with **no `.feature` glue present — the exact known silent-false-green class**. Test classes mirror spec scenario names instead, and each testing task carries an explicit scenario list plus a collect-only count assertion. Run tests via `.venv/bin/python -m pytest` from the task's repo root.

### Standing constraints (apply to every task)

- **One PIPELINE consumer, ever** (workqueue retention; a second consumer fails with err_code 10100). The Slack surface is an in-process sink inside the existing consumer's `_handle_message`; the queued event never touches the stream. TASK-JNB-002/005 carry explicit no-err-10100 startup ACs.
- **DDR-007 never-regress:** notification failures are WARNING + drop; nothing raises into the JetStream callback, `queue_build`, or gating.
- **DDR-027 no-replay:** dedup and pending-approval state are in-process only; a crash inside a 300s window may double-post low-impact noise, which is accepted.
- **Correlation-INDEPENDENT fan-out is deliberate:** the phone is per-operator, not per-session — a jarvis restart (LRU correlation loss) must not blind the overnight surface. DDR-recorded in TASK-JNB-007.

### Operator follow-up tasks: 3

TASK-JNB-004, TASK-JNB-009, TASK-JNB-107 are `task_type: operator_handoff` — AutoBuild will not attempt them; the operator verifies the runtime ACs manually and completes them via /task-complete.
