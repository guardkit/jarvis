# Provider-Abstracted Model Client

## Description

Jarvis and the General Purpose Agent must use a provider-abstracted model client so local vLLM and cloud APIs can be swapped through configuration rather than vendor-specific code paths. This abstraction is necessary to preserve privacy routing, provider independence, and the documented rejection of NVIDIA-only runtime lock-in.

## Bounded Context

Infrastructure and Runtime

## Source Documents

- jarvis-architecture-conversation-starter.md
- jarvis-vision.md
- general-purpose-agent.md
- nemoclaw-assessment.md

## Constraints

- Tool signatures should remain stable across cloud and local modes.
- Provider independence is a recurring documented architectural principle.
- The abstraction must support both router classification and agent execution paths.

## Dependencies

None

## Suggested Context Files

- jarvis-architecture-conversation-starter.md
- jarvis-vision.md
- general-purpose-agent.md
- nemoclaw-assessment.md
