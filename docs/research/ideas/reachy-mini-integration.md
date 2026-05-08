# Reachy Mini Integration — Embodied Interface for Jarvis

## For: `/system-arch` session · Jarvis adapter · May 2026

> **Revision history:**
> - v1 (March 2026) — Initial outline, assumed USB Lite connection
> - v2 (May 2026) — Major revision: Wireless version with Tailscale networking,
>   NVIDIA Photo Booth findings, NATS bridge adapter design, STT/TTS reuse analysis

---

## Purpose

Documents how the two Reachy Mini robots (Wireless version, with onboard Raspberry Pi)
integrate with the Jarvis system as NATS adapters — thin translation layers between
voice/physical interaction and the NATS message bus, connected over a Tailscale mesh
network.

---

## Two Units, Two Roles

| Unit | Name | Role | Primary Agent |
|------|------|------|--------------|
| Reachy Mini #1 | **Scholar** | GCSE English tutoring interface | GCSE Tutor agent |
| Reachy Mini #2 | **Bridge** | Ship's Computer / Jarvis interface | Intent router → any agent |

Both units are the Wireless version ($449) with onboard Raspberry Pi CM4, Wi-Fi,
battery, and IMU. They connect to the GB10 over Tailscale, NOT via USB. The adapter
software is identical — only the default NATS routing topic differs.

---

## Network Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                    Tailscale Mesh Network                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Scholar (Pi)  │  │ Bridge (Pi)  │  │ MacBook Pro M2 Max     │  │
│  │ Daemon :8000  │  │ Daemon :8000 │  │ Planning / Claude      │  │
│  │ NATS client   │  │ NATS client  │  │ Desktop                │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘  │
│         │                  │                       │              │
│         └──────────┬───────┘                       │              │
│                    │                               │              │
│              ┌─────▼───────────────────────────────▼────────┐     │
│              │         GB10 (promaxgb10-41b1)               │     │
│              │  NATS JetStream :4222                        │     │
│              │  llama-swap :9000                            │     │
│              │    → Parakeet STT (Docker NIM)               │     │
│              │    → Kokoro TTS (Docker, GPU-accelerated)    │     │
│              │    → LLM (Qwen/GPT-OSS via llama-swap)      │     │
│              │  Graphiti → FalkorDB (whitestocks)           │     │
│              └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

Key insight: the Pi handles I/O only (motors, camera, mic, speaker). All compute
(STT, LLM, TTS, Graphiti queries) runs on the GB10. The Pi runs the Reachy daemon
and a lightweight NATS bridge adapter (~150 lines of Python).

---

## Adapter Architecture

The Reachy daemon runs on the Pi (auto-starts on boot). A separate NATS bridge
process on the Pi captures audio and forwards it to the GB10 for processing:

```
Voice In:  Pi mic → audio stream over network → Parakeet STT on GB10 → text
           → NATS publish jarvis.voice.{unit_name}
Voice Out: NATS subscribe jarvis.speech.{unit_name} → Kokoro TTS on GB10
           → audio stream over network → Pi speaker via daemon
Physical:  Face tracking → expression control → notification animations
           (runs on Pi via daemon, controlled by SDK commands over network)
```

### Input Flow
1. Reachy detects voice activity (wake word or continuous listening mode)
2. Audio captured on Pi, streamed to GB10 via GStreamer/WebRTC (SDK built-in)
3. Parakeet STT on GB10 transcribes audio to text
4. Transcribed text published to NATS `jarvis.voice.{scholar|bridge}`
5. Intent router classifies and dispatches to appropriate agent
6. Agent processes and publishes result to `agents.results.{agent}`
7. Result text sent to Kokoro TTS on GB10, generates audio
8. Audio streamed back to Pi speaker via daemon

### Output Flow (Proactive Notifications)
1. Any agent publishes to `notifications.{scholar|bridge}`
2. NATS bridge on Pi receives notification
3. Sends SDK command to daemon: play attention animation (head movement, antenna wiggle)
4. Waits for user to engage ("What's up?")
5. Routes notification text through TTS pipeline, speaks via Pi speaker

---

## Tailscale Setup (One-Time)

The Wireless Reachy Mini creates a Wi-Fi hotspot (`reachy-mini-ap`) on first boot.
Setup sequence:

1. Connect to `reachy-mini-ap` from laptop
2. Open `http://reachy-mini.local:8000/settings`, configure home Wi-Fi
3. Robot reboots, joins home network
4. SSH into Pi: `ssh pi@reachy-mini.local` (default password: `reachy`) — **change immediately**
5. Install Tailscale:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
6. Approve device in Tailscale admin console (manual step, cannot be automated)
7. Pi gets stable Tailscale IP and hostname, reachable from anywhere on the tailnet

After this, the Pi is permanently addressable via Tailscale regardless of Wi-Fi
changes. Measured Tailscale RTT on this network: ~1ms direct-connect, no DERP relay.

---

## Reusable Components from NVIDIA Photo Booth

### CES 2026 Demo Findings

NVIDIA's Photo Booth playbook (`github.com/NVIDIA/spark-reachy-photo-booth`, Apache 2.0)
used the Reachy Mini **Lite** (USB) at CES, NOT Wireless. The playbook explicitly states
Wireless "might require minor adaptations". Their Tailscale playbook is for remote SSH
to the Spark, not for Reachy-to-Spark communication.

However, their service decomposition validates our architecture: separate Docker
services for STT, TTS, agent, robot-controller, camera, interaction-manager —
communicating via Redpanda (Kafka-compatible message bus). We use NATS instead of
Redpanda, but the pattern is identical.

### STT: Parakeet CTC 1.1B (NVIDIA Riva NIM)

- **Model:** `nvidia/riva-parakeet-ctc-1.1B`
- **Proven on GB10:** Multiple community confirmations on NVIDIA Developer Forums.
  Available as NIM container or via NeMo toolkit.
- **Deployment:** Docker container on GB10, exposes gRPC/HTTP API.
- **Reuse verdict: YES** — Drop-in replacement for Whisper. Parakeet is optimised for
  NVIDIA hardware and likely faster than Whisper on the GB10's Blackwell GPU. The
  Photo Booth's `speech-to-text-service` wraps Parakeet with a Redpanda consumer/producer;
  we wrap it with a NATS consumer/producer instead.
- **Alternative:** Whisper via llama-swap remains a fallback if Parakeet NIM licensing
  or container size is problematic.

### TTS: Kokoro 82M (hexgrad)

- **Model:** `hexgrad/Kokoro-82M` via `Kokoro-FastAPI` (remsky)
- **Proven on GB10:** Community guide confirms full GPU acceleration on ARM64/GB10.
  Docker image ~18GB, exposes OpenAI-compatible API on port 8880.
  Supports 67 voice packs, multiple languages.
- **Deployment:** Docker container on GB10, `docker run --gpus all -p 7860:8880`.
- **Reuse verdict: YES** — The Photo Booth's `text-to-speech-service` wraps Kokoro;
  we wrap the same Kokoro-FastAPI container with a NATS adapter. Kokoro at 82M params
  is tiny — negligible GPU impact alongside the main LLM.
- **Voice selection:** British English voice packs available. Can configure per-unit
  (Scholar gets a different voice persona to Bridge).

### Other Photo Booth Services

| Service | Reuse? | Notes |
|---------|--------|-------|
| `agent-service` | Partial | NeMo Agent Toolkit + ReAct loop. Our equivalent is Jarvis intent router + NATS dispatch. Different agent framework but same pattern. |
| `robot-controller-service` | Partial | Wraps Reachy SDK. Our NATS bridge adapter serves the same role but runs on the Pi, not the Spark. Reference for SDK usage patterns. |
| `camera-service` | Maybe | Reachy camera → frames. Useful if we add visual context (e.g. face detection for Scholar to know Lilymay is present). |
| `interaction-manager-service` | Reference | Event orchestration and utterance management. Good architectural reference for managing conversation state. |
| `tracker-service` | No | Detectron2 + ByteTrack for user position tracking. Photo booth specific. |
| `animation-compositor-service` | Reference | Animation sequencing for Reachy. Useful patterns for expressive behaviour. |

---

## Existing Software Stack

The Reachy Mini SDK (`pip install reachy_mini`, Apache 2.0) provides:
- Python SDK with auto-detection of Wireless vs Lite
- Client-server architecture: daemon on Pi, your code connects over network
- `connection_mode="auto"` tries localhost first, falls back to network discovery
- Media backend: GStreamer (local) or WebRTC (remote) — auto-detected
- Core primitives: `goto_target()` for head/antenna/body movement
- Camera, mic, speaker access via daemon proxy
- SSHFS for remote development (mount Pi filesystem locally)
- App store via Hugging Face Spaces (one-click install from dashboard)

The Reachy Mini Conversation App (`pollen-robotics/reachy_mini_conversation_app`) provides:
- LLM integration (configurable backend)
- Head tracking (MediaPipe or YOLO face detection)
- Audio pipeline (STT + TTS)
- Vision pipeline
- Daemon connection and error handling

Pollen also ships an `AGENTS.md` guide specifically for AI coding agents (Claude Code,
Codex, Copilot) — recommended starting prompt for dedicated integration threads.

---

## What Makes It Feel Like a Ship's Computer

1. **Persistent presence** — Reachy sits on the desk, always listening (in wake-word mode)
2. **Proactive notifications** — Agents push updates through Reachy without being asked
3. **Contextual awareness** — Camera provides visual context (who's in the room)
4. **Expressive feedback** — Head movements and antenna animations signal state
5. **Multi-agent visibility** — "Status report" triggers fleet-wide status query via NATS
6. **Natural interaction** — Verbal approval/rejection for human-in-the-loop checkpoints

---

## CES 2026 Validation

Jensen Huang demonstrated the DGX Spark + Reachy Mini pattern at CES 2026. The Photo
Booth demo used USB Lite, not Wireless, with Redpanda as message bus. Our architecture
extends this in two ways:

1. **Wireless + Tailscale** — No USB tether, stable addressing across networks
2. **NATS JetStream** — Durable messaging with the same pub/sub pattern, integrated
   with the broader Jarvis agent fleet rather than a standalone demo

The Photo Booth repo (`NVIDIA/spark-reachy-photo-booth`) is Apache 2.0 licensed.
The STT/TTS service implementations are directly reusable with NATS adapter wrappers.

---

## Dependencies

- [x] Reachy Mini Wireless hardware (ordered ~25 Jan 2026, Scholar; ~1 Feb 2026, Bridge)
- [ ] Tailscale installed on Pi (one-time setup after hardware arrives)
- [ ] NATS server running on GB10 as persistent service
- [ ] Parakeet STT Docker container on GB10
- [ ] Kokoro TTS Docker container on GB10
- [ ] NATS bridge adapter deployed to Pi
- [ ] LLM available via llama-swap on GB10:9000

---

## Open Questions (Updated May 2026)

1. **Wake word** — Custom wake word ("Jarvis") or button-activated? Wake word needs
   always-on audio processing on the Pi. The Reachy Conversation App has wake word
   support — evaluate whether it runs acceptably on Pi CM4.
2. **Parakeet vs Whisper** — Parakeet is optimised for NVIDIA but runs as NIM container
   (requires NGC API key). Whisper via llama-swap is simpler but possibly slower.
   Decision: try Parakeet first, fall back to Whisper if NIM overhead is too high.
3. **Kokoro voice persona** — Select British English voice packs for Scholar and Bridge.
   Different voices help distinguish the two units.
4. **Latency budget** — Voice-to-response target: sub-2 seconds feels conversational.
   Network hop (~1ms Tailscale) is negligible. STT (~200-500ms) + LLM (~500-1000ms) +
   TTS (~200-500ms) = ~1-2s total. Acceptable for conversational flow.
5. **GPU contention** — When GB10 is under heavy load (AutoBuild, training), STT/TTS
   Docker containers may compete for GPU. Kokoro at 82M is tiny; Parakeet at 1.1B is
   small. Main risk is LLM inference latency under load. Fallback: cloud TTS via
   OpenAI Realtime API (already supported by Conversation App).
6. **Raspberry Pi CM4 vs Pi 5** — Sources conflict on which Pi ships in the Wireless
   version. GitHub SDK says CM4; some review sites say Pi 5. Need to confirm on
   arrival. Both support Tailscale; Pi 5 would have better performance for local
   audio processing.

---

## Related Documents

- NATS bridge adapter design: `jarvis/docs/research/ideas/reachy-nats-bridge-adapter.md`
- Fleet master index: `guardkitfactory/docs/research/ideas/fleet-master-index.md`
- Distributed agent orchestration: `distributed_agent_orchestration_architecture.md`
- NVIDIA Photo Booth repo: `github.com/NVIDIA/spark-reachy-photo-booth`
- NVIDIA Tailscale playbook: `build.nvidia.com/spark/tailscale`
- Reachy SDK: `github.com/pollen-robotics/reachy_mini`
- Reachy Conversation App: `github.com/pollen-robotics/reachy_mini_conversation_app`
- Reachy AGENTS.md: `github.com/pollen-robotics/reachy_mini/blob/develop/AGENTS.md`
