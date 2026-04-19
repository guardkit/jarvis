# Shared Context Strategy for Cross-Agent Conversations

## Description

Jarvis must support a documented strategy for carrying context across agent boundaries so requests like 'build that idea we just discussed' can be resolved coherently. The current documents leave open whether this is handled by isolated agents, shared Graphiti memory, or Jarvis-maintained session state, so the feature should establish an explicit implementation path while preserving thin-router boundaries.

## Bounded Context

Knowledge Context

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- general-purpose-agent.md

## Constraints

- Cross-agent conversation context is explicitly unresolved in the docs.
- Jarvis must remain thin even if it participates in context handoff.
- Graphiti is the documented candidate for shared memory.

## Dependencies

- FEAT-PO-018

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- general-purpose-agent.md
