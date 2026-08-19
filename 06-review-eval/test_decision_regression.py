import argparse
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import decision_regression
from run import ReviewWorkflowResult
from test_run import example_adr, example_report, passing_review


class DecisionRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.args = argparse.Namespace(
            project_endpoint="https://example.services.ai.azure.com/api/projects/example",
            model_deployment="example-model",
            resource_group=None,
            deployment_name="architecture-review-setup",
            standards_agent_name="standards-agent",
            adr_author_agent_name="author-agent",
            reviewer_agent_name="reviewer-agent",
            submissions_directory=Path("submissions"),
            standards_directory=Path("standards"),
        )

    @staticmethod
    def workflow_result(
        submission_id: str, decision: str, condition_count: int
    ) -> ReviewWorkflowResult:
        conditions = example_adr().conditions * condition_count
        adr = example_adr().model_copy(
            update={
                "submission_id": submission_id,
                "decision": decision,
                "conditions": conditions,
            }
        )
        report = example_report().model_copy(update={"submission_id": submission_id})
        review = passing_review().model_copy(
            update={"submission_id": submission_id, "reviewed_adr": adr}
        )
        return ReviewWorkflowResult(
            standards_report=report,
            draft_adr=adr,
            review=review,
        )

    @patch("decision_regression.Path.is_file", return_value=True)
    @patch("decision_regression.orchestrate_submission")
    @patch("decision_regression.resolve_foundry_config")
    @patch("decision_regression.load_standards", return_value=[])
    @patch("decision_regression.parse_args")
    def test_expected_decisions_exit_zero(
        self,
        parse_args: MagicMock,
        _load_standards: MagicMock,
        resolve_foundry_config: MagicMock,
        orchestrate_submission: MagicMock,
        _is_file: MagicMock,
    ) -> None:
        parse_args.return_value = self.args
        resolve_foundry_config.return_value = (
            self.args.project_endpoint,
            self.args.model_deployment,
        )
        orchestrate_submission.side_effect = [
            self.workflow_result("SUB-001", "approved_with_conditions", 1),
            self.workflow_result("SUB-002", "rejected", 0),
            self.workflow_result("SUB-003", "approved", 0),
        ]
        output = StringIO()

        with redirect_stdout(output):
            exit_code = decision_regression.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue().count(": PASS expected "), 3)

    @patch("decision_regression.Path.is_file", return_value=True)
    @patch("decision_regression.orchestrate_submission")
    @patch("decision_regression.resolve_foundry_config")
    @patch("decision_regression.load_standards", return_value=[])
    @patch("decision_regression.parse_args")
    def test_mismatch_exits_nonzero_and_prints_expected_and_actual(
        self,
        parse_args: MagicMock,
        _load_standards: MagicMock,
        resolve_foundry_config: MagicMock,
        orchestrate_submission: MagicMock,
        _is_file: MagicMock,
    ) -> None:
        parse_args.return_value = self.args
        resolve_foundry_config.return_value = (
            self.args.project_endpoint,
            self.args.model_deployment,
        )
        orchestrate_submission.side_effect = [
            self.workflow_result("SUB-001", "approved", 0),
            self.workflow_result("SUB-002", "rejected", 0),
            self.workflow_result("SUB-003", "approved", 0),
        ]
        output = StringIO()

        with redirect_stdout(output):
            exit_code = decision_regression.main()

        self.assertEqual(exit_code, 1)
        self.assertIn(
            "SUB-001: FAIL expected decision=approved_with_conditions, conditions>=1; "
            "got decision=approved, conditions=0",
            output.getvalue(),
        )
        self.assertIn("SUB-002: PASS", output.getvalue())
        self.assertIn("SUB-003: PASS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
