#!/usr/bin/env python3
"""Run standards review, optional research, and ADR authoring as an explicit workflow."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research import (
    DEFAULT_RESEARCH_AGENT_NAME,
    DEFAULT_RESEARCH_ALLOWLIST,
    build_research_instructions,
    load_research_allowlist,
    normalize_allowed_domains,
    run_research_agent,
    url_is_allowed,
    validate_research,
)
from workshop_core import (
    AI_FOUNDRY_SCOPE,
    DEFAULT_ADR_AUTHOR_AGENT_NAME,
    DEFAULT_STANDARDS_AGENT_NAME,
    DEFAULT_STANDARDS_DIRECTORY,
    AdrCondition,
    ArchitectureDecisionRecord,
    Citation,
    ConformanceFinding,
    ConformanceReport,
    ResearchCitation,
    ResearchClaim,
    StandardDocument,
    TechnologyResearch,
    build_adr_author_instructions,
    build_standards_instructions,
    load_standards,
    run_adr_author_agent,
    run_standards_agent,
    validate_adr,
    validate_citations,
)

DEFAULT_DEPLOYMENT_NAME = "architecture-review-setup"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review one submission and author structured ADR content."
    )
    parser.add_argument("submission", type=Path, help="Path to a submission Markdown file.")
    parser.add_argument(
        "--project-endpoint",
        default=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        help="Microsoft Foundry project endpoint (or FOUNDRY_PROJECT_ENDPOINT).",
    )
    parser.add_argument(
        "--model-deployment",
        default=os.getenv("MODEL_DEPLOYMENT_NAME"),
        help="Model deployment name (or MODEL_DEPLOYMENT_NAME).",
    )
    parser.add_argument(
        "--resource-group",
        default=os.getenv("AZURE_RESOURCE_GROUP"),
        help="Deployment resource group used to discover outputs.",
    )
    parser.add_argument(
        "--deployment-name",
        default=os.getenv("AZURE_DEPLOYMENT_NAME", DEFAULT_DEPLOYMENT_NAME),
        help=f"Infrastructure deployment name (default: {DEFAULT_DEPLOYMENT_NAME}).",
    )
    parser.add_argument(
        "--standards-agent-name",
        default=os.getenv("FOUNDRY_STANDARDS_AGENT_NAME", DEFAULT_STANDARDS_AGENT_NAME),
        help=f"Standards agent name (default: {DEFAULT_STANDARDS_AGENT_NAME}).",
    )
    parser.add_argument(
        "--adr-author-agent-name",
        default=os.getenv("FOUNDRY_ADR_AUTHOR_AGENT_NAME", DEFAULT_ADR_AUTHOR_AGENT_NAME),
        help=f"ADR author agent name (default: {DEFAULT_ADR_AUTHOR_AGENT_NAME}).",
    )
    parser.add_argument(
        "--research-agent-name",
        default=os.getenv("FOUNDRY_RESEARCH_AGENT_NAME", DEFAULT_RESEARCH_AGENT_NAME),
        help=f"Research agent name (default: {DEFAULT_RESEARCH_AGENT_NAME}).",
    )
    parser.add_argument(
        "--web-search-connection-id",
        default=os.getenv("FOUNDRY_WEB_SEARCH_CONNECTION_ID"),
        help="Foundry web-search project connection ID.",
    )
    parser.add_argument(
        "--research-allowlist",
        type=Path,
        default=DEFAULT_RESEARCH_ALLOWLIST,
        help=f"JSON domain allowlist (default: {DEFAULT_RESEARCH_ALLOWLIST}).",
    )
    parser.add_argument(
        "--skip-research",
        action="store_true",
        help="Skip external research when its allowlist or connection is not ready.",
    )
    parser.add_argument(
        "--keep-agent",
        action="store_true",
        help="Keep agents and run resources for inspection in the Microsoft Foundry portal.",
    )
    parser.add_argument(
        "--standards-directory",
        type=Path,
        default=DEFAULT_STANDARDS_DIRECTORY,
        help=(
            "Path to the standards library used to ground the standards agent "
            f"(default: {DEFAULT_STANDARDS_DIRECTORY})."
        ),
    )
    return parser.parse_args()


def load_deployment_outputs(resource_group: str | None, deployment_name: str) -> dict[str, str]:
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
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
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


def resolve_foundry_config(args: argparse.Namespace) -> tuple[str, str]:
    outputs = (
        {}
        if args.project_endpoint and args.model_deployment
        else load_deployment_outputs(args.resource_group, args.deployment_name)
    )
    project_endpoint = args.project_endpoint or outputs.get("foundryProjectEndpoint")
    model_deployment = args.model_deployment or outputs.get("modelDeploymentName")
    missing = [
        name
        for name, value in (
            ("project endpoint", project_endpoint),
            ("model deployment", model_deployment),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing {', '.join(missing)}. Set AZURE_RESOURCE_GROUP to read deployment "
            "outputs, set environment variables, or pass command-line overrides."
        )
    return project_endpoint, model_deployment


def orchestrate_submission(
    project_endpoint: str,
    model_deployment: str,
    standards_agent_name: str,
    research_agent_name: str,
    adr_author_agent_name: str,
    submission_path: Path,
    standards: list[StandardDocument],
    web_search_connection_id: str | None,
    allowed_domains: list[str],
    skip_research: bool = False,
    keep_agent: bool = False,
) -> ArchitectureDecisionRecord:
    total_started = time.perf_counter()
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
            credential_scopes=[AI_FOUNDRY_SCOPE],
        ) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        standards_started = time.perf_counter()
        standards_report = run_standards_agent(
            project_client,
            openai_client,
            model_deployment,
            standards_agent_name,
            submission_path,
            standards,
            keep_agent,
        )
        print(
            f"Standards agent completed in {time.perf_counter() - standards_started:.2f}s",
            file=sys.stderr,
        )

        research: TechnologyResearch | None = None
        if skip_research:
            print("Research agent skipped", file=sys.stderr)
        else:
            if not web_search_connection_id:
                raise RuntimeError(
                    "Missing web-search connection ID. Set FOUNDRY_WEB_SEARCH_CONNECTION_ID, "
                    "pass --web-search-connection-id, or use --skip-research."
                )
            research_started = time.perf_counter()
            research = run_research_agent(
                project_client,
                openai_client,
                model_deployment,
                research_agent_name,
                standards_report,
                web_search_connection_id,
                allowed_domains,
                keep_agent,
            )
            print(
                f"Research agent completed in {time.perf_counter() - research_started:.2f}s",
                file=sys.stderr,
            )

        adr_started = time.perf_counter()
        draft_adr = run_adr_author_agent(
            project_client,
            openai_client,
            model_deployment,
            adr_author_agent_name,
            standards_report,
            research,
            keep_agent,
        )
        print(
            f"ADR author agent completed in {time.perf_counter() - adr_started:.2f}s",
            file=sys.stderr,
        )

    print(
        f"Total orchestration completed in {time.perf_counter() - total_started:.2f}s",
        file=sys.stderr,
    )
    return draft_adr


def main() -> int:
    args = parse_args()
    try:
        if not args.submission.is_file():
            raise RuntimeError(f"Submission not found: {args.submission}")
        standards = load_standards(args.standards_directory)
        allowed_domains = (
            [] if args.skip_research else load_research_allowlist(args.research_allowlist)
        )
        project_endpoint, model_deployment = resolve_foundry_config(args)
        adr = orchestrate_submission(
            project_endpoint,
            model_deployment,
            args.standards_agent_name,
            args.research_agent_name,
            args.adr_author_agent_name,
            args.submission,
            standards,
            args.web_search_connection_id,
            allowed_domains,
            skip_research=args.skip_research,
            keep_agent=args.keep_agent,
        )
    except Exception as error:
        print(f"Architecture review orchestration failed: {error}", file=sys.stderr)
        return 1

    print(adr.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
