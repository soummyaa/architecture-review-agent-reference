import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run import create_app


class AuthHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            RUN_LOG_PATH=Path(self.temporary_directory.name) / "auth-runs.jsonl",
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def sign_in_session(self) -> str:
        with self.client.session_transaction() as browser_session:
            browser_session["user"] = {
                "object_id": "00000000-0000-0000-0000-000000000001",
                "display_name": "Workshop Participant",
            }
            browser_session["form_token"] = "form-token"
        return "form-token"

    def test_review_requires_sign_in(self) -> None:
        response = self.client.post("/review")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/sign-in")

    def test_rejects_submission_outside_synthetic_allowlist(self) -> None:
        form_token = self.sign_in_session()

        response = self.client.post(
            "/review",
            data={"form_token": form_token, "submission": "../../README.md"},
        )

        self.assertEqual(response.status_code, 400)

    @patch("run.run_agent_chain")
    def test_records_identity_with_reviewed_adr(self, run_agent_chain) -> None:
        run_agent_chain.return_value = {
            "title": "Adopt Example Service",
            "decision": "approved",
        }
        form_token = self.sign_in_session()

        response = self.client.post(
            "/review",
            data={
                "form_token": form_token,
                "submission": "SUB-001-northwind-analytics-cloud.md",
                "skip_research": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        run_agent_chain.assert_called_once()
        self.assertTrue(run_agent_chain.call_args.kwargs["skip_research"])
        record = json.loads(Path(self.app.config["RUN_LOG_PATH"]).read_text())
        self.assertEqual(record["user"]["display_name"], "Workshop Participant")
        self.assertEqual(
            record["user"]["object_id"],
            "00000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(record["reviewed_adr"]["decision"], "approved")


if __name__ == "__main__":
    unittest.main()