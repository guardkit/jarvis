# Phase 1 Core Tool Set

## Description

The General Purpose Agent must implement the MVP tool set of Web Search, Web Fetch, Calendar, Email Draft, Slack Draft, File Operations, Weather, and Timer/Reminder so Jarvis can handle research, scheduling, drafting, lookups, and local task support. These tools expand capability without changing the architecture because the ReAct pattern handles selection at runtime.

## Bounded Context

Agent Execution

## Source Documents

- general-purpose-agent.md

## Constraints

- Phase 1 tool set is the documented MVP scope.
- Integrations include web APIs, local filesystem access, and local scheduling plus NATS notification.
- Email and Slack are draft-oriented rather than autonomous send actions in the current docs.

## Dependencies

- FEAT-PO-013
- FEAT-PO-014

## Suggested Context Files

- general-purpose-agent.md
