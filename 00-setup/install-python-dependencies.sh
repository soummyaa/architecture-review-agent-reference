#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON=${PYTHON:-python3}

if [[ -z "${PIP_INDEX_URL:-}" ]]; then
	echo "PIP_INDEX_URL is required; set it to the approved Python package index." >&2
	exit 1
fi

PIP_CONFIG_FILE=/dev/null PIP_EXTRA_INDEX_URL= "$PYTHON" -m pip install \
	--index-url "$PIP_INDEX_URL" \
	--upgrade pip
PIP_CONFIG_FILE=/dev/null PIP_EXTRA_INDEX_URL= "$PYTHON" -m pip install \
	--index-url "$PIP_INDEX_URL" \
	-r "$REPO_ROOT/00-setup/requirements.txt" \
	-r "$REPO_ROOT/01-standards-agent/requirements.txt" \
	-r "$REPO_ROOT/02-intake/requirements.txt" \
	-r "$REPO_ROOT/03-orchestration/requirements.txt" \
	-r "$REPO_ROOT/04-research/requirements.txt" \
	-r "$REPO_ROOT/05-review-eval/requirements.txt" \
	-r "$REPO_ROOT/06-adr-generation/requirements.txt"