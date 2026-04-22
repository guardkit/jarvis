"""Structured logging configuration using structlog.

Configures structlog with:
- **JSON rendering** when stderr is not a TTY (CI, pipes, production).
- **Console rendering** when stderr is a TTY (developer workstation).
- **Secret redaction** processor that masks any dict key ending
  ``_key`` or ``_token`` before the event reaches the renderer.

Must be called before any configuration validation so that startup
errors are captured as structured events.
"""

from __future__ import annotations

import logging
import sys

import structlog


def _redact_secrets(
    logger: object,
    method_name: str,
    event_dict: dict[str, object],
) -> dict[str, object]:
    """Mask values whose keys end with ``_key`` or ``_token``.

    Handles both top-level event_dict entries and nested dicts
    (e.g. from ``config.model_dump()``).  Operates in-place on
    a shallow copy of each dict it encounters.

    Args:
        logger: Unused (structlog processor protocol).
        method_name: Unused (structlog processor protocol).
        event_dict: The log event dictionary to process.

    Returns:
        The event dict with secret values replaced by ``"***"``.
    """
    for key, value in list(event_dict.items()):
        if isinstance(key, str) and (key.endswith("_key") or key.endswith("_token")):
            event_dict[key] = "***"
        elif isinstance(value, dict):
            event_dict[key] = _redact_dict(value)
        elif isinstance(value, str) and key != "event":
            # Handle pydantic SecretStr repr: "SecretStr('**********')" — leave as-is
            pass
    return event_dict


def _redact_dict(d: dict[str, object]) -> dict[str, object]:
    """Recursively redact secret keys in a nested dict.

    Args:
        d: Dictionary to scan for secret keys.

    Returns:
        A new dict with ``_key`` / ``_token`` values replaced by ``"***"``.
    """
    result: dict[str, object] = {}
    for key, value in d.items():
        if isinstance(key, str) and (key.endswith("_key") or key.endswith("_token")):
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = _redact_dict(value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result


def configure(log_level: str) -> None:
    """Set up structlog with secret redaction and format auto-detection.

    Selects JSON rendering when ``sys.stderr`` is not a TTY (production,
    CI pipelines) and human-friendly console rendering when it is a TTY.

    Args:
        log_level: Standard Python log level name (e.g. ``"INFO"``,
            ``"DEBUG"``).  Applied to the stdlib root logger gate.
    """
    is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_secrets,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    if is_tty:
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(),
            ],
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )

    # Configure stdlib root logger with our formatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
