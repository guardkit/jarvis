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
answers in the thread. The whole shape is case-insensitive. A ``build:``
command that is unambiguously unfinished or wrong — nothing after the colon; a
feature id (``FEAT-`` and 3 to 12 letters or digits, any case) and then
nothing, or ``from`` and nothing; or the complete ``build: FEAT-… from
<branch>`` shape with an id the wire cannot carry, a branch git would refuse,
no space after the colon or a line break inside it — gets one usage line back
and is not forwarded, like the half-typed ``next:``. Ordinary prose after
``build:`` (``build: a users page``, ``build: from scratch, a users page``,
``build: feat-flag support on the admin page``) stays a sentence, exactly as
before.

Starting a mission (missions design, 17 October 2026, section 1): a message
whose first line (after any ``target:`` line) is ``mission: <title>``, and
whose every following non-blank line is one feature,
``<key>[ (needs <key>[, <key>...])][ [no sign-in]]: <sentence>``. A key is 1
to 12 letters or digits, no hyphen, and goes on the wire upper-cased. It is
forwarded as one more queue command, verb ``mission``, with the title and the
features in the order typed. Jarvis checks the SHAPE only; the forge checks
the meaning (unknown or repeated keys, cycles, how many features) and answers
in the thread. Any message beginning ``mission:`` is either a mission or, with
a line that does not parse (or no title, or no features), one usage line back
and nothing sent, like a half-typed ``build:``. A message that merely mentions
a mission anywhere else (``our mission: ...``, ``missions: ...``, ``mission``
on a later line) stays a sentence.

Stopping a mission (missions design, section 11, 18 October 2026): ``stop
mission m-3fa21c`` is one more queue command, verb ``stop-mission``, with the
mission's id lower-cased. The forge decides whether the person may stop it and
answers in the thread. ``stop mission`` with nothing after it, or with an
``m-`` word that is not a mission id, gets one usage line back and is not
sent; other prose that happens to begin ``stop mission`` stays a sentence.
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

# A feature planned elsewhere, handed over by its branch: the complete shape,
# case-insensitive. Its separators are captured so a command typed with no
# space after the colon, or broken over two lines, can be told apart (a
# command is one line, with a space after the colon); the id and branch are
# checked after the match. Anything matching this shape is either the command
# or, with one of those parts wrong, the usage line — never a sentence.
_BUILD_RE = re.compile(r"^build:(\s*)(FEAT-\S+)(\s+)from(\s+)(\S+)$", re.IGNORECASE)
# A ``build:`` command left unfinished: nothing after the colon, or a feature
# id (the wire's id characters, any case) and then nothing, or ``from`` and
# nothing. Prose that merely begins with "from" or "feat-" does not match.
_BUILD_UNFINISHED_RE = re.compile(
    r"^build:[ \t]*(?:FEAT-[A-Z0-9]{3,12}(?:[ \t]+from)?[ \t]*)?$", re.IGNORECASE
)

# A mission: the first line names it, every following non-blank line is one
# feature. Only the first line decides whether the message is a mission at
# all; the feature lines are then checked one by one. Both patterns are
# ASCII-only: without ``re.ASCII`` case-insensitive matching lets look-alike
# letters through (the Kelvin sign matches ``k``, the long s ``s``, the
# dotless i ``i``), and ``.upper()`` would put them on the wire as keys.
_MISSION_FIRST_LINE_RE = re.compile(r"^mission:(.*)$", re.IGNORECASE | re.ASCII)
_MISSION_KEY = r"[A-Za-z0-9]{1,12}"
_MISSION_FEATURE_RE = re.compile(
    rf"^(?P<key>{_MISSION_KEY})"
    rf"(?:[ \t]*\(needs[ \t]+(?P<needs>{_MISSION_KEY}(?:[ \t]*,[ \t]*{_MISSION_KEY})*)[ \t]*\))?"
    r"(?P<no_sign_in>[ \t]*\[no sign-in\])?"
    r"[ \t]*:[ \t]*(?P<sentence>\S.*)$",
    re.IGNORECASE | re.ASCII,
)
# A ``target:`` line typed under the ``mission:`` line would otherwise read as
# a feature keyed TARGET; it is a misplaced target, so it gets the usage line.
_MISSION_RESERVED_KEYS = frozenset({"TARGET"})

#: The feature ids the wire accepts (nats-core ``FEATURE_ID_PATTERN``), kept
#: here as a local copy for the same reason as the repository-name set below;
#: a test pins the two together.
_FEATURE_ID_RE = re.compile(r"^FEAT-[A-Z0-9]{3,12}$")

# Stopping a mission: the id is ``m-`` and six hexadecimal digits, as the
# forge makes it. ``stop mission`` alone, or with an ``m-`` word that is not
# an id, is a command begun wrong and gets the usage line; other prose after
# ``stop mission`` stays a sentence.
_STOP_MISSION_RE = re.compile(
    r"^stop[ \t]+mission[ \t]+(m-[0-9a-f]{6})$", re.IGNORECASE | re.ASCII
)
_STOP_MISSION_WRONG_RE = re.compile(r"^stop[ \t]+mission(?:[ \t]+m-\S*)?$", re.IGNORECASE)

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

#: The one line jarvis posts itself for a ``stop mission`` without a mission id.
STOP_MISSION_USAGE_REFUSAL = 'Did you mean "stop mission m-xxxxxx"?'

#: The one line jarvis posts itself for a ``mission:`` message with a line
#: it cannot read.
MISSION_USAGE_REFUSAL = (
    'Did you mean "mission: <title>" and then one line per feature, '
    'such as "B (needs A) [no sign-in]: <sentence>"?'
)

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
            hand-over — no nesting (spec contract 2). The one exception is
            a mission (missions design, 17 October 2026): ``{"verb":
            "mission", "title": str, "features": [{"key": str, "needs":
            [str, ...], "no_sign_in": bool, "sentence": str}, ...]}``.
        refusal_text: The one line jarvis posts itself, or ``None``.
        kind: ``"fix"`` or ``"question"`` when the sentence carried that
            prefix; ``None`` otherwise (the forge defaults to a feature).
    """

    shape: Literal["command", "refusal", "sentence"]
    sentence: str = ""
    command: dict[str, Any] | None = None
    refusal_text: str | None = None
    kind: Literal["fix", "question"] | None = None


def _parse_mission(candidate: str) -> ParsedMessage | None:
    """A mission, the mission usage line, or ``None`` when it is not one.

    Only a message whose first line begins ``mission:`` is a mission. From
    then on there is no falling back to a sentence: a typo in one feature
    line would otherwise start a single planning run from the whole list.
    """
    first_line, _, rest = candidate.partition("\n")
    match = _MISSION_FIRST_LINE_RE.match(first_line.strip())
    if match is None:
        return None
    refusal = ParsedMessage(shape="refusal", refusal_text=MISSION_USAGE_REFUSAL)
    title = match.group(1).strip()
    if not title:
        return refusal
    features: list[dict[str, Any]] = []
    for line in rest.splitlines():
        line = line.strip()
        if not line:
            continue
        feature = _MISSION_FEATURE_RE.match(line)
        if feature is None:
            return refusal
        key = feature.group("key").upper()
        sentence = feature.group("sentence").strip()
        if key in _MISSION_RESERVED_KEYS or not sentence:
            return refusal
        needs = feature.group("needs")
        features.append(
            {
                "key": key,
                "needs": [need.strip().upper() for need in needs.split(",")] if needs else [],
                "no_sign_in": feature.group("no_sign_in") is not None,
                "sentence": sentence,
            }
        )
    if not features:
        return refusal
    return ParsedMessage(
        shape="command",
        command={"verb": "mission", "title": title, "features": features},
    )


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
        after_colon, before_from, after_from = match.group(1, 3, 4)
        feature_id = match.group(2).upper()
        branch = match.group(5)
        one_line = "\n" not in after_colon + before_from + after_from
        if (
            after_colon
            and one_line
            and _FEATURE_ID_RE.match(feature_id)
            and is_allowed_branch_name(branch)
        ):
            return ParsedMessage(
                shape="command",
                command={"verb": "build", "feature_id": feature_id, "branch": branch},
            )
        # The command's shape with one part wrong. Filed as prose it would
        # start a planning run from a typo, so jarvis answers instead.
        return ParsedMessage(shape="refusal", refusal_text=BUILD_USAGE_REFUSAL)
    if _BUILD_UNFINISHED_RE.match(candidate):
        # A hand-over begun and not finished: the usage line, nothing sent.
        return ParsedMessage(shape="refusal", refusal_text=BUILD_USAGE_REFUSAL)

    match = _STOP_MISSION_RE.match(candidate)
    if match:
        return ParsedMessage(
            shape="command",
            command={"verb": "stop-mission", "mission_id": match.group(1).lower()},
        )
    if _STOP_MISSION_WRONG_RE.match(candidate):
        # A stop begun without a usable mission id: the usage line, nothing sent.
        return ParsedMessage(shape="refusal", refusal_text=STOP_MISSION_USAGE_REFUSAL)

    mission = _parse_mission(candidate)
    if mission is not None:
        return mission

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
    "STOP_MISSION_USAGE_REFUSAL",
    "INVALID_TARGET_NAME_REPLY",
    "MISSION_USAGE_REFUSAL",
    "USAGE_REFUSAL",
    "ParsedMessage",
    "is_allowed_branch_name",
    "is_allowed_target_name",
    "parse_queue_message",
]
