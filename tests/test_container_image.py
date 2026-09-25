"""What ``deploy/Dockerfile`` has to keep true about the jarvis image.

Written 25 September 2026, when this repository first grew a Dockerfile.

WHY THESE FOUR THINGS, AND NOT A BUILD. Building the image needs Docker, a
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
4. IT DOES NOT RUN AS ROOT, and the settings file cannot reach the image.

None of this names any target project's toolchain: it is about one image of
this repository's own two services.
"""

from __future__ import annotations

import re
from pathlib import Path

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
