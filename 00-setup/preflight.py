#!/usr/bin/env python3
"""Check that a workstation can run the architecture review workshop."""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import socket
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import urlparse

MINIMUM_PYTHON = (3, 11)
REQUIRED_IMPORTS = (
    "azure.ai.projects",
    "azure.identity",
    "azure.monitor.opentelemetry",
    "docx",
    "docxtpl",
    "pydantic",
    "requests",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", default=os.getenv("AZURE_RESOURCE_GROUP"))
    parser.add_argument(
        "--deployment-name",
        default=os.getenv("AZURE_DEPLOYMENT_NAME", "architecture-review-setup"),
    )
    parser.add_argument("--project-endpoint")
    parser.add_argument("--model-endpoint")
    parser.add_argument("--model-deployment")
    return parser.parse_args()


def run_check(name: str, check: Callable[[], str]) -> bool:
    try:
        detail = check()
        passed = True
    except Exception as error:
        detail = str(error)
        passed = False
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}", flush=True)
    return passed


def check_azure_cli() -> str:
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI was not found on PATH")
    return "Azure CLI is present"


def check_azure_login() -> str:
    try:
        completed = subprocess.run(
            ["az", "account", "show", "--query", "id", "-o", "tsv", "--only-show-errors"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Azure CLI was not found on PATH") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "run `az login`"
        raise RuntimeError(detail) from error
    if not completed.stdout.strip():
        raise RuntimeError("Azure CLI has no active subscription; run `az login`")
    return "Azure CLI has an active signed-in account"


def check_python_version() -> str:
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        raise RuntimeError(f"Python {required} or later is required")
    return f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def check_required_imports() -> str:
    missing: list[str] = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        raise RuntimeError(f"missing imports: {', '.join(missing)}")
    return f"{len(REQUIRED_IMPORTS)} required imports succeeded"


def check_project_reachability(endpoint: str) -> str:
    hostname = urlparse(endpoint).hostname
    if not hostname:
        raise RuntimeError("project endpoint is not a valid URL")
    with socket.create_connection((hostname, 443), timeout=10):
        pass
    return "project host resolved and accepted a TCP connection"


def resolve_foundry_config(args: argparse.Namespace, setup_validator: Any) -> SimpleNamespace:
    outputs = setup_validator.load_deployment_outputs(
        args.resource_group,
        args.deployment_name,
    )
    values = {
        "project_endpoint": (
            args.project_endpoint
            or outputs.get("foundryProjectEndpoint")
            or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        ),
        "model_endpoint": (
            args.model_endpoint
            or outputs.get("modelEndpoint")
            or os.getenv("MODEL_ENDPOINT")
        ),
        "model_deployment": (
            args.model_deployment
            or outputs.get("modelDeploymentName")
            or os.getenv("MODEL_DEPLOYMENT_NAME")
        ),
    }
    missing = [name.replace("_", "-") for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"missing configuration: {', '.join(missing)}")
    return SimpleNamespace(**values)


def main() -> int:
    args = parse_args()
    results = [
        run_check("Azure CLI", check_azure_cli),
        run_check("Azure CLI login", check_azure_login),
        run_check("Python version", check_python_version),
        run_check("Required Python packages", check_required_imports),
    ]

    setup_validator: Any = None
    config: Any = None
    config_error: Exception | None = None
    credential: Any = None
    try:
        setup_validator = importlib.import_module("validate")
        config = resolve_foundry_config(args, setup_validator)
    except Exception as error:
        config_error = error

    def require_config() -> Any:
        if config_error:
            raise RuntimeError(f"configuration unavailable: {config_error}")
        return config

    results.append(
        run_check(
            "Foundry project reachability",
            lambda: check_project_reachability(require_config().project_endpoint),
        )
    )

    def get_credential() -> Any:
        nonlocal credential
        if credential is None:
            credential = setup_validator.DefaultAzureCredential()
        return credential

    def check_model() -> str:
        resolved = require_config()
        token = get_credential().get_token(setup_validator.COGNITIVE_SERVICES_SCOPE).token
        with setup_validator.requests.Session() as session:
            return setup_validator.check_model_deployment(
                session,
                f"Bearer {token}",
                resolved.model_endpoint,
                resolved.model_deployment,
            )

    def check_data_plane_role() -> str:
        resolved = require_config()
        token = get_credential().get_token(setup_validator.AI_FOUNDRY_SCOPE).token
        with setup_validator.requests.Session() as session:
            return setup_validator.check_foundry_project(
                session,
                f"Bearer {token}",
                resolved.project_endpoint,
            )

    results.append(run_check("Model deployment present and callable", check_model))
    results.append(run_check("Data-plane role assignment", check_data_plane_role))

    if credential is not None:
        credential.close()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())