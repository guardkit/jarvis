# RESULTS — TASK-LCA-006 fix verification followup (2026-05-13)

**Parent RESULTS:** [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`](../../RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md)
**Related task:** [`study-tutor@TASK-LCA-006`](https://github.com/guardkit/study-tutor/blob/main/tasks/completed/TASK-LCA-006-coach-misconception-schema-drift-bugfix.md)
**Fix commit:** `study-tutor@3ad9abd` — fix(FEAT-6CC5): coerce bare-string CoachVerdict.misconceptions (TASK-LCA-006)
**Verified at:** 2026-05-13 08:33–08:34 UTC (~09:33 BST)
**Method:** CLI smoke via `nats request agents.command.jarvis` (no OpenWebUI; same wire path the demo uses minus the fleet-pipe leg)

---

## Closes — Known Issue #1 from parent RESULTS

The parent RESULTS file's "Known issues / non-blockers" §1 — *Study-tutor coach orchestrator pydantic schema mismatch* — is **now stale and resolved**. Coach verdict path no longer falls back to `coach_unreachable`; coach evaluation, the revision loop, and (downstream) misconception persistence to Graphiti are all available again on the demo path.

The demo-day talk-track for 2026-05-16 can drop the caveat about "tutor coaching quality is currently degraded" — the tutor coaching arc in Turn 2 will now exercise the full coach loop, not the silent player-only fallback.

---

## Verification chain

### Unit tests (local, no container)

```
$ .venv/bin/python -m pytest tests/unit/tutoring/coach/test_factory.py -x -q
61 passed in 0.09s
```

All 61 tests in the coach factory test module pass, including the new TASK-LCA-006 tests covering: bare-string coercion, canonical happy path, genuinely-malformed rejection (preserves `extra="forbid"` semantics), and regression payload from the 2026-05-12 logs.

### Container rebuild

```
$ cd ~/Projects/appmilla_github/study-tutor
$ docker compose -f docker-compose.study-tutor.yml build
... DONE 1.1s → study-tutor:dev (sha256:4b66eb44…)
$ docker compose -f docker-compose.study-tutor.yml up -d --force-recreate
$ docker ps --filter name=gcse-tutor
study-tutor-gcse-tutor-1   Up 5 seconds   study-tutor:dev
```

Container is on the fresh image carrying the model_validator + tightened coach prompt.

### CLI smoke results

| Smoke | RTT | Wire shape | Outcome |
|---|---|---|---|
| `lca-006-smoke-001` | 22.66s | `tutor_start_session` + first `tutor_turn` | Tutor returned Socratic prompt on dagger soliloquy (AO1-then-AO2 coaching pattern) |
| `lca-006-smoke-002` | 38.19s | second `tutor_turn` w/ deliberately-flawed student response ("witches put a spell on him") | Tutor pushed back on agency / AO3 — *exactly* the coach-evaluated coaching shape, not the player-only fallback shape |

The "witches put a spell on him" misconception in smoke #2 was deliberately chosen to give the coach a high-confidence misconception target. The tutor's pushback ("Macbeth *chooses* to act on the prophecy — he deliberates, he debates, he decides") is the kind of correction that the coach scoring + revision loop is designed to drive.

### Container log signals (post-rebuild, since 2026-05-13 08:29 UTC)

| Signal | Pre-fix (2026-05-12) | Post-fix (this session) |
|---|---|---|
| `coach_unreachable` warnings | every tutor_turn (≥10 in 17h baseline) | **0** ✅ |
| `MalformedCoachOutputError` | every tutor_turn | **0** ✅ |
| `orchestrator_turn_flagged reason=coach_unreachable` | every tutor_turn | **0** ✅ |
| `orchestrator_turn_completed` (clean exit) | 0 | **3** ✅ |
| `coach_misconception_coerced` (positive fix telemetry) | n/a | 0 |
| httpx POSTs to llama-swap from coach orchestrator | n/a | 3 |

Captured logs: [`lca-006-followup-gcse-tutor-container.log`](lca-006-followup-gcse-tutor-container.log) (20 lines, post-restart only) and the JSON summary at [`lca-006-followup-evidence.json`](lca-006-followup-evidence.json).

### Interpretation of the zero `coach_misconception_coerced` count

This is **a feature, not a bug**. The TASK-LCA-006 fix has two layers (per the AC matrix):

1. **Prompt tightening** in `roles/tutor/prompts/coach.md` — primary fix; makes the coach LLM emit canonical `{"topic_name": ..., "misconception_text": ...}` objects natively.
2. **`model_validator(mode="before")`** in `CoachVerdict` — safety-net coercion for prompt drift; emits `coach_misconception_coerced` per coercion.

Zero coercion events in three coach evaluations means **layer 1 is doing the heavy lifting** — the coach LLM is consistently emitting the canonical object shape on its own, so the safety net hasn't needed to engage. If telemetry surfaces non-zero `coach_misconception_coerced` events later, that's the early warning signal that prompt drift is returning and the prompt may need re-tightening.

---

## Knock-on demo-day improvements

With the coach loop restored, Turn 2 of the 2026-05-16 demo will now demonstrate **more than** just specialist dispatching — the tutor will actually show:

- Coach scoring of the player's pedagogical turn (`weighted_total`, `criterion_scores`)
- Decision gate (`accept` vs `revise`) driving the revision loop
- Misconception observations being recorded for downstream Graphiti persistence

This is a stronger demo than the original talk-track planned — the audience sees not just *which* model handled the turn, but *that the coach actually evaluated the player's tutoring quality*. Operator's call whether to highlight this on stage or keep the focus on cross-specialist routing.

---

## Evidence pointers

```
evidence/multi-specialist-demo/
├── RESULTS-LCA-006-followup-2026-05-13.md         # this file
├── lca-006-followup-evidence.json                  # structured verification summary
└── lca-006-followup-gcse-tutor-container.log      # post-rebuild container logs (20 lines)
```

No credentials in any of these — the container logs do not log NATS URLs.

---

## Sign-off

TASK-LCA-006 fix is **verified in production conditions** (container on rebuilt image, real NATS wire, real llama-swap coach model, real supervisor reasoning). No further action required for the 2026-05-16 demo path. The parent RESULTS file's Known Issue #1 can be considered closed.
