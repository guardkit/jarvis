"""Prompt constants for Jarvis agent roles.

Domain-specific instructions are injected at runtime via placeholders.
This module re-exports public prompt constants through a single import surface.

Runtime placeholders:
    {date} — injected via ``datetime.date.today().isoformat()`` at agent creation time
    {domain_prompt} — loaded from ``domains/{domain}/DOMAIN.md`` at startup
"""

from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

__all__ = [
    "SUPERVISOR_SYSTEM_PROMPT",
]
