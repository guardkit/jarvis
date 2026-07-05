# TASK-JNB-105 — Implementation Plan

**Task**: jarvis v1.1 reply-path scenario tests (plain pytest)
**Type**: testing (audit existing coverage, add only the delta — do NOT redesign JNB-104)
**Intensity**: light (feature subtask, complexity 5, parent_review present)

## 1. Audit result (verified against the delivered code + suite, 2026-07-05)

System under test = `src/jarvis/infrastructure/slack_reply.py` (JNB-104 reply path).
Existing suite: `tests/test_slack_reply.py` (43), `tests/test_slack_approval_buttons.py`
(48 collected), `tests/test_contract_nats_core.py`.

| JNB-105 scenario / AC | Existing coverage | Verdict |
|---|---|---|
| 1. Unauthorized responder refusal (WARN + ephemeral + zero publish) | `TestUnauthorizedClickRefused` (asserts `slack_reply_unauthorized_click` WARN, ephemeral, no publish) | COVERED |
| 2. Duplicate click single-publish | `TestDoubleClickPublishesAtMostOnce` (sequential + concurrent) | COVERED |
| 3. Approve one, not another (two builds; approve A only; B untouched) | `test_distinct_request_ids_both_publish` approves BOTH → insufficient | **GAP → G1** |
| 4. Unrecognised decision never offered nor published | `test_unknown_action_id_dropped` (no publish); buttons pin `forge_approve`/`forge_reject`; `_ACTION_DECISIONS` maps only those two | COVERED (canonicalise in new module) |
| 5. Buttons disabled after decision | `test_success_update_disables_buttons_and_shows_decision` | COVERED |
| 6. Reply after ended (stale request_id) | **No pending map on the reply handler** — see §3 | **RECONCILED → faithful test** |
| Contract (wire bytes validate vs installed `nats_core.ApprovalResponsePayload`; `decided_by == settings.slack_decided_by` verbatim; subject == `approval_subject + ".response"`) | `test_publishes_enveloped_payload_to_subject` uses `json.loads` dict-key asserts + literal `decided_by`, not the model / settings | **GAP → G2** |
| No `.feature`, no `pytest-bdd` import | all matches are "NO pytest-bdd" docstrings | SATISFIED |

## 2. Deliverable

New module: `tests/test_slack_reply_scenarios_jnb105.py` — plain pytest, hermetic
(mock `SocketModeClient`/`AsyncWebClient` surface; fake JetStream publish capture; the
only real third-party dep exercised is the installed `nats_core` in the contract class).
Six scenario classes whose names mirror the six spec scenarios 1:1, plus a contract class.
Self-contained helpers (no cross-test-module import coupling).

Planned tests (pinned collect-only count = **10**):

1. `TestUnauthorizedResponderRefusal::test_wrong_user_warns_refuses_and_publishes_nothing`
2. `TestDuplicateClickSinglePublish::test_both_duplicate_clicks_acked_and_published_once` (drives the listener seam → asserts two acks + one publish, per the audit-verifier finding)
3. `TestApproveOneNotAnother::test_approving_build_a_publishes_only_a_and_leaves_b_live` **(G1)**
4. `TestUnrecognisedDecisionNeverOfferedNorPublished::test_unknown_decision_publishes_nothing`
5. `TestUnrecognisedDecisionNeverOfferedNorPublished::test_reply_path_recognises_only_approve_and_reject` (consumer-side pin)
6. `TestUnrecognisedDecisionNeverOfferedNorPublished::test_rendered_pause_blocks_offer_only_approve_and_reject` (producer-side "never offered" — rendered Block Kit, closes review finding; JNB-103 in SUT scope)
7. `TestButtonsDisabledAfterDecision::test_authorized_decision_disables_buttons_in_place`
8. `TestReplyAfterEnded::test_wellformed_stale_click_still_publishes_forge_is_authoritative` **(faithful, §3)**
9. `TestReplyPathEnvelopeContract::test_approve_bytes_validate_and_decided_by_verbatim` **(G2)**
10. `TestReplyPathEnvelopeContract::test_reject_bytes_validate_against_installed_nats_core` **(G2)**

Task-file annotation: AC-7 + Test-Requirement #6 marked RECONCILED (done).

## 3. Scenario 6 reconciliation (Rich, 2026-07-05 — Option A)

`ApprovalReplyHandler.__slots__ = (_decided_request_ids, _decision_lock, _publisher,
_settings, _web_client)` — no pending map, and `create_slack_reply_client` passes none.
A well-formed, authorized, first-time click publishes unconditionally (modulo
first-click-wins + `decided_by` set). This is the deliberate DDR-027 posture
(handoff §6). The `ReplyAfterEnded` test therefore asserts the DELIVERED behaviour —
stale click STILL publishes; forge (JNB-106) is the authoritative refuser. **No
production change.**

## 4. Verify step (AC-9)

`.venv/bin/python -m pytest tests/test_slack_reply_scenarios_jnb105.py --collect-only -q`
→ must equal exactly **10** (pinned; a mismatch is a hard failure — the guard that
motivated dropping pytest-bdd).

## 5. Quality gate

Full suite `.venv/bin/python -m pytest` (baseline 2527 passed / 2 skipped → +10 = 2537)
+ `ruff check` + `ruff format --check` + `mypy` on the new file. Then multi-lens
adversarial review (worktree-isolated verifiers), plan audit, in_review, commit.
`git checkout uv.lock` before commit (this task does not own the nats-core bump).

## 6. Constraints honoured

- Runner always `.venv/bin/python -m pytest` from repo root (default interpreter lacks `nats_core`).
- No pytest-bdd / no `.feature`.
- Do NOT redesign `slack_reply.py`.
- No second PIPELINE consumer implied (fake JetStream keeps it structurally impossible).
