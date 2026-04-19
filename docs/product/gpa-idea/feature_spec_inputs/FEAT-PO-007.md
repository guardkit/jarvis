# Bounded conversation-opening policy for non-intrusive engagement

## Description

The system shall enforce a bounded initiation policy so that conversation starters remain lightweight, non-coercive, and easy for the user to ignore. This policy should constrain the product to socially appropriate openings within the documented assistant vision and assessment guidance, instead of escalating into persuasive, high-frequency, or externally inferred interventions.

## Bounded Context

Safety and Product Constraints

## Source Documents

- nemoclaw-assessment.md
- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- The policy must support ignore/defer behaviour without penalising the user.
- The feature must remain at the level of bounded product behaviour, not speculative governance beyond the docs.

## Dependencies

- FEAT-PO-003
- FEAT-PO-006

## Suggested Context Files

None
