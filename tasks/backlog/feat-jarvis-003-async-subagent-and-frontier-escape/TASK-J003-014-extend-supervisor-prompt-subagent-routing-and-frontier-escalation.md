---
id: TASK-J003-014
title: Extend supervisor_prompt — Subagent Routing + Frontier Escalation sections
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 3
implementation_mode: direct
estimated_minutes: 33
dependencies: [TASK-J003-009, TASK-J003-011]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, prompt]
---

# Extend supervisor_prompt — Subagent Routing + Frontier Escalation sections

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Append two new sections after FEAT-JARVIS-002's Tool-Usage section in `SUPERVISOR_SYSTEM_PROMPT`. Phase 1 attended-conversation posture + FEAT-J002 tool-usage preferences must be preserved verbatim (design.md §10).

## Acceptance Criteria

- [ ] `src/jarvis/prompts/supervisor_prompt.py` — `SUPERVISOR_SYSTEM_PROMPT` gains `## Subagent Routing` section after the Tool-Usage section. The section names `jarvis-reasoner` verbatim, states it runs locally on `gpt-oss-120b`, mentions the three role modes (`critic`, `researcher`, `planner`) and their postures, warns against using it for arithmetic/lookups/file reads, and mentions llama-swap cold-warm ack.
- [ ] Same file — next section `## Frontier Escalation` — states the `escalate_to_frontier` tool is available **only when Rich asks for it explicitly** (e.g. "ask Gemini", "frontier opinion", "cloud model"), is not a default escalation path, will refuse ambient/learning invocation, default target is Gemini 3.1 Pro, `target=OPUS_4_7` is for adversarial critique specifically, and budget is £20–£50/month fleet-wide.
- [ ] Both new sections are **additive**: the diff vs the pre-change file adds only these two sections; Phase 1 + FEAT-J002 content is byte-for-byte unchanged above the insertion point (scenario: *The supervisor system prompt teaches subagent routing and frontier escalation*).
- [ ] Prompt contains **none** of the retired roster names: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local` (Context A concern #3; asserted by TASK-J003-020 regression test).
- [ ] Prompt contains no cloud-fallback-for-quick_local language.
- [ ] Prompt rendered for a new session includes both new sections verbatim.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
