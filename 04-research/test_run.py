import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import (
    AI_FOUNDRY_SCOPE,
    ResearchCitation,
    ResearchClaim,
    TechnologyResearch,
    normalize_allowed_domains,
    read_submission,
    research_submission,
    url_is_allowed,
    validate_research,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIRECTORY = REPOSITORY_ROOT / "data" / "synthetic" / "submissions"


class AllowlistTests(unittest.TestCase):
    def test_allows_exact_domains_and_subdomains_only(self) -> None:
        domains = ["example.com"]

        self.assertTrue(url_is_allowed("https://example.com/product", domains))
        self.assertTrue(url_is_allowed("https://docs.example.com/product", domains))
        self.assertFalse(url_is_allowed("http://example.com/product", domains))
        self.assertFalse(url_is_allowed("https://example.com.evil.test/product", domains))

    def test_normalizes_and_deduplicates_domains(self) -> None:
        self.assertEqual(
            normalize_allowed_domains(["Example.com", "example.com."]),
            ["example.com"],
        )
        with self.assertRaisesRegex(ValueError, "without a scheme or path"):
            normalize_allowed_domains(["https://example.com"])

    def test_rejects_citation_outside_allowlist(self) -> None:
        research = TechnologyResearch(
            submission_id="SUB-001",
            technology="Example Technology",
            summary="One external claim was found.",
            claims=[
                ResearchClaim(
                    claim="An unsupported external claim.",
                    citation=ResearchCitation(
                        title="Unapproved source",
                        url="https://unapproved.example/claim",
                    ),
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "outside the allowlist"):
            validate_research(
                research,
                "SUB-001",
                "Example Technology",
                ["approved.example"],
            )


class SubmissionTests(unittest.TestCase):
    def test_reads_existing_synthetic_submission(self) -> None:
        submission_id, technology, _ = read_submission(
            SUBMISSIONS_DIRECTORY / "SUB-003-member-notification-service.md"
        )

        self.assertEqual(submission_id, "SUB-003")
        self.assertEqual(technology, "Member Notification Service")


class FoundryClientTests(unittest.TestCase):
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    def test_agent_uses_foundry_scope_and_domain_filter(
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
        agent.name = "research-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = TechnologyResearch(
            submission_id="SUB-001",
            technology="Example Technology",
            summary="No approved external sources were found.",
            claims=[],
        ).model_dump_json()

        result = research_submission(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "research-agent",
            "SUB-001",
            "Example Technology",
            "Synthetic submission text",
            ["learn.microsoft.com"],
        )

        self.assertEqual(result.claims, [])
        project_client_factory.assert_called_once_with(
            endpoint="https://example.services.ai.azure.com/api/projects/example",
            credential=credential,
            credential_scopes=[AI_FOUNDRY_SCOPE],
        )
        definition = project_client.agents.create_version.call_args.kwargs["definition"]
        serialized_tool = definition.tools[0].as_dict()
        self.assertEqual(
            serialized_tool["filters"]["allowed_domains"],
            ["learn.microsoft.com"],
        )
        self.assertNotIn("custom_search_configuration", serialized_tool)


if __name__ == "__main__":
    unittest.main()