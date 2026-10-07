import unittest
from streamlit.testing.v1 import AppTest


class TestStreamlitJudgeScenarios(unittest.TestCase):
    """Test the 1-click judge scenarios via Streamlit AppTest harness."""

    def test_app_normal_query_scenario(self):
        at = AppTest.from_file("../app.py", default_timeout=30).run()
        # Click Normal Query button (index 0)
        at.button[0].click().run()
        self.assertEqual(at.session_state["current_scenario_id"], "normal")
        self.assertEqual(at.session_state["current_question"], "What was the total revenue in February?")
        self.assertIn("sales.csv", at.session_state["datasets"])
        
        output = at.session_state["latest_output"]
        self.assertIsNotNone(output)
        self.assertEqual(output.response_type, "ANSWERED")
        self.assertEqual(output.verification_status, "PASSED")
        self.assertIsNotNone(output.code)
        self.assertIn("sales.csv", output.code)

    def test_app_multi_table_scenario(self):
        at = AppTest.from_file("../app.py", default_timeout=30).run()
        # Click Multi-Table Join button (index 1)
        at.button[1].click().run()
        self.assertEqual(at.session_state["current_scenario_id"], "multi_table")
        self.assertIn("sales.csv", at.session_state["datasets"])
        self.assertIn("products.csv", at.session_state["datasets"])
        
        output = at.session_state["latest_output"]
        self.assertIsNotNone(output)
        self.assertEqual(output.response_type, "ANSWERED")
        self.assertEqual(output.verification_status, "PASSED")
        self.assertEqual(output.evidence.get("join_key"), "product_id")
        self.assertIn("merge", output.code)

    def test_app_data_trap_scenario(self):
        at = AppTest.from_file("../app.py", default_timeout=30).run()
        # Click Data Trap button (index 2)
        at.button[2].click().run()
        self.assertEqual(at.session_state["current_scenario_id"], "data_trap")
        
        output = at.session_state["latest_output"]
        self.assertIsNotNone(output)
        self.assertEqual(output.response_type, "REFUSED")
        self.assertIn("August", output.refusal_reason)
        self.assertEqual(output.verification_status, "REFUSED")
        self.assertIsNone(output.code)

    def test_app_duplicate_scenario(self):
        at = AppTest.from_file("../app.py", default_timeout=30).run()
        # Click Duplicate Impact button (index 3)
        at.button[3].click().run()
        self.assertEqual(at.session_state["current_scenario_id"], "duplicate")
        
        output = at.session_state["latest_output"]
        self.assertIsNotNone(output)
        self.assertIn(output.response_type, ["ANSWERED_WITH_ASSUMPTIONS", "ANSWERED"])
        self.assertTrue(len(output.assumptions) > 0)
        self.assertIn("duplicate", str(output.assumptions).lower())
        self.assertEqual(output.verification_status, "PASSED")
        self.assertIsNotNone(output.code)

    def test_app_currency_trap_scenario(self):
        at = AppTest.from_file("../app.py", default_timeout=30).run()
        # Click Currency Trap button (index 4)
        at.button[4].click().run()
        self.assertEqual(at.session_state["current_scenario_id"], "currency")
        
        output = at.session_state["latest_output"]
        self.assertIsNotNone(output)
        self.assertEqual(output.response_type, "REFUSED")
        self.assertTrue("currenc" in output.refusal_reason.lower() or "inr" in output.refusal_reason.lower())
        self.assertEqual(output.verification_status, "REFUSED")
        self.assertIsNone(output.code)

    def test_app_scenario_isolation_cycle(self):
        at = AppTest.from_file("../app.py", default_timeout=30).run()
        # Run Currency Trap first (should refuse)
        at.button[4].click().run()
        self.assertEqual(at.session_state["latest_output"].response_type, "REFUSED")

        # Now click Normal Query again -> MUST reset and succeed
        at.button[0].click().run()
        output = at.session_state["latest_output"]
        self.assertIsNotNone(output)
        self.assertEqual(output.response_type, "ANSWERED")
        self.assertEqual(output.verification_status, "PASSED")
        self.assertIsNotNone(output.code)


if __name__ == "__main__":
    unittest.main()
