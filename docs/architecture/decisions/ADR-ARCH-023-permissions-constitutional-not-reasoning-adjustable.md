# ADR-ARCH-023: Permissions constitutional, not reasoning-adjustable

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Mirrors:** Forge ADR-ARCH-023

## Context

DeepAgents exposes a permissions system (filesystem / shell / network allowlists). If the reasoning model can adjust permissions mid-session (via a tool or prompt suggestion), it opens an attack surface via prompt-injection and an agency-safety surface (reasoning-model decides to read files outside its allowlist to "help").

## Decision

Permissions are declared in `jarvis.config` (or `jarvis.yaml`) at startup and are **not reasoning-adjustable**:

- No tool exposes a "change_permissions" capability to the reasoning model.
- Permission changes require a Jarvis restart with updated config.
- Permission set is versioned in source control; changes reviewed like any other config PR.

Jarvis's default permission set:
- **Filesystem**: read-only to `~/.jarvis/` + `~/Projects/` (read-only); write to `~/.jarvis/traces/`; no access to `/etc`, `/usr`, SSH keys, etc.
- **Shell**: no `execute` on the unattended path. Attended adapter-originated commands go through restricted command allowlist.
- **Network**: outbound HTTPS only to configured endpoints (`promaxgb10-41b1:9000` = llama-swap, `whitestocks:6379` = FalkorDB, configured external APIs, cloud-frontier provider endpoints).

## Alternatives considered

1. **Reasoning-adjustable permissions** *(rejected)*: Prompt-injection exploitation vector; unacceptable.
2. **No permissions at all** *(rejected)*: Agent can accidentally (or adversarially) reach system files or arbitrary endpoints.

## Consequences

- Constitutional — Rich is the only permission author; changes are explicit.
- Restart-to-change ergonomics are acceptable for single-operator use.
- Belt+braces constitutional enforcement (ADR-ARCH-022) means the executor also asserts permissions at tool-invocation time.
