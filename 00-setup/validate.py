#!/usr/bin/env python3
"""Validate workshop access to Microsoft Foundry and SharePoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from azure.identity import DefaultAzureCredential

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_DEPLOYMENT_NAME = "architecture-review-setup"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class SetupConfig:
    project_endpoint: str
    model_endpoint: str
    model_deployment: str
    sharepoint_hostname: str
    sharepoint_site_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate identity-based access required by the workshop."
    )
    parser.add_argument(
        "--resource-group",
        default=os.getenv("AZURE_RESOURCE_GROUP"),
        help="Deployment resource group (or AZURE_RESOURCE_GROUP).",
    )
    parser.add_argument(
        "--deployment-name",
        default=os.getenv("AZURE_DEPLOYMENT_NAME", DEFAULT_DEPLOYMENT_NAME),
        help=f"Deployment name (default: {DEFAULT_DEPLOYMENT_NAME}).",
    )
    parser.add_argument("--project-endpoint", help="Override the project endpoint.")
    parser.add_argument("--model-endpoint", help="Override the model endpoint.")
    parser.add_argument("--model-deployment", help="Override the model deployment.")
    parser.add_argument(
        "--sharepoint-hostname", help="Override the SharePoint hostname."
    )
    parser.add_argument(
        "--sharepoint-site-path", help="Override the SharePoint site path."
    )
    return parser.parse_args()


def load_deployment_outputs(
    resource_group: str | None, deployment_name: str
) -> dict[str, str]:
    if not resource_group:
        return {}

    command = [
        "az",
        "deployment",
        "group",
        "show",
        "--resource-group",
        resource_group,
        "--name",
        deployment_name,
        "--query",
        "properties.outputs",
        "--output",
        "json",
        "--only-show-errors",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        raw_outputs = json.loads(completed.stdout)
    except FileNotFoundError as error:
        raise RuntimeError("Azure CLI was not found on PATH") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "deployment lookup failed"
        raise RuntimeError(detail) from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Azure CLI returned invalid deployment output") from error

    return {
        name: str(output["value"])
        for name, output in raw_outputs.items()
        if isinstance(output, dict) and output.get("value") is not None
    }


def resolve_config(args: argparse.Namespace) -> SetupConfig:
    outputs = load_deployment_outputs(args.resource_group, args.deployment_name)
    sources = {
        "project_endpoint": (
            args.project_endpoint,
            outputs.get("foundryProjectEndpoint"),
            os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        ),
        "model_endpoint": (
            args.model_endpoint,
            outputs.get("modelEndpoint"),
            os.getenv("MODEL_ENDPOINT"),
        ),
        "model_deployment": (
            args.model_deployment,
            outputs.get("modelDeploymentName"),
            os.getenv("MODEL_DEPLOYMENT_NAME"),
        ),
        "sharepoint_hostname": (
            args.sharepoint_hostname,
            outputs.get("sharepointHostname"),
            os.getenv("SHAREPOINT_HOSTNAME"),
        ),
        "sharepoint_site_path": (
            args.sharepoint_site_path,
            outputs.get("sharepointSitePath"),
            os.getenv("SHAREPOINT_SITE_PATH"),
        ),
    }
    values = {
        name: next((value for value in candidates if value), None)
        for name, candidates in sources.items()
    }
    missing = [name for name, value in values.items() if value is None]
    if missing:
        names = ", ".join(name.replace("_", "-") for name in missing)
        raise RuntimeError(
            f"Missing configuration: {names}. Set AZURE_RESOURCE_GROUP to read "
            "deployment outputs, use environment variables, or pass overrides."
        )

    return SetupConfig(**values)  # type: ignore[arg-type]


def response_error(response: requests.Response, forbidden_hint: str) -> str:
    request_id = response.headers.get("request-id") or response.headers.get(
        "x-ms-request-id", "not provided"
    )
    try:
        body: Any = response.json()
        message = body.get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        message = response.text.strip()

    detail = message[:240] if message else response.reason
    result = f"HTTP {response.status_code}: {detail} (request ID: {request_id})"
    if response.status_code == 403:
        result = f"{result}. Remediation: {forbidden_hint}"
    return result


def check_foundry_project(
    session: requests.Session,
    authorization: str,
    endpoint: str,
) -> str:
    url = f"{endpoint.rstrip('/')}/connections?api-version=2025-05-15-preview"
    response = session.get(
        url,
        headers={"Authorization": authorization},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(
            response_error(
                response,
                "assign the Azure AI Developer role on the Microsoft Foundry account.",
            )
        )
    return "authenticated connections API request succeeded"


def check_model_deployment(
    session: requests.Session,
    authorization: str,
    endpoint: str,
    deployment_name: str,
) -> str:
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment_name}"
        "/chat/completions?api-version=2024-10-21"
    )
    response = session.post(
        url,
        headers={"Authorization": authorization, "Content-Type": "application/json"},
        json={
            "messages": [
                {"role": "user", "content": "Reply with the single word ready."}
            ],
            "max_tokens": 8,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(
            response_error(
                response,
                "assign the Azure AI Developer role on the Microsoft Foundry account.",
            )
        )

    body = response.json()
    if not body.get("choices"):
        raise RuntimeError("the model returned no choices")
    return "deployment returned a chat completion"


def check_sharepoint_site(
    session: requests.Session,
    authorization: str,
    hostname: str,
    site_path: str,
) -> str:
    if "://" in hostname or "/" in hostname:
        raise ValueError("hostname must not include a scheme or path")

    normalized_path = site_path.strip("/")
    if not normalized_path:
        raise ValueError("site path must not be empty")

    url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{normalized_path}"
    response = session.get(
        url,
        headers={"Authorization": authorization},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(
            response_error(
                response,
                "Sites.Read.All may not be consented for the Azure CLI client. "
                "A tenant administrator must configure this; it is not a user "
                "access assignment.",
            )
        )

    site_id = response.json().get("id")
    if not site_id:
        raise RuntimeError("Microsoft Graph returned no site ID")
    return "Microsoft Graph returned the SharePoint site"


def run_check(name: str, check: Callable[[], str]) -> CheckResult:
    try:
        detail = check()
        result = CheckResult(name=name, passed=True, detail=detail)
    except Exception as error:
        result = CheckResult(name=name, passed=False, detail=str(error))

    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.name}: {result.detail}", flush=True)
    return result


def main() -> int:
    args = parse_args()
    try:
        config = resolve_config(args)
    except RuntimeError as error:
        print(f"Configuration failed: {error}", file=sys.stderr)
        return 2

    credential = DefaultAzureCredential()
    try:
        cognitive_token = credential.get_token(COGNITIVE_SERVICES_SCOPE).token
        graph_token = credential.get_token(GRAPH_SCOPE).token
    except Exception:
        print(
            "Authentication failed. Run `az login`, then run this command again.",
            file=sys.stderr,
        )
        return 2

    cognitive_authorization = f"Bearer {cognitive_token}"
    graph_authorization = f"Bearer {graph_token}"
    with requests.Session() as session:
        results = [
            run_check(
                "Microsoft Foundry project",
                lambda: check_foundry_project(
                    session, cognitive_authorization, config.project_endpoint
                ),
            ),
            run_check(
                "Model deployment",
                lambda: check_model_deployment(
                    session,
                    cognitive_authorization,
                    config.model_endpoint,
                    config.model_deployment,
                ),
            ),
            run_check(
                "SharePoint via Microsoft Graph",
                lambda: check_sharepoint_site(
                    session,
                    graph_authorization,
                    config.sharepoint_hostname,
                    config.sharepoint_site_path,
                ),
            ),
        ]

    passed = sum(result.passed for result in results)
    print(f"\nSummary: {passed}/{len(results)} checks passed.", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())