import unittest

from evaluate import score_result
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


if __name__ == "__main__":
    unittest.main()