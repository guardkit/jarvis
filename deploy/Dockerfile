# ---------------------------------------------------------------------------
# The jarvis image — ONE image, two services.
#
# Written 25 September 2026 for stage 4c of the factory's containerisation
# rollout gate. Until this file existed, the two jarvis services ran as host
# units out of a checkout and a virtual environment under somebody's home
# directory, so "the same front door on two machines" was not something anybody
# could have. The design's inventory calls that habit rather than need.
#
# WHY ONE IMAGE AND NOT TWO. The two services are two start commands over the
# same package:
#
#   the Slack front door  — serves the two graphs named in langgraph.json
#   the bus gateway       — `jarvis serve-nats`, the supervisor on the bus
#
# They share every dependency, they are built from one commit, and one image
# cannot drift away from itself. That is also how the factory's own coordinator
# and answer service are one image with two start commands, so this is the
# estate's existing pattern and not a new one.
#
# THE BASE IS PINNED BY DIGEST, and it is the factory's ONE base image. A
# release build reads every Dockerfile of the release and refuses one that pins
# no digest, or one whose digest is not the release's: a release has one base,
# or it has two supply chains under one name.
#
# WHAT IS NOT IN HERE, deliberately:
#   * no .env — the repository's own .dockerignore keeps the whole .env family
#     out of the build context, so it cannot be copied in by accident. Every
#     setting arrives at run time, and the Slack tokens arrive as files;
#   * no checkout path and no home directory of anybody — nothing of the
#     machine that builds the image rides into it. That was not free: until 25
#     September 2026 a developer's compiled files went into the build context
#     carrying the absolute path of the machine that compiled them, and the
#     .dockerignore now keeps every one of them out;
#   * no Slack token, no bus password, no licence key of any kind.
#
# ONE THING THAT IS IN HERE, and an earlier version of the list above wrongly
# said otherwise: A MACHINE NAME. This package's own settings module hard-codes
# a host name as the default model-seat address (src/jarvis/config/settings.py,
# llama_swap_base_url), a docstring in src/jarvis/adapters/llamaswap.py repeats
# it, .env.example carries it, and pyproject.toml names a folder in a comment
# about sibling checkouts. All of that pre-dates this file, in a repository
# that is already public, so packaging published nothing that was not published
# already. It is also inert wherever the estate runs this image: the estate
# supplies JARVIS_LLAMA_SWAP_BASE_URL and refuses to start the service without
# it, so that default can never be the value in use. Taking the host name out
# of the source is this repository's own fix, not a packaging one — it is
# written here so that nobody reads the list above and believes the image is
# cleaner than it is.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm@sha256:2e256d0381371566ed96980584957ed31297f437569b79b0e5f7e17f2720e53a

# THE BUS LIBRARY, FROM ITS OWN REPOSITORY.
#
# `nats-core` is a dependency of this package that does NOT come from a public
# index: the name on PyPI is a different project entirely, and a build that
# resolved it by name would install something else. On a developer's machine
# this repository's [tool.uv.sources] resolves it from a sibling checkout; a
# release cannot do that, because a checkout belongs to a machine.
#
# So it arrives as a BuildKit NAMED CONTEXT, exactly the way Forge's own image
# takes it (forge/Dockerfile). The release build offers every repository it
# pins to every image it builds, from clones it fetched itself at the pinned
# commits, so this line reads the pinned nats-core and nothing on any disk:
#
#     docker build --build-context nats-core=<a clone of nats-core> ...
#
# Built by hand without that flag, this build stops here and says so, which is
# the right answer: the image would otherwise be built against whatever a
# public index happens to serve under that name.
COPY --from=nats-core / /tmp/nats-core
RUN test -d /tmp/nats-core/src/nats_core \
    || (echo "the nats-core build context has no src/nats_core in it, so it is not the bus library this image needs" >&2; exit 1)

# The package is installed from THIS repository, from the build context — never
# fetched from an index by name, so what runs is what the pinned commit says.
#
# TWO EXTRAS, ONE FOR EACH SERVICE:
#   [nats]       the live bus client. It is optional in this repository on
#                purpose — the declarative payload models are a base
#                dependency, the client that really connects is opt-in — and
#                the bus gateway is the service that needs it.
#   [front-door] the langgraph CLI and its in-memory server, which is what runs
#                the two graphs langgraph.json declares. Until 25 September
#                2026 it was declared only under `dev`, so installing it meant
#                installing pytest, ruff and mypy as well; pyproject.toml now
#                names it on its own and says why.
#
# The test and lint tooling is NOT in this image.
WORKDIR /app
COPY pyproject.toml ./
COPY uv.lock ./
COPY langgraph.json ./
COPY src ./src

# THE VERSIONS ARE THIS REPOSITORY'S OWN LOCKED ONES, not whatever the index
# serves on the day of the build.
#
# This repository's dependency declarations are RANGES, the way a library's
# should be, and a developer's environment is built from uv.lock. An image built
# by resolving those ranges is therefore a different program from the one the
# live service runs, and a different one again next week — which is the exact
# thing the release path exists to end, said in the release manifest's own
# words. It is not theoretical: built unconstrained on 25 September 2026 this
# image picked up langchain 1.4.2 and deepagents 0.5.9 where the lock says
# 1.2.15 and 0.5.3, and the supervisor graph then refused to build at all
# ("Please remove duplicate middleware instances"), so the bus gateway started,
# joined the bus and exited.
#
# So the lock is turned into a pip constraints file and the install is held to
# it. Packages the lock resolves from a local path (this package, and the bus
# library, which arrives above as a build context) are left out: a constraint
# is a version, and those two have no version on an index.
#
# This is NOT a second source of truth. uv.lock stays the one place the
# versions are written; this step only reads it.
RUN python - <<'PY'
import tomllib
locked = tomllib.load(open("uv.lock", "rb"))
with open("/tmp/constraints.txt", "w") as out:
    for package in locked["package"]:
        source = package.get("source", {})
        if "registry" not in source:
            continue
        out.write(f"{package['name']}=={package['version']}\n")
PY
RUN pip install --no-cache-dir /tmp/nats-core \
    && pip install --no-cache-dir -c /tmp/constraints.txt ".[nats,front-door]" \
    && rm -rf /tmp/nats-core /tmp/constraints.txt

# A NON-ROOT USER, and a home it can write.
#
# Two things in this package write under the user's home by default: the
# offloaded routing-history traces (JARVIS_TRACES_DIR) and the dev server's own
# scratch folder in the working directory. Both are created here, owned by the
# user that runs them, because a container whose user cannot write its own
# working directory fails in a way that looks like something else entirely.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin jarvis \
    && mkdir -p /home/jarvis/.jarvis/traces \
    && chown -R jarvis:jarvis /home/jarvis /app
USER jarvis
ENV HOME=/home/jarvis

# THE DEFAULT START LINE IS THE FRONT DOOR'S, and it is a DEVELOPMENT SERVER.
#
# This is said plainly rather than dressed up. `langgraph dev` is the langgraph
# CLI's in-memory development server, and it is what the live host unit has
# always run (`jarvis-frontdoor.service` starts the same command from a
# checkout's virtual environment). This image changes WHERE that runs, not
# WHAT runs: packaging a habit honestly is the whole of this stage, and
# inventing a serving layer that the repository does not have would be a
# different and much larger thing done quietly.
#
# The production alternative the langgraph CLI offers — `langgraph up`, which
# builds and runs the closed-source langgraph API server image — requires a
# licence key for that server. No licence is baked here and none is read. What
# to serve the graphs with in production is the front door owner's decision and
# is recorded as an open item in the estate's README.
#
# --host 0.0.0.0: the container's own address, not its loopback. A server bound
# to loopback inside a container is reachable by nothing, not even a health
# check from the network.
CMD ["langgraph", "dev", "--no-browser", "--host", "0.0.0.0", "--port", "2024"]
