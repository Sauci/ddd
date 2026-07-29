#!/bin/bash
#
# What the documentation image runs when the working tree is mounted at /sources: the test
# suite first, then the html and pdf documentation, then the distribution.
#
# Kept deliberately close to the sibling python projects so that one image serves them all.
set -e

git config --global --add safe.directory /sources 2>/dev/null || true

python -m pip install --quiet -e ".[dev,docs]"

# Nothing is documented that is not first shown to work.
python -m pytest

sphinx-build -M html docs output -t html -W --keep-going
sphinx-build -M latexpdf docs output -t pdf

python -m build
