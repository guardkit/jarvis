# ADR-ARCH-029: Personal-use compliance posture — no formal regime

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Jarvis is single-operator, single-user. No external user data, no multi-tenancy, no B2B sales surface. Formal compliance regimes (GDPR-as-processor, SOC2, HIPAA, PCI-DSS) don't apply.

## Decision

**No formal compliance regime in v1.** Applicable constraints:

- **GDPR data-subject**: Rich is the sole data subject and the data controller. No processor relationship to manage.
- **External API ToS**: Jarvis respects Telegram, Google, Anthropic, OpenAI, Open-Meteo, Home Assistant terms. LLM content flowing to cloud providers (via `escalate_to_frontier`) falls under Rich's personal relationship with those providers.
- **Data residency**: Trace data and personal content stored on GB10 (local) + Synology NAS (local). No third-party sharing. Cloud LLM content flows off-host under provider ToS as an explicit tradeoff for `escalate_to_frontier` capability.
- **Retention**: Per ADR-FLEET-001 fleet retention policy — Graphiti permanent with archive to NAS. Logs local-rotated (14 days).

If Jarvis ever becomes multi-user, the compliance posture **must be reconsidered before that transition** — in particular, Graphiti retention and cloud-escape routing policies would need to change.

## Alternatives considered

1. **Apply SOC2-lite controls pre-emptively** *(rejected for v1)*: Premature; adds overhead for a posture that doesn't apply yet.
2. **Explicit GDPR compliance documentation** *(not needed)*: Rich is both data controller and data subject.

## Consequences

- No compliance-driven architectural constraints in v1.
- Fast iteration path — no audit/approval cycle for architectural changes.
- **Trigger condition** for reconsideration: any change that admits a second user or shares Jarvis capabilities with external parties.
- Captured as `ASSUM-009`.
