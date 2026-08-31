#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$REPO_ROOT/.venv"

if ! command -v sudo >/dev/null 2>&1; then
	echo "sudo is required to install workstation packages." >&2
	exit 1
fi

sudo apt-get update
sudo apt-get install --yes ca-certificates curl git python3 python3-venv

if ! command -v az >/dev/null 2>&1; then
	curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
fi

az extension add --name bastion --upgrade --yes
az extension add --name ssh --upgrade --yes

python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || {
	echo "Python 3.11 or later is required." >&2
	exit 1
}

if [[ -d "$VENV_DIR" ]]; then
	if [[ ! -x "$VENV_DIR/bin/python" ]]; then
		echo "$VENV_DIR exists but is not a valid virtual environment." >&2
		exit 1
	fi
else
	python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install \
	-r "$REPO_ROOT/00-setup/requirements.txt" \
	-r "$REPO_ROOT/01-standards-agent/requirements.txt" \
	-r "$REPO_ROOT/02-intake/requirements.txt" \
	-r "$REPO_ROOT/03-orchestration/requirements.txt" \
	-r "$REPO_ROOT/04-research/requirements.txt" \
	-r "$REPO_ROOT/05-review-eval/requirements.txt" \
	-r "$REPO_ROOT/06-adr-generation/requirements.txt"

echo "Workstation setup complete. Activate the environment with:"
echo "  source $VENV_DIR/bin/activate"