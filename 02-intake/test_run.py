import argparse
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import GRAPH_SCOPE, download_from_sharepoint, parse_submission, read_submission

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIRECTORY = REPOSITORY_ROOT / "data" / "synthetic" / "submissions"


class IntakeParsingTests(unittest.TestCase):
    def test_parses_all_existing_synthetic_submissions(self) -> None:
        submissions = [
            parse_submission(path.read_text(encoding="utf-8"))
            for path in sorted(SUBMISSIONS_DIRECTORY.glob("SUB-*.md"))
        ]

        self.assertEqual(
            [submission.submission_id for submission in submissions],
            ["SUB-001", "SUB-002", "SUB-003"],
        )
        self.assertIsNotNone(submissions[0].commercials)
        self.assertIsNotNone(submissions[1].support_model)

    def test_rejects_local_and_sharepoint_sources_together(self) -> None:
        args = argparse.Namespace(
            submission=SUBMISSIONS_DIRECTORY / "SUB-001-northwind-analytics-cloud.md",
            sharepoint_item_path="Submissions/SUB-001.md",
            sharepoint_hostname="example.sharepoint.com",
            sharepoint_site_path="/sites/workshop",
        )

        with self.assertRaisesRegex(ValueError, "not both"):
            read_submission(args)


class SharePointReaderTests(unittest.TestCase):
    @patch("run.requests.Session")
    @patch("run.DefaultAzureCredential")
    def test_reads_markdown_with_graph_scope(
        self,
        credential_factory: MagicMock,
        session_factory: MagicMock,
    ) -> None:
        credential = credential_factory.return_value.__enter__.return_value
        credential.get_token.return_value.token = "token"
        session = session_factory.return_value.__enter__.return_value
        site_response = MagicMock(ok=True)
        site_response.json.return_value = {"id": "site-id"}
        content_response = MagicMock(ok=True, content=b"# Submission")
        session.get.side_effect = [site_response, content_response]

        content = download_from_sharepoint(
            "example.sharepoint.com",
            "/sites/workshop",
            "Submissions/SUB-001.md",
        )

        self.assertEqual(content, "# Submission")
        credential.get_token.assert_called_once_with(GRAPH_SCOPE)


if __name__ == "__main__":
    unittest.main()