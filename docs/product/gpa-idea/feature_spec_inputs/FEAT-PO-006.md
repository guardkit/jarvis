# Conversation starter eligibility limited to documented context sources

## Description

The system shall only generate conversation starters from context sources that are explicitly documented for this product, and it shall reject unsupported trigger categories from the operational feature set. Inputs such as schedule-derived prompts, communication-derived prompts, or other external signals that are not clearly established in the product documentation should remain out of scope for implementation and be treated as future options or assumptions rather than active roadmap commitments.

## Bounded Context

Safety and Product Constraints

## Source Documents

- nemoclaw-assessment.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Undocumented trigger sources must not be implemented as part of this roadmap.
- Eligibility rules should be explicit enough to prevent speculative expansion of initiation behaviour.

## Dependencies

- FEAT-PO-002

## Suggested Context Files

None
