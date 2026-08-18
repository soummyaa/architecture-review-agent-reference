import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import (
    AI_FOUNDRY_SCOPE,
    AdrCondition,
    ArchitectureDecisionRecord,
    Citation,
    ConformanceFinding,
    ConformanceReport,
    build_adr_author_instructions,
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
                status="not_evidenced",
                requirement="Use workload identity.",
                analysis="The proposal does not describe workload authentication.",
                submission_evidence="No workload authentication details provided",
                citation=example_citation(),
                remediation="Document the workload authentication mechanism.",
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
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    @patch("run.run_adr_author_agent")
    @patch("run.run_standards_agent")
    def test_passes_typed_standards_report_to_adr_author(
        self,
        standards_agent: MagicMock,
        adr_author_agent: MagicMock,
        credential_factory: MagicMock,
        project_client_factory: MagicMock,
    ) -> None:
        report = example_report()
        expected_adr = example_adr()
        standards_agent.return_value = report
        adr_author_agent.return_value = expected_adr
        standards = []
        credential = credential_factory.return_value.__enter__.return_value
        project_client = project_client_factory.return_value.__enter__.return_value
        openai_client = project_client.get_openai_client.return_value.__enter__.return_value

        stderr = StringIO()
        with redirect_stderr(stderr):
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
        project_client_factory.assert_called_once_with(
            endpoint="https://example.services.ai.azure.com/api/projects/example",
            credential=credential,
            credential_scopes=[AI_FOUNDRY_SCOPE],
        )
        self.assertIs(standards_agent.call_args.args[0], project_client)
        self.assertIs(standards_agent.call_args.args[1], openai_client)
        self.assertIs(adr_author_agent.call_args.args[0], project_client)
        self.assertIs(adr_author_agent.call_args.args[1], openai_client)
        self.assertIs(adr_author_agent.call_args.args[4], report)
        self.assertTrue(standards_agent.call_args.args[-1])
        self.assertTrue(adr_author_agent.call_args.args[-1])
        self.assertIn("Standards agent completed in", stderr.getvalue())
        self.assertIn("ADR author agent completed in", stderr.getvalue())
        self.assertIn("Total orchestration completed in", stderr.getvalue())


class AdrValidationTests(unittest.TestCase):
    def test_author_instructions_state_decision_and_citation_policy(self) -> None:
        instructions = build_adr_author_instructions()

        self.assertIn(
            "even a single not_evidenced finding means approved_with_conditions rather than "
            "approved",
            instructions,
        )
        self.assertIn(
            "every condition must copy exactly the citation of the specific finding it addresses",
            instructions,
        )
        self.assertIn("an approved ADR has no conditions", instructions)
        self.assertIn("a rejected ADR has no conditions", instructions)
        self.assertIn(
            "a vendor that will not contractually guarantee data residency is remediable through "
            "contract terms",
            instructions,
        )
        self.assertIn(
            "a workload deployed on an unapproved hosting model in a single facility is "
            "structural",
            instructions,
        )

    def test_rejects_condition_that_does_not_cite_a_policy_finding(self) -> None:
        report = example_report()
        adr = example_adr().model_copy(deep=True)
        adr.conditions[0].citation.section = "99. Invented section"

        expected_message = (
            "ADR condition 1 does not cite a real gap finding; "
            "cited ('STD-002', '99. Invented section', 'STD-002-identity-and-access.md'); "
            "valid citations: [('STD-002', '2. Workload authentication', "
            "'STD-002-identity-and-access.md')]"
        )
        with self.assertRaisesRegex(ValueError, "does not cite a real gap finding") as error:
            validate_adr(adr, report)
        self.assertEqual(str(error.exception), expected_message)

    def test_rejects_unconditional_approval_when_report_has_gaps(self) -> None:
        report = example_report()
        adr = example_adr().model_copy(
            update={"decision": "approved", "conditions": []}
        )

        with self.assertRaisesRegex(ValueError, "requires every finding to conform"):
            validate_adr(adr, report)

    def test_accepts_approval_when_every_finding_conforms(self) -> None:
        report = example_report().model_copy(deep=True)
        report.findings[0].status = "conforms"
        adr = example_adr().model_copy(update={"decision": "approved", "conditions": []})

        validate_adr(adr, report)

    def test_rejects_approved_adr_with_conditions(self) -> None:
        report = example_report().model_copy(deep=True)
        report.findings[0].status = "conforms"
        adr = example_adr().model_copy(update={"decision": "approved"})

        with self.assertRaisesRegex(ValueError, "approved ADR cannot include conditions"):
            validate_adr(adr, report)

    def test_accepts_conditional_approval_for_partial_conformance(self) -> None:
        report = example_report().model_copy(deep=True)
        report.findings[0].status = "partially_conforms"

        validate_adr(example_adr(), report)

    def test_accepts_conditional_approval_for_remediable_non_conformance(self) -> None:
        report = example_report().model_copy(deep=True)
        report.findings[0].status = "does_not_conform"

        validate_adr(example_adr(), report)

    def test_rejects_rejected_adr_with_conditions(self) -> None:
        report = example_report().model_copy(deep=True)
        report.findings[0].status = "does_not_conform"
        adr = example_adr().model_copy(update={"decision": "rejected"})

        with self.assertRaisesRegex(ValueError, "rejected ADR cannot include conditions"):
            validate_adr(adr, report)

    def test_accepts_rejection_without_conditions(self) -> None:
        report = example_report().model_copy(deep=True)
        report.findings[0].status = "does_not_conform"
        adr = example_adr().model_copy(update={"decision": "rejected", "conditions": []})

        validate_adr(adr, report)

    def test_rejects_evidence_only_report_being_rejected(self) -> None:
        adr = example_adr().model_copy(update={"decision": "rejected", "conditions": []})

        with self.assertRaisesRegex(ValueError, "requires at least one does_not_conform"):
            validate_adr(adr, example_report())


class FoundryClientTests(unittest.TestCase):
    def test_adr_author_uses_shared_foundry_clients(self) -> None:
        project_client = MagicMock()
        openai_client = MagicMock()

        agent = project_client.agents.create_version.return_value
        agent.name = "author-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = example_adr().model_dump_json()

        stderr = StringIO()
        with redirect_stderr(stderr):
            result = run_adr_author_agent(
                project_client,
                openai_client,
                "example-model",
                "author-agent",
                example_report(),
            )

        self.assertEqual(result.submission_id, "SUB-001")
        self.assertIn(
            "ADR decision consistent with 0 material non-conformances, "
            "1 evidence gaps; 1 conditions",
            stderr.getvalue(),
        )
        project_client.agents.delete_version.assert_called_once()
        openai_client.conversations.delete.assert_called_once()

        project_client.agents.delete_version.reset_mock()
        openai_client.conversations.delete.reset_mock()

        run_adr_author_agent(
            project_client,
            openai_client,
            "example-model",
            "author-agent",
            example_report(),
            keep_agent=True,
        )

        project_client.agents.delete_version.assert_not_called()
        openai_client.conversations.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()