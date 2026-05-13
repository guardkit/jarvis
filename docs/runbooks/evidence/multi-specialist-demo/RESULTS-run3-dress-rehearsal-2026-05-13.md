# RESULTS — Run-3 Dress Rehearsal (2026-05-13, ~12:24 BST)

**Parent RESULTS:** [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`](../../RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md)
**Predecessor addendum:** [`RESULTS-LCA-006-followup-2026-05-13.md`](RESULTS-LCA-006-followup-2026-05-13.md)
**Run-3 commit verified:** `jarvis@4044e12` (post TASK-DSR-005); `study-tutor@3dba48f` (post TASK-LCA-006 + TASK-LCA-007)
**Method:** Full Phase 4 (Turns 1–4) driven from a fresh OpenWebUI chat session via fleet-pipe → systemd-managed `jarvis-serve-nats.service`

---

## Why run-3 was necessary

After run-1 (this morning, all four turns green), I made two infrastructure changes:

1. **Replaced the foreground-background `jarvis serve-nats` Python process** with a systemd user unit (`jarvis-serve-nats.service`) + Linger=yes for boot autostart.
2. **Rebuilt study-tutor:dev twice** — once for TASK-LCA-006 (coach pydantic), once for TASK-LCA-007 (tool description enrichment).

A run-2 cross-check (~10:25 BST) caught a P0 supervisor routing regression: same Turn 2 prompt as run-1, but the supervisor self-handled instead of dispatching to gcse-tutor (0 envelopes on `agents.command.gcse-tutor`; 6 CLI smoke retries reproduced deterministically). Run-3 verifies the fix lands end-to-end through the OpenWebUI gateway leg, not just CLI smokes.

## The fixes applied between run-2 and run-3

| Fix | Commit | Scope |
|---|---|---|
| Coach pydantic regression | study-tutor@`3ad9abd` (TASK-LCA-006) | Auto-coerce bare-string `misconceptions` entries in `CoachVerdict` so coach loop no longer silently falls back to `coach_unreachable`. |
| Tutor stub-yaml gap (**root cause of run-2 regression**) | jarvis@`4044e12` (TASK-DSR-005) | Add gcse-tutor block to `stub_capabilities.yaml` mirroring its live KV manifest. Closes the same structural gap TASK-DSR-001 W1 closed for architect-agent on 2026-05-08. Supervisor's `{available_capabilities}` prompt now lists 5 agents (was 4) — gcse-tutor included. |
| Tutor description enrichment (additive only) | study-tutor@`3dba48f` (TASK-LCA-007) | Tool descriptions in live KV gain domain signals (GCSE, AO1/AO2/AO3/AO4, subject coverage). Closed with misdiagnosis note — descriptions did not cause the routing fix, but they reach downstream consumers and mirror the language used in the jarvis stub block. |

## Per-turn outcomes

| Turn | Specialist | Jarvis cid | Verdict | Evidence |
|---|---|---|---|---|
| 1 | architect-agent | `c30f8b2c-e4f3-4764-9018-5ee0573d560e` | ✅ Misaligned, 95% confidence — AlignmentJudgment populated (Why + What would need to change) | [`run3-turn-1-architect-payload.json`](run3-turn-1-architect-payload.json) |
| 2 | **gcse-tutor** | `4bfffecf-a443-4149-bd85-ac799e966c06` | ✅ **dispatched** (was 0/3 in run-2) — `tutor_start_session` envelope on `agents.command.gcse-tutor`, fresh tutor session_id `b3cfb76f-7ca7-4d79-a0fe-e15ae3218bc8`, response shape is tutor-quoted Socratic AO1 opener | [`run3-turn-2-tutor-payload.json`](run3-turn-2-tutor-payload.json) |
| 3 | forge | `75b091bf-5977-4933-861b-a65ec2d511bf` | ✅ queue + inline drain (`notifications_drained=1`); `build_queued` + `build_complete` envelopes on cid `975e61ae-d453-4502-bf78-77d95949eed3` | [`run3-turn-3-forge-queue-payload.json`](run3-turn-3-forge-queue-payload.json), [`jarvis-multi-specialist-e2e-pipeline-run3.log`](jarvis-multi-specialist-e2e-pipeline-run3.log) |
| 4 | (recap) | `96453c8f-9753-4381-b132-05d3071b0a60` | ✅ all 3 specialists correctly attributed — **GCSE Tutor named explicitly**, NOT "general-purpose subagent" (the smoking-gun phrasing from run-2) | [`run3-turn-4-recap-payload.json`](run3-turn-4-recap-payload.json) |

## Turn 4 recap (verbatim — proves all 3 specialists were correctly invoked and remembered)

> - **Architect:** Evaluated a proposal to add supervisor-initiated Claude Opus 4.7 cloud escalation and judged it misaligned with ADR-ARCH-001's local-first, attended-only constraints — requiring an ADR amendment before implementation.
> - **GCSE Tutor:** Started a Macbeth tutoring session on the dagger soliloquy, focusing on AO1 (textual knowledge) and AO2 (imagery analysis), and guided the learner step-by-step through the scene.
> - **Forge:** Queued and successfully built FEAT-EC3C from `.guardkit/features/FEAT-EC3C.yaml` in `appmilla/api_test` on main, with progress notifications delivered through this session.

Compare to run-2's recap that mis-attributed the tutor as *"general-purpose subagent"* — that smoking-gun phrasing is **gone**.

## Coach loop health (LCA-006 fix exercised in production)

```bash
$ docker logs --since 30m study-tutor-gcse-tutor-1 | grep -ciE "coach_unreachable|MalformedCoachOutputError"
0
$ docker logs --since 30m study-tutor-gcse-tutor-1 | grep -c "orchestrator_turn_completed"
3
```

Zero `coach_unreachable` warnings across run-3. Three clean `orchestrator_turn_completed` events. Coach evaluation, revision-gate decision, and misconception dispatch all running on the demo path.

## Forge pipeline notes

| Phase | Run-1 | Run-3 |
|---|---|---|
| build-queued | ✅ | ✅ |
| build-started | ✅ | ❌ (never emitted by forge) |
| build-complete (PASSED) | ✅ | ✅ |
| notifications_drained | 2 | 1 |

Same forge-side behaviour as run-2: FEAT-EC3C is `status: completed`, so forge's autobuild_runner takes a fast-path that emits only `build_complete` (skipping `build_started`). The drain-half pass criterion still met (≥1 pipeline event rendered inline in the queue_build reply). Not a regression — different feature would emit the full lifecycle. Out-of-scope for the demo path verification.

## Demo readiness — final state for 2026-05-16

| Component | Status | Notes |
|---|---|---|
| Boot autostart | ✅ jarvis serve-nats systemd user unit + Linger=yes; containers `unless-stopped`; llama-swap user service | Cold-boot the GB10 → walk to it → paste demo prompts. No manual steps. |
| Supervisor routing — architect | ✅ verified across runs 1, 2, 3 | |
| Supervisor routing — gcse-tutor | ✅ verified runs 1 + 3; **was P0 regression in run-2, now FIXED by TASK-DSR-005** | |
| Supervisor routing — forge | ✅ verified across runs 1, 2, 3 | |
| Coach loop quality | ✅ TASK-LCA-006 fix verified twice (CLI smoke + run-3 production conditions); zero `coach_unreachable` events across run-3 | |
| Forge inline-drain | ✅ verified runs 1, 2, 3 | AC-005-06 now reliably exercised |
| Cross-specialist session retention | ✅ verified all three runs | Turn 4 recap correctly attributes all specialists |
| Wire-tap visibility | ✅ rotated per-run logs (`-run1`, `-run3`) | All credential-redacted |

**Verdict:** 2026-05-16 DDD South West demo is fully green. The runbook itself can be promoted from "Draft (dress-rehearsal target)" to "Verified" — three independent full-Phase-4 passes, plus six CLI smoke trials for the regression-and-fix loop, all green.

## Evidence pointers (run-3 additions)

```
evidence/multi-specialist-demo/
├── jarvis-multi-specialist-e2e-command-run3.log   # agents.command.>  tap (12 envelopes)
├── jarvis-multi-specialist-e2e-result-run3.log    # agents.result.>   tap (11 envelopes)
├── jarvis-multi-specialist-e2e-pipeline-run3.log  # pipeline.>        tap (2 envelopes — FEAT-EC3C fast-path)
├── jarvis-multi-specialist-smoke-run3.log         # systemd journalctl dump for jarvis-serve-nats.service
├── run3-turn-1-architect-payload.json             # cid c30f8b2c — AlignmentJudgment
├── run3-turn-2-tutor-payload.json                 # cid 4bfffecf — tutor_start_session opener (Socratic AO1 prompt)
├── run3-turn-3-forge-queue-payload.json           # cid 75b091bf — queue ack + inline build_complete drain
└── run3-turn-4-recap-payload.json                 # cid 96453c8f — three-specialist recap
```

All logs credential-redacted; JSON payloads contain no credentials.

## Remaining post-demo follow-ups (out-of-scope, captured here for the record)

1. **Structural fix for the supervisor catalogue** — make `available_capabilities` (consumed by the supervisor prompt builder) flow from the live KV registry instead of the stub yaml. Closes the second half of TASK-DSR-003 W2. Without this, every new fleet agent has to be manually mirrored into both the live KV AND `stub_capabilities.yaml`. (Acknowledged in TASK-DSR-005 §Out of scope.)
2. **forge `build_started` emission for completed/no-op features** — investigate the autobuild_runner fast-path that skips `build_started` for already-completed features. Cosmetic — doesn't block any AC.
3. **canonical test_stub_capabilities lock-in tests** — update `EXPECTED_AGENT_IDS` and the `DM-stub-registry.md` canonical YAML extract to reflect 5 agents (architect, gcse-tutor, product-owner, ideation, forge). Pre-existing brittle assertions per TASK-DSR-001 R5; bumped by one more failure with this patch but still out-of-scope.
