#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON=${PYTHON:-python3}

if [[ -n "${PIP_INDEX_URL:-}" ]]; then
	PIP_INSTALL_INDEX_URL=$PIP_INDEX_URL
	echo "Using Python package index from PIP_INDEX_URL."
elif PIP_INSTALL_INDEX_URL=$("$PYTHON" -m pip config get global.index-url 2>/dev/null) \
	&& [[ -n "$PIP_INSTALL_INDEX_URL" ]]; then
	echo "Using Python package index from pip.conf."
else
	echo "No Python package index is configured; set PIP_INDEX_URL or global.index-url in pip.conf." >&2
	exit 1
fi

PIP_EXTRA_INDEX_URL= "$PYTHON" -m pip install \
	--index-url "$PIP_INSTALL_INDEX_URL" \
	-r "$REPO_ROOT/00-setup/requirements.txt" \
	-r "$REPO_ROOT/01-standards-agent/requirements.txt" \
	-r "$REPO_ROOT/02-intake/requirements.txt" \
	-r "$REPO_ROOT/03-orchestration/requirements.txt" \
	-r "$REPO_ROOT/04-research/requirements.txt" \
	-r "$REPO_ROOT/05-review-eval/requirements.txt" \
	-r "$REPO_ROOT/06-adr-generation/requirements.txt"