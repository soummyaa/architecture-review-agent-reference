import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import (
    AI_FOUNDRY_SCOPE,
    AdrCondition,
    ArchitectureDecisionRecord,
    Citation,
    ConformanceFinding,
    ConformanceReport,
    orchestrate_submission,
    run_adr_author_agent,
    validate_adr,
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
        decision_statement="Approve the proposal after its identity gap is addressed.",
        decision_drivers=["Alignment with the workload identity standard."],
        conditions=[
            AdrCondition(
                action="Replace the static password with workload identity.",
                rationale="Static credentials do not meet the applicable standard.",
                citation=example_citation(),
            )
        ],
        positive_consequences=["The service can proceed after remediation."],
        negative_consequences=["The identity integration requires additional work."],
    )


class OrchestratorTests(unittest.TestCase):
    @patch("run.run_adr_author_agent")
    @patch("run.run_standards_agent")
    def test_passes_typed_standards_report_to_adr_author(
        self,
        standards_agent: MagicMock,
        adr_author_agent: MagicMock,
    ) -> None:
        report = example_report()
        expected_adr = example_adr()
        standards_agent.return_value = report
        adr_author_agent.return_value = expected_adr
        standards = []

        actual_adr = orchestrate_submission(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "standards-agent",
            "author-agent",
            Path("submission.md"),
            standards,
            keep_agent=True,
        )

        self.assertIs(actual_adr, expected_adr)
        standards_agent.assert_called_once()
        self.assertIs(adr_author_agent.call_args.args[3], report)
        self.assertTrue(standards_agent.call_args.args[-1])
        self.assertTrue(adr_author_agent.call_args.args[-1])


class AdrValidationTests(unittest.TestCase):
    def test_rejects_condition_that_does_not_cite_a_standards_gap(self) -> None:
        report = example_report()
        adr = example_adr().model_copy(deep=True)
        adr.conditions[0].citation.section = "99. Invented section"

        with self.assertRaisesRegex(ValueError, "does not cite a standards gap"):
            validate_adr(adr, report)

    def test_rejects_unconditional_approval_when_report_has_gaps(self) -> None:
        report = example_report()
        adr = example_adr().model_copy(
            update={"decision": "approved", "conditions": []}
        )

        with self.assertRaisesRegex(ValueError, "cannot be approved"):
            validate_adr(adr, report)


class FoundryClientTests(unittest.TestCase):
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    def test_adr_author_uses_foundry_project_scope(
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
        agent.name = "author-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = example_adr().model_dump_json()

        result = run_adr_author_agent(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "author-agent",
            example_report(),
        )

        self.assertEqual(result.submission_id, "SUB-001")
        project_client_factory.assert_called_once_with(
            endpoint="https://example.services.ai.azure.com/api/projects/example",
            credential=credential,
            credential_scopes=[AI_FOUNDRY_SCOPE],
        )
        project_client.agents.delete_version.assert_called_once()
        openai_client.conversations.delete.assert_called_once()

        project_client.agents.delete_version.reset_mock()
        openai_client.conversations.delete.reset_mock()

        run_adr_author_agent(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "author-agent",
            example_report(),
            keep_agent=True,
        )

        project_client.agents.delete_version.assert_not_called()
        openai_client.conversations.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()