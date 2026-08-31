#!/usr/bin/env python3
"""Render structured ADR content to DOCX and optionally upload it to SharePoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import requests
from azure.identity import DefaultAzureCredential
from docxtpl import DocxTemplate
from pydantic import BaseModel, ConfigDict

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
MODULE_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_PATH = MODULE_DIRECTORY / "adr-template.docx"
DEFAULT_OUTPUT_DIRECTORY = MODULE_DIRECTORY / "output"
REQUEST_TIMEOUT_SECONDS = 30


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standard_id: str
    section: str
    source_file: str


class AdrCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    rationale: str
    citation: Citation


class ArchitectureDecisionRecord(BaseModel):
    """Structured ADR contract produced by 03-orchestration."""

    model_config = ConfigDict(extra="forbid")

    submission_id: str
    technology: str
    title: str
    status: Literal["proposed"]
    decision: Literal["approved", "approved_with_conditions", "rejected"]
    context: str
    standards_assessment: str
    decision_statement: str
    decision_drivers: list[str]
    conditions: list[AdrCondition]
    positive_consequences: list[str]
    negative_consequences: list[str]


class SharePointWriteError(RuntimeError):
    """Raised when the optional SharePoint publishing step fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render structured ADR JSON to a local DOCX file."
    )
    parser.add_argument("adr_json", type=Path, help="ADR JSON produced by 03-orchestration.")
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help=f"DOCX template path (default: {DEFAULT_TEMPLATE_PATH}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output DOCX path (default: 06-adr-generation/output/<submission>-adr.docx).",
    )
    parser.add_argument(
        "--upload-to-sharepoint",
        action="store_true",
        help="After local rendering succeeds, optionally upload the DOCX to SharePoint.",
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
    parser.add_argument(
        "--sharepoint-folder",
        default="Architecture Reviews",
        help="Folder in the site's default document library.",
    )
    return parser.parse_args()


def load_adr(path: Path) -> ArchitectureDecisionRecord:
    if not path.is_file():
        raise RuntimeError(f"ADR JSON not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "review" in payload:
        try:
            payload = payload["review"]["reviewed_adr"]
        except (KeyError, TypeError) as error:
            raise RuntimeError("Reviewed workflow JSON contains no reviewed ADR") from error
    return ArchitectureDecisionRecord.model_validate(payload)


def render_adr(
    adr: ArchitectureDecisionRecord,
    template_path: Path,
    output_path: Path,
) -> Path:
    if not template_path.is_file():
        raise RuntimeError(f"ADR template not found: {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    template = DocxTemplate(str(template_path))
    template.render({"adr": adr.model_dump(mode="json")})
    template.save(str(output_path))
    return output_path


def graph_error(response: requests.Response, action: str) -> SharePointWriteError:
    request_id = response.headers.get("request-id") or response.headers.get(
        "x-ms-request-id", "not provided"
    )
    if response.status_code == 403:
        return SharePointWriteError(
            f"Microsoft Graph denied permission to {action} (HTTP 403, request ID: "
            f"{request_id}). Grant a Graph permission that allows writes to this "
            "SharePoint site, such as site-scoped write access or Sites.ReadWrite.All."
        )
    try:
        detail = response.json().get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        detail = response.text.strip()
    message = detail[:240] if detail else response.reason
    return SharePointWriteError(
        f"Microsoft Graph could not {action}: HTTP {response.status_code}: {message} "
        f"(request ID: {request_id})"
    )


def upload_to_sharepoint(
    document_path: Path,
    hostname: str,
    site_path: str,
    destination_folder: str,
) -> str:
    """Upload a rendered ADR to the site's default library as an optional step."""
    if not document_path.is_file():
        raise SharePointWriteError(f"Local DOCX not found: {document_path}")
    if "://" in hostname or "/" in hostname:
        raise SharePointWriteError("SharePoint hostname must not include a scheme or path")

    normalized_site_path = site_path.strip("/")
    if not normalized_site_path:
        raise SharePointWriteError("SharePoint site path must not be empty")
    normalized_folder = destination_folder.strip("/")
    remote_path = "/".join(
        part for part in (normalized_folder, document_path.name) if part
    )

    with DefaultAzureCredential() as credential, requests.Session() as session:
        try:
            access_token = credential.get_token(GRAPH_SCOPE).token
        except Exception as error:
            raise SharePointWriteError(
                "Could not acquire a Microsoft Graph token. Sign in with an identity "
                "that has write access to the target SharePoint site."
            ) from error

        headers = {"Authorization": f"Bearer {access_token}"}
        site_response = session.get(
            f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{normalized_site_path}",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if not site_response.ok:
            raise graph_error(site_response, "resolve the SharePoint site")
        site_id = site_response.json().get("id")
        if not site_id:
            raise SharePointWriteError("Microsoft Graph returned no SharePoint site ID")

        encoded_remote_path = quote(remote_path, safe="/")
        with document_path.open("rb") as document:
            upload_response = session.put(
                "https://graph.microsoft.com/v1.0/"
                f"sites/{site_id}/drive/root:/{encoded_remote_path}:/content",
                headers={
                    **headers,
                    "Content-Type": (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                },
                data=document,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        if not upload_response.ok:
            raise graph_error(upload_response, "write the ADR document")

    web_url = upload_response.json().get("webUrl")
    return str(web_url or remote_path)


def main() -> int:
    args = parse_args()
    try:
        adr = load_adr(args.adr_json)
        output_path = args.output or (
            DEFAULT_OUTPUT_DIRECTORY / f"{adr.submission_id}-adr.docx"
        )
        rendered_path = render_adr(adr, args.template, output_path)
    except Exception as error:
        print(f"Local ADR rendering failed: {error}", file=sys.stderr)
        return 1

    print(f"Local ADR rendered: {rendered_path}")
    if not args.upload_to_sharepoint:
        return 0

    if not args.sharepoint_hostname or not args.sharepoint_site_path:
        print(
            "Optional SharePoint upload failed: set SHAREPOINT_HOSTNAME and "
            "SHAREPOINT_SITE_PATH, or pass both command-line options. "
            f"The local DOCX remains available at {rendered_path}.",
            file=sys.stderr,
        )
        return 2

    try:
        destination = upload_to_sharepoint(
            rendered_path,
            args.sharepoint_hostname,
            args.sharepoint_site_path,
            args.sharepoint_folder,
        )
    except SharePointWriteError as error:
        print(
            f"Optional SharePoint upload failed: {error} "
            f"The local DOCX remains available at {rendered_path}.",
            file=sys.stderr,
        )
        return 2

    print(f"SharePoint upload completed: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())