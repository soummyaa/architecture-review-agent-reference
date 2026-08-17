import argparse
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from run import (
    Citation,
    ConformanceFinding,
    ConformanceReport,
    load_standards,
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


if __name__ == "__main__":
    unittest.main()