# General Purpose Agent ReAct Runtime

## Description

The General Purpose Agent must run as a single ReAct agent using the `langchain-deepagents` base template, selecting tools to answer natural language requests in one-shot or short multi-turn interactions. It exists to handle the mundane and unclassified requests that do not justify a weighted-evaluation pipeline or specialist dispatch.

## Bounded Context

Agent Execution

## Source Documents

- general-purpose-agent.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- No adversarial loop, no Coach, and no weighted evaluation in this agent.
- The agent should be fast turnaround rather than long-running pipeline execution.
- It is the default fallback participant in the fleet.

## Dependencies

- FEAT-PO-003
- FEAT-PO-005

## Suggested Context Files

- general-purpose-agent.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
