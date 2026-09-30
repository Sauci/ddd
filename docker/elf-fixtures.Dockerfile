# The cross toolchains that build the ELF fixtures of `ddd tool from-elf`, which
# tests/fixtures/elf/ holds and the suite reads without Docker or a compiler: see
# build_elf_fixtures.py beside this file, and `docker compose run --rm elf-fixtures`.
#
# Pinned by digest rather than by tag. The fixtures are committed, and the manifest beside them
# records which compiler built each: a rebuild on a tag that has moved would change them for a
# reason nobody asked for. Every row's compiler is a Debian package, cross gcc for five targets
# and clang with lld for two more; binutils is here for its readelf, which reads every target's
# headers, symbols and DWARF and is the manifest's oracle.
FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        binutils \
        clang \
        gcc-aarch64-linux-gnu \
        gcc-arm-none-eabi \
        gcc-i686-linux-gnu \
        gcc-powerpc-linux-gnu \
        gcc-s390x-linux-gnu \
        gcc-x86-64-linux-gnu \
        lld \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
