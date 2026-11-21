#!/bin/sh
# Create the repo-local Python 3.13 venv with the pinned PyObjC packages.
set -e
cd "$(dirname "$0")/.."
uv venv --quiet --python 3.13 .venv
uv pip install --quiet --python .venv/bin/python --require-hashes -r requirements-macos.txt
.venv/bin/python -c "import AppKit, ApplicationServices, Quartz, CoreText; print('venv ok')"
