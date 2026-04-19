---
id: TASK-JFT-001
title: Bootstrap Jarvis source + Forge build trigger via pipeline.build-queued (Pattern A)
status: backlog
task_type: implementation
parent_review: forge/TASK-REV-A1F2
priority: medium
tags: [jarvis, bootstrap, forge-trigger, nats, integration, pattern-a]
complexity: 8
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Bootstrap Jarvis source and wire the Forge build trigger

## Context

As of TASK-REV-A1F2 (forge alignment review, 15 April 2026), this repo contains **only** `docs/research/ideas/jarvis-vision.md` and no source code. The last commit is `5c04d12` from 31 March 2026 ("Initial ideas docs"). The vision document is well-developed and already uses the CAN-bus fleet-discovery pattern that `nats-infrastructure` has provisioned (`FLEET` stream + `agent-registry` KV bucket), but there is no Python package, no agent manifest, no NATS client wiring, and no way for a human to trigger a Forge build through Jarvis today.

Rich's stated position (captured in the forge anchor v2.2 ADR-SP-014) is:

> Jarvis is the human-facing entry point. Jarvis discovers the Forge's capabilities on the fleet and sends build requests to the Forge.

The chosen integration pattern is **Pattern A** from the alignment review §2.4:

> Jarvis publishes `pipeline.build-queued.{feature_id}` directly to the JetStream `PIPELINE` stream. Forge consumes the same topic regardless of source (CLI or Jarvis). Forge also registers on `fleet.register` for Jarvis's CAN-bus discovery, but the actual dispatch is a JetStream publish, not an `agents.command.forge` request.

This task bootstraps enough Jarvis source code to make that integration real at the minimum level needed for a single-adapter happy path (CLI-wrapper first, voice/Telegram/dashboard later).

## Prerequisites

- `nats-infrastructure` running on GB10 (✅ per alignment review §2.2)
- `nats-core` v2.x with `BuildQueuedPayload` + `pipeline.build-queued` topic (✅ once TASK-NCFA-001 lands)
- Forge registering on `fleet.register` as an agent (⏳ Forge itself does not yet exist — stubbed for now; full Forge wiring is a follow-up)

## Scope

### 1. Repository bootstrap

- `pyproject.toml` — Python package `jarvis`, dependencies: `nats-core` (from local path or git), `pydantic`, `pydantic-settings`, `click` or `typer` for CLI
- `src/jarvis/__init__.py`
- `README.md` — one-paragraph description + "see `docs/research/ideas/jarvis-vision.md` for full design"
- `.gitignore`, `ruff.toml`/`pyproject.toml` lint config matching sibling repos

### 2. Agent manifest (Jarvis is itself a fleet agent)

`src/jarvis/manifest.py`:

```python
from nats_core.manifest import AgentManifest, IntentCapability, ToolCapability

def get_jarvis_manifest(agent_id: str = "jarvis") -> AgentManifest:
    return AgentManifest(
        agent_id=agent_id,
        name="Jarvis",
        description="Intent router and human-facing entry point for the fleet",
        trust_tier="core",
        nats_topic=f"agents.command.{agent_id}",
        max_concurrent=4,
        intents=[
            IntentCapability(
                pattern="dispatch.*",
                signals=["route", "dispatch", "ask"],
                confidence=1.0,
            ),
            IntentCapability(
                pattern="build.*",
                signals=["build", "implement", "ship", "make feature"],
                confidence=0.85,  # defers to Forge's own confidence if Forge is registered
            ),
        ],
        tools=[
            ToolCapability(
                name="jarvis_route",
                description="Classify an intent and dispatch to the best-matching fleet agent",
                risk_level="read_only",
                async_mode=True,
            ),
            ToolCapability(
                name="jarvis_build",
                description="Route a build request to the Forge via pipeline.build-queued",
                risk_level="mutating",
                async_mode=True,
            ),
        ],
    )
```

### 3. Fleet discovery

`src/jarvis/fleet/discovery.py`:

- Subscribes to `fleet.register` / `fleet.deregister` / `fleet.heartbeat.>` via `nats-core`'s `NATSClient`
- Maintains a routing table in-memory, mirrored to the `agent-registry` KV bucket
- Provides `discover_agent_for_intent(intent: str) -> AgentManifest | None` — returns the highest-confidence registered agent for a given intent pattern

Minimum viable: just read the current `agent-registry` KV once on startup and refresh on KV watch events. No need for full signal-word matching in v1 — literal intent pattern match is enough to find the Forge for `build.*`.

### 4. Build-request dispatcher (the whole point)

`src/jarvis/dispatch/forge_build.py`:

```python
import uuid
from datetime import datetime, timezone
from nats_core.events import BuildQueuedPayload
from nats_core.topics import Topics

async def dispatch_build_to_forge(
    nats_client,
    feature_id: str,
    repo: str,
    feature_yaml_path: str,
    originating_adapter: str,  # "voice-reachy", "telegram", "dashboard", "cli-wrapper"
    originating_user: str = "rich",
    parent_request_id: str | None = None,
    branch: str = "main",
    max_turns: int = 5,
) -> str:
    """Publish a BuildQueuedPayload to the JetStream PIPELINE stream and
    return the correlation_id so Jarvis can stream progress back."""
    correlation_id = f"bld-{datetime.now(timezone.utc).isoformat()}-{uuid.uuid4().hex[:4]}"
    payload = BuildQueuedPayload(
        feature_id=feature_id,
        repo=repo,
        branch=branch,
        feature_yaml_path=feature_yaml_path,
        max_turns=max_turns,
        sdk_timeout_seconds=1800,
        wave_gating=False,
        config_overrides=None,
        triggered_by="jarvis",
        originating_adapter=originating_adapter,
        originating_user=originating_user,
        correlation_id=correlation_id,
        parent_request_id=parent_request_id,
        retry_count=0,
        requested_at=datetime.now(timezone.utc),
        queued_at=datetime.now(timezone.utc),
    )
    topic = Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)
    await nats_client.publish(topic, payload.model_dump_json().encode())
    return correlation_id
```

### 5. Progress streamer (stub)

`src/jarvis/dispatch/progress_listener.py`:

- Subscribes to `pipeline.build-*.{feature_id}` filtered by `correlation_id`
- Streams events to a callback that each adapter implements
- For now: one CLI-wrapper callback that prints `[stage] status coach_score=X` to stdout

Full voice/Telegram/dashboard adapters are follow-up tasks — this task only needs the machinery to prove the flow works.

### 6. CLI-wrapper entry point

`src/jarvis/cli/main.py`:

```bash
jarvis build FEAT-LPA-042 --repo guardkit/lpa-platform --feature-yaml specs/FEAT-LPA-042.yaml
```

This exists so we can test the end-to-end path without needing voice or Telegram in place. It:

1. Connects to NATS (reads `NATS_URL` env var, default `nats://localhost:4222`)
2. Calls `dispatch_build_to_forge(...)` with `originating_adapter="cli-wrapper"`
3. Starts the progress listener on the returned `correlation_id`
4. Prints every pipeline event until a `build-complete` or `build-failed` arrives

### 7. Minimal tests

- Unit: `test_dispatch_build_publishes_correct_payload` — mock NATSClient, call `dispatch_build_to_forge`, assert published topic and payload fields
- Unit: `test_jarvis_manifest_has_build_and_dispatch_intents`
- Integration (`@pytest.mark.integration`): `test_jarvis_cli_build_round_trip` — requires a running Forge stub that consumes from `pipeline.build-queued.>` and echoes back `build-started` / `build-complete`; for now this test can be marked `xfail` with reason "awaiting Forge implementation" and wired up once Forge exists

### 8. Update `docs/research/ideas/jarvis-vision.md`

Add a new section **"Forge Integration (Pattern A)"** that:

- Cross-references `forge/docs/research/forge-pipeline-architecture.md` v2.2 ADR-SP-014
- Documents that `jarvis build` is the CLI-wrapper today, voice/Telegram/dashboard come later
- Spells out the publish topic and payload type used

## Acceptance criteria

- [ ] `pyproject.toml` exists, `pip install -e .` works, `jarvis --help` runs
- [ ] `get_jarvis_manifest()` returns a valid `AgentManifest` (passes nats-core validation)
- [ ] Fleet discovery reads `agent-registry` KV on startup and watches for changes
- [ ] `dispatch_build_to_forge()` publishes a valid `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}`
- [ ] `jarvis build FEAT-XXX ...` CLI command executes the full dispatch path without error (against live NATS, with or without a Forge consumer)
- [ ] Progress listener correctly filters events by `correlation_id` and prints them
- [ ] Unit tests pass
- [ ] Integration test exists, marked `xfail` if Forge is not yet consuming — unmark and re-run once Forge is in place
- [ ] `jarvis-vision.md` updated with the Pattern A section
- [ ] Jarvis registers on `fleet.register` on startup (visible in `agent-registry` KV)

## Out of scope

- Voice (Reachy Mini) adapter — follow-up task once this skeleton exists
- Telegram / Slack / dashboard adapters — follow-up
- Intent classification LLM (D11 open decision) — not needed for the CLI-wrapper path; dispatcher is called directly
- General Purpose Agent (fallback routing) — follow-up
- Forge itself — this task just publishes, Forge consumes (when it exists)
- `.guardkit/` config / autobuild / feature-spec tooling — add later; this task bootstraps from a truly empty repo

## Bootstrap note

This task also implicitly creates the `jarvis/tasks/backlog/` directory (first task in a previously taskless repo). Future Jarvis tasks should follow the same flat format as this one.
