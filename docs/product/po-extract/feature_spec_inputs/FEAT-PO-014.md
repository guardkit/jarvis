# Intent-Based Model Routing for Local, Cloud, and Privacy-Sensitive Tasks

## Description

The General Purpose Agent must route simple queries to local vLLM on the GB10, route complex reasoning and synthesis to a cloud API, and keep privacy-sensitive calendar or email tasks on the local model path. This model routing mirrors the local-first privacy router concept while using the existing provider abstraction pattern instead of vendor lock-in.

## Bounded Context

Agent Execution

## Source Documents

- general-purpose-agent.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- nemoclaw-assessment.md

## Constraints

- Provider abstraction must support local and cloud APIs interchangeably.
- Simple and privacy-sensitive tasks should be able to run locally on GB10.
- The design should avoid NVIDIA-specific runtime lock-in.

## Dependencies

- FEAT-PO-013

## Suggested Context Files

- general-purpose-agent.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- nemoclaw-assessment.md
