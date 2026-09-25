"""What ``deploy/Dockerfile`` has to keep true about the jarvis image.

Written 25 September 2026, when this repository first grew a Dockerfile.

WHY THESE THINGS, AND NOT A BUILD. Building the image needs Docker, a
network and a clone of the bus library, so it is not something a unit test
does; the factory's release build does that, and its own proof script opens the
built image and asks it questions. What a test here can hold is the FILE — the
handful of properties that, if one of them quietly stopped being true, would
produce an image that still built and was wrong:

1. THE BASE IS PINNED BY DIGEST. A tag can be moved under you; a digest cannot.
   The factory's release build refuses any Dockerfile of a release that pins no
   digest, so losing this would take this repository out of the release
   entirely — noisily, but only at release time.
2. THE PACKAGE IS INSTALLED FROM THIS REPOSITORY. Not fetched from an index by
   name. What runs has to be the commit the image was built from.
3. THE BUS LIBRARY COMES FROM ITS OWN REPOSITORY, as a build context. The name
   ``nats-core`` on the public index is a DIFFERENT project, so an install that
   resolved it by name would quietly install something else.
4. THE VERSIONS ARE THIS REPOSITORY'S OWN LOCKED ONES. The declarations here
   are ranges; an image that resolves them afresh is a different program every
   week, and a different one from the live service.
5. IT DOES NOT RUN AS ROOT, and the settings file cannot reach the image.
6. WHAT IT COPIES CARRIES NOTHING OF THE MACHINE THAT BUILDS IT — swept with
   words that come from that machine, never from a list written down here.
7. ANOTHER REPOSITORY'S CHECKOUT IS NOT A LAYER OF THE SHIPPED IMAGE. The bus
   library arrives as a whole clone; it is copied in a BUILDER stage, and a
   deletion in a later step of one stage would not do — a deleted file is gone
   from what a container sees and still in what a push sends.

None of this names any target project's toolchain: it is about one image of
this repository's own two services.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "deploy" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _dockerfile_text() -> str:
    assert DOCKERFILE.is_file(), (
        f"{DOCKERFILE} is missing. It is how the two jarvis services are run as "
        "containers instead of as host units out of a checkout."
    )
    return DOCKERFILE.read_text(encoding="utf-8")


def _instructions(text: str) -> list[str]:
    """The Dockerfile's real instructions, with comments and blanks dropped."""
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def test_the_base_image_is_pinned_by_digest() -> None:
    """A tag can be moved; a digest cannot, and the release build insists."""
    froms = [line for line in _instructions(_dockerfile_text()) if line.startswith("FROM ")]
    assert froms, "deploy/Dockerfile has no FROM line at all"
    for line in froms:
        assert re.search(r"@sha256:[0-9a-f]{64}\b", line), (
            f"the base image on '{line}' is not pinned by digest. Two machines "
            "building this a week apart would get different bytes, and a "
            "release build refuses a Dockerfile that pins no digest."
        )


def test_the_package_is_installed_from_this_repository() -> None:
    """Not from an index by name: what runs is the commit it was built from."""
    text = _dockerfile_text()
    instructions = _instructions(text)
    assert any(line.startswith("COPY ") and " ./src" in line for line in instructions), (
        "deploy/Dockerfile does not copy this repository's src/ into the image, "
        "so whatever it installs did not come from this commit"
    )
    assert any(line.startswith("COPY pyproject.toml") for line in instructions), (
        "deploy/Dockerfile does not copy pyproject.toml, so the install has no "
        "declaration of this package to work from"
    )
    installs = [line for line in instructions if "pip install" in line]
    assert installs, "deploy/Dockerfile never installs this package"
    assert any('"."' in line or ' . ' in line or '".[' in line for line in installs), (
        "deploy/Dockerfile's pip install does not install '.', the package in "
        "the build context. An image of this repository has to carry this "
        f"repository's code. It says: {installs}"
    )


def test_the_bus_library_comes_from_its_own_repository() -> None:
    """``nats-core`` on the public index is a different project entirely.

    This repository resolves it from a sibling checkout for developers
    (``[tool.uv.sources]``), which a release cannot do, because a checkout
    belongs to a machine. The image takes it as a build context instead, and
    refuses a context that is not the bus library.
    """
    text = _dockerfile_text()
    assert "--from=nats-core" in text, (
        "deploy/Dockerfile does not take nats-core from a build context. "
        "Installed by name it would resolve to a different project on the "
        "public index."
    )
    assert "src/nats_core" in text, (
        "deploy/Dockerfile does not check that the nats-core build context is "
        "really the bus library, so a wrong or empty context would install "
        "quietly and fail much later"
    )


def _stages(text: str) -> list[list[str]]:
    """The instructions grouped by the ``FROM`` that begins each stage."""
    stages: list[list[str]] = []
    for line in _instructions(text):
        if line.startswith("FROM "):
            stages.append([line])
        elif stages:
            stages[-1].append(line)
    return stages


def test_the_bus_librarys_checkout_is_not_a_layer_of_the_shipped_image() -> None:
    """A deleted file is gone from what a container sees and still in what a
    push sends.

    The bus library arrives as a whole clone of another repository — all of it,
    including whatever working state that repository has committed. A
    single-stage build that copies it in and deletes it later looks clean from
    the inside (``docker export`` is the flattened final filesystem) and is not:
    the layer holding it is still one of the image's layers, and ``docker save``
    and a registry push send every layer. Measured on 25 September 2026 that
    layer was 68.3 MB, and at the commit the release pins it carried a person's
    account name in 127 files.

    So the copy belongs in a stage that is not shipped, and only the installed
    virtual environment crosses into the image.
    """
    text = _dockerfile_text()
    stages = _stages(text)
    assert len(stages) > 1, (
        "deploy/Dockerfile is a single stage, so everything it copies in is a "
        "layer of the image that ships — including the whole clone of the bus "
        "library, whether or not a later step deletes it"
    )

    final = stages[-1]
    final_copies = [line for line in final if line.startswith("COPY ") and "--from=" in line]
    for line in final_copies:
        assert "--from=nats-core" not in line, (
            "the shipped stage copies the bus library's whole checkout into "
            f"the image: {line}"
        )
    assert any("--from=builder" in line for line in final_copies), (
        "the shipped stage takes nothing from the builder stage, so whatever "
        "the builder installed is not in the image"
    )
    assert not any("nats-core" in line for line in final if line.startswith("RUN ")), (
        "the shipped stage handles the bus library's checkout itself; it "
        "belongs to the builder stage alone"
    )

    earlier = [line for stage in stages[:-1] for line in stage]
    assert any("--from=nats-core" in line for line in earlier), (
        "no stage takes the bus library from its build context, so the image "
        "would install whatever the public index serves under that name"
    )


def test_the_versions_are_this_repositorys_locked_ones() -> None:
    """An image that resolves this repository's ranges is a different program
    every week, and a different one from the live service.

    The declarations here are RANGES, the way a library's should be, and a
    developer's environment is built from uv.lock. Built unconstrained on 25
    September 2026 the image picked up langchain 1.4.2 and deepagents 0.5.9
    where the lock says 1.2.15 and 0.5.3, and the supervisor graph then refused
    to build at all — so the bus gateway started, joined the bus and exited,
    while the front door's server came up looking perfectly healthy because it
    loads that graph lazily.
    """
    text = _dockerfile_text()
    assert "uv.lock" in text, (
        "deploy/Dockerfile does not read uv.lock, so the image's versions are "
        "whatever the index served on the day it was built"
    )
    installs = [line for line in _instructions(text) if "pip install" in line]
    package_install = [line for line in installs if '".[' in line]
    assert package_install, "deploy/Dockerfile never installs this package with its extras"
    for line in package_install:
        assert "-c " in line, (
            "deploy/Dockerfile installs this package without holding it to a "
            f"constraints file built from uv.lock: {line}"
        )


def test_it_does_not_run_as_root() -> None:
    users = [line for line in _instructions(_dockerfile_text()) if line.startswith("USER ")]
    assert users, "deploy/Dockerfile names no USER, so the image runs as root"
    assert users[-1].split()[1] not in {"root", "0"}, (
        f"deploy/Dockerfile's last USER line is '{users[-1]}'"
    )


def test_the_settings_file_cannot_reach_the_image() -> None:
    """The .env family holds live Slack tokens and a bus password.

    The Dockerfile copies only the files it names, so nothing picks one up
    today — but a build context that CANNOT carry it survives the next person
    who adds a COPY line.
    """
    assert DOCKERIGNORE.is_file(), (
        ".dockerignore is missing, so the whole checkout — including .env — is "
        "sent to the Docker daemon as build context"
    )
    ignored = {
        line.strip() for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    }
    for pattern in (".env", ".env.*", "*.env"):
        assert pattern in ignored, (
            f".dockerignore does not exclude '{pattern}'. .gitignore here "
            "excludes the whole family for a reason: a timestamped backup once "
            "rode along in a commit because a single '.env' line matches only "
            "itself."
        )
    assert "*.env" in ignored and "!.env.example" in ignored, (
        ".dockerignore should keep the example, which carries no real value"
    )
    text = _dockerfile_text()
    assert "COPY .env" not in text, "deploy/Dockerfile copies a settings file into the image"


# ---------------------------------------------------------------------------
# 6. NOTHING OF THE MACHINE THAT BUILDS IT, in what the Dockerfile COPYs
# ---------------------------------------------------------------------------
#
# Added 25 September 2026. On 25 September a filesystem sweep of the built
# image found this machine's host name in it — not from the build, but from
# this package's own source, where `llama_swap_base_url` defaulted to it. The
# default is gone (see tests/test_config_feat_j003.py), and this test is the
# guard that keeps the tree the image is made of clean.
#
# THE TERMS COME FROM THE MACHINE, NEVER FROM A LIST HERE. A tracked list of
# this machine's names would be the very defect it is looking for, so the words
# arrive in RELEASE_SWEEP_TERMS — the same environment name the release build's
# own image sweep reads (forge/scripts/build-release-image.sh). With nothing
# set this test says so and skips, rather than passing and looking like an
# answer.


def test_what_the_image_copies_carries_none_of_this_machines_names() -> None:
    terms = [word for word in os.environ.get("RELEASE_SWEEP_TERMS", "").split() if word]
    if not terms:
        pytest.skip(
            "RELEASE_SWEEP_TERMS is not set, so no sweep ran. Set it to this "
            "machine's names (its host name, its user name, its home path, its "
            "projects folder), space separated, to sweep what the image copies."
        )

    # Exactly what deploy/Dockerfile COPYs into the image.
    copied = ["pyproject.toml", "uv.lock", "langgraph.json", "src"]
    hits: list[str] = []
    for relative in copied:
        target = REPO_ROOT / relative
        files = sorted(target.rglob("*")) if target.is_dir() else [target]
        for path in files:
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for term in terms:
                if term in text:
                    hits.append(f"{path.relative_to(REPO_ROOT)}: {term}")

    assert not hits, (
        "what deploy/Dockerfile copies into the image carries this machine's "
        "own names, and the image is public:\n  " + "\n  ".join(hits)
    )
