# DeepAgents Runtime Path Instead of NemoClaw

## Description

Jarvis must use the NATS plus DeepAgents SDK runtime path as the current execution strategy instead of NemoClaw, because NemoClaw is documented as rejected for now due to alpha instability and DGX Spark onboarding failures. This decision keeps implementation on proven templates and battle-tested vLLM patterns while leaving room to revisit NemoClaw later if it matures.

## Bounded Context

Infrastructure and Runtime

## Source Documents

- nemoclaw-assessment.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Decision D6 rejects NemoClaw for now and should not be reopened in the current roadmap.
- Current preferred path is DeepAgents SDK plus NATS plus existing Docker setup.
- NemoClaw may be revisited later as a complementary runtime, not a replacement architecture.

## Dependencies

- FEAT-PO-021

## Suggested Context Files

- nemoclaw-assessment.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
