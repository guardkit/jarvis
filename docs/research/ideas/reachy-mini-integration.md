# Reachy Mini Integration — Embodied Interface for Jarvis

## For: `/system-arch` session · Jarvis adapter · March 2026

---

## Purpose

Documents how the two Reachy Mini robots integrate with the Jarvis system as NATS
adapters — thin translation layers between voice/physical interaction and the
NATS message bus.

---

## Two Units, Two Roles

| Unit | Name | Role | Primary Agent |
|------|------|------|--------------|
| Reachy Mini #1 | **Scholar** | GCSE English tutoring interface | GCSE Tutor agent (future) |
| Reachy Mini #2 | **Bridge** | Ship's Computer / Jarvis interface | Intent router → any agent |

Both units are physically connected to the GB10 via USB and communicate with Jarvis
via NATS. The adapter software is identical — only the default routing differs.

---

## Adapter Architecture

Each Reachy Mini runs a `nats-asyncio-service` adapter with this pipeline:

```
Voice In:  Microphone → Whisper (local on GB10) → Text → NATS publish
Voice Out: NATS subscribe → TTS (local or OpenAI Realtime API) → Speaker
Physical:  Face tracking → expression control → notification animations
```

### Input Flow
1. Reachy detects voice activity (wake word or continuous listening mode)
2. Audio captured and transcribed via Whisper on GB10 (local, fast, private)
3. Transcribed text published to `jarvis.command.reachy-bridge`
4. Intent router classifies and dispatches
5. Agent processes and publishes result to `agents.results.{agent}`
6. Reachy adapter subscribes, receives result, speaks it via TTS

### Output Flow (Proactive Notifications)
1. Any agent publishes to `notifications.reachy-bridge`
2. Reachy adapter receives notification
3. Reachy plays attention animation (head movement, antenna wiggle, sound)
4. Waits for user to engage ("What's up?")
5. Speaks the notification content

---

## Existing Software Stack

The Reachy Mini Conversation App (Pollen Robotics, open source) already provides:
- OpenAI Realtime API integration for voice
- Face tracking via camera
- Expressive movements (head, antenna, eyes)
- Wake word detection

The NATS adapter wraps this existing functionality — we don't rebuild the voice pipeline,
we bridge it to NATS.

---

## What Makes It Feel Like a Ship's Computer

1. **Persistent presence** — Reachy sits on the desk, always listening (in wake-word mode)
2. **Proactive notifications** — Agents push updates through Reachy without being asked
3. **Contextual awareness** — Camera provides visual context (who's in the room)
4. **Expressive feedback** — Head movements and antenna animations signal state
5. **Multi-agent visibility** — "Status report" triggers fleet-wide status query
6. **Natural interaction** — Verbal approval/rejection for human-in-the-loop checkpoints

---

## CES 2026 Validation

Jensen Huang demonstrated exactly this pattern at CES 2026: DGX Spark + Reachy Mini as
a personal AI assistant. The demo showed task management via voice, action execution,
visual input processing, and home monitoring. Our architecture extends this with the
multi-agent fleet concept and NATS backbone.

---

## Dependencies

- Reachy Mini hardware delivery (on order)
- `nats-asyncio-service` template (being built)
- NATS server running on GB10 (designed, not yet deployed as running service)
- Whisper model running on GB10 via vLLM or standalone

---

## Open Questions

1. **Wake word** — Custom wake word ("Jarvis") or button-activated? Wake word needs
   always-on audio processing.
2. **Dual-Reachy coordination** — Can Scholar and Bridge share the same GB10 resources
   without contention? Need to understand Reachy SDK resource requirements.
3. **Latency budget** — Voice-to-response target? Sub-2 seconds feels conversational.
   Whisper transcription + intent classification + agent dispatch + TTS adds up.
4. **Fallback** — When GB10 is under heavy GPU load (AutoBuild running), does voice
   quality degrade? Need graceful degradation or cloud TTS fallback.
