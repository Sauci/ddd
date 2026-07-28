# Linux image that runs DDD and compiles the c code it generates.
#
# Built and used through docker compose from a WSL shell:
#   wsl -d Ubuntu
#   cd /mnt/c/git/ac11/ddd && docker compose run --rm compile
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gcc compiles the generated sources and binutils (nm) verifies that every variable DDD
# promised really ends up in the object file exactly once; cmake and ninja build the
# example that integrates the tool through cmake/Ddd.cmake.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        gcc \
        libc6-dev \
        binutils \
        ninja-build \
    && rm -rf /var/lib/apt/lists/*

# cmake/Ddd.cmake needs the TRANSITIVE_LINK_PROPERTIES feature of CMake 3.30; debian bookworm
# still ships 3.25, so the current release comes from pypi.
RUN pip install --no-cache-dir "cmake>=3.30"

WORKDIR /opt/ddd
COPY pyproject.toml README.md ./
COPY src ./src
COPY cmake ./cmake
RUN pip install --no-cache-dir ".[dev]"

COPY docker/compile.sh docker/verify_symbols.py /opt/ddd/bin/
RUN chmod +x /opt/ddd/bin/compile.sh \
    && ln -s /opt/ddd/bin/compile.sh /usr/local/bin/ddd-compile

# The project is bind mounted here by docker compose; PYTHONPATH=/work/src then
# shadows the copy installed above, so the container always runs the working tree.
WORKDIR /work

CMD ["ddd", "--help"]
