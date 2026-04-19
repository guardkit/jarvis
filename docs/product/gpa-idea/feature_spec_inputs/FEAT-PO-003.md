# User response handling for accepted, ignored, or deferred openings

## Description

The system shall handle the immediate outcomes of a conversation starter, including the user engaging with it, ignoring it, or deferring it. This behaviour should let Jarvis treat a conversation opening as an invitation rather than a command, preserving user agency and enabling future interaction behaviour to adapt to whether the opening was welcomed.

## Bounded Context

Conversation Starter

## Source Documents

- jarvis-architecture-conversation-starter.md
- jarvis-vision.md

## Constraints

- Response handling must preserve user control over whether interaction continues.
- Outcome states should be explicit enough to support later adaptation and measurement.

## Dependencies

- FEAT-PO-001
- FEAT-PO-002

## Suggested Context Files

None
