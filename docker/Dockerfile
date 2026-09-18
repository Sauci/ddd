# Linux image that runs DDD and compiles the c code it generates.
#
# Built and used through docker compose from a WSL shell:
#   wsl -d Ubuntu
#   cd /mnt/c/path/to/ddd && docker compose run --rm compile
#
# This image exists to prove that the generated c compiles, and that proof is only worth
# something if it is the same toolchain tomorrow. The tag below still floats: pin it to a
# digest before relying on the result for a release, with
#
#   docker pull python:3.12-slim-bookworm
#   docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim-bookworm
#
# and replace the tag with the "python@sha256:..." it prints.
#
# Two stages start from that tag, and the digest replaces it in both. The node image the pages
# of `ddd gui` are compiled with floats the same way, and is pinned the same way.

# Where node comes from; nothing is built on it.
FROM node:24-bookworm-slim AS node

# The pages of `ddd gui`, which git does not track: compiled here, taken by the stage after this
# one, and thrown away with everything else this stage holds - node, npm and node_modules - so
# that the image serves `ddd gui` with none of them in it.
#
# python rather than node as the base, because the pages are compiled against types generated
# from the package, so it is installed here as well. Only node, npm and node's headers are taken
# from node's image, never the whole of /usr/local: that is where this image keeps python, and a
# copy of node's would write whatever node's image keeps there over it. A node from 25 on also
# needs libatomic1, which node's image installs and this one does not.
FROM python:3.12-slim-bookworm AS pages
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=node /usr/local/include/node /usr/local/include/node
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# The lock file before the sources, so that changing a source downloads no package again.
WORKDIR /opt/ddd/gui
COPY gui/package.json gui/package-lock.json ./
RUN npm ci

# The files the final stage's install copies, and for the same reason: the wheel cannot be
# built without every path it force-includes.
WORKDIR /opt/ddd
COPY pyproject.toml README.md LICENSE requirements*.txt ./
COPY src ./src
COPY cmake ./cmake
COPY examples/templates ./examples/templates
RUN pip install --no-cache-dir .

COPY gui ./gui
WORKDIR /opt/ddd/gui
RUN npm run schemas && npm run build

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gcc compiles the generated sources and binutils (nm) verifies that every variable DDD
# promised really ends up in the object file exactly once.
#
# graphviz and plantuml draw the figures of the documentation, which builds with warnings as
# errors: without them the `docs` service fails rather than dropping a diagram. plantuml brings
# a headless jre with it, which is most of what these two add to the image.
#
# No node here, deliberately. The VS Code extension under editors/vscode is built and tested by
# ci, which can put python and node 20 side by side with two setup actions; carrying a second
# toolchain in this image would cost everyone who only wants to compile c or build the
# documentation, to save a contributor changing typescript from installing node. The pages of
# `ddd gui` are compiled with node all the same, in the stage above: only the pages reach this
# one.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        gcc \
        libc6-dev \
        binutils \
        graphviz \
        plantuml \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/ddd
COPY pyproject.toml README.md LICENSE requirements*.txt ./
COPY src ./src
# The compiled pages of `ddd gui`, from the stage above, into the tree the install below builds
# its wheel from, so that the package it installs carries them. The build context has none of
# its own to mix in: .dockerignore leaves out any the host compiled.
COPY --from=pages /opt/ddd/src/ddd/gui/static ./src/ddd/gui/static
COPY cmake ./cmake
# Every path the wheel force-includes has to be here, or the install below cannot build it.
# The templates are the one that is easy to forget: they live under examples/ rather than
# beside the other two, and leaving them out fails the image build rather than the tests.
COPY examples/templates ./examples/templates
# The dev requirements bring cmake and ninja as wheels, which is what builds the example that
# integrates the tool through cmake/Ddd.cmake. They come from pypi rather than from apt because
# the module needs the TRANSITIVE_LINK_PROPERTIES feature of CMake 3.30 and debian bookworm
# still ships 3.25 - and because tests/test_cmake.py runs against exactly this pair.
#
# The docs requirements are here rather than in the `docs` service, which used to install them
# on every run: a service that installs anything is a second build step nothing pins, needs the
# network before every documentation build, and leaves the five other services sharing an image
# that cannot do what the sixth does.
RUN pip install --no-cache-dir ".[dev,docs]"

COPY docker/compile.sh docker/verify_symbols.py /opt/ddd/bin/
RUN chmod +x /opt/ddd/bin/compile.sh \
    && ln -s /opt/ddd/bin/compile.sh /usr/local/bin/ddd-compile

# The project is bind mounted here by docker compose; PYTHONPATH=/work/src then
# shadows the copy installed above, so the container always runs the working tree.
# The pages of `ddd gui` too: a service serves the working tree's, which only a checkout that
# compiled them has; the ones installed above are what a container run without that
# PYTHONPATH serves.
WORKDIR /work

CMD ["ddd", "--help"]
