import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import (
    AI_FOUNDRY_SCOPE,
    AdrCondition,
    AdrReview,
    ArchitectureDecisionRecord,
    Citation,
    ConformanceFinding,
    ConformanceReport,
    ReviewIssue,
    orchestrate_submission,
    run_reviewer_agent,
    validate_review,
)


def example_citation() -> Citation:
    return Citation(
        standard_id="STD-002",
        section="2. Workload authentication",
        source_file="STD-002-identity-and-access.md",
    )


def example_report() -> ConformanceReport:
    return ConformanceReport(
        submission_id="SUB-001",
        technology="Example Service",
        summary="The service has one identity gap.",
        findings=[
            ConformanceFinding(
                status="does_not_conform",
                requirement="Use workload identity.",
                analysis="The proposal uses a static password.",
                submission_evidence="Static username and password",
                citation=example_citation(),
                remediation="Replace the password with workload identity.",
            )
        ],
    )


def example_adr() -> ArchitectureDecisionRecord:
    return ArchitectureDecisionRecord(
        submission_id="SUB-001",
        technology="Example Service",
        title="Adopt Example Service",
        status="proposed",
        decision="approved_with_conditions",
        context="Example Service is under architecture review.",
        standards_assessment="The review identified one identity gap.",
        decision_statement="Approve after the identity gap is addressed.",
        decision_drivers=["Alignment with the workload identity standard."],
        conditions=[
            AdrCondition(
                action="Replace the static password with workload identity.",
                rationale="Static credentials do not meet the standard.",
                citation=example_citation(),
            )
        ],
        positive_consequences=["The service can proceed after remediation."],
        negative_consequences=["Identity integration requires additional work."],
    )


def passing_review() -> AdrReview:
    return AdrReview(
        submission_id="SUB-001",
        verdict="pass",
        unsupported_claims=[],
        omitted_findings=[],
        reviewed_adr=example_adr(),
    )


class OrchestratorTests(unittest.TestCase):
    @patch("run.run_reviewer_agent")
    @patch("run.run_adr_author_agent")
    @patch("run.run_standards_agent")
    def test_reviewer_receives_exact_report_and_draft(
        self,
        standards_agent: MagicMock,
        author_agent: MagicMock,
        reviewer_agent: MagicMock,
    ) -> None:
        report = example_report()
        draft = example_adr()
        review = passing_review()
        standards_agent.return_value = report
        author_agent.return_value = draft
        reviewer_agent.return_value = review

        result = orchestrate_submission(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "standards-agent",
            "author-agent",
            "reviewer-agent",
            Path("submission.md"),
            [],
        )

        self.assertIs(result.standards_report, report)
        self.assertIs(result.draft_adr, draft)
        self.assertIs(result.review, review)
        self.assertIs(reviewer_agent.call_args.args[3], report)
        self.assertIs(reviewer_agent.call_args.args[4], draft)


class ReviewValidationTests(unittest.TestCase):
    def test_rejects_omission_with_unknown_finding_index(self) -> None:
        review = passing_review().model_copy(
            update={
                "verdict": "revised",
                "omitted_findings": [
                    ReviewIssue(
                        category="omitted_finding",
                        severity="error",
                        draft_field="standards_assessment",
                        description="A standards gap was omitted.",
                        finding_indices=[2],
                    )
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "outside the standards report"):
            validate_review(review, example_report())

    def test_rejects_pass_verdict_when_issues_were_found(self) -> None:
        review = passing_review().model_copy(
            update={
                "unsupported_claims": [
                    ReviewIssue(
                        category="unsupported_claim",
                        severity="warning",
                        draft_field="context",
                        description="The report does not support this claim.",
                        finding_indices=[],
                    )
                ]
            }
        )

        with self.assertRaisesRegex(ValueError, "must use verdict revised"):
            validate_review(review, example_report())


class FoundryClientTests(unittest.TestCase):
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    def test_reviewer_uses_foundry_scope(
        self,
        credential_factory: MagicMock,
        project_client_factory: MagicMock,
    ) -> None:
        credential = MagicMock()
        credential_factory.return_value.__enter__.return_value = credential
        project_client = MagicMock()
        project_client_factory.return_value.__enter__.return_value = project_client
        openai_client = MagicMock()
        project_client.get_openai_client.return_value.__enter__.return_value = openai_client

        agent = project_client.agents.create_version.return_value
        agent.name = "reviewer-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = passing_review().model_dump_json()

        result = run_reviewer_agent(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "reviewer-agent",
            example_report(),
            example_adr(),
        )

        self.assertEqual(result.verdict, "pass")
        project_client_factory.assert_called_once_with(
            endpoint="https://example.services.ai.azure.com/api/projects/example",
            credential=credential,
            credential_scopes=[AI_FOUNDRY_SCOPE],
        )


if __name__ == "__main__":
    unittest.main()