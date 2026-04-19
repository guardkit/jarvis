# ideas -- Product Roadmap

## Mode

idea

## Epics

### EPIC-001: Conversation-Initiated Presence and Engagement

**Bounded Context:** Conversation Starter

This epic covers the capability for Jarvis to notice meaningful context and initiate a short, timely conversation opening. It is limited to context sources and interaction patterns that are explicitly supported by the product documentation, and avoids introducing speculative channels or policies not yet documented.

**Features:**
  - FEAT-PO-001: Context-aware conversation opening generation
  - FEAT-PO-002: Conversation starter orchestration from documented signals
  - FEAT-PO-003: User response handling for accepted, ignored, or deferred openings

### EPIC-002: Embodied Delivery and Interaction Surface

**Bounded Context:** Embodied Interaction

This epic covers how a conversation starter is delivered through the documented embodied interaction surface. It keeps the roadmap grounded in the Reachy Mini integration and avoids assuming additional communication channels not explicitly supported in the docs.

**Features:**
  - FEAT-PO-004: Embodied presentation of conversation starters through Reachy Mini
  - FEAT-PO-005: Embodied acknowledgement and turn-taking after a starter

### EPIC-003: Assessment-informed Safety and Scope Boundaries

**Bounded Context:** Safety and Product Constraints

This epic adds explicit roadmap coverage for the Nemoclaw assessment by turning its implications into bounded product behaviour. Rather than treating the assessment as background reading, these features ensure the conversation starter remains inside safe, documented scope and does not overreach into policy or external-signal decisions not yet established.

**Features:**
  - FEAT-PO-006: Conversation starter eligibility limited to documented context sources
  - FEAT-PO-007: Bounded conversation-opening policy for non-intrusive engagement

## Priority Rationale

The roadmap starts with the core ability to generate and orchestrate a context-grounded conversation opening, because embodied delivery and policy controls are not meaningful until the product can first decide what to say and when to say it. Response handling follows early because the documentation frames the opening as an invitation that the user may accept, ignore, or defer, which is essential to the interaction model. Embodied delivery comes next, grounded specifically in the Reachy Mini integration rather than a broader assumed assistant channel. Assessment-informed scope controls are then made explicit to constrain trigger eligibility and initiation policy, which addresses the risk of speculative feature creep while incorporating the Nemoclaw assessment as a direct roadmap input.

## Constraints and Dependencies

- FEAT-PO-002 depends on FEAT-PO-001 because initiation logic requires a defined conversation-opening format and contextual basis.
- FEAT-PO-003 depends on FEAT-PO-001 and FEAT-PO-002 because response handling begins only after a conversation starter has been generated and initiated.
- FEAT-PO-004 depends on FEAT-PO-001 because embodied delivery requires a defined starter payload to present.
- FEAT-PO-005 depends on FEAT-PO-003 and FEAT-PO-004 because acknowledgement and turn-taking require both embodied presentation and known user response states.
- FEAT-PO-006 depends on FEAT-PO-002 because trigger eligibility constrains the orchestration logic that decides whether a starter is permitted.
- FEAT-PO-007 depends on FEAT-PO-003 and FEAT-PO-006 because bounded initiation policy is enforced across both trigger eligibility and user-outcome handling.

## Open Questions

- Which specific context sources named in jarvis-architecture-conversation-starter.md are intended to be treated as in-scope at first release, beyond the exclusion of speculative schedule and communication inputs?
- How should Reachy Mini indicate a deferred conversation starter in a way that is consistent with the documented interaction model?
- Does the Nemoclaw assessment imply any explicit auditability or review requirement for rejected trigger categories, or only product-scope constraints?

## Feature Spec Inputs

### FEAT-PO-001: Context-aware conversation opening generation

**Bounded Context:** Conversation Starter

**Description:**
The system shall generate a conversation starter when it has a documented contextual basis for opening an interaction, rather than emitting generic greetings. The generated opening should reflect the current situational context available to Jarvis and frame the interaction as a lightweight, socially intelligible prompt that can be accepted, ignored, or deferred by the user.

**Source Documents:** jarvis-architecture-conversation-starter.md, jarvis-vision.md

**Constraints:**
  - Openings must be grounded in context explicitly described in the product documentation.
  - The feature should produce short prompts suitable for ambient or embodied interaction.

### FEAT-PO-002: Conversation starter orchestration from documented signals

**Bounded Context:** Conversation Starter

**Description:**
The system shall evaluate documented contextual signals and decide when a conversation starter should be proposed. This orchestration must distinguish between the presence of relevant context and the decision to initiate, so Jarvis can avoid over-triggering and can open interaction only when a supported signal justifies it.

**Source Documents:** jarvis-architecture-conversation-starter.md, general-purpose-agent.md

**Constraints:**
  - Only trigger logic supported by documented signals should be included in scope.
  - Initiation policy should remain conservative to reduce unnecessary interruptions.

**Depends On:** FEAT-PO-001

### FEAT-PO-003: User response handling for accepted, ignored, or deferred openings

**Bounded Context:** Conversation Starter

**Description:**
The system shall handle the immediate outcomes of a conversation starter, including the user engaging with it, ignoring it, or deferring it. This behaviour should let Jarvis treat a conversation opening as an invitation rather than a command, preserving user agency and enabling future interaction behaviour to adapt to whether the opening was welcomed.

**Source Documents:** jarvis-architecture-conversation-starter.md, jarvis-vision.md

**Constraints:**
  - Response handling must preserve user control over whether interaction continues.
  - Outcome states should be explicit enough to support later adaptation and measurement.

**Depends On:** FEAT-PO-001, FEAT-PO-002

### FEAT-PO-004: Embodied presentation of conversation starters through Reachy Mini

**Bounded Context:** Embodied Interaction

**Description:**
The system shall present conversation starters through the documented Reachy Mini integration so that initiation feels like an embodied social interaction rather than a background system event. The presentation should use the robot interaction surface described in the product documentation and should not assume any separate established assistant channel beyond what the embodied integration explicitly supports.

**Source Documents:** reachy-mini-integration.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - The interaction surface must stay within the Reachy Mini capabilities documented for the project.
  - Feature wording must not assume an already-established non-robot assistant channel.

**Depends On:** FEAT-PO-001

### FEAT-PO-005: Embodied acknowledgement and turn-taking after a starter

**Bounded Context:** Embodied Interaction

**Description:**
The system shall provide a clear embodied acknowledgement when a conversation starter is delivered and when the user begins to engage. This behaviour should create a visible transition from initiation to interaction, allowing the embodied agent to signal that the opening was noticed and that the conversational turn has moved forward.

**Source Documents:** reachy-mini-integration.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Acknowledgement behaviour should use interaction patterns compatible with the documented robot integration.
  - Turn-taking cues should remain lightweight and suitable for short-initiated exchanges.

**Depends On:** FEAT-PO-003, FEAT-PO-004

### FEAT-PO-006: Conversation starter eligibility limited to documented context sources

**Bounded Context:** Safety and Product Constraints

**Description:**
The system shall only generate conversation starters from context sources that are explicitly documented for this product, and it shall reject unsupported trigger categories from the operational feature set. Inputs such as schedule-derived prompts, communication-derived prompts, or other external signals that are not clearly established in the product documentation should remain out of scope for implementation and be treated as future options or assumptions rather than active roadmap commitments.

**Source Documents:** nemoclaw-assessment.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Undocumented trigger sources must not be implemented as part of this roadmap.
  - Eligibility rules should be explicit enough to prevent speculative expansion of initiation behaviour.

**Depends On:** FEAT-PO-002

### FEAT-PO-007: Bounded conversation-opening policy for non-intrusive engagement

**Bounded Context:** Safety and Product Constraints

**Description:**
The system shall enforce a bounded initiation policy so that conversation starters remain lightweight, non-coercive, and easy for the user to ignore. This policy should constrain the product to socially appropriate openings within the documented assistant vision and assessment guidance, instead of escalating into persuasive, high-frequency, or externally inferred interventions.

**Source Documents:** nemoclaw-assessment.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - The policy must support ignore/defer behaviour without penalising the user.
  - The feature must remain at the level of bounded product behaviour, not speculative governance beyond the docs.

**Depends On:** FEAT-PO-003, FEAT-PO-006

## Source Documents

| Document | Contribution |
| --- | --- |
| jarvis-architecture-conversation-starter.md | This document grounds the core conversation-starter architecture, including the need to generate, initiate, and handle openings as part of a distinct product capability. |
| jarvis-vision.md | This document supports the product intent for Jarvis as a socially appropriate assistant and helps bound interaction style, user agency, and non-intrusive engagement. |
| general-purpose-agent.md | This document informs the orchestration feature by grounding the broader agent pattern that evaluates context and chooses whether to act. |
| reachy-mini-integration.md | This document provides explicit support for embodied delivery through Reachy Mini and constrains the roadmap to the documented interaction surface. |
| nemoclaw-assessment.md | This document is now explicitly covered through features that limit eligible context sources and bound initiation policy so the roadmap reflects assessment-driven scope and safety constraints. |

## Assumptions

| # | Category | Assumption | Confidence | Impact if Wrong |
| --- | --- | --- | --- | --- |
| ASM-001 | scope | The conversation starter is the primary capability under consideration, and broader assistant functionality is out of scope except where required to initiate and handle a starter. | high | If broader assistant workflows are in scope, the roadmap is too narrow and would miss downstream execution features. |
| ASM-002 | constraints | Schedule-derived and communication-derived prompts are not yet sufficiently documented to be committed as in-scope trigger sources for this roadmap. | medium | If those signals are in fact explicitly supported in the docs, FEAT-PO-006 is overly restrictive and the roadmap omits valid trigger features. |
| ASM-003 | technology | Reachy Mini is the only explicitly grounded embodied interaction surface for delivering conversation starters in the current documentation set. | high | If other delivery channels are equally established, the embodied epic is too constrained and channel coverage is incomplete. |
| ASM-004 | constraints | The Nemoclaw assessment is intended to shape product boundaries and safe behaviour for initiation rather than introduce a separate standalone user-facing workflow. | medium | If the assessment defines an explicit operational workflow, the roadmap should include additional features for review, logging, or control points. |
