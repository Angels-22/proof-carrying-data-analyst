"""
Unit tests for VerifyAI Profiler Engine.
"""

import unittest
import pandas as pd
import numpy as np

from profiler.schema_detector import detect_schema
from profiler.duplicate_detector import detect_duplicates
from profiler.missing_detector import detect_missing_values
from profiler.date_detector import detect_dates
from profiler.currency_detector import detect_currency
from profiler.unit_detector import detect_units
from profiler.relationship_detector import detect_relationships
from profiler.profiler import profile_dataset, profile_multiple_datasets


class TestProfilerEngine(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "order_id": ["O1", "O2", "O3", "O3"],
            "date": ["2025-01-05", "2025-01-12", "2025-02-15", "2025-02-15"],
            "product_id": ["P101", "P102", "P101", "P101"],
            "revenue": [100.5, 200.0, 150.0, 150.0],
            "price_usd": ["$100.5", "$200.0", "$150.0", "$150.0"],
            "weight_kg": [2.5, 3.0, 1.2, 1.2],
            "notes": ["ok", None, "done", "done"],
        })

    def test_schema_detector(self):
        schema = detect_schema(self.df)
        self.assertIn("revenue", schema["numeric_columns"])
        self.assertIn("order_id", schema["columns"])
        self.assertEqual(schema["stats"]["revenue"]["min"], 100.5)

    def test_duplicate_detector(self):
        dup_info = detect_duplicates(self.df)
        self.assertTrue(dup_info["has_duplicates"])
        self.assertEqual(dup_info["duplicate_count"], 1)
        self.assertEqual(dup_info["duplicate_percentage"], 25.0)

    def test_missing_detector(self):
        missing_info = detect_missing_values(self.df)
        self.assertTrue(missing_info["has_missing"])
        self.assertEqual(missing_info["missing_counts"]["notes"], 1)

    def test_date_detector(self):
        date_info = detect_dates(self.df)
        self.assertIn("date", date_info["date_columns"])
        self.assertEqual(date_info["date_ranges"]["date"]["min"], "2025-01-05")
        self.assertEqual(date_info["date_ranges"]["date"]["max"], "2025-02-15")

    def test_currency_detector(self):
        curr_info = detect_currency(self.df, filename="sales.csv")
        self.assertEqual(curr_info["primary_currency"], "USD")

    def test_unit_detector(self):
        unit_info = detect_units(self.df)
        self.assertIn("weight_kg", unit_info["column_units"])
        self.assertEqual(unit_info["column_units"]["weight_kg"], "kilograms")

    def test_relationship_detector(self):
        df_prod = pd.DataFrame({
            "product_id": ["P101", "P102", "P103"],
            "name": ["A", "B", "C"],
        })
        dfs = {"sales": self.df, "products": df_prod}
        rel = detect_relationships(dfs)
        self.assertEqual(len(rel["relationships"]), 1)
        self.assertEqual(rel["relationships"][0]["join_key"], "product_id")

    def test_full_profile(self):
        profile = profile_dataset(self.df, "test_sales.csv")
        self.assertEqual(profile.rows, 4)
        self.assertEqual(profile.duplicates, 1)
        self.assertTrue(profile.has_missing)


if __name__ == "__main__":
    unittest.main()
