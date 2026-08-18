#!/usr/bin/env python3
"""Run the three synthetic submissions and report simple reviewer scores."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from run import (
    DEFAULT_ADR_AUTHOR_AGENT_NAME,
    DEFAULT_DEPLOYMENT_NAME,
    DEFAULT_REVIEWER_AGENT_NAME,
    DEFAULT_STANDARDS_AGENT_NAME,
    DEFAULT_STANDARDS_DIRECTORY,
    ReviewWorkflowResult,
    load_standards,
    orchestrate_submission,
    resolve_foundry_config,
    validate_adr,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBMISSIONS_DIRECTORY = REPOSITORY_ROOT / "data" / "synthetic" / "submissions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score all three synthetic review cases.")
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


def score_result(result: ReviewWorkflowResult) -> dict[str, bool]:
    try:
        validate_adr(result.review.reviewed_adr, result.standards_report)
        reviewed_adr_valid = True
    except ValueError:
        reviewed_adr_valid = False
    return {
        "reviewed_adr_valid": reviewed_adr_valid,
        "no_unsupported_claims": not result.review.unsupported_claims,
        "no_omitted_findings": not result.review.omitted_findings,
    }


def main() -> int:
    args = parse_args()
    submissions = sorted(args.submissions_directory.glob("SUB-*.md"))
    if len(submissions) != 3:
        print(
            f"Evaluation requires exactly three synthetic submissions; found {len(submissions)}",
            file=sys.stderr,
        )
        return 1

    try:
        standards = load_standards(args.standards_directory)
        project_endpoint, model_deployment = resolve_foundry_config(args)
    except Exception as error:
        print(f"Evaluation setup failed: {error}", file=sys.stderr)
        return 1

    total_score = 0
    maximum_score = len(submissions) * 3
    for submission in submissions:
        try:
            result = orchestrate_submission(
                project_endpoint,
                model_deployment,
                args.standards_agent_name,
                args.adr_author_agent_name,
                args.reviewer_agent_name,
                submission,
                standards,
            )
            checks = score_result(result)
            score = sum(checks.values())
            submission_id = result.standards_report.submission_id
            detail = ", ".join(
                f"{name}={'pass' if passed else 'fail'}" for name, passed in checks.items()
            )
        except Exception as error:
            score = 0
            submission_id = submission.stem.split("-", maxsplit=2)[0:2]
            submission_id = "-".join(submission_id)
            detail = f"workflow_error={error}"
        total_score += score
        print(f"{submission_id}: {score}/3 ({detail})")

    print(f"Total: {total_score}/{maximum_score}")
    return 0 if total_score == maximum_score else 1


if __name__ == "__main__":
    sys.exit(main())