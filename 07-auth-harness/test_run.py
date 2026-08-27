import json
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run import create_app, execute_run, run_agent_chain


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

    @patch("run.subprocess.Popen")
    def test_agent_chain_reports_each_stage(self, process_factory: MagicMock) -> None:
        process = process_factory.return_value
        process.stdout = io.StringIO(
            json.dumps({"review": {"reviewed_adr": {"decision": "approved"}}})
        )
        process.stderr = io.StringIO(
            "Standards agent: complete\n"
            "Research agent: complete\n"
            "ADR author agent: complete\n"
        )
        process.wait.return_value = 0
        stages: list[str] = []

        result = run_agent_chain(Path("submission.md"), False, stages.append)

        self.assertEqual(
            stages, ["standards", "research", "adr_author", "reviewer"]
        )
        self.assertEqual(result["decision"], "approved")

    @patch("run.threading.Thread")
    def test_submission_creates_queued_run(self, thread: MagicMock) -> None:
        form_token = self.sign_in_session()

        response = self.client.post(
            "/review",
            data={
                "form_token": form_token,
                "submission": "SUB-001-northwind-analytics-cloud.md",
                "skip_research": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRegex(response.headers["Location"], r"/runs/[0-9a-f-]+$")
        thread.return_value.start.assert_called_once()
        status = self.client.get(response.headers["Location"])
        self.assertIn(b"Queued", status.data)

    @patch("run.run_agent_chain")
    def test_completed_run_records_identity_and_displays_adr(
        self, run_agent_chain: MagicMock
    ) -> None:
        run_agent_chain.return_value = {
            "title": "Adopt Example Service",
            "decision": "approved",
        }
        runs = {
            "run-1": {
                "run_id": "run-1",
                "status": "queued",
                "submission": "SUB-001-northwind-analytics-cloud.md",
                "user": {
                    "object_id": "00000000-0000-0000-0000-000000000001",
                    "display_name": "Workshop Participant",
                },
            }
        }
        execute_run(
            "run-1",
            "SUB-001-northwind-analytics-cloud.md",
            Path("submission.md"),
            True,
            runs["run-1"]["user"],
            runs,
            threading.Lock(),
            Path(self.app.config["RUN_LOG_PATH"]),
        )

        self.assertEqual(runs["run-1"]["status"], "complete")
        record = json.loads(Path(self.app.config["RUN_LOG_PATH"]).read_text())
        self.assertEqual(record["run_id"], "run-1")
        self.assertEqual(record["user"]["display_name"], "Workshop Participant")
        self.assertEqual(
            record["user"]["object_id"],
            "00000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(record["reviewed_adr"]["decision"], "approved")

        self.sign_in_session()
        self.app.config["RUNS"].update(runs)
        status = self.client.get("/runs/run-1")
        self.assertIn(b"Adopt Example Service", status.data)

    @patch("run.run_agent_chain")
    def test_failed_run_surfaces_downstream_error(
        self, run_agent_chain: MagicMock
    ) -> None:
        run_agent_chain.side_effect = RuntimeError("Reviewer agent returned no text")
        runs = {
            "run-2": {
                "run_id": "run-2",
                "status": "queued",
                "submission": "SUB-002-quickship-document-service.md",
                "user": {
                    "object_id": "00000000-0000-0000-0000-000000000001",
                    "display_name": "Workshop Participant",
                },
            }
        }
        execute_run(
            "run-2",
            "SUB-002-quickship-document-service.md",
            Path("submission.md"),
            False,
            runs["run-2"]["user"],
            runs,
            threading.Lock(),
            Path(self.app.config["RUN_LOG_PATH"]),
        )

        self.assertEqual(runs["run-2"]["status"], "failed")
        self.assertEqual(runs["run-2"]["error"], "Reviewer agent returned no text")

        self.sign_in_session()
        self.app.config["RUNS"].update(runs)
        status = self.client.get("/runs/run-2")
        self.assertIn(b"Reviewer agent returned no text", status.data)


if __name__ == "__main__":
    unittest.main()