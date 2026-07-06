"""Jarvis configuration model — pydantic-settings ``BaseSettings`` subclass.

Provides :class:`JarvisConfig` which reads environment variables with the
``JARVIS_`` prefix and validates provider-specific API keys at runtime.

Default supervisor model routes through llama-swap on the local GB10
(ADR-ARCH-001 — local-first inference).

This module belongs to Group E (cross-cutting) per ADR-ARCH-006.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jarvis.shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider-key requirements keyed by the provider prefix in supervisor_model.
# Each entry maps to (field_name, env_var_name) so error messages name the
# exact environment variable the operator needs to set.
#
# ADR-ARCH-001: the ``openai:`` provider is intentionally absent. The
# supervisor always routes through llama-swap on the GB10 (or its
# Tailscale-reachable equivalent) and that endpoint is governed by
# ``llama_swap_base_url``, which has a hard-coded default — no operator
# action is required to satisfy the ``openai:`` provider, so there is
# nothing to validate. Cloud OpenAI is NOT a supported supervisor target.
# ---------------------------------------------------------------------------
_PROVIDER_KEY_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "anthropic": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    "google_genai": ("google_api_key", "GOOGLE_API_KEY"),
}


class JarvisConfig(BaseSettings):
    """Application configuration loaded from environment / ``.env`` file.

    Fields use the ``JARVIS_`` prefix so ``JARVIS_LOG_LEVEL=DEBUG`` maps to
    ``log_level``.  Provider API keys are stored as :class:`SecretStr` to
    prevent accidental leakage in logs or ``repr()`` output.
    """

    # -- Application settings ------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    supervisor_model: str = "openai:jarvis-reasoner"
    memory_store_backend: Literal["in_memory", "file"] = "in_memory"
    data_dir: Path = Path.home() / ".jarvis"

    # -- Provider API keys (SecretStr for masking) ---------------------------
    # NOTE: there is intentionally no ``openai_base_url`` field. The supervisor
    # always routes through llama-swap (ADR-ARCH-001 — local-first inference);
    # the active endpoint is ``llama_swap_base_url`` below. Cloud OpenAI is
    # NOT a supported supervisor target — see TASK-FRR-002.
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # -- Phase 2: web search + workspace settings ----------------------------
    web_search_provider: Literal["tavily", "none"] = "tavily"
    # The langchain-tavily SDK natively reads `TAVILY_API_KEY`, so we honour
    # the un-prefixed variable as well as the `JARVIS_TAVILY_API_KEY` form —
    # same precedent as `gemini_api_key` (GOOGLE_API_KEY / JARVIS_GEMINI_API_KEY).
    # TASK-REV-RM01: without this alias the bare `.env` line was silently
    # ignored and `search_web` returned `ERROR: config_missing` at runtime.
    tavily_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("TAVILY_API_KEY", "JARVIS_TAVILY_API_KEY"),
    )
    stub_capabilities_path: Path = Path("src/jarvis/config/stub_capabilities.yaml")
    workspace_root: Path = Path(".").resolve()

    # -- FEAT-JARVIS-003: routing + frontier-escape settings -----------------
    # llama-swap base URL on the local GB10 (ADR-ARCH-012). Picked up from
    # JARVIS_LLAMA_SWAP_BASE_URL via the env_prefix below.
    llama_swap_base_url: str = "http://promaxgb10-41b1:9000"

    # Default target model for `escalate_to_frontier` (ADR-ARCH-027).
    # Closed enum — adding a new target requires a DDR.
    frontier_default_target: Literal["GEMINI_3_1_PRO", "OPUS_4_7"] = "GEMINI_3_1_PRO"

    # Frontier provider key for the Gemini path of `escalate_to_frontier`.
    # The Google GenAI SDK natively reads `GOOGLE_API_KEY`, so we honour the
    # un-prefixed variable as well as the `JARVIS_GEMINI_API_KEY` form.
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "JARVIS_GEMINI_API_KEY"),
    )

    # Adapter IDs that count as "attended" consumer surfaces — the
    # constitutional gate on `escalate_to_frontier` checks membership here
    # (ADR-ARCH-016 consumer-surface list).
    attended_adapter_ids: frozenset[str] = frozenset({"telegram", "cli", "dashboard", "reachy"})

    # -- FEAT-JARVIS-004: NATS / fleet / dispatch / memory settings ----------
    # See docs/design/FEAT-JARVIS-004/contracts/API-internal.md §8 for the
    # authoritative field list. This module remains dependency-free — no
    # ``nats-py`` import lives here; the typed Python APIs that consume these
    # values live under ``src/jarvis/infrastructure``.

    # ── NATS ────────────────────────────────────────────
    # JARVIS_NATS_URL — NATS broker endpoint. Default is the in-process
    # localhost broker used by the integration test pattern.
    nats_url: str = "nats://localhost:4222"
    # JARVIS_NATS_CREDENTIALS_PATH — optional path to a NATS .creds file.
    # ``None`` means "anonymous / dev broker"; production deployments set
    # this to the operator-provisioned credentials file.
    nats_credentials_path: Path | None = None
    # JARVIS_NATS_USER / JARVIS_NATS_PASSWORD — optional username + password
    # for user/password NATS accounts (the fleet broker's auth model, as
    # distinct from NKey ``.creds`` files). When both are set to non-blank
    # values (and no ``.creds`` file is configured) they are forwarded to the
    # connect call by the supervisor's ``NATSClient.connect`` AND the
    # fleet-memory publisher's ``build_nats_client`` — so operators no longer
    # need to embed the password inline in ``nats_url``
    # (``nats://user:pass@host``). Resolution is centralised in
    # :meth:`resolve_nats_user_password` so both surfaces behave identically:
    # a lone half, a blank placeholder, or coexistence with
    # ``nats_credentials_path`` all fall back to the URL / creds-file / anon
    # auth path rather than forwarding a broken pair. ``SecretStr`` masks the
    # password in logs and ``repr()``.
    nats_user: str | None = None
    nats_password: SecretStr | None = None
    # JARVIS_HEARTBEAT_INTERVAL_SECONDS — fleet heartbeat cadence per
    # DDR-021/heartbeat. Constrained to 5..300 seconds.
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=300)
    # JARVIS_STARTUP_CONNECT_TIMEOUT_SECONDS — bounded wait for the initial
    # NATS connect at process boot per TASK-J006-010 (hard-dependency
    # posture per runbook §3.8 / AC-005-08). Once connected, steady-state
    # reconnect uses nats-py's default loop unchanged. Constrained to
    # 1..60 seconds; default 10s matches the runbook AC.
    startup_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # ── Fleet-memory (routing-history writes) ───────────
    # Jarvis publishes routing-history telemetry to the fleet-memory store as
    # ``document`` episodes over NATS (FEAT-MEM-09 cutover off Graphiti). The
    # write path reuses the NATS endpoint + credentials above; no separate
    # memory NATS identity is required. See
    # ``src/jarvis/infrastructure/fleet_memory/``.
    #
    # JARVIS_FLEET_MEMORY_ENABLED — master switch for the memory write path.
    # ``False`` (default) triggers the DDR-019 soft-fail: routing-history
    # entries are offloaded to ``jarvis_traces_dir`` instead of published, and
    # the supervisor stays up. Accepts the fleet-wide un-prefixed
    # ``FLEET_MEMORY_ENABLED`` as well as the ``JARVIS_``-prefixed form.
    fleet_memory_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "FLEET_MEMORY_ENABLED",
            "JARVIS_FLEET_MEMORY_ENABLED",
            "fleet_memory_enabled",
        ),
    )
    # JARVIS_FLEET_MEMORY_PROJECT — the fleet-memory project namespace this
    # Jarvis instance writes under (``memory.episode.{project}.{type}`` subject
    # + the ``project`` component of every natural key). Accepts the un-prefixed
    # ``FLEET_MEMORY_PROJECT`` for fleet-wide consistency.
    fleet_memory_project: str = Field(
        default="jarvis",
        validation_alias=AliasChoices(
            "FLEET_MEMORY_PROJECT",
            "JARVIS_FLEET_MEMORY_PROJECT",
            "fleet_memory_project",
        ),
    )
    # JARVIS_TRACES_DIR — local directory for offloaded routing-history
    # payloads when the memory write path soft-fails (disabled or unreachable).
    # Bound via ``validation_alias`` so the friendlier ``JARVIS_TRACES_DIR`` env
    # name resolves to this field instead of the double-prefixed
    # ``JARVIS_JARVIS_TRACES_DIR`` form the env_prefix would otherwise produce.
    jarvis_traces_dir: Path = Field(
        default=Path.home() / ".jarvis" / "traces",
        validation_alias=AliasChoices(
            "JARVIS_TRACES_DIR",
            "jarvis_traces_dir",
        ),
    )

    # ── Dispatch ────────────────────────────────────────
    # JARVIS_SPECIALIST_DISPATCH_TIMEOUT_SECONDS — per-call timeout for
    # specialist dispatch per DDR-016. Constrained to 5..600 seconds.
    specialist_dispatch_timeout_seconds: int = Field(default=60, ge=5, le=600)
    # JARVIS_DISPATCH_CONCURRENT_CAP — concurrent dispatch cap per DDR-020.
    # Constrained to 1..64.
    dispatch_concurrent_cap: int = Field(default=8, ge=1, le=64)

    # ── Fleet ───────────────────────────────────────────
    # JARVIS_AGENT_VERSION — semver string emitted on heartbeat /
    # registration frames. Tracks the FEAT-JARVIS-004 release. Bound via
    # ``validation_alias`` so the friendlier ``JARVIS_AGENT_VERSION`` env
    # name resolves here instead of the double-prefixed
    # ``JARVIS_JARVIS_AGENT_VERSION`` form.
    jarvis_agent_version: str = Field(
        default="0.4.0",
        pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$",
        validation_alias=AliasChoices(
            "JARVIS_AGENT_VERSION",
            "jarvis_agent_version",
        ),
    )

    # -- FEAT-JARVIS-005: pipeline + forge subscriber settings ---------------
    # See docs/design/FEAT-JARVIS-005/design.md §7 for the authoritative
    # field list. Declarative-only — TASK-J005-005 (`queue_build`),
    # TASK-J005-003 (subscriber), and TASK-J005-008 (lifecycle) consume
    # these values. No new module imports introduced by this task.

    # JARVIS_PIPELINE_PUBLISH_TIMEOUT_SECONDS — per-publish timeout for the
    # pipeline `queue_build` path. Default 5s per DDR-025.
    pipeline_publish_timeout_seconds: int = Field(
        default=5,
        description=(
            "Per-publish timeout (seconds) for the pipeline queue_build path. "
            "DDR-025 — see docs/design/FEAT-JARVIS-005/design.md §7."
        ),
    )

    # JARVIS_FORGE_NOTIFICATIONS_QUEUE_CAP — per-session bound on the CLI
    # forge-notifications queue. Default 100 entries per DDR-030.
    forge_notifications_queue_cap: int = Field(
        default=100,
        description=(
            "Per-session cap for the CLI forge-notifications queue. "
            "DDR-030 — see docs/design/FEAT-JARVIS-005/design.md §7."
        ),
    )

    # JARVIS_FORGE_CORRELATION_MAP_CAP — bound on the LRU correlation map
    # used by the forge-event subscriber. Default 1000 entries per DDR-028.
    forge_correlation_map_cap: int = Field(
        default=1000,
        description=(
            "Cap for the LRU correlation map in the forge-event subscriber. "
            "DDR-028 — see docs/design/FEAT-JARVIS-005/design.md §7."
        ),
    )

    # -- FEAT-28FF: Slack notification settings (TASK-JNB-001) --------------
    # JARVIS_SLACK_BOT_TOKEN — Slack bot token for posting notifications.
    # None triggers no-op sink (no network calls). SecretStr masks in logs.
    slack_bot_token: SecretStr | None = None

    # JARVIS_SLACK_CHANNEL_ID — Slack channel ID for notification delivery.
    # None triggers no-op sink alongside slack_bot_token.
    slack_channel_id: str | None = None

    # -- FEAT-BF39: Slack approval reply-path settings (TASK-JNB-103) -------
    # JARVIS_SLACK_APP_TOKEN — Slack app-level token (xapp-...) for the
    # Socket Mode reply path (TASK-JNB-104). None keeps the reply path a
    # logged no-op. SecretStr masks in logs.
    slack_app_token: SecretStr | None = None

    # JARVIS_SLACK_OPERATOR_USER_IDS — comma-separated allowlist of Slack
    # member ids permitted to click Approve/Reject (TASK-JNB-110). This is the
    # AUTHORIZATION gate ("who MAY decide"); it is deliberately separate from
    # IDENTITY ("who DID decide"), which is now the clicker's own member id
    # published verbatim as ``decided_by`` — never a config constant. Empty /
    # unset keeps the reply path a logged no-op. Resolution (merging the
    # DEPRECATED singular below, blank-stripping) lives in
    # :meth:`resolve_operator_allowlist` so every caller sees one allowlist.
    slack_operator_user_ids: str | None = None

    # JARVIS_SLACK_OPERATOR_USER_ID — DEPRECATED (TASK-JNB-110) singular
    # predecessor of ``slack_operator_user_ids``. Still honoured (folded into
    # the allowlist as a single entry) so existing deployments keep working;
    # ``create_slack_reply_client`` logs a deprecation notice when it is set.
    # Prefer the plural ``JARVIS_SLACK_OPERATOR_USER_IDS``.
    slack_operator_user_id: str | None = None

    # JARVIS_SLACK_DECIDED_BY — DEPRECATED and IGNORED (TASK-JNB-110). Under
    # the fleet-wide member-id identity scheme, ``decided_by`` is a factual
    # claim about who clicked (the interaction payload's user id), NOT a config
    # constant, so this field no longer feeds the published response. It is
    # retained only so a stale environment value does not raise on load;
    # ``create_slack_reply_client`` emits a deprecation WARNING when it is set.
    # Forge's build-gate ``approval.expected_approver`` must now be set to the
    # approver's Slack member id (config-only forge change — see TASK-JNB-110).
    slack_decided_by: str | None = None

    # -- FEAT-SPL-001: Slack planning intake settings (TASK-SPL-J01) --------
    # JARVIS_SLACK_PLANNING_CHANNEL_ID — the dedicated planning channel id
    # (SPL scope §5: #factory-planning). None keeps planning intake a logged
    # no-op; unset planning keys never affect the approval reply path
    # (TASK-REV-3240 F1 union-gate contract).
    slack_planning_channel_id: str | None = None

    # JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID — Slack member id(s) authorized
    # to originate planning requests. Comma-separated allow-list-ready
    # (ASSUM-001 hedge); v1 is documented and operated as a single id (James
    # for the exemplar). None keeps planning intake a logged no-op.
    slack_planning_originator_user_id: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # populate_by_name=True is required so fields that declare
        # `validation_alias` (e.g. `gemini_api_key` → `GOOGLE_API_KEY`)
        # remain assignable by their Python field name in tests and
        # programmatic construction. Without this, the alias replaces the
        # field name as the only accepted input key.
        populate_by_name=True,
    )

    # -- Validators ----------------------------------------------------------

    @field_validator("supervisor_model")
    @classmethod
    def _supervisor_model_must_have_provider_prefix(cls, value: str) -> str:
        """Reject bare model names — require ``provider:model`` format.

        Raises :class:`~pydantic.ValidationError` when the value does not
        contain a colon with non-empty segments on both sides.
        """
        if ":" not in value:
            msg = (
                "supervisor_model must use 'provider:model' format "
                f"(e.g. 'openai:gpt-4'), got {value!r}"
            )
            raise ValueError(msg)

        provider, model_name = value.split(":", 1)
        if not provider or not model_name:
            msg = f"supervisor_model must have non-empty provider and model name, got {value!r}"
            raise ValueError(msg)

        return value

    # -- NATS auth resolution ------------------------------------------------

    def resolve_nats_user_password(self) -> tuple[str, str] | None:
        """Resolve the NATS ``(user, password)`` pair to forward, or ``None``.

        The single source of truth for user/password auth, called by BOTH the
        supervisor's ``NATSClient.connect`` and the fleet-memory
        ``build_nats_client`` so the two connect surfaces cannot diverge.
        Returns the plaintext pair **only** when both ``nats_user`` and
        ``nats_password`` are set to non-empty values and no ``.creds`` file is
        configured; otherwise returns ``None`` so callers omit the pair
        entirely. Three edge cases this gate exists to absorb — each would
        otherwise break a connection or (on the publisher) raise and silently
        fail-open every routing-history write:

        * **Lone half** (only user, or only password) — ``nats_core.NATSConfig``
          rejects a half-pair with ``ValueError`` ("user and password must be
          provided together"). Returning ``None`` keeps URL / anonymous auth
          authoritative on both surfaces.
        * **Blank placeholders** — ``JARVIS_NATS_USER=`` / ``JARVIS_NATS_PASSWORD=``
          (or a templating tool emitting a bare ``KEY=``) coerce to ``""`` /
          ``SecretStr("")``, which are non-``None``; forwarding them would
          clobber working URL-embedded creds with empty credentials.
        * **``.creds`` file present** — ``NATSConfig`` treats password auth and
          a creds file as mutually exclusive, so an explicitly configured
          ``nats_credentials_path`` wins and the user/password pair is dropped.
        """
        if self.nats_credentials_path is not None:
            return None
        user = self.nats_user
        password = self.nats_password.get_secret_value() if self.nats_password is not None else None
        if not user or not password:
            return None
        return user, password

    # -- Slack operator allowlist resolution ---------------------------------

    def resolve_operator_allowlist(self) -> frozenset[str]:
        """Resolve the set of Slack member ids permitted to decide approvals.

        The single source of truth for the reply-path AUTHORIZATION gate
        (TASK-JNB-110). Merges the canonical comma-separated
        ``slack_operator_user_ids`` with the DEPRECATED singular
        ``slack_operator_user_id`` (folded in as one entry) so both surfaces
        keep working during migration. Blank / whitespace-only entries are
        dropped, so ``JARVIS_SLACK_OPERATOR_USER_IDS=`` or a stray trailing
        comma cannot smuggle an empty id into the allowlist (an empty id would
        never match a real click and would blur the no-op gate). Returns a
        frozenset; empty means "no operator configured" — the caller then
        keeps the approval reply path a logged no-op.

        Identity is deliberately NOT derived from this allowlist: the published
        ``decided_by`` is the clicker's own member id, so the allowlist answers
        only "who MAY decide", never "who DID".
        """
        ids: set[str] = set()
        if self.slack_operator_user_ids:
            ids.update(
                entry.strip() for entry in self.slack_operator_user_ids.split(",") if entry.strip()
            )
        if self.slack_operator_user_id and self.slack_operator_user_id.strip():
            ids.add(self.slack_operator_user_id.strip())
        return frozenset(ids)

    # -- Runtime validation --------------------------------------------------

    def validate_provider_keys(self) -> None:
        """Validate that required provider credentials are present.

        Checks two things:

        1. The ``memory_store_backend`` is ``"in_memory"`` (only backend
           implemented in Phase 1).
        2. The provider extracted from ``supervisor_model`` has the required
           API key or base URL configured.

        Raises:
            ConfigurationError: With a clear message naming the missing
                environment variable.
        """
        # Phase 1: only in_memory backend is supported
        if self.memory_store_backend != "in_memory":
            raise ConfigurationError(
                f"{self.memory_store_backend} backend is not implemented in Phase 1"
            )

        # Phase 2: warn (do not raise) if Tavily is selected without an API key.
        # Web search is optional/best-effort, so a missing key downgrades the
        # capability rather than breaking startup.
        if self.web_search_provider == "tavily":
            tavily_key = self.tavily_api_key
            tavily_value = (
                tavily_key.get_secret_value() if isinstance(tavily_key, SecretStr) else tavily_key
            )
            if not tavily_value:
                message = (
                    "web_search_provider='tavily' but TAVILY_API_KEY "
                    "(JARVIS_TAVILY_API_KEY) is not set — web search will be "
                    "disabled."
                )
                warnings.warn(message, stacklevel=2)
                logger.warning(message)

        provider = self.supervisor_model.split(":", 1)[0]

        requirement = _PROVIDER_KEY_REQUIREMENTS.get(provider)
        if requirement is None:
            # Unknown provider — nothing to validate
            return

        field_name, env_var_name = requirement
        field_value = getattr(self, field_name, None)

        # SecretStr wraps the value — check if it's set
        if isinstance(field_value, SecretStr):
            if not field_value.get_secret_value():
                raise ConfigurationError(f"Provider '{provider}' requires {env_var_name} to be set")
        elif not field_value:
            raise ConfigurationError(f"Provider '{provider}' requires {env_var_name} to be set")
