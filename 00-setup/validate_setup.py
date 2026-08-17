#!/usr/bin/env python3
"""Validate workshop access to Microsoft Foundry and SharePoint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from azure.identity import DefaultAzureCredential

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate identity-based access required by the workshop."
    )
    parser.add_argument(
        "--project-endpoint",
        required=True,
        help="Microsoft Foundry project endpoint from the Bicep deployment output.",
    )
    parser.add_argument(
        "--model-endpoint",
        required=True,
        help="Model endpoint from the Bicep deployment output.",
    )
    parser.add_argument(
        "--model-deployment",
        required=True,
        help="Deployed model name from the Bicep deployment output.",
    )
    parser.add_argument(
        "--sharepoint-hostname",
        required=True,
        help="SharePoint hostname, without a scheme or path.",
    )
    parser.add_argument(
        "--sharepoint-site-path",
        required=True,
        help="Server-relative SharePoint site path, for example /sites/workshop.",
    )
    return parser.parse_args()


def response_error(response: requests.Response) -> str:
    request_id = response.headers.get("request-id") or response.headers.get(
        "x-ms-request-id", "not provided"
    )
    try:
        body: Any = response.json()
        message = body.get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        message = response.text.strip()

    detail = message[:240] if message else response.reason
    return f"HTTP {response.status_code}: {detail} (request ID: {request_id})"


def bearer_headers(credential: DefaultAzureCredential, scope: str) -> dict[str, str]:
    token = credential.get_token(scope)
    return {"Authorization": f"Bearer {token.token}"}


def check_foundry_project(
    session: requests.Session,
    credential: DefaultAzureCredential,
    endpoint: str,
) -> str:
    response = session.get(
        endpoint.rstrip("/"),
        headers=bearer_headers(credential, COGNITIVE_SERVICES_SCOPE),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(response_error(response))
    return "authenticated project request succeeded"


def check_model_deployment(
    session: requests.Session,
    credential: DefaultAzureCredential,
    endpoint: str,
    deployment_name: str,
) -> str:
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment_name}"
        "/chat/completions?api-version=2024-10-21"
    )
    response = session.post(
        url,
        headers={
            **bearer_headers(credential, COGNITIVE_SERVICES_SCOPE),
            "Content-Type": "application/json",
        },
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with the single word ready.",
                }
            ],
            "max_tokens": 8,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(response_error(response))

    body = response.json()
    if not body.get("choices"):
        raise RuntimeError("the model returned no choices")
    return "deployment returned a chat completion"


def check_sharepoint_site(
    session: requests.Session,
    credential: DefaultAzureCredential,
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
        headers=bearer_headers(credential, GRAPH_SCOPE),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(response_error(response))

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
    credential = DefaultAzureCredential()

    with requests.Session() as session:
        results = [
            run_check(
                "Microsoft Foundry project",
                lambda: check_foundry_project(
                    session, credential, args.project_endpoint
                ),
            ),
            run_check(
                "Model deployment",
                lambda: check_model_deployment(
                    session,
                    credential,
                    args.model_endpoint,
                    args.model_deployment,
                ),
            ),
            run_check(
                "SharePoint via Microsoft Graph",
                lambda: check_sharepoint_site(
                    session,
                    credential,
                    args.sharepoint_hostname,
                    args.sharepoint_site_path,
                ),
            ),
        ]

    passed = sum(result.passed for result in results)
    print(f"\nSummary: {passed}/{len(results)} checks passed.", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())