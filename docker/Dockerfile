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
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gcc compiles the generated sources and binutils (nm) verifies that every variable DDD
# promised really ends up in the object file exactly once; cmake and ninja build the
# example that integrates the tool through cmake/Ddd.cmake.
#
# graphviz and plantuml draw the figures of the documentation, which builds with warnings as
# errors: without them the `docs` service fails rather than dropping a diagram. plantuml brings
# a headless jre with it, which is most of what these two add to the image.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        gcc \
        libc6-dev \
        binutils \
        ninja-build \
        graphviz \
        plantuml \
    && rm -rf /var/lib/apt/lists/*

# cmake/Ddd.cmake needs the TRANSITIVE_LINK_PROPERTIES feature of CMake 3.30; debian bookworm
# still ships 3.25, so the current release comes from pypi.
RUN pip install --no-cache-dir "cmake>=3.30"

WORKDIR /opt/ddd
COPY pyproject.toml README.md LICENSE requirements*.txt ./
COPY src ./src
COPY cmake ./cmake
COPY completion ./completion
RUN pip install --no-cache-dir ".[dev]"

COPY docker/compile.sh docker/verify_symbols.py /opt/ddd/bin/
RUN chmod +x /opt/ddd/bin/compile.sh \
    && ln -s /opt/ddd/bin/compile.sh /usr/local/bin/ddd-compile

# The project is bind mounted here by docker compose; PYTHONPATH=/work/src then
# shadows the copy installed above, so the container always runs the working tree.
WORKDIR /work

CMD ["ddd", "--help"]
