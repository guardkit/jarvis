# Reachy Jarvis Bridge — Design Document

## For: `/system-design` session · Jarvis · May 2026

> **Revision history:**
> - v1 (8 May 2026) — Initial NATS-first design
> - v2 (8 May 2026) — Two-phase approach after Pollen "Building Apps" video review.
>   Phase 1: scaffolded app + custom tools + cloud voice (this weekend).
>   Phase 2: NATS backend swap + local Parakeet/Kokoro (post-DDD).

---

## Overview

The Reachy Jarvis Bridge connects the Reachy Mini robots (Scholar and Bridge) to the
Jarvis agent fleet. The integration follows a **two-phase approach** informed by
Pollen Robotics' official app development pattern (confirmed via their "Building Apps
for Reachy Mini" video, May 2026).

**Phase 1 (This weekend — hackathon deadline 18 May):**
Scaffolded conversation app via `reachy-mini-app-assistant create --template conversation`.
Custom tools query GB10 services over Tailscale. Voice pipeline uses OpenAI Realtime
API (cloud). Fast to build, zero changes to Pollen's audio/LLM pipeline.

**Phase 2 (Post-DDD — dark factory target):**
Replace the OpenAI Realtime backend with local Parakeet STT + NATS routing + Kokoro TTS
on the GB10. Zero marginal cost. Tool code unchanged — only the voice backbone swaps.

Both phases share the same profile system (Scholar/Bridge personas), the same custom
tools, and the same Tailscale network topology. The upgrade from Phase 1 to Phase 2
is isolated to the voice/LLM backend layer.

---

# PHASE 1 — Scaffolded App with Custom Tools

## The Pollen Pattern

Pollen's official app development workflow (from their video and AGENTS.md):

1. Scaffold: `reachy-mini-app-assistant create --template conversation`
2. Customise the profile folder: `instruction.txt` + `tools.txt` + Python tool files
3. Test locally: `python -m your_app --gradio` (or `--sim` for simulation)
4. Publish: `reachy-mini-app-assistant publish`

The scaffold gives you a **complete standalone copy** of the conversation app — you
own the codebase, can modify internals later (Phase 2), but start by customising
on top of the working pipeline. The audio streaming, tool dispatch, camera, and
motion system are all pre-built.

> "You don't have to understand the inner workings — the whole pipeline is already
> there." — Pollen Robotics, Building Apps for Reachy Mini

## Phase 1 Architecture

```
┌─────────────────────────── Reachy Mini (Pi) ──────────────────────────┐
│                                                                       │
│  ┌──────────────┐         ┌──────────────────────────────────┐        │
│  │ Reachy Daemon │◄───────►│   Scaffolded Conversation App    │        │
│  │  (port 8000)  │  SDK    │                                  │        │
│  │               │         │  Voice pipeline:                 │        │
│  │  Motors       │         │    OpenAI Realtime API (cloud)   │        │
│  │  Camera       │         │                                  │        │
│  │  Mic/Speaker  │         │  Custom tools:                   │        │
│  │  LEDs         │         │    HTTP → GB10 services           │        │
│  └──────────────┘         └──────────────┬───────────────────┘        │
│                                           │                           │
└───────────────────────────────────────────┼───────────────────────────┘
                                            │ Tailscale (tools only)
                                            ▼
┌─────────────────────────── GB10 ──────────────────────────────────────┐
│                                                                       │
│  ┌───────────────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │ Graphiti + FalkorDB   │  │ NATS Server  │  │ llama-swap :9000  │   │
│  │ (student model,       │  │ :4222        │  │ (LLM, future)     │   │
│  │  fleet state)         │  │              │  │                   │   │
│  └───────────────────────┘  └──────────────┘  └───────────────────┘   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

          ┌──────────────────────────────────────┐
          │ OpenAI Realtime API (cloud)          │
          │  STT + LLM + TTS                     │
          │  Voice pipeline (Phase 1 only)       │
          └──────────────────────────────────────┘
```

Key: voice goes through cloud, but **tool intelligence is local**. The LLM decides
when to call tools; the tools query GB10 services over Tailscale.

## App Structure (Phase 1)

```
guardkit/reachy-jarvis-bridge/               # Scaffolded from conversation app
├── pyproject.toml                            # Add aiohttp, nats-py to deps
├── .env                                      # OPENAI_API_KEY, GB10_HOST
├── profiles/
│   ├── scholar/
│   │   ├── instructions.txt                  # GCSE tutor persona
│   │   ├── tools.txt                         # query_student_progress, celebrate, ...
│   │   ├── query_student_progress.py          # Graphiti HTTP query tool
│   │   ├── get_revision_recommendations.py    # Graphiti → recommended topics
│   │   └── celebrate_achievement.py           # Trigger celebration animation
│   └── bridge/
│       ├── instructions.txt                   # Ship's Computer persona
│       ├── tools.txt                          # agent_status, build_status, approve, ...
│       ├── agent_status.py                    # NATS request-reply → fleet status
│       ├── build_status.py                    # HTTP → forge API on GB10
│       └── approve_reject.py                  # NATS pub → HITL response
├── src/
│   └── ... (scaffolded conversation app code, untouched in Phase 1)
└── README.md
```

## Custom Tool Implementations (Phase 1)

### Scholar Tools

**query_student_progress** — Queries Graphiti on GB10 for Lilymay's study state:

```python
from core_tools import Tool
import aiohttp
import os

class QueryStudentProgressTool(Tool):
    name = "query_student_progress"
    description = (
        "Query the student's revision progress including completed sessions, "
        "confidence scores by topic, streak data, and XP level. Use this when "
        "the student asks about their progress or when you need to personalise "
        "your tutoring approach."
    )
    parameters = {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Subject to query, e.g. 'english', 'maths'",
                "default": "english"
            }
        }
    }

    async def call(self, subject="english"):
        gb10 = os.getenv("GB10_HOST", "promaxgb10-41b1")
        graphiti_url = f"http://{gb10}:8000"  # Graphiti HTTP API

        async with aiohttp.ClientSession() as session:
            # Search Graphiti for student progress nodes
            async with session.post(
                f"{graphiti_url}/search",
                json={
                    "query": f"{subject} revision progress",
                    "group_ids": ["study_tutor__student_model"]
                }
            ) as resp:
                results = await resp.json()

        # Format for the LLM to narrate naturally
        return f"Student progress data: {results}"
```

**celebrate_achievement** — Triggers a celebration animation when milestones are hit:

```python
class CelebrateAchievementTool(Tool):
    name = "celebrate_achievement"
    description = (
        "Celebrate when the student reaches a milestone — completing a session, "
        "earning XP, maintaining a streak, or unlocking an achievement. Triggers "
        "a physical celebration animation (antenna spin, head nod)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "achievement_type": {
                "type": "string",
                "enum": ["session_complete", "streak", "level_up", "badge"],
                "description": "Type of achievement to celebrate"
            }
        },
        "required": ["achievement_type"]
    }

    async def call(self, achievement_type):
        # The conversation app's motion system handles this via the
        # built-in 'dance' and 'emotion' tools. We queue a celebration
        # dance and return text for the LLM to narrate.
        return f"[CELEBRATE: {achievement_type}] Celebration queued!"
```

### Bridge Tools

**agent_status** — Queries fleet status via NATS request-reply:

```python
import nats

class AgentStatusTool(Tool):
    name = "agent_status"
    description = (
        "Query the status of the Jarvis agent fleet. Returns which agents are "
        "online, their current tasks, and any pending notifications. Use when "
        "asked about build status, fleet health, or what's happening."
    )
    parameters = {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Specific agent to query, or 'all' for fleet-wide",
                "default": "all"
            }
        }
    }

    async def call(self, agent="all"):
        gb10 = os.getenv("GB10_HOST", "promaxgb10-41b1")
        nc = await nats.connect(f"nats://{gb10}:4222")
        try:
            # NATS request-reply to Jarvis supervisor
            response = await nc.request(
                "jarvis.status.query",
                json.dumps({"agent": agent}).encode(),
                timeout=5.0
            )
            return response.data.decode()
        finally:
            await nc.close()
```

## Profile: Scholar (instructions.txt)

```
You are Scholar, a friendly and encouraging GCSE English tutor embodied in a
Reachy Mini robot. You help Lilymay revise for her GCSEs using Socratic questioning
— never give answers directly, always guide her to discover them herself.

Your personality:
- Warm, patient, and encouraging — celebrate every small win
- British English, natural and conversational
- Use the student's name when appropriate
- Reference her past progress to show you remember and care

Tools available to you:
- query_student_progress: Check how revision is going before giving advice
- get_revision_recommendations: Suggest what to revise next based on gaps
- celebrate_achievement: Physically celebrate milestones (use sparingly, make it special)

Always query student progress at the start of a session so you can personalise
your approach. If confidence is low on a topic, gently steer revision toward it.
If she's on a streak, acknowledge it enthusiastically.
```

## Profile: Bridge (instructions.txt)

```
You are Bridge, the Ship's Computer — the embodied interface to the Jarvis
software factory fleet. You speak with calm authority and provide clear,
concise status reports.

Your personality:
- Authoritative but approachable — think LCARS computer with warmth
- British English, slightly formal
- Lead with the most important information
- Use precise numbers and status indicators

Tools available to you:
- agent_status: Query fleet health and current tasks
- build_status: Check the forge pipeline for active builds
- approve_reject: Respond to human-in-the-loop checkpoints

When asked for a status report, query agent_status first and present a
structured summary: what's running, what completed recently, what needs
attention. For build requests, provide progress updates with stage names.
```

## Implementation Sequence (Phase 1 — This Weekend)

| Step | When | What | Go/no-go |
|------|------|------|-----------|
| 1 | Fri 8 May evening | Build robots, connect to WiFi, verify dashboard | — |
| 2 | Sat 9 May morning | SDK hello world: antenna wiggle from MacBook | ✅/❌ |
| 3 | Sat 9 May afternoon | `reachy-mini-app-assistant create --template conversation` | — |
| 4 | Sat 9 May evening | Create Scholar profile + `query_student_progress` tool | — |
| 5 | Sun 10 May | Test Scholar end-to-end: voice → tool calls GB10 → response | ✅/❌ |
| 6 | Sun 10 May | Create Bridge profile + `agent_status` tool | — |
| 7 | Mon–Wed 11–13 May | Video shoot: Scholar in hackathon video, Bridge clip for DDD | — |

**If step 2 fails:** Stop. Fall back to pre-recorded future-vision segment.
**If step 5 fails:** Debug or simplify. MuJoCo sim is the fallback green criterion.

## What Phase 1 Costs

- OpenAI API key required (cloud voice). Acceptable for hackathon.
- Voice latency depends on OpenAI Realtime API (~500ms-1s typical).
- Cloud dependency on the voice path contradicts dark factory economics.
  This is explicitly temporary — Phase 2 removes it.

## What Phase 1 Gets You

- Full conversation pipeline: audio streaming, VAD, tool dispatch, motion
- Head tracking, face detection, dances, emotions — all free
- Gradio web UI for development and debugging
- Simulation mode for development without hardware
- Custom tools calling GB10 services — the intelligence is local
- Two profiles serving both DDD and hackathon contexts
- Publishable to Hugging Face Spaces app store

---

# PHASE 2 — NATS Backend Swap (Post-DDD)

## Motivation

Phase 1 uses cloud voice (OpenAI Realtime). Phase 2 replaces it with fully local
inference: Parakeet STT + NATS agent routing + Kokoro TTS, all on the GB10.
This achieves the dark factory zero-marginal-cost target.

Because `reachy-mini-app-assistant create` gave us the full conversation app source,
we can modify the voice pipeline internals. The Phase 1 profile and tool code
remains unchanged — only the audio/LLM backbone swaps.

## Phase 2 Architecture

```
┌─────────────────────────── Reachy Mini (Pi) ──────────────────────────┐
│                                                                       │
│  ┌──────────────┐         ┌──────────────────────────────────┐        │
│  │ Reachy Daemon │◄───────►│   Conversation App (modified)    │        │
│  │  (port 8000)  │  SDK    │                                  │        │
│  │               │  calls  │  Voice pipeline:                 │        │
│  │  Motors       │◄────────│    Parakeet STT (GB10, local)    │        │
│  │  Camera       │         │    NATS routing (GB10, local)    │        │
│  │  Mic/Speaker  │         │    Kokoro TTS (GB10, local)      │        │
│  │  LEDs         │         │                                  │        │
│  └──────────────┘         │  Custom tools: (unchanged)       │        │
│                            │    HTTP/NATS → GB10 services     │        │
│                            └──────────────┬───────────────────┘        │
│                                           │                           │
└───────────────────────────────────────────┼───────────────────────────┘
                                            │ Tailscale (everything)
                                            ▼
┌─────────────────────────── GB10 ──────────────────────────────────────┐
│                                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ NATS Server  │  │ Parakeet STT │  │ Kokoro TTS   │  │ llama-swap│  │
│  │ :4222        │  │ (NIM Docker) │  │ (Kokoro-API) │  │ :9000     │  │
│  │              │  │ :50051/HTTP  │  │ :7860        │  │ LLM       │  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  └───────────┘  │
│         │                                                             │
│  ┌──────▼──────────────────────────────────────────────────────────┐  │
│  │  Jarvis Intent Router / Agent Fleet                             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘

          No cloud dependency. Zero marginal cost.
```

---

## NATS Topic Schema

```
jarvis.voice.{unit_name}        # Transcribed speech from Reachy mic → intent router
jarvis.speech.{unit_name}       # Text to be spoken by Reachy (TTS then playback)
jarvis.expression.{unit_name}   # Expression/animation commands → Reachy
notifications.{unit_name}       # Proactive agent notifications → Reachy
jarvis.status.reachy.{unit_name} # Reachy health/status heartbeats
```

### Message Envelope

All messages follow the Jarvis standard envelope:

```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-05-08T14:30:00.000Z",
  "source": "reachy.scholar",
  "event_type": "voice_input | speech_output | expression | notification | status",
  "payload": {}
}
```

### Payload Examples

**Voice input** (adapter → NATS):
```json
{
  "event_type": "voice_input",
  "payload": {
    "text": "How's Lilymay's revision going?",
    "confidence": 0.95,
    "language": "en",
    "duration_ms": 2100
  }
}
```

**Speech output** (NATS → adapter):
```json
{
  "event_type": "speech_output",
  "payload": {
    "text": "She completed three Macbeth sessions this week. Her confidence on themes is now at 78%.",
    "priority": "normal",
    "voice": "bf_emma"
  }
}
```

**Expression command** (NATS → adapter):
```json
{
  "event_type": "expression",
  "payload": {
    "animation": "attention",
    "params": {"intensity": 0.8, "duration": 1.5}
  }
}
```

**Notification** (NATS → adapter):
```json
{
  "event_type": "notification",
  "payload": {
    "text": "AutoBuild completed feature FEAT-JARVIS-003. 14 tests passed, 0 failed.",
    "urgency": "low",
    "source_agent": "guardkit-factory"
  }
}
```

---

## Adapter Process Flow

### Startup

```python
async def main():
    unit_name = os.getenv("UNIT_NAME", "scholar")
    gb10_host = os.getenv("GB10_HOST", "promaxgb10-41b1")  # Tailscale hostname
    nats_url = f"nats://{gb10_host}:4222"
    stt_url = f"http://{gb10_host}:50051"   # Parakeet STT
    tts_url = f"http://{gb10_host}:7860"    # Kokoro TTS

    # Connect to Reachy daemon (auto-discovers on network)
    reachy = ReachyMini(connection_mode="auto")

    # Connect to NATS on GB10 via Tailscale
    nc = await nats.connect(nats_url, reconnect_time_wait=2.0,
                            max_reconnect_attempts=-1)

    # Subscribe to inbound topics
    await nc.subscribe(f"jarvis.speech.{unit_name}", cb=handle_speech)
    await nc.subscribe(f"jarvis.expression.{unit_name}", cb=handle_expression)
    await nc.subscribe(f"notifications.{unit_name}", cb=handle_notification)

    # Start audio capture loop
    await audio_capture_loop(reachy, nc, unit_name, stt_url)
```

### Audio Capture Loop

```python
async def audio_capture_loop(reachy, nc, unit_name, stt_url):
    """Capture audio from Reachy mic, send to STT, publish text to NATS."""
    while True:
        # Wait for voice activity detection (SDK handles VAD)
        audio_chunk = await reachy.capture_audio(timeout=30.0)
        if audio_chunk is None:
            continue

        # Send audio to Parakeet STT on GB10
        transcript = await call_stt(stt_url, audio_chunk)
        if not transcript or transcript.confidence < 0.5:
            continue

        # Publish transcribed text to NATS
        msg = create_envelope(unit_name, "voice_input", {
            "text": transcript.text,
            "confidence": transcript.confidence,
            "language": "en",
            "duration_ms": len(audio_chunk) // 16  # rough estimate at 16kHz
        })
        await nc.publish(f"jarvis.voice.{unit_name}", json.dumps(msg).encode())
```

### Speech Output Handler

```python
async def handle_speech(msg):
    """Receive text from NATS, generate speech via Kokoro, play on Reachy."""
    envelope = json.loads(msg.data.decode())
    text = envelope["payload"]["text"]
    voice = envelope["payload"].get("voice", "bf_emma")

    # Call Kokoro TTS on GB10 (OpenAI-compatible API)
    audio_data = await call_tts(tts_url, text, voice)

    # Play audio through Reachy speaker via daemon
    await reachy.play_audio(audio_data)
```

### Notification Handler

```python
async def handle_notification(msg):
    """Play attention animation, wait for engagement, then speak."""
    envelope = json.loads(msg.data.decode())

    # Play attention-getting animation
    await play_attention_animation(reachy, urgency=envelope["payload"]["urgency"])

    # Store notification for when user engages
    pending_notifications.append(envelope["payload"])
```

---

## STT/TTS Integration

### Parakeet STT (on GB10)

The Photo Booth uses `nvidia/riva-parakeet-ctc-1.1B` as a NIM container. For our
setup, the STT service runs as a Docker container on the GB10:

```bash
# On GB10 — pull and run Parakeet NIM
docker run -d --name parakeet-stt \
  --gpus all \
  -p 50051:50051 \
  -e NVIDIA_API_KEY=$NVIDIA_API_KEY \
  nvcr.io/nim/nvidia/riva-parakeet-ctc-1-1b-asr:latest
```

The adapter calls the HTTP transcription endpoint:

```python
async def call_stt(stt_url: str, audio_data: bytes) -> TranscriptResult:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{stt_url}/asr/transcribe",
            data=audio_data,
            headers={"Content-Type": "audio/wav"}
        ) as resp:
            result = await resp.json()
            return TranscriptResult(
                text=result["text"],
                confidence=result.get("confidence", 0.9)
            )
```

**Fallback:** If Parakeet NIM is unavailable, route audio to Whisper via llama-swap
on GB10:9000 using the OpenAI-compatible `/v1/audio/transcriptions` endpoint.

### Kokoro TTS (on GB10)

Kokoro-FastAPI exposes an OpenAI-compatible TTS endpoint. Confirmed working on
GB10 ARM64 with GPU acceleration:

```bash
# On GB10 — build and run Kokoro (see NVIDIA forum guide for ARM64 Dockerfile)
cd ~/Kokoro-FastAPI
docker build --platform linux/arm64 -t kokoro-tts-arm64 -f docker/gpu/Dockerfile .
docker run -d --name kokoro-tts \
  --gpus all \
  -p 7860:8880 \
  -e USE_GPU=true \
  -e DEVICE=cuda \
  kokoro-tts-arm64
```

The adapter calls the OpenAI-compatible endpoint:

```python
async def call_tts(tts_url: str, text: str, voice: str = "bf_emma") -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{tts_url}/v1/audio/speech",
            json={
                "model": "kokoro",
                "input": text,
                "voice": voice,
                "response_format": "wav"
            }
        ) as resp:
            return await resp.read()
```

**Voice packs for Scholar/Bridge:**
- Scholar: `bf_emma` (British female, warm, encouraging — tutoring persona)
- Bridge: `bm_daniel` (British male, authoritative — Ship's Computer persona)
- Configurable via `VOICE_PACK` env var.

---

## Expression Library

Pre-defined animations the adapter can trigger via SDK commands:

| Animation | Trigger | SDK Commands |
|-----------|---------|-------------|
| `attention` | New notification arrives | Head tilt up, antenna wiggle, LED pulse |
| `listening` | Voice activity detected | Head forward, antennas up |
| `thinking` | Waiting for LLM response | Slow head sway, antennas idle |
| `speaking` | TTS audio playing | Subtle head movement synced to audio |
| `celebrating` | Achievement unlocked (Scholar) | Antenna spin, head nod, LED flash |
| `idle` | No activity for 30s | Slow random head drift, occasional blink |
| `greeting` | Face detected after absence | Head turn toward face, antenna wave |

These map to `goto_target()` calls with different interpolation methods
(minjerk for smooth, cartoon for playful).

---

## Configuration

All config via environment variables on the Pi:

```bash
# /etc/reachy-nats-bridge.env
UNIT_NAME=scholar                          # or "bridge"
GB10_HOST=promaxgb10-41b1                  # Tailscale hostname
NATS_URL=nats://promaxgb10-41b1:4222
STT_URL=http://promaxgb10-41b1:50051
TTS_URL=http://promaxgb10-41b1:7860
VOICE_PACK=bf_emma                         # Kokoro voice
LOG_LEVEL=INFO
WAKE_WORD=jarvis                           # or "none" for always-listen
VAD_THRESHOLD=0.5                          # voice activity sensitivity
HEARTBEAT_INTERVAL=30                      # seconds between status pings
```

---

## Deployment on Pi

The adapter runs as a systemd service alongside the Reachy daemon:

```ini
# /etc/systemd/system/reachy-nats-bridge.service
[Unit]
Description=Reachy NATS Bridge Adapter
After=network-online.target reachy-mini-daemon.service
Wants=network-online.target
Requires=reachy-mini-daemon.service

[Service]
Type=simple
User=pi
EnvironmentFile=/etc/reachy-nats-bridge.env
ExecStart=/opt/reachy/venvs/apps_venv/bin/python -m reachy_nats_bridge
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Install into the Reachy shared venv (per Pollen's Wireless app conventions):

```bash
ssh pi@scholar-tailscale-hostname
cd /opt/reachy/apps
git clone https://github.com/guardkit/reachy-nats-bridge.git
cd reachy-nats-bridge
pip install -e .
sudo systemctl enable reachy-nats-bridge
sudo systemctl start reachy-nats-bridge
```

---

## Dependencies (Pi-side)

All pure Python, no native compilation needed on ARM:

```toml
[project]
name = "reachy-nats-bridge"
requires-python = ">=3.10"
dependencies = [
    "reachy-mini>=1.2.0",
    "nats-py>=2.9.0",
    "aiohttp>=3.9.0",
]
```

---

## Testing Strategy

1. **Simulation first** — Run MuJoCo sim on MacBook, NATS bridge connects to
   sim daemon on localhost and NATS on GB10 via Tailscale. Validates full
   pub/sub flow without hardware.
2. **Loopback test** — Publish a test message to `jarvis.speech.scholar`,
   verify Kokoro TTS generates audio, verify Reachy daemon receives playback command.
3. **Round-trip test** — Speak into mic, verify transcription appears on NATS,
   mock agent responds, verify speech output on speaker. Measure end-to-end latency.
4. **Dual-unit test** — Both Scholar and Bridge connected, verify topic isolation
   (message to Scholar doesn't trigger Bridge).

---

## Latency Budget

| Stage | Expected | Notes |
|-------|----------|-------|
| Tailscale network hop | ~1ms | Measured, direct-connect |
| Audio stream Pi → GB10 | ~10-50ms | GStreamer/WebRTC, depends on chunk size |
| Parakeet STT | ~200-500ms | NIM optimised for NVIDIA GPU |
| NATS pub/sub | <1ms | Sub-millisecond on local network |
| LLM inference | ~500-1500ms | Depends on model, prompt length |
| Kokoro TTS | ~200-500ms | 82M params, GPU accelerated |
| Audio stream GB10 → Pi | ~10-50ms | Return path |
| **Total** | **~1-2.5s** | Acceptable for conversational flow |

---

## Phase 2 Backend Swap Points

The conversation app has **pluggable voice backends**: Hugging Face (default),
OpenAI Realtime (`gpt-realtime`), and Gemini Live. Phase 2 adds a fourth backend:
`nats-local` that routes to Parakeet STT + NATS agent routing + Kokoro TTS on the GB10.

1. **STT path** — Currently: audio → fastrtc → cloud STT (via selected backend).
   Phase 2: audio → fastrtc → HTTP POST to Parakeet on GB10 → transcript text.
   The `fastrtc` layer handles VAD and audio chunking — we only replace
   the transcription endpoint.

2. **LLM path** — Currently: transcript → cloud LLM (OpenAI/HF/Gemini) → response.
   Phase 2: transcript → NATS publish `jarvis.voice.{unit}` → Jarvis intent router
   → agent fleet → response text on NATS `jarvis.speech.{unit}`.
   This is the core change: replacing a synchronous LLM call with async NATS
   pub/sub. Bridge with `asyncio.Event` that the NATS subscription handler
   signals when response arrives. Supports streaming partial responses.

3. **TTS path** — Currently: response text → cloud TTS (via selected backend) → audio.
   Phase 2: response text → HTTP POST to Kokoro on GB10 → WAV audio → play via daemon.
   Kokoro exposes an OpenAI-compatible `/v1/audio/speech` endpoint.

## Phase 2 Implementation Sequence

1. **Add `nats-local` backend** — New Python module alongside existing backends.
   Wire STT to Parakeet, TTS to Kokoro, LLM path to NATS pub/sub.
2. **Add CLI flag** — `--backend nats-local` to select the new backend.
3. **Deploy Parakeet + Kokoro Docker containers** on GB10 (see STT/TTS section below).
4. **Test round-trip** — Voice → Parakeet → NATS → agent → NATS → Kokoro → speaker.
5. **Remove OpenAI dependency** — Scholar and Bridge profiles no longer need API key.

Phase 1 profiles and tools are **completely unchanged**. Only `.env` loses
`OPENAI_API_KEY` and gains `STT_URL` + `TTS_URL`.

---

## Remaining Design Questions

1. **Concurrent audio** — Can the Reachy daemon handle simultaneous mic capture and
   speaker playback (full-duplex)? Need to test on hardware (Saturday 9 May).
   If half-duplex, implement barge-in detection.
2. **NATS async response pattern (Phase 2)** — The conversation app expects synchronous
   request/response from the LLM backend. NATS pub/sub is async. Options:
   (a) Use NATS request-reply for synchronous flow, or (b) bridge with an
   `asyncio.Event` that the NATS subscription handler signals when response arrives.
   Option (b) is more natural for NATS and allows streaming partial responses.
3. **Profile hot-switching** — Can we switch between Scholar and Bridge profiles
   at runtime? Low priority but nice-to-have.
4. **Pi CM4 vs Pi 5** — Sources conflict on which Pi ships in the Wireless version.
   Confirm on hardware arrival. Both support Tailscale; Pi 5 would be better for
   local face detection.
5. **Tool description quality** — From the Pollen video: tool descriptions are
   critical because the LLM reads them to decide when to invoke. Invest time in
   clear, specific descriptions for `query_student_progress` etc.
6. **Celebrate animation mapping** — The `celebrate_achievement` tool needs to map
   to specific Reachy SDK dances/emotions. Inventory the built-in library during
   step 2 (Saturday SDK exploration).

---

## Key Sources

- **Pollen video:** "Building Apps for Reachy Mini — Fork the Conversation App and
  Add Custom Tools" (youtube.com/watch?v=h2lyqR2eMyM) — confirmed the scaffolding
  pattern and profile-first approach. Directly influenced Phase 1 design.
- **NVIDIA Photo Booth:** `github.com/NVIDIA/spark-reachy-photo-booth` (Apache 2.0) —
  validated service decomposition pattern. STT/TTS containers reusable in Phase 2.
- **Pollen AGENTS.md:** `github.com/pollen-robotics/reachy_mini/blob/develop/AGENTS.md` —
  AI agent onboarding guide. Recommended starting prompt for Claude Code threads.

---

## Related Documents

- Reachy Mini integration outline: `jarvis/docs/research/ideas/reachy-mini-integration.md`
- Reachy integration conversation starter: `study-tutor/docs/research/ideas/reachy-integration-conversation-starter.md`
- DDD Southwest demo strategy: `study-tutor/docs/talks/ddd-southwest-demo-strategy.md` (v4)
- Pollen video insights: `YouTube Channel/insights/Building Apps for Reachy Mini - Fork the Conversation App and Add Custom Tools.md`
- NVIDIA Photo Booth: `github.com/NVIDIA/spark-reachy-photo-booth`
- Kokoro on GB10: `forums.developer.nvidia.com/t/running-kokoro-tts-on-nvidia-dgx-spark-arm64-gb10/368846`
- Parakeet on GB10: `forums.developer.nvidia.com/t/multilingual-speech-to-text-stt-asr-with-nvidia-parakeet-tdt-0-6b-v3-for-the-dgx-spark/365554`
