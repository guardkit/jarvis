"""The shape of a queue command typed in the planning channel.

Binding spec 2026-09-05 (the work queue, Lane B stage one), contracts 1 and 3.

Rich manages the factory's work queue by typing short commands in the same
Slack channel he types ideas into. This module recognises the *shape* of
those commands and nothing else: jarvis does no reasoning and holds no queue
state (contract 1). The forge owns the queue, executes the command and posts
the reply.

The rules, verbatim from the spec's table:

* anchored, case-insensitive, first token only;
* anything that does not match is a sentence, so ordinary prose — including
  a sentence that happens to start with the word "queue" followed by more
  words — travels exactly as it does today;
* the bare word ``next`` is the one message jarvis answers itself, with a
  single line asking which of the two ``next`` shapes was meant.

The ``target: <name>`` first line is parsed BEFORE this module runs
(:func:`jarvis.infrastructure.slack_planning_intake.parse_target_token`), so
a target line applies to sentences and to ``next:``/``before`` sentences
alike.

Two small choices the spec left open, both the smallest thing that works:

* the message is matched with its outer whitespace removed, so an invisible
  trailing space typed into Slack cannot turn ``queue`` into a planning
  sentence (the JNB-107 verbatim-config lesson applied to a typed command);
* ``fix:``/``question:`` and ``next:``/``before`` do not combine — a kind
  prefix inside a command's sentence is just part of that sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

# --- the grammar table (spec 2026-09-05, contract 3) ----------------------
_QUEUE_RE = re.compile(r"^queue$", re.IGNORECASE)
_ADD_FRONT_RE = re.compile(r"^next:\s+(.+)$", re.IGNORECASE)
_ADD_BEFORE_RE = re.compile(r"^before\s+#(\d+):\s+(.+)$", re.IGNORECASE)
_PROMOTE_RE = re.compile(r"^#(\d+)\s+next$", re.IGNORECASE)
_LINK_RE = re.compile(r"^#(\d+)\s+after\s+#(\d+)$", re.IGNORECASE)
_KEEP_DROP_RE = re.compile(r"^(keep|drop)\s+#?(\d+)$", re.IGNORECASE)
_KIND_RE = re.compile(r"^(fix|question):\s+(.+)$", re.IGNORECASE)
_BARE_NEXT_RE = re.compile(r"^next$", re.IGNORECASE)

#: The one line jarvis posts itself: the bare word ``next`` is ambiguous
#: between the two ``next`` shapes, so it asks rather than guessing.
BARE_NEXT_REFUSAL = 'Did you mean "next: <sentence>" or "#12 next"?'

#: Which characters a typed repository name may use. The same set the wire
#: allows (nats-core ``PLANNING_TARGET_REPO_PATTERN``, ``_pipeline.py``):
#: letters, digits, ``.``, ``_``, ``-`` and at most one ``/``. Kept here as a
#: local copy so this module has no import-time dependency on nats_core (the
#: schema-import-isolation convention); a test pins the two together.
_ALLOWED_TARGET_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")

#: What jarvis says when a typed repository name uses a character the wire
#: cannot carry. One sentence, naming the characters that are allowed —
#: before this, such a name was dropped with only a log line and no reply.
INVALID_TARGET_NAME_REPLY = (
    "A repository name can only use letters, digits, full stops, underscores, "
    "hyphens and at most one slash, so nothing was sent — please retype it."
)


def is_allowed_target_name(name: str) -> bool:
    """True when ``name`` uses only characters the wire allows."""
    return bool(_ALLOWED_TARGET_NAME_RE.match(name))


@dataclass(frozen=True, slots=True)
class ParsedMessage:
    """What one planning-channel message turned out to be.

    Attributes:
        shape: ``"command"`` (forward it and post nothing), ``"refusal"``
            (post :attr:`refusal_text` and forward nothing) or ``"sentence"``
            (today's behaviour, unchanged).
        sentence: The sentence for ``shape == "sentence"``; empty otherwise
            (a command's own sentence lives in :attr:`command`).
        command: The flat object forwarded on the wire as ``queue_command``
            — ``{"verb": ..., "id"?: int, "after"?: int, "sentence"?: str}``,
            no nesting (spec contract 2).
        refusal_text: The one line jarvis posts itself, or ``None``.
        kind: ``"fix"`` or ``"question"`` when the sentence carried that
            prefix; ``None`` otherwise (the forge defaults to a feature).
    """

    shape: Literal["command", "refusal", "sentence"]
    sentence: str = ""
    command: dict[str, Any] | None = None
    refusal_text: str | None = None
    kind: Literal["fix", "question"] | None = None


def parse_queue_message(text: str) -> ParsedMessage:
    """Decide whether a message is a queue command, a refusal, or a sentence.

    Args:
        text: The message text with any ``target:`` first line already
            stripped off by ``parse_target_token``.

    Returns:
        The :class:`ParsedMessage`. Anything the table does not match comes
        back as a sentence carrying ``text`` unchanged, so no ordinary post
        can be swallowed by the grammar.
    """
    candidate = text.strip()

    if _QUEUE_RE.match(candidate):
        return ParsedMessage(shape="command", command={"verb": "list"})

    match = _ADD_FRONT_RE.match(candidate)
    if match:
        return ParsedMessage(
            shape="command",
            command={"verb": "add_front", "sentence": match.group(1).strip()},
        )

    match = _ADD_BEFORE_RE.match(candidate)
    if match:
        return ParsedMessage(
            shape="command",
            command={
                "verb": "add_before",
                "id": int(match.group(1)),
                "sentence": match.group(2).strip(),
            },
        )

    match = _PROMOTE_RE.match(candidate)
    if match:
        return ParsedMessage(
            shape="command",
            command={"verb": "promote", "id": int(match.group(1))},
        )

    match = _LINK_RE.match(candidate)
    if match:
        return ParsedMessage(
            shape="command",
            command={
                "verb": "link",
                "id": int(match.group(1)),
                "after": int(match.group(2)),
            },
        )

    match = _KEEP_DROP_RE.match(candidate)
    if match:
        return ParsedMessage(
            shape="command",
            command={"verb": match.group(1).lower(), "id": int(match.group(2))},
        )

    match = _KIND_RE.match(candidate)
    if match:
        kind: Literal["fix", "question"] = "fix" if match.group(1).lower() == "fix" else "question"
        return ParsedMessage(shape="sentence", sentence=match.group(2).strip(), kind=kind)

    if _BARE_NEXT_RE.match(candidate):
        return ParsedMessage(shape="refusal", refusal_text=BARE_NEXT_REFUSAL)

    # Not a command: an ordinary planning sentence, byte-for-byte as it
    # arrived (the wire strips its outer whitespace, as it always has).
    return ParsedMessage(shape="sentence", sentence=text)


__all__ = [
    "BARE_NEXT_REFUSAL",
    "INVALID_TARGET_NAME_REPLY",
    "ParsedMessage",
    "is_allowed_target_name",
    "parse_queue_message",
]
