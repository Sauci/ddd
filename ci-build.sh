#!/bin/bash
#
# Runs the documentation build inside the shared documentation image, the same way the sibling
# python projects do. The image carries sphinx, the extensions, a JRE and plantuml.jar, and a
# LaTeX distribution for the pdf; the working tree is mounted at /sources and build.sh is the
# entry point.
#
#   ./ci-build.sh
#
# The image is a linux image, so on a Windows host run this from a WSL shell where docker
# speaks linux containers.
set -e

image="${DDD_DOC_IMAGE:-docker.lmb.liebherr.i/ac1/python-packages-documentation:0.4.4}"

docker run \
    --rm \
    -v "$(pwd)":/sources \
    "$image"
