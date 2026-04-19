# Routing Policy and General Purpose Agent Fallback

## Description

Jarvis must select the best specialist agent for a classified intent and fall back to the General Purpose Agent when no specialist is a strong match. The routing policy needs to respect documented confidence thresholds, preserve the 'generous with the general bucket' behaviour, and allow user redirection when a different agent is preferred.

## Bounded Context

Intent Routing

## Source Documents

- jarvis-vision.md
- general-purpose-agent.md
- jarvis-architecture-conversation-starter.md

## Constraints

- If no registered agent matches with confidence greater than 0.5, route to the General Purpose Agent.
- General Purpose Agent is the default fallback path.
- Jarvis should not hard-code specialist routing logic beyond policy rules.

## Dependencies

- FEAT-PO-002
- FEAT-PO-005
- FEAT-PO-010

## Suggested Context Files

- jarvis-vision.md
- general-purpose-agent.md
- jarvis-architecture-conversation-starter.md
