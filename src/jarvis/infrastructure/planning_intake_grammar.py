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
* three shapes are answered by jarvis itself with one usage line and are not
  forwarded at all: the bare word ``next``, and the two half-typed commands
  ``next:`` and ``before #12:`` with nothing after them. Without that last
  rule a half-typed command would become a planning sentence whose entire
  text is ``next:`` — a real build started from a typo (the coach's ruling
  of 2026-09-05 evening).

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

Handing over a feature planned elsewhere (register-projects design, 5 October
2026, part 3): ``build: FEAT-1A2B from prepared/FEAT-1A2B`` asks the factory to
build a feature whose spec and plan are already committed on that branch. It
is one more queue command, forwarded with verb ``build`` and the feature and
branch as typed; the forge resolves the ``target:`` name (or its default) and
answers in the thread. A ``build:`` begun and not finished — nothing after the
colon, or a first word written like a feature id (``FEAT-1…`` in capitals)
with no branch, or an id or branch that cannot be one — gets one usage line
back and is not forwarded, like the half-typed ``next:``. Prose after
``build:`` that does not start like a feature id (``build: a users page``,
``build: from scratch, a users page``, ``build: feat-flag support``) stays a
sentence, exactly as before.
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

# A feature planned elsewhere, handed over by its branch. One line only: the
# separators are spaces or tabs, never a line break.
_BUILD_RE = re.compile(r"^build:[ \t]+(FEAT-[A-Z0-9]+)[ \t]+from[ \t]+(\S+)$", re.IGNORECASE)
# A ``build:`` begun as a command: nothing after the colon, or a first word
# that starts like a feature id as the wire writes it — ``FEAT-`` in capitals
# followed by a capital or a digit. When the whole shape above does not match,
# this is a command left unfinished, never a sentence. Only ``build:`` is
# matched case-insensitively here, so prose such as "build: feat-flag support"
# or "build: from scratch, a users page" stays a sentence. (The complete
# command above stays case-insensitive: a fully typed "build: feat-1a2b from
# main" is still a command, its id upper-cased.)
_BUILD_BEGUN_RE = re.compile(r"^(?i:build:)[ \t]*(?:$|FEAT-[A-Z0-9])")

#: The feature ids the wire accepts (nats-core ``FEATURE_ID_PATTERN``), kept
#: here as a local copy for the same reason as the repository-name set below;
#: a test pins the two together.
_FEATURE_ID_RE = re.compile(r"^FEAT-[A-Z0-9]{3,12}$")

# The three shapes jarvis answers itself. Each is a command begun and not
# finished, so there is no sentence to file and nothing to forward.
_BARE_NEXT_RE = re.compile(r"^next$", re.IGNORECASE)
_EMPTY_ADD_FRONT_RE = re.compile(r"^next:\s*$", re.IGNORECASE)
_EMPTY_ADD_BEFORE_RE = re.compile(r"^before\s+#(\d+):\s*$", re.IGNORECASE)

#: The one line jarvis posts itself when a ``next``-shaped message carries no
#: sentence: bare ``next`` is ambiguous between the two ``next`` shapes, and
#: ``next:`` / ``before #12:`` were begun and not finished. The same line
#: serves all three, so Rich sees one usage reminder rather than three.
USAGE_REFUSAL = 'Did you mean "next: <sentence>" or "#12 next"?'

#: The one line jarvis posts itself for a ``build:`` begun and not finished.
BUILD_USAGE_REFUSAL = 'Did you mean "build: FEAT-XXXX from <branch>"?'

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


#: Characters git never allows in a branch name (``git check-ref-format``):
#: control characters, space, and ``~ ^ : ? * [ \``.
_BRANCH_FORBIDDEN_RE = re.compile(r"[\x00-\x20\x7f~^:?*\[\\]")


def is_allowed_branch_name(name: str) -> bool:
    """True when ``name`` is a branch name git would accept.

    The rules of ``git check-ref-format --branch``, written out so jarvis
    needs no git: none of the forbidden characters; not beginning with ``-``;
    no ``..``, ``@{`` or ``//``; not ``@`` on its own; not beginning or ending
    with ``/``, not ending with ``.``; and no path part beginning with ``.``
    or ending with ``.lock``.
    """
    if not name or name == "@" or _BRANCH_FORBIDDEN_RE.search(name):
        return False
    if name.startswith(("-", "/")) or name.endswith(("/", ".")):
        return False
    if ".." in name or "@{" in name or "//" in name:
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock") for part in name.split("/")
    )


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
            or ``{"verb": "build", "feature_id": str, "branch": str}`` for a
            hand-over — no nesting (spec contract 2).
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

    match = _BUILD_RE.match(candidate)
    if match:
        feature_id = match.group(1).upper()
        branch = match.group(2)
        if _FEATURE_ID_RE.match(feature_id) and is_allowed_branch_name(branch):
            return ParsedMessage(
                shape="command",
                command={"verb": "build", "feature_id": feature_id, "branch": branch},
            )
    if _BUILD_BEGUN_RE.match(candidate):
        # A hand-over begun and not finished, or with a feature id or branch
        # that cannot be one. Filed as prose it would start a planning run
        # from a typo, so jarvis answers with the usage line instead.
        return ParsedMessage(shape="refusal", refusal_text=BUILD_USAGE_REFUSAL)

    match = _KIND_RE.match(candidate)
    if match:
        kind: Literal["fix", "question"] = "fix" if match.group(1).lower() == "fix" else "question"
        return ParsedMessage(shape="sentence", sentence=match.group(2).strip(), kind=kind)

    if (
        _BARE_NEXT_RE.match(candidate)
        or _EMPTY_ADD_FRONT_RE.match(candidate)
        or _EMPTY_ADD_BEFORE_RE.match(candidate)
    ):
        # A command with its sentence missing. Filing it as prose would start
        # a planning run whose whole request is "next:", so jarvis answers
        # with the usage line and publishes nothing.
        return ParsedMessage(shape="refusal", refusal_text=USAGE_REFUSAL)

    # Not a command: an ordinary planning sentence, byte-for-byte as it
    # arrived (the wire strips its outer whitespace, as it always has).
    return ParsedMessage(shape="sentence", sentence=text)


__all__ = [
    "BUILD_USAGE_REFUSAL",
    "INVALID_TARGET_NAME_REPLY",
    "USAGE_REFUSAL",
    "ParsedMessage",
    "is_allowed_branch_name",
    "is_allowed_target_name",
    "parse_queue_message",
]
