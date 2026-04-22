/feature-spec "Project Scaffolding, Supervisor Skeleton & Session Lifecycle: pyproject.toml with deepagents>=0.5.3,<0.6 pin, src/jarvis/ layer structure, DeepAgents supervisor via create_deep_agent(), thread-per-session with Memory Store, jarvis CLI (chat/version/health), smoke tests" \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/architecture/decisions/ADR-J-004-supervisor-model-default.md \
  --context docs/architecture/decisions/ADR-J-005-memory-store-backend.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context ../forge/src/forge/cli/main.py \
  --context ../specialist-agent/src/specialist_agent/cli/main.py \
  --context .guardkit/context-manifest.yaml

Globpattern: "pyproject.toml"
No files found
Globpattern: "**/*.feature"
No files found
Globpattern: "src/**/*.py"
No files found
Read design.md
Read ARCHITECTURE.md
Read phase1-supervisor-scaffolding-scope.md
Read phase1-build-plan.md
Read ADR-J-001-deepagents-pin.md
Globpattern: "docs/architecture/decisions/*.md"
Found 30 files
Globpattern: "docs/design/FEAT-JARVIS-001/**/*.md"
Found 10 files
The tentative ADR-J-* paths in the command don't exist; they were renumbered to ADR-ARCH-*. I'll map to the actual ones and continue context gathering.

Read API-cli.md
Read API-internal.md
Read DM-jarvis-reasoning.md
Read DM-config.md
Read DDR-002-memory-store-keyed-by-user-id.md
Read DDR-004-session-thread-1to1.md
Read ADR-ARCH-010-python-312-and-deepagents-pin.md
Read ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md
Read main.py
Read main.py
Read context-manifest.yaml
Read DDR-003-cli-minimal-surface.md
Globpattern: "../forge/src/**/main.py"
No files found
Globpattern: "../specialist-agent/docs/reviews/deepagents*"
No files found
Context loaded: stack=python (pyproject.toml not yet present — this feature creates it per ADR-ARCH-010), 0 existing src/ or .feature files, 30 architecture ADRs, 4 design DDRs, 2 contract specs (API-cli, API-internal), 2 data models (Session/Adapter/AppState, JarvisConfig). Note: the --context docs/architecture/decisions/ADR-J-00* paths were renumbered to ADR-ARCH-* per the build plan status log; substituted mapping (ADR-J-001→ADR-ARCH-010, -002→-002, -003→-006, -004→-011, -005→-009). --context ../forge/src/forge/cli/main.py and --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md not found — proceeding without them; specialist-agent CLI at ../specialist-agent/src/specialist_agent/cli/main.py read as substitute.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: Project Scaffolding, Supervisor Skeleton & Session Lifecycle
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@feat-jarvis-001 @foundation
Feature: Project Scaffolding, Supervisor Skeleton & Session Lifecycle
  As Rich, the attended operator of the Jarvis fleet surface
  I want a runnable jarvis package, a buildable DeepAgents supervisor,
    a CLI that starts conversations, and cross-session fact recall
  So that I can have a useful conversation with Jarvis on day 1
    and every subsequent v1 feature lands on a stable scaffold

  Background:
    Given the jarvis package has been installed into a clean Python 3.12 environment
    And no sessions are currently live
    And the supervisor model is configured to return deterministic canned responses for tests
━━ GROUP A: Key Examples (8 scenarios) ━━


  # Why: Core day-1 success criterion — Rich can hold a conversation from the CLI
  @key-example @smoke
  Scenario: Rich starts a conversation and receives a supervisor response
    Given the required provider configuration is in place
    When Rich runs "jarvis chat"
    And Rich enters "Hi Jarvis"
    Then the session should start successfully
    And Rich should see the supervisor's reply

  # Why: A conversation must end cleanly on the documented exit signals
  @key-example @smoke
  Scenario Outline: Rich ends a chat session cleanly
    Given Rich has started a chat session
    When Rich <end-signal>
    Then the session should end
    And a "session ended." banner should be shown
    And the process should exit with success

    Examples:
      | end-signal                |
      | types "/exit"             |
      | sends end-of-input (EOF)  |

  # Why: "version" is the smallest self-test for the installed package
  @key-example @smoke
  Scenario: Rich checks the installed jarvis version
    When Rich runs "jarvis version"
    Then the package version should be printed on a single line
    And the command should exit with success
    And no configuration should be loaded

  # Why: "health" is the wiring-debug primitive — validates config + builds the supervisor without spending tokens
  @key-example @smoke
  Scenario: Rich checks that the scaffold is healthy before a conversation
    Given the required provider configuration is in place
    When Rich runs "jarvis health"
    Then a status report should summarise the configuration
    And the report should indicate that the supervisor builds successfully
    And the report should indicate that the memory store is ready
    And the command should exit with success

  # Why: The day-1 cross-session recall criterion — Memory Store is keyed per user
  @key-example @smoke
  Scenario: A fact stated in one session is recalled in a later session for the same user
    Given Rich has had a chat session in which he stated "my DDD Southwest talk is on 16 May"
    And that session has ended
    When Rich starts a new chat session as the same user
    And Rich asks "when is my DDD talk?"
    Then the supervisor's reply should reference 16 May

  # Why: Running "jarvis" with no arguments should be discoverable (prints command list)
  @key-example
  Scenario: Running jarvis with no command prints the available commands
    When Rich runs "jarvis"
    Then the available commands should be listed
    And the command should exit with success

  # Why: Supervisor factory is the public contract consumed by every later feature
  @key-example
  Scenario: The supervisor factory produces a compiled graph with Phase 1 built-ins
    Given a valid configuration
    When build_supervisor is called with the configuration
    Then a compiled supervisor graph should be returned
    And the built-in tools "write_todos", virtual filesystem, and "task" should be enabled
    And the built-in tool "execute" should be disabled
    And no custom tools should be registered
    And no subagents should be registered

  # Why: Session identity is the stable primitive every later feature extends
  @key-example
  Scenario: Starting a session mints a new session with a stable identity
    When a CLI session is started for the user "rich"
    Then a Session object should be created
    And the session's thread_id should equal its session_id
    And the session's session_id should follow the documented adapter-prefixed pattern
    And a SessionStarted event should be emitted to the structured log
━━ GROUP B: Boundary Conditions (7 scenarios) ━━


  # Why: Just-inside boundary — two sessions started in quick succession must have distinct identity
  @boundary
  Scenario: Two successive session starts return distinct session identities
    When two CLI sessions are started for the same user
    Then the two session_ids should differ
    And the two thread_ids should differ
    And each session_id should match the documented adapter-prefixed pattern

  # Why: Just-outside boundary — adapter values other than CLI are reserved and must be refused in Phase 1
  @boundary @negative
  Scenario Outline: Non-CLI adapters are refused until their adapter feature ships
    When a session start is attempted with adapter "<adapter>"
    Then the session start should be refused
    And the refusal should reference the adapter name

    Examples:
      | adapter   |
      | telegram  |
      | dashboard |
      | reachy    |

  # Why: Default configuration loads with no env overrides (zero-config happy path)
  @boundary
  Scenario: Default configuration loads with no environment overrides
    Given no JARVIS_ environment variables are set
    When the configuration is loaded
    Then the log level should default to "INFO"
    And the memory store backend should default to "in_memory"
    And the supervisor model should default to the llama-swap alias

  # Why: Memory Store namespace scheme is load-bearing — pin the exact layout
  @boundary
  Scenario: Memory Store entries are namespaced by user, not by session
    Given the supervisor has written a fact during a session for user "rich"
    Then the fact should be stored under a namespace whose first segment is "user"
    And the second segment of the namespace should be the user_id
    And the namespace should contain no session_id segment

  # Why: end_session must be idempotent so adapter/CLI shutdown paths can call it unconditionally
  @boundary
  Scenario: end_session is idempotent
    Given a live session exists
    When end_session is called for that session_id
    And end_session is called again for the same session_id
    Then both calls should succeed
    And the session should be marked ended exactly once

  # Why: Empty-input turn is the smallest non-degenerate REPL input
  @boundary
  Scenario: An empty chat turn is handled without breaking the REPL
    Given Rich has started a chat session
    When Rich submits an empty line
    Then the REPL should continue accepting input
    And no supervisor invocation should be recorded for that empty turn

  # Why: Chat exit code on clean exit is the documented contract (0)
  @boundary
  Scenario: A chat session that receives no turns before EOF exits cleanly
    Given Rich has started a chat session
    When Rich sends end-of-input immediately
    Then the session should end
    And the process should exit with success
━━ GROUP C: Negative Cases (8 scenarios) ━━


  # Why: The default supervisor model points at llama-swap — missing base URL must fail loud
  @negative
  Scenario: Default supervisor model without OPENAI_BASE_URL fails with a clear configuration error
    Given the supervisor model is left at its default
    And OPENAI_BASE_URL is not set
    When jarvis health is run
    Then the command should fail with a configuration error
    And the error should name OPENAI_BASE_URL
    And the process should exit with the documented configuration-error code

  # Why: A cloud-provider-prefixed model must fail loud when its key is absent
  @negative
  Scenario Outline: A model that requires a provider key fails when the key is missing
    Given the supervisor model is set to "<model>"
    And "<env_var>" is not set
    When jarvis health is run
    Then the command should fail with a configuration error
    And the error should name "<env_var>"

    Examples:
      | model                         | env_var            |
      | anthropic:claude-haiku-4-5    | ANTHROPIC_API_KEY  |
      | google_genai:gemini-3-flash   | GOOGLE_API_KEY     |

  # Why: Malformed model strings must be rejected at config time, not at invoke time
  @negative
  Scenario: A supervisor model string with no provider prefix is rejected at config load
    Given JARVIS_SUPERVISOR_MODEL is set to "jarvis-reasoner"
    When the configuration is loaded
    Then configuration loading should fail with a validation error

  # Why: Phase 1 only implements in_memory; file and graphiti backends must refuse at startup
  @negative
  Scenario Outline: Unsupported memory store backends are refused at startup
    Given JARVIS_MEMORY_STORE_BACKEND is set to "<backend>"
    When lifecycle startup runs
    Then startup should fail with a configuration error
    And the error should indicate that the backend is not implemented in this phase

    Examples:
      | backend  |
      | file     |
      | graphiti |

  # Why: Unknown session id must fail loudly so future adapter code cannot silently drop turns
  @negative
  Scenario: Resuming an unknown session raises SessionNotFoundError
    When resume_session is called with an unknown session_id
    Then a SessionNotFoundError should be raised

  # Why: Secrets must never leak via repr, logs, or status output
  @negative
  Scenario: Rendering the configuration does not disclose provider secrets
    Given provider API keys are set to known sensitive values
    When the configuration is converted to a string or logged
    Then the sensitive values should not appear in the output
    And the keys should be masked

  # Why: Invalid log levels must fail at config load, not silently degrade to a default
  @negative
  Scenario: An invalid log level is rejected at configuration load
    Given JARVIS_LOG_LEVEL is set to "bogus"
    When the configuration is loaded
    Then configuration loading should fail with a validation error

  # Why: Provider errors during invoke must not kill the REPL — the conversation recovers
  @negative
  Scenario: A provider error during a chat turn is surfaced but the REPL continues
    Given Rich has started a chat session
    And the next supervisor invocation will raise a provider error
    When Rich submits a turn
    Then an error line prefixed with "[error]" should be printed
    And the REPL should continue accepting the next turn
    And the session should not be ended
━━ GROUP D: Edge Cases (5 scenarios) ━━


  # Why: SIGINT mid-chat must exit with 130 and still clean up the live session
  @edge-case
  Scenario: Pressing Ctrl-C during a chat session exits with 130 and cleans up the session
    Given Rich has started a chat session
    When a SIGINT signal is delivered to the process
    Then the session should be ended
    And a SessionEnded event should be emitted
    And the process should exit with code 130

  # Why: End-to-end smoke — the shell is structurally sound when mocked-LLM responses flow through the whole stack
  @edge-case @smoke
  Scenario: End-to-end smoke test — CLI input produces CLI output via a mocked supervisor
    Given the supervisor is configured with a canned response "Hello, Rich."
    When Rich runs "jarvis chat" and submits a single turn
    Then the canned response should be printed to stdout
    And the session should end cleanly on end-of-input

  # Why: Lifecycle ordering — logging must be configured before config validation so errors are traceable
  @edge-case
  Scenario: Startup configures logging before validating configuration
    Given an invalid configuration is about to be loaded
    When lifecycle startup runs
    Then structured logging should already be configured
    And the configuration failure should be emitted as a structured log event

  # Why: Jarvis restart is acceptable loss — live sessions do not persist across process boundaries (ADR-ARCH-008)
  @edge-case
  Scenario: A Jarvis restart invalidates live sessions
    Given a live session exists
    When the Jarvis process is restarted
    Then resuming the previous session_id in the new process should fail with SessionNotFoundError

  # Why: Module-boundary invariant — domain code must not import adapters or tools
  @edge-case @regression
  Scenario: Domain modules do not import from adapter or tool layers
    When the import graph of the jarvis.sessions package is inspected
    Then it should not import from jarvis.adapters
    And it should not import from jarvis.tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 28 scenarios across 4 groups (Group A: 8, Group B: 7, Group C: 8, Group D: 5)
Inferred assumptions: 6 (will be resolved in Phase 5 — all low/medium confidence)
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

GROUP A — Key Examples (8 scenarios): _
GROUP B — Boundary Conditions (7 scenarios): _
GROUP C — Negative Cases (8 scenarios): _
GROUP D — Edge Cases (5 scenarios): _

Awaiting your curation decisions. After Group curation, I'll offer the Phase 4 edge-case expansion (security/concurrency/integration boundaries) and then resolve the 6 inferred assumptions in Phase 5.

phase1-build-plan.md
A A A A
All four groups accepted. Proceeding to Phase 4.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've identified 7 additional scenarios covering security, concurrency, and integration boundaries specific to this scaffolding feature:

Security (3):

A .env file containing secrets is git-ignored and its values do not leak into the repr or logs
The structlog redaction processor strips *_key / *_token fields from log events even when a developer accidentally logs a config object
Memory Store entries written during a session for user "rich" are not readable when the supervisor invokes under a different user_id (namespace isolation)
Concurrency (2):

Two concurrent invoke calls on the same session are not supported in Phase 1 and the second call should fail or serialise explicitly (captures the single-threaded contract so FEAT-JARVIS-006 Telegram knows what to revisit)
A chat turn submitted while the previous turn is still being processed is serialised by the REPL (one turn at a time)
Integration boundaries (2):

When OPENAI_BASE_URL points at a llama-swap endpoint that is unreachable, jarvis chat surfaces the connection error as [error] without killing the REPL
The supervisor factory must not invoke the language model during build_supervisor (so jarvis health stays token-free even when the model endpoint is reachable)
Include them?

[Y] Yes — show and curate all 7 (same A/R/M/+/? actions)
[S] Sample — show 2 examples, then decide
[N] No — skip and proceed to Phase 5

Your choice [Y/S/N]:

Y
Here are the 7 additional scenarios in full Gherkin, organised by sub-category.

━━ GROUP E: Edge Case Expansion — Security (3 scenarios) ━━


  # Why: .env is the only secret-bearing file — git-ignoring it is the first line of defence
  @edge-case @security
  Scenario: The .env file is git-ignored
    Given the repository has a .gitignore
    Then ".env" should be listed as an ignored pattern
    And ".env.example" should be committed as a template

  # Why: The structlog redaction processor must catch accidental secret logging belt-and-braces with SecretStr
  @edge-case @security @regression
  Scenario: Structured log events redact provider-key and token fields
    Given structured logging has been configured
    And provider API keys are set to known sensitive values
    When a log event is emitted carrying the full configuration
    Then any field whose name ends in "_key" should be masked in the emitted event
    And any field whose name ends in "_token" should be masked in the emitted event
    And the sensitive values should not appear in the rendered log output

  # Why: Memory Store namespace isolation is what lets Phase 1 commit to a multi-user path without rework
  @edge-case @security
  Scenario: Memory Store entries written for one user are not recalled for another user
    Given the supervisor has written a fact during a session for user "rich"
    When the supervisor runs a new session for a different user_id
    And the supervisor attempts to recall that fact
    Then the fact should not be returned
━━ GROUP F: Edge Case Expansion — Concurrency (2 scenarios) ━━


  # Why: Single-threaded contract must be explicit so FEAT-JARVIS-006 Telegram knows what to revisit
  @edge-case @concurrency
  Scenario: The SessionManager does not support concurrent invokes on the same session in Phase 1
    Given Rich has started a chat session
    And an invoke call for that session is already in flight
    When a second invoke call is made for the same session before the first completes
    Then the second call should either serialise behind the first or be refused
    And the outcome should be documented as a Phase 1 constraint, not a silent race

  # Why: REPL-level serialisation protects the single-threaded contract at the user-facing boundary
  @edge-case @concurrency
  Scenario: Chat REPL serialises turns one at a time
    Given Rich has started a chat session
    When Rich submits a turn
    Then the REPL should not read the next line from standard input until the supervisor's reply for the current turn has been printed
━━ GROUP G: Edge Case Expansion — Integration boundaries (2 scenarios) ━━


  # Why: llama-swap is the single inference front door — its unavailability must degrade gracefully, not kill the shell
  @edge-case @integration
  Scenario: An unreachable llama-swap endpoint surfaces as an error in the REPL without ending the session
    Given the supervisor model is configured to reach llama-swap
    And the llama-swap endpoint is unreachable
    When Rich starts a chat session and submits a turn
    Then an error line prefixed with "[error]" should be printed
    And the REPL should continue accepting the next turn
    And the session should not be ended

  # Why: build_supervisor must be token-free so jarvis health is safe to run constantly during AutoBuild
  @edge-case @integration @regression
  Scenario: build_supervisor does not invoke the language model
    Given a valid configuration
    When build_supervisor is called
    Then no request should be issued to the configured model endpoint
    And the compiled supervisor graph should be returned successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each edge-case expansion sub-group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Actions per group: [A]ccept all / [R]eject all / [M]odify with inline change / [+] add more / [?] defer.

Fast path: type "A A A" to accept all three sub-groups.

GROUP E — Security (3 scenarios): _
GROUP F — Concurrency (2 scenarios): _
GROUP G — Integration boundaries (2 scenarios): _

A A A
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (6 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each assumption has a proposed default. Press Enter (or reply "accept") to accept, or type the actual value.

[1] Empty chat turn handling
Proposed: blank-line input is silently skipped — the REPL continues, no supervisor invocation, no event emitted
Confidence: medium
Basis: conventional REPL behaviour; not stated in API-cli.md §3.3
Accept or enter value: _

[2] /exit command matching semantics
Proposed: case-sensitive exact match for the literal "/exit" with leading/trailing whitespace trimmed (so "  /exit  " ends the session, but "/EXIT" is passed through as a chat turn)
Confidence: low
Basis: API-cli.md names "/exit" as an end-signal but does not specify case or whitespace handling
Accept or enter value: _

[3] Concurrent invoke on the same session
Proposed: the second concurrent call is refused with a clear error (not serialised silently) — documented as a Phase 1 constraint revisited at FEAT-JARVIS-006
Confidence: low
Basis: API-internal.md §4.2 says SessionManager is not thread-safe in Phase 1 but does not pick between serialise-behind vs. refuse
Accept or enter value: _

[4] Chat REPL turn serialisation
Proposed: the REPL does not read the next line from stdin until the current turn's reply has been printed
Confidence: medium
Basis: follows from the stated single-asyncio-loop contract but is not explicitly written in any contract
Accept or enter value: _

[5] Exit code when a pydantic ValidationError is raised at config load (malformed model string, bogus log level)
Proposed: exit code 1 — treated as a configuration error by the CLI, same as ConfigurationError
Confidence: medium
Basis: API-cli.md §3.2 documents exit 1 for ConfigurationError but is silent on pre-construction ValidationError; the user-visible failure mode is identical
Accept or enter value: _

[6] Refusal mechanism for non-CLI adapters in Phase 1
Proposed: SessionManager.start_session(adapter=Adapter.TELEGRAM, ...) raises JarvisError (wrapping the underlying assertion) with a message naming the adapter
Confidence: medium
Basis: DM-jarvis-reasoning.md §6 says "AssertionError → wrapped in JarvisError" but the spec consumer needs a user-visible exception type to key tests against
Accept or enter value: _
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Awaiting your resolution for each of the 6 items. Reply with a list (e.g. "1 accept, 2 accept, 3 refuse, 4 accept, 5 accept, 6 accept") or item-by-item.

accept defaults
All 6 assumptions confirmed. Writing output files now.

Write project-scaffolding-supervisor-sessions.feature
370 lines
# Generated by /feature-spec
# Feature: Project Scaffolding, Supervisor Skeleton & Session Lifecycle (FEAT-JARVIS-001)
# Stack: python (Python 3.12)
# Assumptions: 6 (see project-scaffolding-supervisor-sessions_assumptions.yaml)
# Generated: 2026-04-21T14:00:00Z

@feat-jarvis-001 @foundation
Feature: Project Scaffolding, Supervisor Skeleton & Session Lifecycle
  As Rich, the attended operator of the Jarvis fleet surface
  I want a runnable jarvis package, a buildable DeepAgents supervisor,
    a CLI that starts conversations, and cross-session fact recall
  So that I can have a useful conversation with Jarvis on day 1
    and every subsequent v1 feature lands on a stable scaffold

  Background:
    Given the jarvis package has been installed into a clean Python 3.12 environment
    And no sessions are currently live
    And the supervisor model is configured to return deterministic canned responses for tests

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP A — Key Examples
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Core day-1 success criterion — Rich can hold a conversation from the CLI
  @key-example @smoke
  Scenario: Rich starts a conversation and receives a supervisor response
    Given the required provider configuration is in place
    When Rich runs "jarvis chat"
    And Rich enters "Hi Jarvis"
    Then the session should start successfully
    And Rich should see the supervisor's reply

  # Why: A conversation must end cleanly on the documented exit signals
  # [ASSUMPTION: confidence=low] "/exit" matches case-sensitively with leading/trailing whitespace trimmed
  @key-example @smoke
  Scenario Outline: Rich ends a chat session cleanly
    Given Rich has started a chat session
    When Rich <end-signal>
    Then the session should end
    And a "session ended." banner should be shown
    And the process should exit with success

    Examples:
      | end-signal                |
      | types "/exit"             |
      | sends end-of-input (EOF)  |

  # Why: "version" is the smallest self-test for the installed package
  @key-example @smoke
  Scenario: Rich checks the installed jarvis version
    When Rich runs "jarvis version"
    Then the package version should be printed on a single line
    And the command should exit with success
    And no configuration should be loaded

  # Why: "health" is the wiring-debug primitive — validates config + builds the supervisor without spending tokens
  @key-example @smoke
  Scenario: Rich checks that the scaffold is healthy before a conversation
    Given the required provider configuration is in place
    When Rich runs "jarvis health"
    Then a status report should summarise the configuration
    And the report should indicate that the supervisor builds successfully
    And the report should indicate that the memory store is ready
    And the command should exit with success

  # Why: The day-1 cross-session recall criterion — Memory Store is keyed per user
  @key-example @smoke
  Scenario: A fact stated in one session is recalled in a later session for the same user
    Given Rich has had a chat session in which he stated "my DDD Southwest talk is on 16 May"
    And that session has ended
    When Rich starts a new chat session as the same user
    And Rich asks "when is my DDD talk?"
    Then the supervisor's reply should reference 16 May

  # Why: Running "jarvis" with no arguments should be discoverable (prints command list)
  @key-example
  Scenario: Running jarvis with no command prints the available commands
    When Rich runs "jarvis"
    Then the available commands should be listed
    And the command should exit with success

  # Why: Supervisor factory is the public contract consumed by every later feature
  @key-example
  Scenario: The supervisor factory produces a compiled graph with Phase 1 built-ins
    Given a valid configuration
    When build_supervisor is called with the configuration
    Then a compiled supervisor graph should be returned
    And the built-in tools "write_todos", virtual filesystem, and "task" should be enabled
    And the built-in tool "execute" should be disabled
    And no custom tools should be registered
    And no subagents should be registered

  # Why: Session identity is the stable primitive every later feature extends
  @key-example
  Scenario: Starting a session mints a new session with a stable identity
    When a CLI session is started for the user "rich"
    Then a Session object should be created
    And the session's thread_id should equal its session_id
    And the session's session_id should follow the documented adapter-prefixed pattern
    And a SessionStarted event should be emitted to the structured log

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP B — Boundary Conditions
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Just-inside boundary — two sessions started in quick succession must have distinct identity
  @boundary
  Scenario: Two successive session starts return distinct session identities
    When two CLI sessions are started for the same user
    Then the two session_ids should differ
    And the two thread_ids should differ
    And each session_id should match the documented adapter-prefixed pattern

  # Why: Just-outside boundary — adapter values other than CLI are reserved and must be refused in Phase 1
  # [ASSUMPTION: confidence=medium] The refusal surfaces as a JarvisError naming the adapter
  @boundary @negative
  Scenario Outline: Non-CLI adapters are refused until their adapter feature ships
    When a session start is attempted with adapter "<adapter>"
    Then the session start should be refused with a JarvisError
    And the error message should reference the adapter name

    Examples:
      | adapter   |
      | telegram  |
      | dashboard |
      | reachy    |

  # Why: Default configuration loads with no env overrides (zero-config happy path)
  @boundary
  Scenario: Default configuration loads with no environment overrides
    Given no JARVIS_ environment variables are set
    When the configuration is loaded
    Then the log level should default to "INFO"
    And the memory store backend should default to "in_memory"
    And the supervisor model should default to the llama-swap alias

  # Why: Memory Store namespace scheme is load-bearing — pin the exact layout
  @boundary
  Scenario: Memory Store entries are namespaced by user, not by session
    Given the supervisor has written a fact during a session for user "rich"
    Then the fact should be stored under a namespace whose first segment is "user"
    And the second segment of the namespace should be the user_id
    And the namespace should contain no session_id segment

  # Why: end_session must be idempotent so adapter/CLI shutdown paths can call it unconditionally
  @boundary
  Scenario: end_session is idempotent
    Given a live session exists
    When end_session is called for that session_id
    And end_session is called again for the same session_id
    Then both calls should succeed
    And the session should be marked ended exactly once

  # Why: Empty-input turn is the smallest non-degenerate REPL input
  # [ASSUMPTION: confidence=medium] A blank-line turn is silently skipped — no supervisor invocation, no event
  @boundary
  Scenario: An empty chat turn is handled without breaking the REPL
    Given Rich has started a chat session
    When Rich submits an empty line
    Then the REPL should continue accepting input
    And no supervisor invocation should be recorded for that empty turn

  # Why: Chat exit code on clean exit is the documented contract (0)
  @boundary
  Scenario: A chat session that receives no turns before EOF exits cleanly
    Given Rich has started a chat session
    When Rich sends end-of-input immediately
    Then the session should end
    And the process should exit with success

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP C — Negative Cases
  # ─────────────────────────────────────────────────────────────────────────

  # Why: The default supervisor model points at llama-swap — missing base URL must fail loud
  @negative
  Scenario: Default supervisor model without OPENAI_BASE_URL fails with a clear configuration error
    Given the supervisor model is left at its default
    And OPENAI_BASE_URL is not set
    When jarvis health is run
    Then the command should fail with a configuration error
    And the error should name OPENAI_BASE_URL
    And the process should exit with code 1

  # Why: A cloud-provider-prefixed model must fail loud when its key is absent
  @negative
  Scenario Outline: A model that requires a provider key fails when the key is missing
    Given the supervisor model is set to "<model>"
    And "<env_var>" is not set
    When jarvis health is run
    Then the command should fail with a configuration error
    And the error should name "<env_var>"
    And the process should exit with code 1

    Examples:
      | model                         | env_var            |
      | anthropic:claude-haiku-4-5    | ANTHROPIC_API_KEY  |
      | google_genai:gemini-3-flash   | GOOGLE_API_KEY     |

  # Why: Malformed model strings must be rejected at config time, not at invoke time
  # [ASSUMPTION: confidence=medium] Pydantic ValidationError at config load exits the CLI with code 1, same as ConfigurationError
  @negative
  Scenario: A supervisor model string with no provider prefix is rejected at config load
    Given JARVIS_SUPERVISOR_MODEL is set to "jarvis-reasoner"
    When the configuration is loaded
    Then configuration loading should fail with a validation error
    And the process should exit with code 1

  # Why: Phase 1 only implements in_memory; file and graphiti backends must refuse at startup
  @negative
  Scenario Outline: Unsupported memory store backends are refused at startup
    Given JARVIS_MEMORY_STORE_BACKEND is set to "<backend>"
    When lifecycle startup runs
    Then startup should fail with a configuration error
    And the error should indicate that the backend is not implemented in this phase

    Examples:
      | backend  |
      | file     |
      | graphiti |

  # Why: Unknown session id must fail loudly so future adapter code cannot silently drop turns
  @negative
  Scenario: Resuming an unknown session raises SessionNotFoundError
    When resume_session is called with an unknown session_id
    Then a SessionNotFoundError should be raised

  # Why: Secrets must never leak via repr, logs, or status output
  @negative
  Scenario: Rendering the configuration does not disclose provider secrets
    Given provider API keys are set to known sensitive values
    When the configuration is converted to a string or logged
    Then the sensitive values should not appear in the output
    And the keys should be masked

  # Why: Invalid log levels must fail at config load, not silently degrade to a default
  # [ASSUMPTION: confidence=medium] Pydantic ValidationError at config load exits the CLI with code 1, same as ConfigurationError
  @negative
  Scenario: An invalid log level is rejected at configuration load
    Given JARVIS_LOG_LEVEL is set to "bogus"
    When the configuration is loaded
    Then configuration loading should fail with a validation error
    And the process should exit with code 1

  # Why: Provider errors during invoke must not kill the REPL — the conversation recovers
  @negative
  Scenario: A provider error during a chat turn is surfaced but the REPL continues
    Given Rich has started a chat session
    And the next supervisor invocation will raise a provider error
    When Rich submits a turn
    Then an error line prefixed with "[error]" should be printed
    And the REPL should continue accepting the next turn
    And the session should not be ended

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP D — Edge Cases
  # ─────────────────────────────────────────────────────────────────────────

  # Why: SIGINT mid-chat must exit with 130 and still clean up the live session
  @edge-case
  Scenario: Pressing Ctrl-C during a chat session exits with 130 and cleans up the session
    Given Rich has started a chat session
    When a SIGINT signal is delivered to the process
    Then the session should be ended
    And a SessionEnded event should be emitted
    And the process should exit with code 130

  # Why: End-to-end smoke — the shell is structurally sound when mocked-LLM responses flow through the whole stack
  @edge-case @smoke
  Scenario: End-to-end smoke test — CLI input produces CLI output via a mocked supervisor
    Given the supervisor is configured with a canned response "Hello, Rich."
    When Rich runs "jarvis chat" and submits a single turn
    Then the canned response should be printed to stdout
    And the session should end cleanly on end-of-input

  # Why: Lifecycle ordering — logging must be configured before config validation so errors are traceable
  @edge-case
  Scenario: Startup configures logging before validating configuration
    Given an invalid configuration is about to be loaded
    When lifecycle startup runs
    Then structured logging should already be configured
    And the configuration failure should be emitted as a structured log event

  # Why: Jarvis restart is acceptable loss — live sessions do not persist across process boundaries (ADR-ARCH-008)
  @edge-case
  Scenario: A Jarvis restart invalidates live sessions
    Given a live session exists
    When the Jarvis process is restarted
    Then resuming the previous session_id in the new process should fail with SessionNotFoundError

  # Why: Module-boundary invariant — domain code must not import adapters or tools
  @edge-case @regression
  Scenario: Domain modules do not import from adapter or tool layers
    When the import graph of the jarvis.sessions package is inspected
    Then it should not import from jarvis.adapters
    And it should not import from jarvis.tools

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP E — Edge Case Expansion: Security
  # ─────────────────────────────────────────────────────────────────────────

  # Why: .env is the only secret-bearing file — git-ignoring it is the first line of defence
  @edge-case @security
  Scenario: The .env file is git-ignored
    Given the repository has a .gitignore
    Then ".env" should be listed as an ignored pattern
    And ".env.example" should be committed as a template

  # Why: The structlog redaction processor must catch accidental secret logging belt-and-braces with SecretStr
  @edge-case @security @regression
  Scenario: Structured log events redact provider-key and token fields
    Given structured logging has been configured
    And provider API keys are set to known sensitive values
    When a log event is emitted carrying the full configuration
    Then any field whose name ends in "_key" should be masked in the emitted event
    And any field whose name ends in "_token" should be masked in the emitted event
    And the sensitive values should not appear in the rendered log output

  # Why: Memory Store namespace isolation is what lets Phase 1 commit to a multi-user path without rework
  @edge-case @security
  Scenario: Memory Store entries written for one user are not recalled for another user
    Given the supervisor has written a fact during a session for user "rich"
    When the supervisor runs a new session for a different user_id
    And the supervisor attempts to recall that fact
    Then the fact should not be returned

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP F — Edge Case Expansion: Concurrency
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Single-threaded contract must be explicit so FEAT-JARVIS-006 Telegram knows what to revisit
  # [ASSUMPTION: confidence=low] A second concurrent invoke on the same session is refused with an error rather than silently serialised
  @edge-case @concurrency
  Scenario: The SessionManager does not support concurrent invokes on the same session in Phase 1
    Given Rich has started a chat session
    And an invoke call for that session is already in flight
    When a second invoke call is made for the same session before the first completes
    Then the second call should be refused with a clear error
    And the outcome should be documented as a Phase 1 constraint, not a silent race

  # Why: REPL-level serialisation protects the single-threaded contract at the user-facing boundary
  # [ASSUMPTION: confidence=medium] The REPL reads the next line only after the prior reply has been printed
  @edge-case @concurrency
  Scenario: Chat REPL serialises turns one at a time
    Given Rich has started a chat session
    When Rich submits a turn
    Then the REPL should not read the next line from standard input until the supervisor's reply for the current turn has been printed

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP G — Edge Case Expansion: Integration Boundaries
  # ─────────────────────────────────────────────────────────────────────────

  # Why: llama-swap is the single inference front door — its unavailability must degrade gracefully, not kill the shell
  @edge-case @integration
  Scenario: An unreachable llama-swap endpoint surfaces as an error in the REPL without ending the session
    Given the supervisor model is configured to reach llama-swap
    And the llama-swap endpoint is unreachable
    When Rich starts a chat session and submits a turn
    Then an error line prefixed with "[error]" should be printed
    And the REPL should continue accepting the next turn
    And the session should not be ended

  # Why: build_supervisor must be token-free so jarvis health is safe to run constantly during AutoBuild
  @edge-case @integration @regression
  Scenario: build_supervisor does not invoke the language model
    Given a valid configuration
    When build_supervisor is called
    Then no request should be issued to the configured model endpoint
    And the compiled supervisor graph should be returned successfully
Write project-scaffolding-supervisor-sessions_assumptions.yaml
52 lines
# Assumptions manifest for project-scaffolding-supervisor-sessions.feature
# Generated by /feature-spec

feature: "Project Scaffolding, Supervisor Skeleton & Session Lifecycle"
feature_id: "FEAT-JARVIS-001"
generated: "2026-04-21T14:00:00Z"
stack: "python"
review_required: true

assumptions:
  - id: "ASSUM-001"
    scenario: "An empty chat turn is handled without breaking the REPL"
    assumption: "Blank-line input is silently skipped — the REPL continues, no supervisor invocation, no event emitted"
    confidence: medium
    basis: "Conventional REPL behaviour; not stated in API-cli.md §3.3"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Rich ends a chat session cleanly"
    assumption: "\"/exit\" matches case-sensitively against the literal lowercase string with leading/trailing whitespace trimmed (so \"  /exit  \" ends the session, but \"/EXIT\" is passed through as a chat turn)"
    confidence: low
    basis: "API-cli.md §3.3 names \"/exit\" as an end-signal but does not specify case sensitivity or whitespace handling"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "The SessionManager does not support concurrent invokes on the same session in Phase 1"
    assumption: "A second concurrent invoke on the same session is refused with a clear error rather than silently serialised behind the first"
    confidence: low
    basis: "API-internal.md §4.2 states SessionManager is not thread-safe in Phase 1 but does not pick between serialise-behind and refuse"
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "Chat REPL serialises turns one at a time"
    assumption: "The REPL does not read the next line from standard input until the current turn's reply has been printed"
    confidence: medium
    basis: "Follows from the stated single-asyncio-loop contract but is not explicitly written in any contract"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "A supervisor model string with no provider prefix is rejected at config load / An invalid log level is rejected at configuration load"
    assumption: "A pydantic ValidationError raised at config load causes the CLI to exit with code 1, the same exit code documented for ConfigurationError"
    confidence: medium
    basis: "API-cli.md §3.2 documents exit code 1 for ConfigurationError but is silent on pre-construction pydantic ValidationError; the user-visible failure mode is identical"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "Non-CLI adapters are refused until their adapter feature ships"
    assumption: "SessionManager.start_session refuses a non-CLI adapter by raising JarvisError (wrapping the underlying assertion) with a message naming the adapter"
    confidence: medium
    basis: "DM-jarvis-reasoning.md §6 says \"AssertionError → wrapped in JarvisError\" but the spec consumer needs a user-visible exception type to key tests against"
    human_response: "confirmed"
Write project-scaffolding-supervisor-sessions_summary.md
61 lines
# Feature Spec Summary: Project Scaffolding, Supervisor Skeleton & Session Lifecycle

**Feature ID**: FEAT-JARVIS-001
**Stack**: python (Python 3.12 + DeepAgents >=0.5.3,<0.6)
**Generated**: 2026-04-21T14:00:00Z
**Scenarios**: 35 total (6 @smoke, 3 @regression)
**Assumptions**: 6 total (0 high / 4 medium / 2 low confidence)
**Review required**: Yes

## Scope

The Phase 1 foundation feature: a runnable Python scaffold (`pyproject.toml` with the `deepagents>=0.5.3,<0.6` pin plus the five-group `src/jarvis/` layer structure), a `build_supervisor(config)` factory that returns a DeepAgents `CompiledStateGraph` with built-ins only, a thread-per-session `SessionManager` with a user-keyed LangGraph Memory Store, and a `jarvis` CLI exposing exactly three commands (`chat`, `version`, `health`). The specification pins the day-1 success criterion — Rich can hold a useful conversation on the CLI, and a fact stated in one session is recalled in a later session for the same user.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 8 |
| Boundary conditions (@boundary) | 7 |
| Negative cases (@negative) | 8 |
| Edge cases (@edge-case) | 12 |
| — of which @security | 3 |
| — of which @concurrency | 2 |
| — of which @integration | 2 |
| Smoke (@smoke) | 6 |
| Regression (@regression) | 3 |

## Deferred Items

None. All four initial groups and all three edge-case-expansion sub-groups were accepted without deferral.

## Open Assumptions (low confidence)

Two low-confidence assumptions require human verification before AutoBuild:

- **ASSUM-002** — `/exit` command matching semantics (case sensitivity + whitespace trimming). *Proposed*: case-sensitive exact match for lowercase "/exit", with leading/trailing whitespace trimmed. Not stated in the API contract.
- **ASSUM-003** — Concurrent `invoke` on the same session. *Proposed*: refuse the second call with a clear error, rather than silently serialise. `SessionManager` is documented as not thread-safe in Phase 1, but the exact refusal vs. serialisation behaviour was not pinned.

Four further assumptions are medium-confidence (ASSUM-001, 004, 005, 006) and should be reviewed by the Coach before AutoBuild lands the corresponding scenarios, but do not gate the specification.

## Cross-references

- Design: [docs/design/FEAT-JARVIS-001/design.md](../../docs/design/FEAT-JARVIS-001/design.md)
- CLI contract: [docs/design/FEAT-JARVIS-001/contracts/API-cli.md](../../docs/design/FEAT-JARVIS-001/contracts/API-cli.md)
- Internal API contract: [docs/design/FEAT-JARVIS-001/contracts/API-internal.md](../../docs/design/FEAT-JARVIS-001/contracts/API-internal.md)
- Session data model: [docs/design/FEAT-JARVIS-001/models/DM-jarvis-reasoning.md](../../docs/design/FEAT-JARVIS-001/models/DM-jarvis-reasoning.md)
- Config data model: [docs/design/FEAT-JARVIS-001/models/DM-config.md](../../docs/design/FEAT-JARVIS-001/models/DM-config.md)
- Key ADRs: ADR-ARCH-002 (clean/hexagonal in DeepAgents supervisor), ADR-ARCH-006 (five-group module layout), ADR-ARCH-009 (thread-per-session + Memory Store), ADR-ARCH-010 (Python 3.12 + DeepAgents pin), ADR-ARCH-020 (trace-richness by default), ADR-ARCH-021 (tools return structured errors)
- Design DDRs: DDR-001 (in-process only), DDR-002 (Memory Store keyed by user_id), DDR-003 (CLI minimal surface), DDR-004 (session/thread 1:1)

## Integration with /feature-plan

This summary is the primary context for the next step in the build plan:

    /feature-plan "Project Scaffolding, Supervisor Skeleton & Session Lifecycle" \
      --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md \
      --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature \
      --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml \
      --context docs/design/FEAT-JARVIS-001/design.md \
      --context docs/research/ideas/phase1-build-plan.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Project Scaffolding, Supervisor Skeleton & Session Lifecycle
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml
features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md

Scenarios: 35 total
@key-example: 8   @boundary: 7
@negative: 8      @edge-case: 12
@smoke: 6         @regression: 3
@security: 3      @concurrency: 2   @integration: 2

Assumptions: 6 total
high: 0
medium: 4 (ASSUM-001, 004, 005, 006 — Coach review recommended)
low: 2 (ASSUM-002, 003 — human review required)

REVIEW REQUIRED: 2 low-confidence assumptions need verification
See: features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml

ASSUM-002: "/exit" case/whitespace handling — not pinned in any contract
ASSUM-003: Concurrent invoke on same session — refuse vs. serialise not pinned
Deferred: 0 scenario groups

Next steps:

Review low-confidence assumptions (ASSUM-002, 003) — either confirm now or leave for the Coach gate at /task-review
Run Step 4 of the Phase 1 build plan:

/feature-plan "Project Scaffolding, Supervisor Skeleton & Session Lifecycle" \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/research/ideas/phase1-build-plan.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

lets review ASSUM-002, 003 - I was happy with the reccomendations
Recording your explicit re-confirmation of ASSUM-002 and ASSUM-003. The confidence levels stay low (they describe the strength of the basis, not your agreement), but the REVIEW REQUIRED gate is satisfied since you are the reviewer and have now explicitly signed off.

Edit project-scaffolding-supervisor-sessions_assumptions.yaml
Added 1 line
Edit project-scaffolding-supervisor-sessions_assumptions.yaml
Modified
Edit project-scaffolding-supervisor-sessions_assumptions.yaml
Modified
Edit project-scaffolding-supervisor-sessions_summary.md
Modified
Edit project-scaffolding-supervisor-sessions_summary.md
Modified
ASSUM-002 and ASSUM-003 are now signed off. Summary updated: review_required: false, both items marked as explicitly re-reviewed. The spec is now clear to feed into /feature-plan FEAT-JARVIS-001 without a human gate.

please update the build plan with the status and decisions
Read phase1-build-plan.md (lines 13-42)
Read phase1-build-plan.md (lines 2-12)
Read phase1-build-plan.md (lines 403-452)
Read phase1-build-plan.md (lines 586-605)
Edit phase1-build-plan.md
Modified
Edit phase1-build-plan.md
Added 2 lines
Edit phase1-build-plan.md
Modified
Edit phase1-build-plan.md
Added 6 lines
Edit phase1-build-plan.md
Modified
Build plan updated. Summary of changes to phase1-build-plan.md:

Header Status line — Step 3 marked complete; Next pointer advanced to Step 4.
Status Log — two new rows added: one recording /feature-spec completion (feature folder, scenario counts, assumption outcomes, skipped context paths), one recording the six Phase-5 assumption resolutions as load-bearing design decisions for AutoBuild.
Step 3 section — changed from ⬅ NEXT to ✅ COMPLETE (21 April 2026) with actual deliverables noted.
Step 4 section — now carries ⬅ NEXT; the invocation block updated to use the real feature folder (features/project-scaffolding-supervisor-sessions/) and the actual ADR-ARCH-* ADR paths. Added a line instructing the plan step to honour the six pinned assumption-resolved behaviours.
Expected Timeline — Day 1 row now covers Steps 1–3 (all landed same day); Day 2 promoted from "Step 3" to "Step 4"; Day 3 advanced accordingly. Target still 3–4 working days, now tracking ahead of schedule.  