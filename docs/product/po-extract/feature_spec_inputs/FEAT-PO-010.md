# Reachy Bridge Voice Interaction Pipeline

## Description

The Reachy Bridge adapter must translate between voice interaction and Jarvis routing by capturing audio, transcribing locally on the GB10, publishing `jarvis.command.reachy-bridge`, and speaking returned results through TTS. The pipeline needs to preserve the embodied interaction pattern where Reachy feels like a persistent Ship's Computer interface rather than just another microphone.

## Bounded Context

Adapter Interface

## Source Documents

- reachy-mini-integration.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Voice input uses local Whisper on GB10 in the documented flow.
- Reachy is a thin NATS adapter rather than an embedded intelligence layer.
- Voice latency should feel conversational and sub-2 seconds is desirable.

## Dependencies

- FEAT-PO-001
- FEAT-PO-004
- FEAT-PO-009

## Suggested Context Files

- reachy-mini-integration.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
