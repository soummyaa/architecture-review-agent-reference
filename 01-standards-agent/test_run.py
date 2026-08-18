import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import (
    Citation,
    ConformanceFinding,
    ConformanceReport,
    load_standards,
    review_submission,
    resolve_foundry_config,
    validate_citations,
)


class StandardsCatalogTests(unittest.TestCase):
    @patch("run.load_deployment_outputs")
    def test_explicit_foundry_config_skips_deployment_lookup(self, load_outputs) -> None:
        args = argparse.Namespace(
            project_endpoint="https://example.services.ai.azure.com/api/projects/example",
            model_deployment="example-model",
            resource_group="rg-architecture-review-workshop",
            deployment_name="architecture-review-setup",
        )

        config = resolve_foundry_config(args)

        self.assertEqual(config, (args.project_endpoint, args.model_deployment))
        load_outputs.assert_not_called()

    def test_loads_identifier_and_numbered_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "STD-999-example.md"
            path.write_text(
                "# STD-999: Example\n\n## Requirements\n\n### 1. First rule\nText\n",
                encoding="utf-8",
            )

            standards = load_standards(Path(directory))

        self.assertEqual(standards[0].standard_id, "STD-999")
        self.assertEqual(standards[0].sections, frozenset({"1. First rule"}))

    def test_rejects_citation_to_unknown_section(self) -> None:
        standards = load_standards(
            Path(__file__).resolve().parents[1] / "data" / "synthetic" / "standards"
        )
        report = ConformanceReport(
            submission_id="SUB-001",
            technology="Example",
            summary="Example summary",
            findings=[
                ConformanceFinding(
                    status="does_not_conform",
                    requirement="Use approved authentication.",
                    analysis="The proposal uses a password.",
                    submission_evidence="Static password",
                    citation=Citation(
                        standard_id="STD-002",
                        section="99. Invented section",
                        source_file="STD-002-identity-and-access.md",
                    ),
                    remediation="Use workload identity.",
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "unknown section"):
            validate_citations(report, standards)


class AgentLifecycleTests(unittest.TestCase):
    @patch("run.AIProjectClient")
    @patch("run.DefaultAzureCredential")
    def test_cleanup_is_default_and_keep_agent_skips_it(
        self,
        credential_factory: MagicMock,
        project_client_factory: MagicMock,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        standards = load_standards(repository_root / "data" / "synthetic" / "standards")
        submission = (
            repository_root
            / "data"
            / "synthetic"
            / "submissions"
            / "SUB-001-northwind-analytics-cloud.md"
        )
        report = ConformanceReport(
            submission_id="SUB-001",
            technology="Northwind Analytics Cloud",
            summary="One finding.",
            findings=[
                ConformanceFinding(
                    status="conforms",
                    requirement="Use an approved hosting model.",
                    analysis="The proposal uses SaaS.",
                    submission_evidence="Vendor-hosted SaaS",
                    citation=Citation(
                        standard_id="STD-001",
                        section="1. Approved hosting models",
                        source_file="STD-001-cloud-hosting-and-residency.md",
                    ),
                    remediation="",
                )
            ],
        )
        credential_factory.return_value.__enter__.return_value = MagicMock()
        project_client = MagicMock()
        project_client_factory.return_value.__enter__.return_value = project_client
        openai_client = MagicMock()
        project_client.get_openai_client.return_value.__enter__.return_value = openai_client
        openai_client.vector_stores.create.return_value.id = "vector-store-1"
        openai_client.vector_stores.files.upload_and_poll.return_value.id = "file-1"
        agent = project_client.agents.create_version.return_value
        agent.name = "standards-agent"
        agent.version = "1"
        openai_client.conversations.create.return_value.id = "conversation-1"
        openai_client.responses.create.return_value.output_text = report.model_dump_json()

        review_submission(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "standards-agent",
            submission,
            standards,
        )

        project_client.agents.delete_version.assert_called_once()
        openai_client.conversations.delete.assert_called_once()
        openai_client.vector_stores.delete.assert_called_once()
        openai_client.files.delete.assert_called()

        project_client.agents.delete_version.reset_mock()
        openai_client.conversations.delete.reset_mock()
        openai_client.vector_stores.delete.reset_mock()
        openai_client.files.delete.reset_mock()

        review_submission(
            "https://example.services.ai.azure.com/api/projects/example",
            "example-model",
            "standards-agent",
            submission,
            standards,
            keep_agent=True,
        )

        project_client.agents.delete_version.assert_not_called()
        openai_client.conversations.delete.assert_not_called()
        openai_client.vector_stores.delete.assert_not_called()
        openai_client.files.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()