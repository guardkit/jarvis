# Cross-Agent Tools for Fleet Awareness and Handoff

## Description

The General Purpose Agent must expose cross-agent tools for Agent Status, Agent Trigger, and Knowledge Query so users can inspect fleet activity, trigger pipelines, and retrieve prior decisions. These tools are what make the fallback agent fleet-aware instead of behaving like a standalone desktop chat assistant.

## Bounded Context

Agent Execution

## Source Documents

- general-purpose-agent.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Agent Status uses NATS `agents.status.*` subscription patterns.
- Agent Trigger uses NATS dispatch subjects for handoff into the fleet.
- Knowledge Query should use Graphiti search.

## Dependencies

- FEAT-PO-013
- FEAT-PO-005
- FEAT-PO-018

## Suggested Context Files

- general-purpose-agent.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
