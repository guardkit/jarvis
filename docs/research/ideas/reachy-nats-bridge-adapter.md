# Reachy NATS Bridge Adapter — Design Document

## For: `/system-design` session · Jarvis · May 2026

---

## Overview

The NATS bridge adapter is a lightweight Python process that runs on the Reachy Mini's
onboard Raspberry Pi. It bridges the Reachy daemon's audio/sensor capabilities with
the Jarvis agent fleet via NATS JetStream on the GB10.

The adapter is the **only custom code** that runs on the Pi. Everything else — the
Reachy daemon, Tailscale, and the OS — is standard. All AI compute (STT, LLM, TTS)
runs on the GB10.

---

## Design Principles

1. **Thin adapter** — ~150-200 lines of Python. No AI inference on the Pi.
2. **Daemon-first** — Uses the Reachy SDK to interact with the daemon, never bypasses it.
3. **Network-resilient** — NATS reconnection with backoff; daemon reconnection on timeout.
4. **Unit-configurable** — Single codebase, configured via env vars (`UNIT_NAME=scholar`
   or `UNIT_NAME=bridge`) to set NATS topics and behaviour defaults.
5. **Reusable STT/TTS** — Calls Parakeet and Kokoro HTTP APIs on the GB10, same
   containers used by any other Jarvis service.

---

## Architecture

```
┌─────────────────────────── Reachy Mini (Pi) ──────────────────────────┐
│                                                                       │
│  ┌──────────────┐         ┌──────────────────────────────────┐        │
│  │ Reachy Daemon │◄───────►│       NATS Bridge Adapter        │        │
│  │  (port 8000)  │  SDK    │                                  │        │
│  │               │  calls  │  - Audio capture (mic via SDK)   │        │
│  │  Motors       │◄────────│  - Audio playback (spkr via SDK) │        │
│  │  Camera       │         │  - Expression commands           │        │
│  │  Mic/Speaker  │         │  - NATS pub/sub (nats-py)        │        │
│  │  LEDs         │         │  - HTTP calls to STT/TTS on GB10 │        │
│  └──────────────┘         └──────────────┬───────────────────┘        │
│                                           │                           │
└───────────────────────────────────────────┼───────────────────────────┘
                                            │ Tailscale
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
│  │  Subscribes: jarvis.voice.{scholar|bridge}                      │  │
│  │  Publishes:  jarvis.speech.{scholar|bridge}                     │  │
│  │              notifications.{scholar|bridge}                     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
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

## Fork Strategy: reachy_mini_conversation_app

### Decision: Fork the Conversation App

The `pollen-robotics/reachy_mini_conversation_app` is broadly compatible with our
NATS bridge architecture. Forking it gives us a substantial feature set for free,
and the changes required are well-isolated to the voice/LLM backend layer.

### What We Get for Free

| Feature | How it works | Value |
|---------|-------------|-------|
| Real-time audio loop | `fastrtc` for low-latency streaming | Handles VAD, chunking, streaming — no custom audio code |
| Head tracking | YOLO or MediaPipe face detection | Scholar tracks Lilymay's face during tutoring |
| Motion system | Layered: primary moves + speech-reactive wobble + tracking | Natural, alive feel without manual animation coding |
| Dances & emotions | Pre-recorded choreography library via HF datasets | Celebration animations, idle behaviours |
| Profile system | `profiles/<name>/instructions.txt` | Maps directly to Scholar/Bridge persona config |
| Gradio web UI | Optional `--gradio` flag, live transcripts | Debug UI during development, console mode for production |
| Camera integration | Vision via backend or local SmolVLM2 | Future: Scholar recognises who's in the room |
| Wireless support | `uv sync --extra wireless` adds GStreamer deps | Already handles Pi ↔ remote audio streaming |
| App framework | Extends `ReachyMiniApp` base class | Installable via Reachy app store / HF Spaces |

### What We Change

The conversation app has **pluggable voice backends**: Hugging Face (default),
OpenAI Realtime (`gpt-realtime`), and Gemini Live. We add a fourth backend:
`nats-local` that routes to our Parakeet STT + Kokoro TTS on the GB10 via NATS.

**Backend swap points:**

1. **STT path** — Currently: audio → fastrtc → cloud STT (via selected backend).
   Fork: audio → fastrtc → HTTP POST to Parakeet on GB10 → transcript text.
   The `fastrtc` layer handles VAD and audio chunking for us — we only replace
   the transcription endpoint.

2. **LLM path** — Currently: transcript → cloud LLM (OpenAI/HF/Gemini) → response.
   Fork: transcript → NATS publish `jarvis.voice.{unit}` → Jarvis intent router
   → agent fleet → response text on NATS `jarvis.speech.{unit}`.
   This is the core change: replacing a synchronous LLM call with async NATS
   pub/sub. The adapter subscribes to the response topic and feeds text back
   into the conversation loop.

3. **TTS path** — Currently: response text → cloud TTS (via selected backend) → audio.
   Fork: response text → HTTP POST to Kokoro on GB10 → WAV audio → play via daemon.
   Again, Kokoro exposes an OpenAI-compatible `/v1/audio/speech` endpoint, so the
   integration is minimal.

**New tools to register:**

- `agent_status` — Query Jarvis fleet status via NATS request-reply
- `approve` / `reject` — Human-in-the-loop responses to pending agent actions
- `student_progress` (Scholar only) — Query Graphiti for Lilymay's study state
- `notify_list` — Read back pending notifications

These are registered as tools in the conversation app's tool dispatch system,
which already supports async tool calls with motion blending.

### What We Don't Change

- Motion system (wobble, breathing, head tracking, dances, emotions)
- Camera pipeline and face detection
- Daemon connection and error handling
- App lifecycle (`ReachyMiniApp` base class)
- Gradio UI (useful for development, optional in production)
- Profile system (Scholar/Bridge profiles with custom instructions)

### Fork Repo Structure

```
guardkit/reachy-jarvis-bridge/          # Fork of reachy_mini_conversation_app
├── pyproject.toml                       # Add nats-py, aiohttp deps
├── .env.example                         # GB10_HOST, NATS_URL, STT_URL, TTS_URL
├── profiles/
│   ├── scholar/
│   │   └── instructions.txt             # GCSE tutor persona, Lilymay context
│   └── bridge/
│       └── instructions.txt             # Ship's Computer / Jarvis persona
├── src/
│   ├── backends/
│   │   └── nats_local.py                # NEW: NATS + Parakeet STT + Kokoro TTS
│   ├── tools/
│   │   ├── agent_status.py              # NEW: Fleet status via NATS
│   │   ├── approve_reject.py            # NEW: HITL approval via NATS
│   │   └── student_progress.py          # NEW: Graphiti query (Scholar only)
│   └── ... (existing conversation app code)
└── README.md
```

### Implementation Sequence

1. **Fork and verify** — Clone conversation app, run in simulation mode (`--sim`)
   with existing OpenAI backend. Confirm motion, tools, Gradio UI all work.
2. **Add NATS backend** — Implement `nats_local.py` backend. Wire STT to Parakeet,
   TTS to Kokoro, LLM path to NATS pub/sub. Test against GB10 via Tailscale.
3. **Create profiles** — Write Scholar and Bridge persona instructions.
   Configure voice packs (Kokoro `bf_emma` for Scholar, `bm_daniel` for Bridge).
4. **Add custom tools** — Register `agent_status`, `approve_reject`,
   `student_progress` in the tool dispatch system.
5. **Test on hardware** — Deploy to Pi via SSHFS editable install. Verify
   audio round-trip, head tracking, motion blending, NATS connectivity.
6. **Package as app** — Register as Reachy Mini app installable from dashboard.

### Compatibility Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `fastrtc` audio loop tightly coupled to cloud backends | Low | The backend is selected via CLI flag; adding a new one follows established pattern |
| Pi CM4 too slow for face detection (YOLO/MediaPipe) | Medium | Use `--no-camera` flag initially; add face detection later when confirmed |
| `nats-py` async loop conflicts with `fastrtc` event loop | Low | Both are asyncio-native; test early in step 2 |
| Conversation app updates diverge from fork | Medium | Pin to known-good commit; periodically rebase. Upstream changes unlikely to touch backend abstraction layer |
| Kokoro/Parakeet Docker containers contend with llama-swap | Low | Kokoro is 82M params, Parakeet is 1.1B — both tiny vs main LLM. Monitor with `nvidia-smi` |

---

## Remaining Design Questions

1. **Concurrent audio** — Can the Reachy daemon handle simultaneous mic capture and
   speaker playback (full-duplex)? Need to test. If half-duplex, implement
   barge-in detection (stop TTS playback when user starts speaking).
2. **NATS async response pattern** — The conversation app expects synchronous
   request/response from the LLM backend. NATS pub/sub is async. Options:
   (a) Use NATS request-reply for synchronous flow, or (b) bridge with an
   `asyncio.Event` that the NATS subscription handler signals when response arrives.
   Option (b) is more natural for NATS and allows streaming partial responses.
3. **Profile hot-switching** — Can we switch between Scholar and Bridge profiles
   at runtime (e.g. if the same physical unit needs to serve both roles)?
   Low priority but nice-to-have.

---

## Related Documents

- Reachy Mini integration outline: `jarvis/docs/research/ideas/reachy-mini-integration.md`
- NVIDIA Photo Booth: `github.com/NVIDIA/spark-reachy-photo-booth`
- Kokoro on GB10: `forums.developer.nvidia.com/t/running-kokoro-tts-on-nvidia-dgx-spark-arm64-gb10/368846`
- Parakeet on GB10: `forums.developer.nvidia.com/t/multilingual-speech-to-text-stt-asr-with-nvidia-parakeet-tdt-0-6b-v3-for-the-dgx-spark/365554`
