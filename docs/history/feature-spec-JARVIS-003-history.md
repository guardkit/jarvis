/feature-spec "Async Subagents for Model Routing: four AsyncSubAgent instances (deep_reasoner, adversarial_critic, long_research, quick_local) via AsyncSubAgentMiddleware with ASGI transport; cost+latency descriptions; quick_local fallback hook under stubbed GB10 health signal" \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/tools/general.py \
  --context .guardkit/context-manifest.yaml
I'll execute the six-phase Propose-Review methodology. Starting with Phase 1: Context Gathering.

Read design.md
Read phase2-dispatch-foundations-scope.md
Read phase2-build-plan.md
Read supervisor.py
Read general.py
Globpattern: "src/jarvis/tools/**/*.py"
Found 1 file
Read __init__.py
Read context-manifest.yaml
Bash List existing features and FEAT-JARVIS-003 design directory
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/ 2>/dev/null && ls -la /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/ 2>/dev/null

OUT
total 0
drwxr-xr-x   4 richardwoollcott  staff  128 Apr 23 22:18 .
drwxr-xr-x  27 richardwoollcott  staff  864 Apr 22 20:56 ..
drwxr-xr-x   5 richardwoollcott  staff  160 Apr 23 22:19 feat-jarvis-002-core-tools-and-dispatch
drwxr-xr-x   5 richardwoollcott  staff  160 Apr 22 13:55 project-scaffolding-supervisor-sessions
total 64
drwxr-xr-x  7 richardwoollcott  staff    224 Apr 23 21:23 .
drwxr-xr-x  5 richardwoollcott  staff    160 Apr 23 21:20 ..
drwxr-xr-x  5 richardwoollcott  staff    160 Apr 23 21:32 contracts
drwxr-xr-x  8 richardwoollcott  staff    256 Apr 23 21:29 decisions
-rw-r--r--  1 richardwoollcott  staff  30852 Apr 23 21:23 design.md
drwxr-xr-x  3 richardwoollcott  staff     96 Apr 23 21:34 diagrams
drwxr-xr-x  3 richardwoollcott  staff     96 Apr 23 21:33 models
Bash List FEAT-002 feature files for convention reference
IN
ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-002-core-tools-and-dispatch/

OUT
feat-jarvis-002-core-tools-and-dispatch_assumptions.yaml
feat-jarvis-002-core-tools-and-dispatch_summary.md
feat-jarvis-002-core-tools-and-dispatch.feature
Read feat-jarvis-002-core-tools-and-dispatch_summary.md
Read feat-jarvis-002-core-tools-and-dispatch.feature
Bash List FEAT-003 design subdirs
IN
ls /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/contracts/ /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/models/ /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/decisions/

OUT
/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/contracts/:
API-internal.md
API-subagent.md
API-tools.md

/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/decisions/:
DDR-010-single-async-subagent-supersedes-four-roster.md
DDR-011-role-enum-closed-v1.md
DDR-012-subagent-module-import-compilation.md
DDR-013-langgraph-json-at-repo-root.md
DDR-014-escalate-to-frontier-in-dispatch-tool-module.md
DDR-015-llamaswap-adapter-with-stubbed-health.md

/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-003/models/:
DM-subagent-types.md
Read API-subagent.md
Read API-tools.md
Read API-internal.md
Read DM-subagent-types.md
Context gathered. Note: command title uses superseded four-subagent language; the authoritative design (FEAT-JARVIS-003 design.md, DDRs 010-015) supersedes it with one jarvis-reasoner subagent + escalate_to_frontier tool + LlamaSwapAdapter. I'll spec to the authoritative design.

Context loaded: stack=python, 0 existing source modules in src/jarvis/agents/subagents/ or src/jarvis/adapters/, FEAT-JARVIS-003 design.md + 6 DDRs + 3 contracts + 1 model doc read; FEAT-JARVIS-002 feature spec used as convention reference.

Proceeding to Phase 2.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: Async Subagent for Model Routing + Attended Frontier Escape (FEAT-JARVIS-003)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Note on scope reframe: Your command line names the retired four-cloud-subagent roster (deep_reasoner / adversarial_critic / long_research / quick_local) and the JA6 quick_local cloud-fallback hook. Both are superseded by ADR-ARCH-001/011/012/027 and reconciled in docs/design/FEAT-JARVIS-003/design.md + DDR-010/014/015. This proposal specs the authoritative design: a single jarvis-reasoner AsyncSubAgent with a role kwarg, an attended-only escalate_to_frontier tool, and a swap-aware LlamaSwapAdapter with stubbed health.


@feat-jarvis-003
Feature: Async Subagent for Model Routing + Attended Frontier Escape
  As the Jarvis supervisor's reasoning model
  I want a single local jarvis-reasoner subagent that I can dispatch to with a
  named role, an attended-only escalate_to_frontier tool for cloud opinions Rich
  has explicitly asked for, and a swap-aware view of the GB10 model so my voice
  responses stay honest about latency
  So that "one reasoning model that knows which reasoning model to use" works
  in practice without ever silently sending Rich's data to a cloud provider

  Background:
    Given Jarvis has started with the FEAT-JARVIS-002 tool surface intact
    And llama-swap is reachable at the configured base URL
    And the supervisor has been built with the jarvis-reasoner async subagent wired
    And the attended tool list includes escalate_to_frontier
    And the ambient tool list excludes escalate_to_frontier
━━ GROUP A: Key Examples (10 scenarios) ━━


  # Why: Core path — one AsyncSubAgent named jarvis-reasoner is registered (DDR-010, ADR-ARCH-011)
  @key-example @smoke
  Scenario: A single jarvis-reasoner async subagent is registered at startup
    When the subagent registry is built from the configuration
    Then exactly one async subagent is returned
    And the subagent is named jarvis-reasoner
    And its graph identifier is jarvis_reasoner
    And its description names the local model, names the three role modes, states no cloud cost, and warns against use for arithmetic, lookups, and file reads

  # Why: Description is the contract with the reasoning model — must carry cost + latency signals
  @key-example @smoke
  Scenario: The jarvis-reasoner description carries cost and latency signals the reasoning model can read
    When the supervisor receives the subagent catalogue
    Then the description states that all inference stays on the premises
    And the description states sub-second per-turn latency when the model is loaded
    And the description warns that a cold swap can take two to four minutes and the supervisor will emit a voice acknowledgement if so

  # Why: Role-dispatch happy path for CRITIC — the canonical adversarial use-case
  @key-example @smoke
  Scenario: Dispatching to the critic role launches an async task and returns a task identifier
    Given the reasoning model wants an adversarial review of an architecture document
    When it starts an async task targeting jarvis-reasoner with role critic and a non-empty prompt
    Then the middleware returns a task identifier immediately
    And the subagent graph resolves the system prompt for the critic role
    And the task runs against the local jarvis-reasoner alias

  # Why: Role-dispatch happy path for RESEARCHER
  @key-example @smoke
  Scenario: Dispatching to the researcher role uses the open-ended research posture
    Given the reasoning model wants open-ended research on a topic
    When it starts an async task targeting jarvis-reasoner with role researcher and a non-empty prompt
    Then the middleware returns a task identifier
    And the subagent graph resolves the system prompt for the researcher role

  # Why: Role-dispatch happy path for PLANNER
  @key-example @smoke
  Scenario: Dispatching to the planner role uses the multi-step planning posture
    Given the reasoning model wants a multi-step plan
    When it starts an async task targeting jarvis-reasoner with role planner and a non-empty prompt
    Then the middleware returns a task identifier
    And the subagent graph resolves the system prompt for the planner role

  # Why: Role prompts must exist for every member of the closed RoleName enum (DDR-011)
  @key-example
  Scenario: The role prompt registry covers every member of the role enum
    When the role prompt registry is inspected
    Then it contains a non-empty system prompt for the critic role
    And it contains a non-empty system prompt for the researcher role
    And it contains a non-empty system prompt for the planner role
    And no extra members are present beyond the closed enum

  # Why: AsyncSubAgentMiddleware injects the five operational tools — supervisor sees them
  @key-example @smoke
  Scenario: Wiring the async subagent injects the five middleware operational tools
    When the supervisor is built with the jarvis-reasoner async subagent
    Then the supervisor's tool catalogue includes start_async_task, check_async_task, update_async_task, cancel_async_task, and list_async_tasks

  # Why: Attended escalation happy path — Rich asks Jarvis to ask Gemini
  @key-example @smoke
  Scenario: An attended session can escalate to the default frontier model
    Given the active session is on an attended adapter
    And the configured default frontier target is reachable
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns the frontier model's response as a string
    And the invocation is recorded as a frontier escalation event

  # Why: Supervisor prompt teaches both new sections — DDR-013 and design.md §10
  @key-example
  Scenario: The supervisor system prompt teaches subagent routing and frontier escalation
    When the supervisor system prompt is rendered for a new session
    Then it includes a Subagent Routing section that names jarvis-reasoner and lists the three role modes
    And it includes a Frontier Escalation section that states cloud escalation is only available when Rich asks for it explicitly

  # Why: Repo-root langgraph.json declares both graphs with ASGI transport (DDR-013)
  @key-example
  Scenario: The repo-root langgraph manifest declares both graphs with ASGI transport
    When the langgraph manifest at the repo root is loaded
    Then it declares a graph named jarvis bound to the supervisor module
    And it declares a graph named jarvis_reasoner bound to the subagent module
    And both graphs use the in-process ASGI transport
━━ GROUP B: Boundary Conditions (6 scenarios) ━━


  # Why: Role enum is a closed set — only the three members are accepted (DDR-011)
  @boundary
  Scenario Outline: The jarvis-reasoner subagent accepts only the three documented role values
    Given the supervisor wants to dispatch to jarvis-reasoner
    When it starts an async task with role <role> and a non-empty prompt
    Then the outcome is <outcome>

    Examples:
      | role        | outcome                                                               |
      | critic      | the task is launched and a task identifier is returned                |
      | researcher  | the task is launched and a task identifier is returned                |
      | planner     | the task is launched and a task identifier is returned                |

  # Why: Just-outside boundary — anything not in the enum is rejected via structured error
  @boundary @negative
  Scenario Outline: Unknown role values are rejected with a structured error
    When the supervisor starts an async task targeting jarvis-reasoner with role <role> and a non-empty prompt
    Then the subagent reports an error indicating the role was not recognised
    And the error names the three accepted role values

    Examples:
      | role           |
      | bard           |
      | adversarial    |
      | CRITIC         |
      | ""             |

  # Why: Swap ETA boundary drives ADR-ARCH-012 voice-ack policy
  @boundary
  Scenario Outline: Swap status above the voice-ack threshold triggers the supervisor TTS acknowledgement
    Given the active session is on a voice-reactive adapter
    And the llama-swap adapter reports an estimated time of <eta_seconds> seconds for the wanted alias
    When the supervisor decides whether to emit a voice acknowledgement
    Then the outcome is <outcome>

    Examples:
      | eta_seconds | outcome                                                              |
      | 0           | no voice acknowledgement is emitted; the request proceeds directly   |
      | 30          | no voice acknowledgement is emitted; the request proceeds directly   |
      | 31          | the supervisor emits the voice acknowledgement and queues the request|
      | 240         | the supervisor emits the voice acknowledgement and queues the request|

  # Why: Frontier targets are a closed set — additions require a DDR
  @boundary
  Scenario Outline: Only documented frontier targets are accepted
    Given the active session is on an attended adapter
    When the reasoning model invokes escalate_to_frontier with target <target>
    Then the outcome is <outcome>

    Examples:
      | target                              | outcome                                                       |
      | GEMINI_3_1_PRO (default)            | the configured Gemini provider is invoked                     |
      | OPUS_4_7                            | the configured Anthropic provider is invoked                  |
      | a value not in the FrontierTarget enum | the call is rejected before any provider is contacted      |

  # Why: prompt is a required, non-empty field on AsyncTaskInput
  @boundary @negative
  Scenario: An async task with an empty prompt is rejected with a missing-field error
    When the supervisor starts an async task targeting jarvis-reasoner with role critic and an empty prompt
    Then the subagent reports an error indicating the prompt field is required

  # Why: SwapStatus.eta_seconds invariant: zero means ready, negative is illegal
  @boundary
  Scenario Outline: Swap status enforces a non-negative ETA
    When the llama-swap adapter is asked to construct a swap status with eta_seconds <value>
    Then the outcome is <outcome>

    Examples:
      | value | outcome                                                |
      | 0     | a status with eta_seconds 0 is returned                |
      | 1     | a status with eta_seconds 1 is returned                |
      | -1    | construction is rejected as an invalid model           |
━━ GROUP C: Negative Cases (10 scenarios) ━━


  # Why: Layer 2 of DDR-014 belt+braces — executor assertion on adapter
  @negative @smoke
  Scenario: An ambient session is rejected if it somehow invokes escalate_to_frontier
    Given the active session is on an ambient adapter
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns an error indicating attended use only
    And the error names the offending adapter

  # Why: Layer 2 again — executor assertion on async-subagent caller frame
  @negative
  Scenario: A call from an async subagent frame is rejected as attended-only
    Given an async subagent invocation is in progress
    When code in that frame invokes escalate_to_frontier with an instruction
    Then the tool returns an error indicating attended use only
    And the error names the async-subagent caller frame

  # Why: Layer 3 of DDR-014 — registration absence is the third brace
  @negative @smoke
  Scenario: escalate_to_frontier is not present in the ambient tool list at all
    When the ambient tool list is assembled
    Then escalate_to_frontier is not present in the assembled list
    And the assembled list still contains all FEAT-JARVIS-002 tools

  # Why: Provider key absence — graceful structured error per ADR-ARCH-021
  @negative
  Scenario: Escalating to Gemini without a configured Google API key returns a configuration error
    Given the active session is on an attended adapter
    And no Google API key is configured
    When the reasoning model invokes escalate_to_frontier with the default target
    Then the tool returns an error indicating the Google API key is not set
    And no outbound request is made to the provider

  # Why: Provider key absence for the alternate target
  @negative
  Scenario: Escalating to Opus without a configured Anthropic API key returns a configuration error
    Given the active session is on an attended adapter
    And no Anthropic API key is configured
    When the reasoning model invokes escalate_to_frontier targeting Opus
    Then the tool returns an error indicating the Anthropic API key is not set
    And no outbound request is made to the provider

  # Why: Provider availability — degraded outcome surfaces as DEGRADED prefix
  @negative
  Scenario: Frontier provider unavailability returns a degraded result without raising
    Given the active session is on an attended adapter
    And the configured frontier provider is unreachable
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns a degraded result indicating provider unavailability
    And no exception propagates to the supervisor

  # Why: Subagent never raises — model unavailability is structured per ADR-ARCH-021
  @negative
  Scenario: A missing llama-swap alias surfaces as a structured model-unavailable error
    Given the llama-swap alias for jarvis-reasoner cannot be resolved
    When the supervisor starts an async task targeting jarvis-reasoner with role planner and a non-empty prompt
    Then the subagent reports an error indicating the model is unavailable
    And the error mentions checking the llama-swap running endpoint

  # Why: Subagent timeout is a structured TIMEOUT, not an exception
  @negative
  Scenario: An async task that exceeds its timeout returns a structured timeout result
    Given an async task targeting jarvis-reasoner is running past the configured timeout
    When the supervisor checks the task status
    Then the result indicates the task timed out
    And the result identifies the affected task

  # Why: Subagent input requires both prompt and role — missing role is rejected
  @negative
  Scenario: An async task missing the role field is rejected with a structured error
    When the supervisor starts an async task targeting jarvis-reasoner with a non-empty prompt and no role
    Then the subagent reports an error indicating a required field is missing

  # Why: Subagent factory must not silently expand its roster — guard against accidental DDR-010 regression
  @negative
  Scenario: Adding an unsanctioned subagent does not silently appear in the registry
    When the subagent registry is built from the configuration
    Then no subagent named deep_reasoner is present
    And no subagent named adversarial_critic is present
    And no subagent named long_research is present
    And no subagent named quick_local is present
━━ GROUP D: Edge Cases (10 scenarios) ━━


  # Why: Acceptance test for FEAT-JARVIS-003 — seven canned routing decisions
  @edge-case @smoke
  Scenario Outline: The supervisor routes the seven canned acceptance prompts to the expected tools
    Given the supervisor has been built with all FEAT-JARVIS-002 tools, the jarvis-reasoner subagent, and the attended tool list including escalate_to_frontier
    And the active session is on an attended adapter
    When the user says <prompt>
    Then the reasoning model invokes <expected_action>

    Examples:
      | prompt                                                            | expected_action                                                                  |
      | "What's 15% of 847?"                                              | calculate                                                                        |
      | "Summarise /tmp/test.md"                                          | read_file                                                                        |
      | "Critique this architecture doc for subtle flaws."                | start_async_task targeting jarvis-reasoner with role critic                      |
      | "Research Meta-Harness deeply."                                   | start_async_task targeting jarvis-reasoner with role researcher                  |
      | "Plan the migration to Python 3.13."                              | start_async_task targeting jarvis-reasoner with role planner                     |
      | "Ask Gemini 3.1 Pro for a frontier opinion on this ADR."          | escalate_to_frontier with the default target                                     |
      | "Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo."               | queue_build                                                                      |

  # Why: Backwards-compatibility guarantee — Phase 1 + FEAT-002 callers still work
  @edge-case
  Scenario: Building the supervisor without async subagents preserves existing behaviour
    When the supervisor is built without the async-subagents argument
    Then the build succeeds
    And the supervisor's tool catalogue does not include the five middleware operational tools

  # Why: ambient_tool_factory default — design.md §8 — falls back to attended list minus frontier
  @edge-case
  Scenario: Not configuring an ambient tool factory falls back to the attended tools without frontier
    When the supervisor is built with an attended tool list and no ambient tool factory
    Then ambient and learning paths see the attended tool list with escalate_to_frontier removed

  # Why: Multiple roles in flight at once — middleware should handle parallel tasks
  @edge-case
  Scenario: Two different role-mode tasks can run in parallel without collision
    Given an async task targeting jarvis-reasoner with role critic is running
    When the supervisor starts a second async task targeting jarvis-reasoner with role planner
    Then both tasks have distinct task identifiers
    And the second task uses the planner system prompt
    And neither task overwrites the other's state

  # Why: Voice ack on cold swap — exercised on the voice-reactive adapter
  @edge-case @smoke
  Scenario: A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued
    Given the active session is on a voice-reactive adapter
    And the llama-swap adapter reports an estimated time of two hundred and forty seconds for jarvis-reasoner
    When the supervisor receives a request that would dispatch to jarvis-reasoner
    Then the supervisor emits the TTS acknowledgement
    And the request is queued for dispatch once the swap completes

  # Why: Swap status source defaults to stub in Phase 2 — guard against accidental live-wiring
  @edge-case
  Scenario: The llama-swap adapter reports a stub source in Phase 2
    When the llama-swap adapter is asked for the current status of any alias
    Then the returned status is marked as coming from the stub source

  # Why: Subagent graph compiles at module import — DDR-012
  @edge-case
  Scenario: Importing the jarvis-reasoner subagent module compiles its graph
    When the jarvis-reasoner subagent module is imported in a fresh process
    Then a compiled graph object is exposed at module scope
    And no LLM network call has been made

  # Why: Frontier escalation log shape feeds FEAT-JARVIS-004 trace ingestion
  @edge-case
  Scenario: A successful frontier escalation logs a structured event with target, session, correlation, adapter, instruction length, and outcome
    Given the active session is on an attended adapter with a known correlation id
    When the reasoning model successfully invokes escalate_to_frontier with an instruction
    Then a structured frontier-escalation log entry is recorded
    And the log entry contains the target, the session id, the correlation id, the adapter, the instruction length, and a success outcome
    And the log entry never contains the instruction body

  # Why: Description-text invariant guards routing-behaviour regressions
  @edge-case @regression
  Scenario: The jarvis-reasoner description does not mention the retired four-subagent roster
    When the subagent description is inspected
    Then it does not contain the names deep_reasoner, adversarial_critic, long_research, or quick_local
    And it does not promise cloud-tier reasoning

  # Why: Subagent never has further tools — leaf, per design.md §8 and DDR-010
  @edge-case
  Scenario: The jarvis-reasoner subagent graph carries no tools of its own
    When the jarvis-reasoner compiled graph is inspected
    Then it has no application tools wired
    And it has no further subagents wired
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 36 scenarios across 4 groups
Inferred assumptions: 6 (will be resolved in Phase 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each group, you may:

[A] Accept  — include all scenarios in this group as-is
[R] Reject  — exclude all scenarios in this group
[M] Modify  — accept but specify changes (provide inline)
[+] Add     — accept and add additional scenarios you describe
[?] Defer   — mark group for future specification; excluded from output

Fast path: type "A A A A" to accept all four groups at once.

GROUP A — Key Examples (10 scenarios): _
GROUP B — Boundary Conditions (6 scenarios): _
GROUP C — Negative Cases (10 scenarios): _
GROUP D — Edge Cases (10 scenarios): _

phase2-build-plan.md
A A A A
All four groups accepted. Proceeding to Phase 4: Edge Case Expansion.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've identified 8 additional scenarios covering security, concurrency, data integrity, and integration boundaries that DDR-014's belt+braces gating, ADR-ARCH-022, and the FEAT-JARVIS-004 hand-off invite:

Security (3):

A spoofed-ambient invocation from inside an attended session is rejected (the explicit DDR-014 spoof case)
Frontier escalation cannot be added to the ambient list by reasoning-time configuration (ADR-ARCH-023 — permissions are constitutional)
A malicious instruction containing prompt-injection text aimed at bypassing the attended-only gate does not bypass it (the gate fires before the model is reached)
Concurrency (2):

A cancel_async_task mid-flight on a running jarvis-reasoner task transitions cleanly to a cancelled status
The supervisor checking an unknown task_id returns a structured "no such task" result rather than raising
Data integrity (1):

correlation_id propagates from session through start_async_task input and is preserved on the eventual check_async_task result (the trace-richness invariant FEAT-JARVIS-004 will rely on)
Integration boundaries (2):

The frontier provider returning an empty body is treated as a degraded outcome, not a silent success
The llama-swap adapter recovering from the previously-stubbed degraded path returns ETA 0 on the next call (idempotency under repeated reads)
[Y] Yes — show and curate them (same A/R/M/+/? actions)
[S] Sample — show 2 examples, then decide
[N] No — skip and proceed to Phase 5

Your choice [Y/S/N]:

Y
Here are the 8 edge-case expansion scenarios in full Gherkin.


  # ---------------------------------------------------------------------------
  # GROUP E — Edge Case Expansion (Security / Concurrency / Integrity / Integration)
  # ---------------------------------------------------------------------------

  # Why: DDR-014 Layer 2 explicit spoof case — attended-session reasoning that tries to
  # call escalate_to_frontier from inside an async-subagent frame must still be rejected
  @edge-case @negative @security
  Scenario: A spoofed-ambient invocation from inside an attended session is rejected
    Given the active session is on an attended adapter
    And an async subagent invocation is in progress within that session
    When code in the async-subagent frame invokes escalate_to_frontier with an instruction
    Then the tool returns an error indicating attended use only
    And the error names the async-subagent caller frame
    And no outbound request is made to any frontier provider

  # Why: ADR-ARCH-023 — permissions are constitutional; reasoning cannot mutate them
  @edge-case @negative @security
  Scenario: The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime
    Given the supervisor has been built with attended and ambient tool lists in place
    When the reasoning model attempts to register escalate_to_frontier on the ambient tool list during a turn
    Then the ambient tool list remains unchanged
    And escalate_to_frontier is still absent from the assembled ambient list

  # Why: Layer 2 fires before the frontier model sees the instruction — prompt injection
  # in the instruction body cannot bypass the gate
  @edge-case @negative @security
  Scenario: A prompt-injection instruction does not bypass the attended-only gate
    Given the active session is on an ambient adapter
    When the reasoning model invokes escalate_to_frontier with an instruction that asks the gate to be ignored
    Then the tool returns an error indicating attended use only
    And no outbound request is made to any frontier provider
    And the instruction body is not echoed in the structured error

  # Why: cancel_async_task is part of the middleware contract — supervisor must be able
  # to reach a clean cancelled status without hanging
  @edge-case @concurrency
  Scenario: Cancelling a running jarvis-reasoner task transitions it cleanly to a cancelled status
    Given an async task targeting jarvis-reasoner with role researcher is running
    When the supervisor cancels the task by its identifier
    And the supervisor then checks the task status
    Then the result indicates the task was cancelled
    And the task identifier in the result matches the cancelled task

  # Why: Defensive — checking an unknown task identifier must not raise per ADR-ARCH-021
  @edge-case @negative
  Scenario: Checking an unknown task identifier returns a structured no-such-task result
    When the supervisor checks the status of a task identifier that was never started
    Then the result indicates no such task exists
    And no exception propagates to the supervisor

  # Why: correlation_id is the trace-richness invariant FEAT-JARVIS-004 depends on
  @edge-case @integrity
  Scenario: The session correlation identifier propagates from input through to check-task results
    Given the active session has a known correlation identifier
    When the supervisor starts an async task targeting jarvis-reasoner with role planner, a non-empty prompt, and the session's correlation identifier
    And the supervisor later checks the task status
    Then the returned result carries the same correlation identifier the session originated with

  # Why: Empty response from the frontier provider is a degraded outcome, not silent success
  @edge-case @negative @integration
  Scenario: An empty frontier response is reported as a degraded outcome
    Given the active session is on an attended adapter
    And the configured frontier provider returns an empty body
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns a degraded result indicating the provider returned no content
    And the structured frontier-escalation log entry records the degraded outcome

  # Why: Swap-adapter idempotency — repeated reads stay consistent and never accumulate state
  @edge-case @integration
  Scenario: Repeated swap-status reads for the same alias return consistent results
    Given the llama-swap adapter is configured with a stubbed status for jarvis-reasoner
    When the supervisor reads the swap status for jarvis-reasoner three times in succession
    Then each call returns an equivalent swap status
    And no internal counter or cache is mutated by the reads
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Edge case expansion group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GROUP E — Edge Case Expansion (8 scenarios): _

Apply [A] Accept / [R] Reject / [M] Modify / [+] Add / [?] Defer.

A
Group E accepted. Proceeding to Phase 5: Assumption Resolution.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (6 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each assumption has a proposed default. Press Enter to accept, or type the actual value.


[1] Empty frontier-provider response is reported as DEGRADED (not ERROR)
    Proposed: DEGRADED: provider_unavailable family — empty body is "provider returned nothing useful",
              which semantically matches "unavailable" more than "config missing" or "attended-only"
    Confidence: medium
    Basis: Design.md §8 + API-tools.md §"Error modes" name only three DEGRADED/ERROR branches;
           empty-body isn't explicitly mapped. Could also argue ERROR: empty_response.
    Accept or enter value: _

[2] A cancelled async task reports status="cancelled" (not "error" or "complete-empty")
    Proposed: status="cancelled" — separate from "error" / "running" / "complete"
    Confidence: medium
    Basis: API-subagent.md §"Output contract" lists {complete, running, error} explicitly;
           cancel_async_task exists in the middleware catalogue but its surfaced status isn't
           spelled out. DeepAgents 0.5.3 convention would pin this.
    Accept or enter value: _

[3] Checking an unknown task_id returns a structured "no such task" result (not raise, not silent empty)
    Proposed: status="error", error="ERROR: unknown_task_id — <id>" (ADR-ARCH-021 discipline)
    Confidence: medium
    Basis: Design explicitly requires structured errors; this specific path isn't in the Error modes
           table but the discipline generalises.
    Accept or enter value: _

[4] An empty-string role ("") is rejected as "unknown_role" (not "missing_field")
    Proposed: unknown_role — "" is present-but-invalid rather than absent; RoleName("") raises
              ValueError at enum lookup which maps to unknown_role per design.md §8
    Confidence: low
    Basis: Inference only; could be argued either way. If you prefer missing_field semantics
           for empty strings specifically, change to "missing_field".
    Accept or enter value: _

[5] A FrontierTarget value not in the enum is rejected before any provider is contacted
    Proposed: Rejected at tool-boundary type validation — no outbound request made
    Confidence: medium
    Basis: @tool(parse_docstring=True) + Enum type coercion happens before the body runs;
           DDR-014 Layer 2 (executor assertion) is a second safety but the Enum reject is
           the actual first line.
    Accept or enter value: _

[6] The attended-only error return string does not echo the instruction body
    Proposed: Error return names only the adapter / caller-frame — never the instruction text
    Confidence: medium
    Basis: DM-subagent-types.md §6 FrontierEscalationContext explicitly redacts the instruction
           body from logs; extending the same posture to structured error strings is consistent
           with ADR-ARCH-029 but not literally specified.
    Accept or enter value: _
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Press Enter after each to accept the proposal, or type an override.

accept defauls
All 6 defaults accepted. Proceeding to Phase 6: Output Generation.

Bash Create feature output directory
IN
mkdir -p /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-003-async-subagent-and-frontier-escape

OUT
(Bash completed with no output)
Write feat-jarvis-003-async-subagent-and-frontier-escape.feature
456 lines
# Generated by /feature-spec
# Feature: Async Subagent for Model Routing + Attended Frontier Escape
# Stack: python
# Assumptions: 6 (see feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml)
# Generated: 2026-04-24T00:00:00Z
#
# Scope reframe: the originating command named the retired four-cloud-subagent
# roster (deep_reasoner / adversarial_critic / long_research / quick_local) and
# the JA6 cloud-fallback hook. Both are superseded by ADR-ARCH-001 /
# ADR-ARCH-011 / ADR-ARCH-012 / ADR-ARCH-027 and reconciled in
# docs/design/FEAT-JARVIS-003/design.md + DDR-010 / DDR-014 / DDR-015. This
# feature file specs the authoritative design: one jarvis-reasoner AsyncSubAgent
# with a role kwarg, an attended-only escalate_to_frontier tool, and a
# swap-aware LlamaSwapAdapter with stubbed health.

@feat-jarvis-003
Feature: Async Subagent for Model Routing + Attended Frontier Escape
  As the Jarvis supervisor's reasoning model
  I want a single local jarvis-reasoner subagent that I can dispatch to with a
  named role, an attended-only escalate_to_frontier tool for cloud opinions Rich
  has explicitly asked for, and a swap-aware view of the GB10 model so my voice
  responses stay honest about latency
  So that "one reasoning model that knows which reasoning model to use" works
  in practice without ever silently sending Rich's data to a cloud provider

  Background:
    Given Jarvis has started with the FEAT-JARVIS-002 tool surface intact
    And llama-swap is reachable at the configured base URL
    And the supervisor has been built with the jarvis-reasoner async subagent wired
    And the attended tool list includes escalate_to_frontier
    And the ambient tool list excludes escalate_to_frontier

  # ---------------------------------------------------------------------------
  # GROUP A — Key Examples
  # ---------------------------------------------------------------------------

  # Why: Core path — one AsyncSubAgent named jarvis-reasoner is registered (DDR-010, ADR-ARCH-011)
  @key-example @smoke
  Scenario: A single jarvis-reasoner async subagent is registered at startup
    When the subagent registry is built from the configuration
    Then exactly one async subagent is returned
    And the subagent is named jarvis-reasoner
    And its graph identifier is jarvis_reasoner
    And its description names the local model, names the three role modes, states no cloud cost, and warns against use for arithmetic, lookups, and file reads

  # Why: Description is the contract with the reasoning model — must carry cost + latency signals
  @key-example @smoke
  Scenario: The jarvis-reasoner description carries cost and latency signals the reasoning model can read
    When the supervisor receives the subagent catalogue
    Then the description states that all inference stays on the premises
    And the description states sub-second per-turn latency when the model is loaded
    And the description warns that a cold swap can take two to four minutes and the supervisor will emit a voice acknowledgement if so

  # Why: Role-dispatch happy path for CRITIC — the canonical adversarial use-case
  @key-example @smoke
  Scenario: Dispatching to the critic role launches an async task and returns a task identifier
    Given the reasoning model wants an adversarial review of an architecture document
    When it starts an async task targeting jarvis-reasoner with role critic and a non-empty prompt
    Then the middleware returns a task identifier immediately
    And the subagent graph resolves the system prompt for the critic role
    And the task runs against the local jarvis-reasoner alias

  # Why: Role-dispatch happy path for RESEARCHER
  @key-example @smoke
  Scenario: Dispatching to the researcher role uses the open-ended research posture
    Given the reasoning model wants open-ended research on a topic
    When it starts an async task targeting jarvis-reasoner with role researcher and a non-empty prompt
    Then the middleware returns a task identifier
    And the subagent graph resolves the system prompt for the researcher role

  # Why: Role-dispatch happy path for PLANNER
  @key-example @smoke
  Scenario: Dispatching to the planner role uses the multi-step planning posture
    Given the reasoning model wants a multi-step plan
    When it starts an async task targeting jarvis-reasoner with role planner and a non-empty prompt
    Then the middleware returns a task identifier
    And the subagent graph resolves the system prompt for the planner role

  # Why: Role prompts must exist for every member of the closed RoleName enum (DDR-011)
  @key-example
  Scenario: The role prompt registry covers every member of the role enum
    When the role prompt registry is inspected
    Then it contains a non-empty system prompt for the critic role
    And it contains a non-empty system prompt for the researcher role
    And it contains a non-empty system prompt for the planner role
    And no extra members are present beyond the closed enum

  # Why: AsyncSubAgentMiddleware injects the five operational tools — supervisor sees them
  @key-example @smoke
  Scenario: Wiring the async subagent injects the five middleware operational tools
    When the supervisor is built with the jarvis-reasoner async subagent
    Then the supervisor's tool catalogue includes start_async_task, check_async_task, update_async_task, cancel_async_task, and list_async_tasks

  # Why: Attended escalation happy path — Rich asks Jarvis to ask Gemini
  @key-example @smoke
  Scenario: An attended session can escalate to the default frontier model
    Given the active session is on an attended adapter
    And the configured default frontier target is reachable
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns the frontier model's response as a string
    And the invocation is recorded as a frontier escalation event

  # Why: Supervisor prompt teaches both new sections — design.md §10
  @key-example
  Scenario: The supervisor system prompt teaches subagent routing and frontier escalation
    When the supervisor system prompt is rendered for a new session
    Then it includes a Subagent Routing section that names jarvis-reasoner and lists the three role modes
    And it includes a Frontier Escalation section that states cloud escalation is only available when Rich asks for it explicitly

  # Why: Repo-root langgraph.json declares both graphs with ASGI transport (DDR-013)
  @key-example
  Scenario: The repo-root langgraph manifest declares both graphs with ASGI transport
    When the langgraph manifest at the repo root is loaded
    Then it declares a graph named jarvis bound to the supervisor module
    And it declares a graph named jarvis_reasoner bound to the subagent module
    And both graphs use the in-process ASGI transport

  # ---------------------------------------------------------------------------
  # GROUP B — Boundary Conditions
  # ---------------------------------------------------------------------------

  # Why: Role enum is a closed set — only the three members are accepted (DDR-011)
  @boundary
  Scenario Outline: The jarvis-reasoner subagent accepts only the three documented role values
    Given the supervisor wants to dispatch to jarvis-reasoner
    When it starts an async task with role <role> and a non-empty prompt
    Then the outcome is <outcome>

    Examples:
      | role        | outcome                                                |
      | critic      | the task is launched and a task identifier is returned |
      | researcher  | the task is launched and a task identifier is returned |
      | planner     | the task is launched and a task identifier is returned |

  # Why: Just-outside boundary — anything not in the enum is rejected via structured error
  # [ASSUMPTION: confidence=low] An empty-string role value is treated as unknown_role (not missing_field);
  # RoleName("") raises at enum lookup and the subagent maps that to the unknown_role path
  @boundary @negative
  Scenario Outline: Unknown role values are rejected with a structured error
    When the supervisor starts an async task targeting jarvis-reasoner with role <role> and a non-empty prompt
    Then the subagent reports an error indicating the role was not recognised
    And the error names the three accepted role values

    Examples:
      | role           |
      | bard           |
      | adversarial    |
      | CRITIC         |
      | ""             |

  # Why: Swap ETA boundary drives ADR-ARCH-012 voice-ack policy
  @boundary
  Scenario Outline: Swap status above the voice-ack threshold triggers the supervisor TTS acknowledgement
    Given the active session is on a voice-reactive adapter
    And the llama-swap adapter reports an estimated time of <eta_seconds> seconds for the wanted alias
    When the supervisor decides whether to emit a voice acknowledgement
    Then the outcome is <outcome>

    Examples:
      | eta_seconds | outcome                                                               |
      | 0           | no voice acknowledgement is emitted; the request proceeds directly    |
      | 30          | no voice acknowledgement is emitted; the request proceeds directly    |
      | 31          | the supervisor emits the voice acknowledgement and queues the request |
      | 240         | the supervisor emits the voice acknowledgement and queues the request |

  # Why: Frontier targets are a closed set — additions require a DDR
  # [ASSUMPTION: confidence=medium] A FrontierTarget value outside the enum is rejected at
  # tool-boundary type validation before any provider is contacted
  @boundary
  Scenario Outline: Only documented frontier targets are accepted
    Given the active session is on an attended adapter
    When the reasoning model invokes escalate_to_frontier with target <target>
    Then the outcome is <outcome>

    Examples:
      | target                                 | outcome                                               |
      | GEMINI_3_1_PRO (default)               | the configured Gemini provider is invoked             |
      | OPUS_4_7                               | the configured Anthropic provider is invoked          |
      | a value not in the FrontierTarget enum | the call is rejected before any provider is contacted |

  # Why: prompt is a required, non-empty field on AsyncTaskInput
  @boundary @negative
  Scenario: An async task with an empty prompt is rejected with a missing-field error
    When the supervisor starts an async task targeting jarvis-reasoner with role critic and an empty prompt
    Then the subagent reports an error indicating the prompt field is required

  # Why: SwapStatus.eta_seconds invariant: zero means ready, negative is illegal
  @boundary
  Scenario Outline: Swap status enforces a non-negative ETA
    When the llama-swap adapter is asked to construct a swap status with eta_seconds <value>
    Then the outcome is <outcome>

    Examples:
      | value | outcome                                       |
      | 0     | a status with eta_seconds 0 is returned       |
      | 1     | a status with eta_seconds 1 is returned       |
      | -1    | construction is rejected as an invalid model  |

  # ---------------------------------------------------------------------------
  # GROUP C — Negative Cases
  # ---------------------------------------------------------------------------

  # Why: Layer 2 of DDR-014 belt+braces — executor assertion on adapter
  @negative @smoke
  Scenario: An ambient session is rejected if it somehow invokes escalate_to_frontier
    Given the active session is on an ambient adapter
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns an error indicating attended use only
    And the error names the offending adapter

  # Why: Layer 2 again — executor assertion on async-subagent caller frame
  @negative
  Scenario: A call from an async subagent frame is rejected as attended-only
    Given an async subagent invocation is in progress
    When code in that frame invokes escalate_to_frontier with an instruction
    Then the tool returns an error indicating attended use only
    And the error names the async-subagent caller frame

  # Why: Layer 3 of DDR-014 — registration absence is the third brace
  @negative @smoke
  Scenario: escalate_to_frontier is not present in the ambient tool list at all
    When the ambient tool list is assembled
    Then escalate_to_frontier is not present in the assembled list
    And the assembled list still contains all FEAT-JARVIS-002 tools

  # Why: Provider key absence — graceful structured error per ADR-ARCH-021
  @negative
  Scenario: Escalating to Gemini without a configured Google API key returns a configuration error
    Given the active session is on an attended adapter
    And no Google API key is configured
    When the reasoning model invokes escalate_to_frontier with the default target
    Then the tool returns an error indicating the Google API key is not set
    And no outbound request is made to the provider

  # Why: Provider key absence for the alternate target
  @negative
  Scenario: Escalating to Opus without a configured Anthropic API key returns a configuration error
    Given the active session is on an attended adapter
    And no Anthropic API key is configured
    When the reasoning model invokes escalate_to_frontier targeting Opus
    Then the tool returns an error indicating the Anthropic API key is not set
    And no outbound request is made to the provider

  # Why: Provider availability — degraded outcome surfaces as DEGRADED prefix
  @negative
  Scenario: Frontier provider unavailability returns a degraded result without raising
    Given the active session is on an attended adapter
    And the configured frontier provider is unreachable
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns a degraded result indicating provider unavailability
    And no exception propagates to the supervisor

  # Why: Subagent never raises — model unavailability is structured per ADR-ARCH-021
  @negative
  Scenario: A missing llama-swap alias surfaces as a structured model-unavailable error
    Given the llama-swap alias for jarvis-reasoner cannot be resolved
    When the supervisor starts an async task targeting jarvis-reasoner with role planner and a non-empty prompt
    Then the subagent reports an error indicating the model is unavailable
    And the error mentions checking the llama-swap running endpoint

  # Why: Subagent timeout is a structured TIMEOUT, not an exception
  @negative
  Scenario: An async task that exceeds its timeout returns a structured timeout result
    Given an async task targeting jarvis-reasoner is running past the configured timeout
    When the supervisor checks the task status
    Then the result indicates the task timed out
    And the result identifies the affected task

  # Why: Subagent input requires both prompt and role — missing role is rejected
  @negative
  Scenario: An async task missing the role field is rejected with a structured error
    When the supervisor starts an async task targeting jarvis-reasoner with a non-empty prompt and no role
    Then the subagent reports an error indicating a required field is missing

  # Why: Subagent factory must not silently expand its roster — guard against accidental DDR-010 regression
  @negative
  Scenario: Adding an unsanctioned subagent does not silently appear in the registry
    When the subagent registry is built from the configuration
    Then no subagent named deep_reasoner is present
    And no subagent named adversarial_critic is present
    And no subagent named long_research is present
    And no subagent named quick_local is present

  # ---------------------------------------------------------------------------
  # GROUP D — Edge Cases
  # ---------------------------------------------------------------------------

  # Why: Acceptance test for FEAT-JARVIS-003 — seven canned routing decisions
  @edge-case @smoke
  Scenario Outline: The supervisor routes the seven canned acceptance prompts to the expected tools
    Given the supervisor has been built with all FEAT-JARVIS-002 tools, the jarvis-reasoner subagent, and the attended tool list including escalate_to_frontier
    And the active session is on an attended adapter
    When the user says <prompt>
    Then the reasoning model invokes <expected_action>

    Examples:
      | prompt                                                   | expected_action                                                 |
      | "What's 15% of 847?"                                     | calculate                                                       |
      | "Summarise /tmp/test.md"                                 | read_file                                                       |
      | "Critique this architecture doc for subtle flaws."       | start_async_task targeting jarvis-reasoner with role critic     |
      | "Research Meta-Harness deeply."                          | start_async_task targeting jarvis-reasoner with role researcher |
      | "Plan the migration to Python 3.13."                     | start_async_task targeting jarvis-reasoner with role planner    |
      | "Ask Gemini 3.1 Pro for a frontier opinion on this ADR." | escalate_to_frontier with the default target                    |
      | "Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo."      | queue_build                                                     |

  # Why: Backwards-compatibility guarantee — Phase 1 + FEAT-002 callers still work
  @edge-case
  Scenario: Building the supervisor without async subagents preserves existing behaviour
    When the supervisor is built without the async-subagents argument
    Then the build succeeds
    And the supervisor's tool catalogue does not include the five middleware operational tools

  # Why: ambient_tool_factory default — design.md §8 — falls back to attended list minus frontier
  @edge-case
  Scenario: Not configuring an ambient tool factory falls back to the attended tools without frontier
    When the supervisor is built with an attended tool list and no ambient tool factory
    Then ambient and learning paths see the attended tool list with escalate_to_frontier removed

  # Why: Multiple roles in flight at once — middleware should handle parallel tasks
  @edge-case
  Scenario: Two different role-mode tasks can run in parallel without collision
    Given an async task targeting jarvis-reasoner with role critic is running
    When the supervisor starts a second async task targeting jarvis-reasoner with role planner
    Then both tasks have distinct task identifiers
    And the second task uses the planner system prompt
    And neither task overwrites the other's state

  # Why: Voice ack on cold swap — exercised on the voice-reactive adapter
  @edge-case @smoke
  Scenario: A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued
    Given the active session is on a voice-reactive adapter
    And the llama-swap adapter reports an estimated time of two hundred and forty seconds for jarvis-reasoner
    When the supervisor receives a request that would dispatch to jarvis-reasoner
    Then the supervisor emits the TTS acknowledgement
    And the request is queued for dispatch once the swap completes

  # Why: Swap status source defaults to stub in Phase 2 — guard against accidental live-wiring
  @edge-case
  Scenario: The llama-swap adapter reports a stub source in Phase 2
    When the llama-swap adapter is asked for the current status of any alias
    Then the returned status is marked as coming from the stub source

  # Why: Subagent graph compiles at module import — DDR-012
  @edge-case
  Scenario: Importing the jarvis-reasoner subagent module compiles its graph
    When the jarvis-reasoner subagent module is imported in a fresh process
    Then a compiled graph object is exposed at module scope
    And no LLM network call has been made

  # Why: Frontier escalation log shape feeds FEAT-JARVIS-004 trace ingestion
  @edge-case
  Scenario: A successful frontier escalation logs a structured event with target, session, correlation, adapter, instruction length, and outcome
    Given the active session is on an attended adapter with a known correlation id
    When the reasoning model successfully invokes escalate_to_frontier with an instruction
    Then a structured frontier-escalation log entry is recorded
    And the log entry contains the target, the session id, the correlation id, the adapter, the instruction length, and a success outcome
    And the log entry never contains the instruction body

  # Why: Description-text invariant guards routing-behaviour regressions
  @edge-case @regression
  Scenario: The jarvis-reasoner description does not mention the retired four-subagent roster
    When the subagent description is inspected
    Then it does not contain the names deep_reasoner, adversarial_critic, long_research, or quick_local
    And it does not promise cloud-tier reasoning

  # Why: Subagent never has further tools — leaf, per design.md §8 and DDR-010
  @edge-case
  Scenario: The jarvis-reasoner subagent graph carries no tools of its own
    When the jarvis-reasoner compiled graph is inspected
    Then it has no application tools wired
    And it has no further subagents wired

  # ---------------------------------------------------------------------------
  # GROUP E — Edge Case Expansion (Security / Concurrency / Integrity / Integration)
  # ---------------------------------------------------------------------------

  # Why: DDR-014 Layer 2 explicit spoof case — attended-session reasoning that tries to
  # call escalate_to_frontier from inside an async-subagent frame must still be rejected
  @edge-case @negative @security
  Scenario: A spoofed-ambient invocation from inside an attended session is rejected
    Given the active session is on an attended adapter
    And an async subagent invocation is in progress within that session
    When code in the async-subagent frame invokes escalate_to_frontier with an instruction
    Then the tool returns an error indicating attended use only
    And the error names the async-subagent caller frame
    And no outbound request is made to any frontier provider

  # Why: ADR-ARCH-023 — permissions are constitutional; reasoning cannot mutate them
  @edge-case @negative @security
  Scenario: The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime
    Given the supervisor has been built with attended and ambient tool lists in place
    When the reasoning model attempts to register escalate_to_frontier on the ambient tool list during a turn
    Then the ambient tool list remains unchanged
    And escalate_to_frontier is still absent from the assembled ambient list

  # Why: Layer 2 fires before the frontier model sees the instruction — prompt injection
  # in the instruction body cannot bypass the gate
  # [ASSUMPTION: confidence=medium] The attended-only error return string does not echo
  # the instruction body — consistent with ADR-ARCH-029 redaction posture applied to
  # structured error strings as well as log fields
  @edge-case @negative @security
  Scenario: A prompt-injection instruction does not bypass the attended-only gate
    Given the active session is on an ambient adapter
    When the reasoning model invokes escalate_to_frontier with an instruction that asks the gate to be ignored
    Then the tool returns an error indicating attended use only
    And no outbound request is made to any frontier provider
    And the instruction body is not echoed in the structured error

  # Why: cancel_async_task is part of the middleware contract — supervisor must be able
  # to reach a clean cancelled status without hanging
  # [ASSUMPTION: confidence=medium] A cancelled async task surfaces via check_async_task
  # with status cancelled (distinct from complete / running / error)
  @edge-case @concurrency
  Scenario: Cancelling a running jarvis-reasoner task transitions it cleanly to a cancelled status
    Given an async task targeting jarvis-reasoner with role researcher is running
    When the supervisor cancels the task by its identifier
    And the supervisor then checks the task status
    Then the result indicates the task was cancelled
    And the task identifier in the result matches the cancelled task

  # Why: Defensive — checking an unknown task identifier must not raise per ADR-ARCH-021
  # [ASSUMPTION: confidence=medium] An unknown task_id returns a structured no-such-task
  # result rather than raising or silently returning empty
  @edge-case @negative
  Scenario: Checking an unknown task identifier returns a structured no-such-task result
    When the supervisor checks the status of a task identifier that was never started
    Then the result indicates no such task exists
    And no exception propagates to the supervisor

  # Why: correlation_id is the trace-richness invariant FEAT-JARVIS-004 depends on
  @edge-case @integrity
  Scenario: The session correlation identifier propagates from input through to check-task results
    Given the active session has a known correlation identifier
    When the supervisor starts an async task targeting jarvis-reasoner with role planner, a non-empty prompt, and the session's correlation identifier
    And the supervisor later checks the task status
    Then the returned result carries the same correlation identifier the session originated with

  # Why: Empty response from the frontier provider is a degraded outcome, not silent success
  # [ASSUMPTION: confidence=medium] An empty body from the frontier provider is mapped to
  # the DEGRADED: provider_unavailable family rather than an ERROR or silent success
  @edge-case @negative @integration
  Scenario: An empty frontier response is reported as a degraded outcome
    Given the active session is on an attended adapter
    And the configured frontier provider returns an empty body
    When the reasoning model invokes escalate_to_frontier with an instruction
    Then the tool returns a degraded result indicating the provider returned no content
    And the structured frontier-escalation log entry records the degraded outcome

  # Why: Swap-adapter idempotency — repeated reads stay consistent and never accumulate state
  @edge-case @integration
  Scenario: Repeated swap-status reads for the same alias return consistent results
    Given the llama-swap adapter is configured with a stubbed status for jarvis-reasoner
    When the supervisor reads the swap status for jarvis-reasoner three times in succession
    Then each call returns an equivalent swap status
    And no internal counter or cache is mutated by the reads
Write feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml
102 lines
# Assumptions manifest for feat-jarvis-003-async-subagent-and-frontier-escape.feature
# Generated by /feature-spec

feature: "Async Subagent for Model Routing + Attended Frontier Escape"
generated: "2026-04-24T00:00:00Z"
stack: "python"
review_required: true

assumptions:
  - id: "ASSUM-001"
    scenario: "An empty frontier response is reported as a degraded outcome"
    assumption: >
      An empty body from the frontier provider is mapped to the
      DEGRADED: provider_unavailable family rather than an ERROR or silent
      success. The structured frontier-escalation log entry records a degraded
      outcome.
    confidence: medium
    basis: >
      docs/design/FEAT-JARVIS-003/contracts/API-tools.md §"Error modes" lists
      ERROR (attended_only, config_missing) and DEGRADED (provider_unavailable)
      branches but does not explicitly map empty-body to a branch. Mapping to
      DEGRADED matches the semantic of "provider returned nothing useful";
      could equally be modelled as ERROR: empty_response.
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Cancelling a running jarvis-reasoner task transitions it cleanly to a cancelled status"
    assumption: >
      A cancelled async task surfaces via check_async_task with status
      "cancelled" — distinct from the {complete, running, error} statuses
      enumerated in API-subagent.md §"Output contract".
    confidence: medium
    basis: >
      docs/design/FEAT-JARVIS-003/contracts/API-subagent.md §"Output contract"
      enumerates statuses {complete, running, error}; cancel_async_task is
      listed in the middleware tool catalogue but its surfaced status is not
      explicitly named. DeepAgents 0.5.3 convention would pin this; the
      0.5.3 SDK review (specialist-agent/docs/reviews/deepagents-sdk-2026-04.md)
      is the authoritative reference.
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "Checking an unknown task identifier returns a structured no-such-task result"
    assumption: >
      An unknown task_id passed to check_async_task returns a structured
      "no such task" result (e.g. ERROR: unknown_task_id) rather than raising
      or silently returning an empty result. Honours ADR-ARCH-021 discipline.
    confidence: medium
    basis: >
      ADR-ARCH-021 (tools return structured errors) generalises to this path
      but the API-subagent.md §"Error modes" table does not list it
      explicitly. Behaviour is the natural application of the discipline.
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "Unknown role values are rejected with a structured error"
    assumption: >
      An empty-string role value ("") is treated as unknown_role rather than
      missing_field. RoleName("") raises ValueError at enum lookup which the
      subagent maps to the unknown_role error path.
    confidence: low
    basis: >
      Inference from Python enum semantics. docs/design/FEAT-JARVIS-003/
      contracts/API-subagent.md §"Error modes" distinguishes unknown_role
      ("expected one of {critic, researcher, planner}, got=<value>") from
      missing_field ("prompt is required") but does not explicitly state
      whether "" routes to unknown_role or missing_field. Could be argued
      either way; flagged for human verification at implementation time.
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "Only documented frontier targets are accepted"
    assumption: >
      A FrontierTarget value outside the closed enum is rejected at
      tool-boundary type validation (Pydantic / @tool argument coercion)
      before the tool body runs and before any provider is contacted.
    confidence: medium
    basis: >
      docs/design/FEAT-JARVIS-003/models/DM-subagent-types.md §5 declares
      FrontierTarget as a closed str-Enum and DDR-014 §Layer 2 describes the
      executor assertion; the explicit rejection-before-provider-contact
      ordering is consistent with @tool(parse_docstring=True) coercion but
      not literally specified.
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "A prompt-injection instruction does not bypass the attended-only gate"
    assumption: >
      The structured error returned by escalate_to_frontier when invoked
      from an ambient adapter or async-subagent frame does not echo the
      instruction body. Only the adapter identity or caller-frame label is
      named in the error string.
    confidence: medium
    basis: >
      docs/design/FEAT-JARVIS-003/models/DM-subagent-types.md §6
      FrontierEscalationContext explicitly redacts the instruction body from
      log fields ("instruction_length is the length, never the body"). Apply­
      ing the same redaction posture to structured error return strings is
      consistent with ADR-ARCH-029 (personal-use compliance / redaction-by-
      default) but is not literally specified in the error-mode table.
    human_response: "confirmed"
Write feat-jarvis-003-async-subagent-and-frontier-escape_summary.md
105 lines
# Feature Spec Summary: Async Subagent for Model Routing + Attended Frontier Escape

**Stack**: python
**Generated**: 2026-04-24T00:00:00Z
**Scenarios**: 44 total (11 smoke, 1 regression)
**Assumptions**: 6 total (0 high / 5 medium / 1 low confidence)
**Review required**: Yes

## Scope

Gherkin specification for FEAT-JARVIS-003 — the surface that turns
*"one reasoning model that knows which reasoning model to use"* from aspiration
into observable behaviour. The feature ships:

1. A single `jarvis-reasoner` `AsyncSubAgent` (per
   [DDR-010](../../docs/design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md)
   / [ADR-ARCH-011](../../docs/architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md))
   with a closed-enum `role` kwarg (`critic` / `researcher` / `planner` per
   [DDR-011](../../docs/design/FEAT-JARVIS-003/decisions/DDR-011-role-enum-closed-v1.md)),
   compiled at module import time
   ([DDR-012](../../docs/design/FEAT-JARVIS-003/decisions/DDR-012-subagent-module-import-compilation.md)),
   exposed via repo-root `langgraph.json` with ASGI transport
   ([DDR-013](../../docs/design/FEAT-JARVIS-003/decisions/DDR-013-langgraph-json-at-repo-root.md)).

2. The five `AsyncSubAgentMiddleware` operational tools auto-injected by
   wiring `async_subagents=...` into `create_deep_agent`.

3. An attended-only `escalate_to_frontier` tool in `jarvis.tools.dispatch`
   ([DDR-014](../../docs/design/FEAT-JARVIS-003/decisions/DDR-014-escalate-to-frontier-in-dispatch-tool-module.md))
   with belt+braces gating across three layers — docstring + executor
   assertion (adapter + caller-frame) + ambient-tool-list registration absence.

4. A swap-aware `LlamaSwapAdapter` with stubbed health
   ([DDR-015](../../docs/design/FEAT-JARVIS-003/decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md))
   so the supervisor can honour ADR-ARCH-012's voice-latency policy without
   live llama-swap reads in Phase 2.

Aligned to the authoritative design at
[docs/design/FEAT-JARVIS-003/design.md](../../docs/design/FEAT-JARVIS-003/design.md)
and its contracts/models. The originating `/feature-spec` command named the
retired four-cloud-subagent roster (`deep_reasoner` / `adversarial_critic` /
`long_research` / `quick_local`) and the JA6 cloud-fallback hook; both are
superseded by ADR-ARCH-001 / -011 / -012 / -027 and the spec follows the
reframed design.

## Scenario Counts by Category

| Category                             | Count |
|--------------------------------------|-------|
| Key examples (`@key-example`)        | 10    |
| Boundary conditions (`@boundary`)    | 6     |
| Negative cases (`@negative`)         | 17    |
| Edge cases (`@edge-case`)            | 18    |
| Smoke (`@smoke`)                     | 11    |
| Regression (`@regression`)           | 1     |
| Security expansion (`@security`)     | 3     |
| Concurrency expansion (`@concurrency`)| 1    |
| Integrity expansion (`@integrity`)   | 1     |
| Integration expansion (`@integration`)| 2    |

Some scenarios carry multiple tags (e.g. `@boundary @negative`,
`@edge-case @negative @security`), so category counts overlap intentionally.

## Deferred Items

None — all five proposed groups (A/B/C/D/E) were accepted in full.

## Open Assumptions (low confidence)

- **ASSUM-004** — Empty-string `role` value (`""`) is treated as
  `unknown_role` rather than `missing_field`. `RoleName("")` raises
  `ValueError` at enum lookup which the subagent maps to the `unknown_role`
  path. Inference from Python enum semantics; the design does not
  literally specify which side of the boundary `""` falls on. Verify
  at implementation time and adjust the `unknown_role` example row if
  `missing_field` semantics are preferred for empty strings.

## Medium-confidence Assumptions To Verify At Implementation Time

- **ASSUM-001** — Empty body from the frontier provider maps to
  `DEGRADED: provider_unavailable` (rather than `ERROR: empty_response`).
- **ASSUM-002** — A cancelled async task surfaces as
  `status="cancelled"` via `check_async_task` (the design enumerates
  `complete` / `running` / `error` only).
- **ASSUM-003** — An unknown `task_id` returns a structured no-such-task
  result (e.g. `ERROR: unknown_task_id`) per ADR-ARCH-021 generalisation.
- **ASSUM-005** — Out-of-enum `FrontierTarget` is rejected at the
  `@tool` argument-coercion boundary before any provider is contacted.
- **ASSUM-006** — The attended-only structured error string does not echo
  the instruction body — extending DM-subagent-types §6's log-field
  redaction posture to error returns.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Async Subagent for Model Routing + Attended Frontier Escape" \
      --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md \
      --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature \
      --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml \
      --context docs/design/FEAT-JARVIS-003/design.md \
      --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
      --context docs/research/ideas/phase2-build-plan.md \
      --context .guardkit/context-manifest.yaml
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Async Subagent for Model Routing + Attended Frontier Escape
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature
features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml
features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md

Scenarios: 44 total
@key-example: 10   @boundary: 6
@negative: 17      @edge-case: 18
@smoke: 11         @regression: 1
@security: 3       @concurrency: 1
@integrity: 1      @integration: 2

Assumptions: 6 total
high: 0 (auto-proceed)
medium: 5 (Coach review recommended)
low: 1 (human review required)

REVIEW REQUIRED: 1 low-confidence assumption needs verification
See: features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml
- ASSUM-004: Empty-string role ("") → unknown_role (vs missing_field)

Deferred: 0 scenario groups

Important reframe note: The originating command line names the retired four-cloud-subagent roster (deep_reasoner / adversarial_critic / long_research / quick_local) and the JA6 cloud-fallback hook. These were superseded between scope-doc authorship (2026-04-20) and design-doc landing (2026-04-23) by ADR-ARCH-001 / -011 / -012 / -027. The spec follows the authoritative design (docs/design/FEAT-JARVIS-003/design.md): one jarvis-reasoner AsyncSubAgent with role kwarg, attended-only escalate_to_frontier tool, swap-aware LlamaSwapAdapter with stubbed health.

Next steps:
Review: features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature
Pass to feature-plan:


/feature-plan "Async Subagent for Model Routing + Attended Frontier Escape" \
  --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md \
  --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature \
  --context features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context .guardkit/context-manifest.yaml
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━