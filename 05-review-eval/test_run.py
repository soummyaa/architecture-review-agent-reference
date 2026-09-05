import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import workshop_core
import run as review_run
from run import (
    AI_FOUNDRY_SCOPE,
    AdrCondition,
    AdrReview,
    ArchitectureDecisionRecord,
    Citation,
    ConformanceFinding,
    ConformanceReport,
    ReviewIssue,
    build_adr_author_instructions,
    build_reviewer_instructions,
    build_standards_instructions,
    orchestrate_submission,
    run_reviewer_agent,
    validate_review,
)
from workshop_core import configure_tracing, traced_span


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
                standard_evidence=(
                    "Service-to-service authentication must use workload identity issued by "
                    "the cloud platform."
                ),
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


class TracingTests(unittest.TestCase):
    @patch.object(workshop_core, "_TRACING_CONFIGURED", False)
    def test_missing_connection_string_leaves_tracing_disabled(self) -> None:
        self.assertFalse(configure_tracing(None))

    def test_shutdown_flushes_and_stops_logging_last(self) -> None:
        tracer_provider = MagicMock()
        meter_provider = MagicMock()
        logger_provider = MagicMock()
        providers = (tracer_provider, meter_provider, logger_provider)
        calls: list[str] = []
        for name, provider in zip(("tracer", "meter", "logger"), providers):
            provider.force_flush.side_effect = lambda name=name: calls.append(f"flush {name}")
            provider.shutdown.side_effect = lambda name=name: calls.append(f"shutdown {name}")

        workshop_core._shutdown_telemetry(*providers)

        for provider in providers:
            provider.force_flush.assert_called_once_with()
            provider.shutdown.assert_called_once_with()
        self.assertEqual(
            calls,
            [
                "flush tracer",
                "flush meter",
                "flush logger",
                "shutdown tracer",
                "shutdown meter",
                "shutdown logger",
            ],
        )

    @patch("opentelemetry.trace.get_tracer")
    @patch.object(workshop_core, "_TRACING_CONFIGURED", True)
    def test_traced_span_uses_documented_agent_name(self, get_tracer: MagicMock) -> None:
        @traced_span("Standards agent")
        def operation() -> str:
            return "complete"

        self.assertEqual(operation(), "complete")
        get_tracer.return_value.start_as_current_span.assert_called_once_with(
            "Standards agent"
        )


class OrchestratorTests(unittest.TestCase):
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    @patch("run.run_reviewer_agent")
    @patch("run.run_adr_author_agent")
    @patch("run.run_research_agent")
    @patch("run.run_standards_agent")
    def test_four_agent_chain_preserves_typed_handoffs(
        self,
        standards_agent: MagicMock,
        research_agent: MagicMock,
        author_agent: MagicMock,
        reviewer_agent: MagicMock,
        credential_factory: MagicMock,
        project_client_factory: MagicMock,
    ) -> None:
        report = example_report()
        research = MagicMock()
        draft = example_adr()
        review = passing_review()
        standards_agent.return_value = report
        research_agent.return_value = research
        author_agent.return_value = draft
        reviewer_agent.return_value = review

        credential = MagicMock()
        credential_factory.return_value.__enter__.return_value = credential
        project_client = MagicMock()
        project_client_factory.return_value.__enter__.return_value = project_client
        openai_client = MagicMock()
        project_client.get_openai_client.return_value.__enter__.return_value = openai_client

        result = orchestrate_submission(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "standards-agent",
            "research-agent",
            "author-agent",
            "reviewer-agent",
            Path("submission.md"),
            [],
            "connection-id",
            ["example.com"],
            keep_agent=True,
        )

        self.assertIs(result.standards_report, report)
        self.assertIs(result.draft_adr, draft)
        self.assertIs(result.review, review)
        self.assertIs(research_agent.call_args.args[4], report)
        self.assertIs(author_agent.call_args.args[4], report)
        self.assertIs(author_agent.call_args.args[5], research)
        self.assertIs(reviewer_agent.call_args.args[4], report)
        self.assertIs(reviewer_agent.call_args.args[5], draft)
        self.assertTrue(standards_agent.call_args.args[-1])
        self.assertTrue(research_agent.call_args.args[-1])
        self.assertTrue(author_agent.call_args.args[-1])
        self.assertTrue(reviewer_agent.call_args.args[-1])

    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    @patch("run.run_reviewer_agent")
    @patch("run.run_adr_author_agent")
    @patch("run.run_research_agent")
    @patch("run.run_standards_agent")
    def test_missing_connection_passes_empty_research_to_author(
        self,
        standards_agent: MagicMock,
        research_agent: MagicMock,
        author_agent: MagicMock,
        reviewer_agent: MagicMock,
        _credential_factory: MagicMock,
        _project_client_factory: MagicMock,
    ) -> None:
        report = example_report()
        standards_agent.return_value = report
        author_agent.return_value = example_adr()
        reviewer_agent.return_value = passing_review()

        stderr = StringIO()
        with redirect_stderr(stderr):
            orchestrate_submission(
                "https://example.services.ai.azure.com/api/projects/example",
                "example-model",
                "standards-agent",
                "research-agent",
                "author-agent",
                "reviewer-agent",
                Path("submission.md"),
                [],
                None,
                ["example.com"],
            )

        research_agent.assert_not_called()
        research = author_agent.call_args.args[5]
        self.assertEqual(research.submission_id, report.submission_id)
        self.assertEqual(research.technology, report.technology)
        self.assertEqual(research.claims, [])
        self.assertIn("no Bing or Bing Custom Search connection", stderr.getvalue())


class ReviewValidationTests(unittest.TestCase):
    def test_agent_instructions_state_validation_policies(self) -> None:
        author_instructions = build_adr_author_instructions()
        reviewer_instructions = build_reviewer_instructions()
        standards_instructions = " ".join(build_standards_instructions([]).split())

        self.assertIn("the submitted design stands", author_instructions)
        self.assertIn("the design itself must change", author_instructions)
        self.assertIn("Vendor-resolvable and contract-resolvable gaps are remediable", author_instructions)
        self.assertIn("Do not classify that integration change as replacement", author_instructions)
        self.assertIn("A not_evidenced finding is never structural", author_instructions)
        self.assertIn("a condition requiring the missing evidence", author_instructions)
        self.assertIn(
            "no unsupported claims and no omitted findings means verdict pass",
            reviewer_instructions,
        )
        self.assertIn("Section 3 applies only to vendor-hosted SaaS", standards_instructions)
        self.assertIn("cite it once with status not_applicable", standards_instructions)
        self.assertIn("only when an applicable requirement is genuinely unaddressed", standards_instructions)
        self.assertIn("A brief direct statement is evidence", standards_instructions)
        self.assertIn("do not invent additional components", standards_instructions)
        self.assertIn("three availability zones", standards_instructions)
        self.assertIn("schemas registered in a schema registry", standards_instructions)

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
    def test_reviewer_uses_shared_foundry_clients(self) -> None:
        project_client = MagicMock()
        openai_client = MagicMock()

        agent = project_client.agents.create_version.return_value
        agent.name = "reviewer-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = passing_review().model_dump_json()

        result = run_reviewer_agent(
            project_client,
            openai_client,
            "example-model",
            "reviewer-agent",
            example_report(),
            example_adr(),
        )

        self.assertEqual(result.verdict, "pass")
        definition = project_client.agents.create_version.call_args.kwargs["definition"]
        self.assertEqual(definition.temperature, 0.0)
        self.assertEqual(definition.top_p, 1.0)
        project_client.agents.delete_version.assert_called_once()
        openai_client.conversations.delete.assert_called_once()

        project_client.agents.delete_version.reset_mock()
        openai_client.conversations.delete.reset_mock()

        run_reviewer_agent(
            project_client,
            openai_client,
            "example-model",
            "reviewer-agent",
            example_report(),
            example_adr(),
            keep_agent=True,
        )

        project_client.agents.delete_version.assert_not_called()
        openai_client.conversations.delete.assert_not_called()


class CliErrorTests(unittest.TestCase):
    @patch("run.orchestrate_submission")
    @patch("run.resolve_foundry_config", return_value=("endpoint", "model"))
    @patch("run.load_research_allowlist", return_value=["example.com"])
    @patch("run.load_standards", return_value=[])
    @patch("run.parse_args")
    def test_main_includes_condition_notice_in_success_json(
        self,
        parse_args_mock: MagicMock,
        _load_standards_mock: MagicMock,
        _load_allowlist_mock: MagicMock,
        _resolve_config_mock: MagicMock,
        orchestrate_mock: MagicMock,
    ) -> None:
        parse_args_mock.return_value = SimpleNamespace(
            submission=Path(__file__),
            standards_directory=Path("standards"),
            skip_research=False,
            research_allowlist=Path("allowlist.json"),
            standards_agent_name="standards",
            research_agent_name="research",
            adr_author_agent_name="author",
            reviewer_agent_name="reviewer",
            web_search_connection_id="connection",
            keep_agent=False,
        )
        draft = example_adr()
        notice = 'Condition removed: "Retain TLS 1.3." cited conforming finding 003/3.'
        draft._processing_notices = [notice]
        orchestrate_mock.return_value = review_run.ReviewWorkflowResult(
            standards_report=example_report(),
            draft_adr=draft,
            review=passing_review(),
        )
        stdout = StringIO()

        with redirect_stdout(stdout), redirect_stderr(StringIO()):
            exit_code = review_run.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["notices"], [notice])

    @patch("run.parse_args")
    def test_main_emits_json_when_workflow_fails(self, parse_args_mock: MagicMock) -> None:
        parse_args_mock.return_value.submission = Path("missing-submission.md")
        stdout = StringIO()

        with redirect_stdout(stdout), redirect_stderr(StringIO()):
            exit_code = review_run.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["error"]["type"], "RuntimeError")
        self.assertIn("Submission not found", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()