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
    ResearchCitation,
    ResearchClaim,
    TechnologyResearch,
    build_adr_author_instructions,
    build_standards_instructions,
    normalize_allowed_domains,
    orchestrate_submission,
    run_adr_author_agent,
    run_research_agent,
    url_is_allowed,
    validate_adr,
    validate_research,
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


def example_research() -> TechnologyResearch:
    return TechnologyResearch(
        submission_id="SUB-001",
        technology="Example Service",
        summary="One approved external source was found.",
        claims=[
            ResearchClaim(
                claim="Example Service publishes deployment guidance.",
                citation=ResearchCitation(
                    title="Deployment guidance",
                    url="https://docs.example.com/deployment",
                ),
            )
        ],
    )


class ResearchValidationTests(unittest.TestCase):
    def test_allows_exact_domains_and_subdomains_only(self) -> None:
        domains = normalize_allowed_domains(["Example.com", "example.com."])

        self.assertEqual(domains, ["example.com"])
        self.assertTrue(url_is_allowed("https://docs.example.com/product", domains))
        self.assertFalse(url_is_allowed("https://example.com.evil.test/product", domains))

    def test_rejects_research_citation_outside_allowlist(self) -> None:
        research = example_research().model_copy(deep=True)
        research.claims[0].citation.url = "https://unapproved.example/deployment"

        with self.assertRaisesRegex(ValueError, "outside the allowlist"):
            validate_research(research, example_report(), ["example.com"])


class OrchestratorTests(unittest.TestCase):
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    @patch("run.run_adr_author_agent")
    @patch("run.run_research_agent")
    @patch("run.run_standards_agent")
    def test_passes_typed_reports_through_three_agent_chain(
        self,
        standards_agent: MagicMock,
        research_agent: MagicMock,
        adr_author_agent: MagicMock,
        credential_factory: MagicMock,
        project_client_factory: MagicMock,
    ) -> None:
        report = example_report()
        research = example_research()
        expected_adr = example_adr()
        standards_agent.return_value = report
        research_agent.return_value = research
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
                "research-agent",
                "author-agent",
                Path("submission.md"),
                standards,
                "connection-id",
                ["example.com"],
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
        self.assertIs(research_agent.call_args.args[0], project_client)
        self.assertIs(research_agent.call_args.args[1], openai_client)
        self.assertIs(research_agent.call_args.args[4], report)
        self.assertIs(adr_author_agent.call_args.args[0], project_client)
        self.assertIs(adr_author_agent.call_args.args[1], openai_client)
        self.assertIs(adr_author_agent.call_args.args[4], report)
        self.assertIs(adr_author_agent.call_args.args[5], research)
        self.assertTrue(standards_agent.call_args.args[-1])
        self.assertTrue(research_agent.call_args.args[-1])
        self.assertTrue(adr_author_agent.call_args.args[-1])
        self.assertIn("Standards agent completed in", stderr.getvalue())
        self.assertIn("Research agent completed in", stderr.getvalue())
        self.assertIn("ADR author agent completed in", stderr.getvalue())
        self.assertIn("Total orchestration completed in", stderr.getvalue())

    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    @patch("run.run_adr_author_agent")
    @patch("run.run_research_agent")
    @patch("run.run_standards_agent")
    def test_skip_research_passes_no_research_to_author(
        self,
        standards_agent: MagicMock,
        research_agent: MagicMock,
        adr_author_agent: MagicMock,
        credential_factory: MagicMock,
        project_client_factory: MagicMock,
    ) -> None:
        standards_agent.return_value = example_report()
        adr_author_agent.return_value = example_adr()

        stderr = StringIO()
        with redirect_stderr(stderr):
            orchestrate_submission(
                "https://example.services.ai.azure.com/api/projects/example",
                "example-model",
                "standards-agent",
                "research-agent",
                "author-agent",
                Path("submission.md"),
                [],
                None,
                [],
                skip_research=True,
            )

        research_agent.assert_not_called()
        self.assertIsNone(adr_author_agent.call_args.args[5])
        self.assertIn("Research agent skipped", stderr.getvalue())


class AdrValidationTests(unittest.TestCase):
    def test_standards_instructions_limit_saas_conditions_to_saas(self) -> None:
        instructions = " ".join(build_standards_instructions([]).split())

        self.assertIn(
            "omit requirements that do not apply to the proposed technology",
            instructions,
        )
        self.assertIn(
            "STD-001 Section 3 applies only to vendor-hosted SaaS",
            instructions,
        )
        self.assertIn(
            "It is not a valid citation for an internally built or self-hosted workload",
            instructions,
        )
        self.assertIn(
            "return at most one finding for each applicable numbered standard section",
            instructions,
        )
        self.assertIn(
            "schemas registered in a schema registry are documented schemas",
            instructions,
        )

    def test_author_instructions_state_decision_and_citation_policy(self) -> None:
        instructions = build_adr_author_instructions()
        normalized = " ".join(instructions.split())

        self.assertIn(
            "even a single not_evidenced finding means approved_with_conditions rather than "
            "approved",
            normalized,
        )
        self.assertIn(
            "copy exactly that finding's citation into the condition",
            normalized,
        )
        self.assertIn("An approved ADR has no conditions", normalized)
        self.assertIn("A rejected ADR has no conditions", normalized)
        self.assertIn(
            "A vendor that will not contractually guarantee data residency is remediable through "
            "contract terms",
            normalized,
        )
        self.assertIn(
            "A workload on an unapproved hosting model in a single facility is "
            "structural",
            normalized,
        )
        self.assertIn("The standards library is authoritative", normalized)
        self.assertIn("External research is supporting context only", normalized)
        self.assertIn("inform the ADR context and consequences", normalized)
        self.assertIn("never let it override, weaken, or replace a standards finding", normalized)
        self.assertIn("Research must not change the decision or the conditions", normalized)
        self.assertIn("every finding conforms. An approved ADR has no conditions", normalized)
        self.assertIn(
            "every non-conforming or evidence-gap finding is remediable through",
            normalized,
        )
        self.assertIn("Create one condition for each does_not_conform", normalized)
        self.assertIn(
            "at least one non-conformance is structural, meaning the proposed design itself must",
            normalized,
        )
        self.assertIn(
            "Configuration of credentials, federation, roles, privileged-access workflows, "
            "exports, encryption, resilience, logging, and contract commitments is remediable",
            normalized,
        )
        self.assertIn(
            "Do not classify a finding as structural merely because its status is "
            "does_not_conform",
            normalized,
        )
        self.assertIn(
            "For a vendor-hosted SaaS proposal, missing residency commitments, subprocessor "
            "terms, local administrator controls, credential handling, access reviews, export "
            "capabilities, and operational controls are remediable conditions",
            normalized,
        )
        self.assertIn(
            "A vendor-hosted SaaS proposal remains approved_with_conditions when its gaps include "
            "a missing contractual residency guarantee, follow-the-sun support access, local "
            "administrator accounts, a static connector credential, incomplete portable export",
            normalized,
        )
        self.assertIn(
            "An unapproved self-managed colocation hosting model and a single-facility deployment "
            "are structural",
            normalized,
        )
        self.assertIn("Follow this decision order exactly", normalized)
        self.assertIn(
            "Never infer rejection from the number of findings or from does_not_conform status "
            "alone",
            normalized,
        )
        self.assertIn(
            "Keeping vendor-hosted SaaS while changing its contract terms, account controls, "
            "credential configuration, export process, or connector governance is not a design "
            "change",
            normalized,
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
    def test_research_agent_uses_shared_clients_and_domain_filter(self) -> None:
        project_client = MagicMock()
        openai_client = MagicMock()
        agent = project_client.agents.create_version.return_value
        agent.name = "research-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = example_research().model_dump_json()

        stderr = StringIO()
        with redirect_stderr(stderr):
            result = run_research_agent(
                project_client,
                openai_client,
                "example-model",
                "research-agent",
                example_report(),
                "connection-id",
                ["example.com"],
            )

        self.assertEqual(result.claims, example_research().claims)
        definition = project_client.agents.create_version.call_args.kwargs["definition"]
        serialized_tool = definition.tools[0].as_dict()
        self.assertEqual(serialized_tool["filters"]["allowed_domains"], ["example.com"])
        self.assertEqual(
            serialized_tool["custom_search_configuration"]["project_connection_id"],
            "connection-id",
        )
        self.assertIn("Validated 1 research citations", stderr.getvalue())

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
                example_research(),
            )

        self.assertEqual(result.submission_id, "SUB-001")
        self.assertIn(
            "ADR decision consistent with 0 material non-conformances, "
            "1 evidence gaps; 1 conditions",
            stderr.getvalue(),
        )
        author_input = openai_client.responses.create.call_args.kwargs["input"]
        self.assertIn('"technology_research"', author_input)
        self.assertIn("https://docs.example.com/deployment", author_input)

        run_adr_author_agent(
            project_client,
            openai_client,
            "example-model",
            "author-agent",
            example_report(),
            None,
        )
        skipped_research_input = openai_client.responses.create.call_args.kwargs["input"]
        self.assertNotIn('"technology_research"', skipped_research_input)
        self.assertIn('"findings"', skipped_research_input)

        self.assertEqual(project_client.agents.delete_version.call_count, 2)
        self.assertEqual(openai_client.conversations.delete.call_count, 2)

        project_client.agents.delete_version.reset_mock()
        openai_client.conversations.delete.reset_mock()

        run_adr_author_agent(
            project_client,
            openai_client,
            "example-model",
            "author-agent",
            example_report(),
            example_research(),
            keep_agent=True,
        )

        project_client.agents.delete_version.assert_not_called()
        openai_client.conversations.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()