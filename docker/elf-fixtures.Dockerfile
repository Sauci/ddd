# The cross toolchains that build the ELF fixtures of `ddd tool from-elf`, which
# tests/fixtures/elf/ holds and the suite reads without Docker or a compiler: see
# build_elf_fixtures.py beside this file, and `docker compose run --rm elf-fixtures`.
#
# What is pinned is the base image, by digest rather than by tag, so that a rebuild starts from
# the Debian the fixtures were built on. The packages are not pinned: apt installs the versions
# trixie carries on the day the image is built, and a point release of trixie moves them, where
# a pinned version would stop the build instead. The fixtures are committed, and the manifest
# beside them records the compiler each image was built with, as the compiler states its own
# version - the `compiler` of every row and negative input - so that a rebuild on newer packages
# shows in its diff. Every row's compiler is a Debian package, cross gcc for five targets and
# clang with lld for two more; binutils is here for its readelf, which reads every target's
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
