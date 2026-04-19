# Intent Classification Against Registered Signals

## Description

Jarvis must classify inbound requests using rule-based matching against registered signal words and intent metadata, with optional model fallback when requests remain ambiguous. The classifier needs to support low-latency conversational paths, especially for Reachy Mini voice interaction, while still handling less obvious phrasing when rule matches are weak.

## Bounded Context

Intent Routing

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- reachy-mini-integration.md

## Constraints

- Latency matters for voice flows and sub-2-second interaction is desirable.
- Classification should use registered signals and confidence metadata where available.
- Provider abstraction must allow local and cloud classification paths.

## Dependencies

- FEAT-PO-005

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- reachy-mini-integration.md
