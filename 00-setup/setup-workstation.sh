#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$REPO_ROOT/.venv"
SKIP_OS_PACKAGE_INSTALL=false
SKIP_AZURE_CLI_INSTALL=false
INSTALL_BASTION_EXTENSIONS=false

usage() {
	cat <<'EOF'
Usage: setup-workstation.sh [options]

Options:
  --skip-os-packages       Use preinstalled ca-certificates, Python, and venv support.
  --skip-azure-cli         Do not install Azure CLI when it is absent.
  --install-bastion-tools  Install the optional bastion and ssh Azure CLI extensions.
  -h, --help               Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--skip-os-packages) SKIP_OS_PACKAGE_INSTALL=true ;;
		--skip-azure-cli) SKIP_AZURE_CLI_INSTALL=true ;;
		--install-bastion-tools) INSTALL_BASTION_EXTENSIONS=true ;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Unknown option: $1" >&2
			usage >&2
			exit 2
			;;
	esac
	shift
done

require_sudo() {
	if ! command -v sudo >/dev/null 2>&1; then
		echo "sudo is required for the requested installation step." >&2
		exit 1
	fi
}

if [[ "$SKIP_OS_PACKAGE_INSTALL" == false ]]; then
	require_sudo
	packages=(ca-certificates python3 python3-venv)
	if ! command -v az >/dev/null 2>&1 \
		&& [[ "$SKIP_AZURE_CLI_INSTALL" == false ]]; then
		packages+=(curl)
	fi
	sudo apt-get update
	sudo apt-get install --yes "${packages[@]}"
else
	echo "Skipping operating-system package installation."
fi

if ! command -v az >/dev/null 2>&1; then
	if [[ "$SKIP_AZURE_CLI_INSTALL" == true ]]; then
		echo "Azure CLI is not installed; Module 00 provisioning commands will be unavailable." >&2
	else
		require_sudo
		if ! command -v curl >/dev/null 2>&1; then
			echo "curl is required to install Azure CLI. Install it from an approved OS mirror." >&2
			exit 1
		fi
		curl --fail --show-error --location https://aka.ms/InstallAzureCLIDeb | sudo bash
	fi
fi

if [[ "$INSTALL_BASTION_EXTENSIONS" == true ]]; then
	if ! command -v az >/dev/null 2>&1; then
		echo "Optional Bastion tools skipped because Azure CLI is not installed." >&2
	else
		for extension in bastion ssh; do
			if ! az extension show --name "$extension" --output none 2>/dev/null; then
				az extension add --name "$extension" --yes \
					|| echo "Optional Azure CLI extension '$extension' could not be installed." >&2
			fi
		done
	fi
fi

if ! command -v python3 >/dev/null 2>&1; then
	echo "Python 3 is required. Install Python 3.11 or later from an approved OS mirror." >&2
	exit 1
fi

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

PYTHON="$VENV_DIR/bin/python" "$SCRIPT_DIR/install-python-dependencies.sh"

echo "Workstation setup complete. Activate the environment with:"
echo "  source $VENV_DIR/bin/activate"