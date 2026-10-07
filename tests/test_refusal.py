"""
Unit tests for VerifyAI Refusal Engine.
"""

import unittest
import pandas as pd
from traps.refusal import RefusalPayload, RefusalException
from core import VerifyAIEngine
from profiler.profiler import profile_multiple_datasets


class TestRefusalEngine(unittest.TestCase):
    def setUp(self):
        self.engine = VerifyAIEngine()
        self.df = pd.DataFrame({
            "order_id": [1, 2, 3],
            "revenue": [10.0, 20.0, 30.0],
            "date": ["2025-01-01", "2025-02-01", "2025-03-01"],
        })
        self.datasets = {"sales.csv": self.df}
        self.paths = {"sales.csv": "data/demo/sales.csv"}

    def test_refusal_payload_structure(self):
        payload = RefusalPayload(
            response_type="REFUSED",
            confidence="LOW",
            reason="August data unavailable.",
            data_issue="Temporal gap in date column.",
            what_would_be_needed="Upload records for August.",
        )
        fmt = payload.formatted_text()
        self.assertIn("REFUSED", fmt)
        self.assertIn("Reason: August data unavailable.", fmt)
        self.assertIn("Data issue:", fmt)
        self.assertIn("What would be needed:", fmt)

    def test_unsupported_column_refusal(self):
        # Asking for customer churn when churn column does not exist
        output = self.engine.run_pipeline(
            question="What is the average customer churn rate?",
            datasets=self.datasets,
            dataset_paths=self.paths,
        )
        self.assertEqual(output.response_type, "REFUSED")
        self.assertEqual(output.confidence, "LOW")
        self.assertIsNotNone(output.refusal_reason)
        self.assertIn("churn", output.refusal_reason.lower())

    def test_missing_month_refusal(self):
        # Sales data only has Jan-Mar, asking for August
        output = self.engine.run_pipeline(
            question="What was total revenue in August?",
            datasets=self.datasets,
            dataset_paths=self.paths,
        )
        self.assertEqual(output.response_type, "REFUSED")
        self.assertIn("August", output.refusal_reason)

    def test_code_execution_failure_refusal(self):
        # Simulate a query where code crashes
        from verifier.verifier import verify_code
        from profiler.profiler import MultiDatasetProfile

        bad_code = "import json; x = 1 / 0; print(json.dumps(x))"
        with self.assertRaises(RefusalException) as ctx:
            verify_code(bad_code, "test", "sales.csv", MultiDatasetProfile(datasets={}))
        self.assertEqual(ctx.exception.payload.response_type, "REFUSED")
        self.assertIn("could not be executed successfully", ctx.exception.payload.reason)


if __name__ == "__main__":
    unittest.main()
