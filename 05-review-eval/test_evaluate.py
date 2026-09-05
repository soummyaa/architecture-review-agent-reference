import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from evaluate import main, score_result
from run import ReviewIssue, ReviewWorkflowResult
from test_run import example_adr, example_report, passing_review


class EvaluationScoringTests(unittest.TestCase):
    def test_clean_review_scores_all_three_points(self) -> None:
        result = ReviewWorkflowResult(
            standards_report=example_report(),
            draft_adr=example_adr(),
            review=passing_review(),
        )

        checks = score_result(result)

        self.assertEqual(sum(checks.values()), 3)

    def test_flagged_draft_loses_the_matching_point(self) -> None:
        review = passing_review().model_copy(
            update={
                "verdict": "revised",
                "unsupported_claims": [
                    ReviewIssue(
                        category="unsupported_claim",
                        severity="warning",
                        draft_field="context",
                        description="The report does not support this claim.",
                        finding_indices=[],
                    )
                ],
            }
        )
        result = ReviewWorkflowResult(
            standards_report=example_report(),
            draft_adr=example_adr(),
            review=review,
        )

        checks = score_result(result)

        self.assertTrue(checks["reviewed_adr_valid"])
        self.assertFalse(checks["no_unsupported_claims"])
        self.assertEqual(sum(checks.values()), 2)

    @patch("evaluate.resolve_foundry_config", return_value=("endpoint", "model"))
    @patch("evaluate.load_research_allowlist", return_value=["example.com"])
    @patch("evaluate.load_standards", return_value=[])
    @patch("evaluate.orchestrate_submission")
    @patch("evaluate.parse_args")
    def test_main_evaluates_all_four_submissions(
        self,
        parse_args_mock,
        orchestrate_submission_mock,
        _load_standards_mock,
        _load_allowlist_mock,
        _resolve_config_mock,
    ) -> None:
        orchestrate_submission_mock.return_value = ReviewWorkflowResult(
            standards_report=example_report(),
            draft_adr=example_adr(),
            review=passing_review(),
        )
        with TemporaryDirectory() as directory:
            submissions_directory = Path(directory)
            for index in range(1, 5):
                (submissions_directory / f"SUB-00{index}-example.md").touch()
            parse_args_mock.return_value = SimpleNamespace(
                submissions_directory=submissions_directory,
                standards_directory=Path("standards"),
                skip_research=False,
                research_allowlist=Path("allowlist.json"),
                project_endpoint=None,
                model_deployment=None,
                resource_group=None,
                deployment_name="deployment",
                standards_agent_name="standards",
                research_agent_name="research",
                adr_author_agent_name="author",
                reviewer_agent_name="reviewer",
                web_search_connection_id="connection",
            )

            with redirect_stdout(StringIO()):
                exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(orchestrate_submission_mock.call_count, 4)


if __name__ == "__main__":
    unittest.main()