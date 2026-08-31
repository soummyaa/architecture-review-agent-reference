#!/usr/bin/env python3
"""Run the synthetic submissions through the full review chain and verify decisions."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from run import (
    DEFAULT_ADR_AUTHOR_AGENT_NAME,
    DEFAULT_DEPLOYMENT_NAME,
    DEFAULT_RESEARCH_AGENT_NAME,
    DEFAULT_RESEARCH_ALLOWLIST,
    DEFAULT_REVIEWER_AGENT_NAME,
    DEFAULT_STANDARDS_AGENT_NAME,
    DEFAULT_STANDARDS_DIRECTORY,
    ArchitectureDecisionRecord,
    load_research_allowlist,
    load_standards,
    orchestrate_submission,
    resolve_foundry_config,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBMISSIONS_DIRECTORY = REPOSITORY_ROOT / "data" / "synthetic" / "submissions"


@dataclass(frozen=True)
class ExpectedDecision:
    submission_id: str
    file_name: str
    decision: str
    minimum_conditions: int = 0
    maximum_conditions: int | None = 0

    def describe(self) -> str:
        if self.maximum_conditions is None:
            condition_expectation = f"conditions>={self.minimum_conditions}"
        elif self.minimum_conditions == self.maximum_conditions:
            condition_expectation = f"conditions={self.minimum_conditions}"
        else:
            condition_expectation = (
                f"conditions={self.minimum_conditions}..{self.maximum_conditions}"
            )
        return f"decision={self.decision}, {condition_expectation}"


EXPECTED_DECISIONS = (
    ExpectedDecision(
        "SUB-001",
        "SUB-001-northwind-analytics-cloud.md",
        "approved_with_conditions",
        minimum_conditions=1,
        maximum_conditions=None,
    ),
    ExpectedDecision(
        "SUB-002",
        "SUB-002-quickship-document-service.md",
        "rejected",
    ),
    ExpectedDecision(
        "SUB-003",
        "SUB-003-member-notification-service.md",
        "approved",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify expected decisions for all synthetic submissions."
    )
    parser.add_argument("--project-endpoint", default=os.getenv("FOUNDRY_PROJECT_ENDPOINT"))
    parser.add_argument("--model-deployment", default=os.getenv("MODEL_DEPLOYMENT_NAME"))
    parser.add_argument("--resource-group", default=os.getenv("AZURE_RESOURCE_GROUP"))
    parser.add_argument(
        "--deployment-name",
        default=os.getenv("AZURE_DEPLOYMENT_NAME", DEFAULT_DEPLOYMENT_NAME),
    )
    parser.add_argument(
        "--standards-agent-name",
        default=os.getenv("FOUNDRY_STANDARDS_AGENT_NAME", DEFAULT_STANDARDS_AGENT_NAME),
    )
    parser.add_argument(
        "--adr-author-agent-name",
        default=os.getenv("FOUNDRY_ADR_AUTHOR_AGENT_NAME", DEFAULT_ADR_AUTHOR_AGENT_NAME),
    )
    parser.add_argument(
        "--research-agent-name",
        default=os.getenv("FOUNDRY_RESEARCH_AGENT_NAME", DEFAULT_RESEARCH_AGENT_NAME),
    )
    parser.add_argument(
        "--web-search-connection-id",
        default=os.getenv("FOUNDRY_WEB_SEARCH_CONNECTION_ID"),
    )
    parser.add_argument(
        "--research-allowlist",
        type=Path,
        default=DEFAULT_RESEARCH_ALLOWLIST,
    )
    parser.add_argument("--skip-research", action="store_true")
    parser.add_argument(
        "--reviewer-agent-name",
        default=os.getenv("FOUNDRY_REVIEWER_AGENT_NAME", DEFAULT_REVIEWER_AGENT_NAME),
    )
    parser.add_argument(
        "--submissions-directory",
        type=Path,
        default=DEFAULT_SUBMISSIONS_DIRECTORY,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--standards-directory",
        type=Path,
        default=DEFAULT_STANDARDS_DIRECTORY,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def decision_matches(
    expected: ExpectedDecision, adr: ArchitectureDecisionRecord
) -> bool:
    condition_count = len(adr.conditions)
    return (
        adr.submission_id == expected.submission_id
        and adr.decision == expected.decision
        and condition_count >= expected.minimum_conditions
        and (
            expected.maximum_conditions is None
            or condition_count <= expected.maximum_conditions
        )
    )


def main() -> int:
    args = parse_args()
    try:
        standards = load_standards(args.standards_directory)
        allowed_domains = (
            [] if args.skip_research else load_research_allowlist(args.research_allowlist)
        )
        project_endpoint, model_deployment = resolve_foundry_config(args)
    except Exception as error:
        print(f"Decision regression setup failed: {error}", file=sys.stderr)
        return 1

    failures = 0
    for expected in EXPECTED_DECISIONS:
        submission = args.submissions_directory / expected.file_name
        try:
            if not submission.is_file():
                raise RuntimeError(f"submission not found: {submission}")
            result = orchestrate_submission(
                project_endpoint,
                model_deployment,
                args.standards_agent_name,
                args.research_agent_name,
                args.adr_author_agent_name,
                args.reviewer_agent_name,
                submission,
                standards,
                args.web_search_connection_id,
                allowed_domains,
                skip_research=args.skip_research,
            )
            adr = result.review.reviewed_adr
            actual = f"decision={adr.decision}, conditions={len(adr.conditions)}"
            passed = decision_matches(expected, adr)
        except Exception as error:
            actual = f"workflow_error={error}"
            passed = False

        status = "PASS" if passed else "FAIL"
        print(
            f"{expected.submission_id}: {status} expected {expected.describe()}; "
            f"got {actual}"
        )
        if not passed:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
