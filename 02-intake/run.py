#!/usr/bin/env python3
"""Convert a synthetic technology submission into a typed intake contract."""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, ConfigDict

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
REQUEST_TIMEOUT_SECONDS = 30
METADATA_PATTERN = re.compile(r"^\*\*(.+?):\*\*\s*(.+)$", re.MULTILINE)
SECTION_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)


class IntakeSubmission(BaseModel):
    """The stable contract produced from an unstructured submission."""

    model_config = ConfigDict(extra="forbid")

    submission_id: str
    submitted_by: str
    date_submitted: date
    requested_decision_date: date
    technology: str
    business_driver: str
    proposed_usage: str
    hosting_and_deployment: str
    integration_approach: str
    identity_and_access: str
    security_posture: str
    support_model: str | None = None
    commercials: str | None = None
    data_export: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a synthetic Markdown submission to typed JSON."
    )
    parser.add_argument(
        "submission",
        type=Path,
        nargs="?",
        help="Local synthetic submission Markdown file.",
    )
    parser.add_argument(
        "--sharepoint-item-path",
        help="Optional path in the SharePoint site's default document library.",
    )
    parser.add_argument(
        "--sharepoint-hostname",
        default=os.getenv("SHAREPOINT_HOSTNAME"),
        help="SharePoint hostname (or SHAREPOINT_HOSTNAME).",
    )
    parser.add_argument(
        "--sharepoint-site-path",
        default=os.getenv("SHAREPOINT_SITE_PATH"),
        help="SharePoint site path (or SHAREPOINT_SITE_PATH).",
    )
    return parser.parse_args()


def split_sections(markdown: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group(1).strip().lower()] = markdown[start:end].strip()
    return sections


def require_value(values: dict[str, str], name: str, source: str) -> str:
    value = values.get(name)
    if not value:
        raise ValueError(f"Submission is missing {source}: {name}")
    return value


def parse_submission(markdown: str) -> IntakeSubmission:
    metadata = {
        name.strip().lower(): value.strip()
        for name, value in METADATA_PATTERN.findall(markdown)
    }
    sections = split_sections(markdown)

    # These names deliberately mirror the headings in data/synthetic/submissions.
    return IntakeSubmission(
        submission_id=require_value(metadata, "submission id", "metadata"),
        submitted_by=require_value(metadata, "submitted by", "metadata"),
        date_submitted=date.fromisoformat(
            require_value(metadata, "date submitted", "metadata")
        ),
        requested_decision_date=date.fromisoformat(
            require_value(metadata, "requested decision date", "metadata")
        ),
        technology=require_value(sections, "technology being proposed", "section"),
        business_driver=require_value(sections, "business driver", "section"),
        proposed_usage=require_value(sections, "proposed usage", "section"),
        hosting_and_deployment=require_value(
            sections, "hosting and deployment", "section"
        ),
        integration_approach=require_value(
            sections, "integration approach", "section"
        ),
        identity_and_access=require_value(sections, "identity and access", "section"),
        security_posture=require_value(sections, "security posture", "section"),
        support_model=sections.get("support model"),
        commercials=sections.get("commercials"),
        data_export=require_value(sections, "data export", "section"),
    )


def graph_error(response: requests.Response, action: str) -> RuntimeError:
    request_id = response.headers.get("request-id") or response.headers.get(
        "x-ms-request-id", "not provided"
    )
    if response.status_code == 403:
        return RuntimeError(
            f"Microsoft Graph denied permission to {action} (HTTP 403, request ID: "
            f"{request_id}). The signed-in identity needs read access to the SharePoint site."
        )
    try:
        detail = response.json().get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        detail = response.text.strip()
    message = detail[:240] if detail else response.reason
    return RuntimeError(
        f"Microsoft Graph could not {action}: HTTP {response.status_code}: {message} "
        f"(request ID: {request_id})"
    )


def download_from_sharepoint(hostname: str, site_path: str, item_path: str) -> str:
    """Read one Markdown file from the site's default document library."""
    if "://" in hostname or "/" in hostname:
        raise ValueError("SharePoint hostname must not include a scheme or path")
    normalized_site_path = site_path.strip("/")
    normalized_item_path = item_path.strip("/")
    if not normalized_site_path or not normalized_item_path:
        raise ValueError("SharePoint site path and item path must not be empty")

    with DefaultAzureCredential() as credential, requests.Session() as session:
        token = credential.get_token(GRAPH_SCOPE).token
        headers = {"Authorization": f"Bearer {token}"}
        site_response = session.get(
            f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{normalized_site_path}",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if not site_response.ok:
            raise graph_error(site_response, "resolve the SharePoint site")
        site_id = site_response.json().get("id")
        if not site_id:
            raise RuntimeError("Microsoft Graph returned no SharePoint site ID")

        # Graph follows this drive-item URL to the file content.
        content_response = session.get(
            "https://graph.microsoft.com/v1.0/"
            f"sites/{site_id}/drive/root:/{normalized_item_path}:/content",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if not content_response.ok:
            raise graph_error(content_response, "read the submission")
        return content_response.content.decode("utf-8")


def read_submission(args: argparse.Namespace) -> str:
    if args.submission and args.sharepoint_item_path:
        raise ValueError("Choose a local submission or --sharepoint-item-path, not both")
    if args.submission:
        if not args.submission.is_file():
            raise RuntimeError(f"Submission not found: {args.submission}")
        return args.submission.read_text(encoding="utf-8")
    if not args.sharepoint_item_path:
        raise ValueError("Provide a local submission or --sharepoint-item-path")
    if not args.sharepoint_hostname or not args.sharepoint_site_path:
        raise ValueError(
            "SharePoint input requires SHAREPOINT_HOSTNAME and SHAREPOINT_SITE_PATH, "
            "or both command-line options"
        )
    return download_from_sharepoint(
        args.sharepoint_hostname,
        args.sharepoint_site_path,
        args.sharepoint_item_path,
    )


def main() -> int:
    args = parse_args()
    try:
        submission = parse_submission(read_submission(args))
    except Exception as error:
        print(f"Intake failed: {error}", file=sys.stderr)
        return 1

    print(submission.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())