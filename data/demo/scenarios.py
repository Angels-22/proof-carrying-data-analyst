"""
Centralized Judge Scenario Configurations for VerifyAI.
Defines the 5 independent, deterministic hackathon demonstration scenarios.
"""

from typing import Any, Dict, List
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent

JUDGE_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "normal": {
        "id": "normal",
        "name": "1️⃣ Normal Query",
        "tag": "Standard Analytics",
        "badge_color": "#10b981",
        "title": "Normal Query — February Total Revenue",
        "question": "What was the total revenue in February?",
        "datasets": ["sales.csv"],
        "dataset_files": [
            str(BASE_DIR / "data" / "demo" / "clean" / "sales.csv")
        ],
        "expected_response_type": "ANSWERED",
        "expected_confidence": "HIGH",
        "description": "Calculates February revenue on a clean dataset with verified execution and calendar month assumption.",
        "expected_behavior": "Query Plan generated -> Validated -> Python code generated -> Subprocess Run 1 & 2 -> Verification PASSED.",
    },
    "multi_table": {
        "id": "multi_table",
        "name": "2️⃣ Multi-Table Join",
        "tag": "Relational Join",
        "badge_color": "#6366f1",
        "title": "Multi-Table Join — Top Revenue Category",
        "question": "Which product category generated the highest revenue?",
        "datasets": ["sales.csv", "products.csv"],
        "dataset_files": [
            str(BASE_DIR / "data" / "demo" / "clean" / "sales.csv"),
            str(BASE_DIR / "data" / "demo" / "clean" / "products.csv"),
        ],
        "expected_response_type": "ANSWERED",
        "expected_confidence": "HIGH",
        "description": "Joins transactional sales with product catalog on product_id to determine top revenue category.",
        "expected_behavior": "Auto-detects join key 'product_id', generates merge code, passes dual verification.",
    },
    "data_trap": {
        "id": "data_trap",
        "name": "3️⃣ Data Trap (Missing Month)",
        "tag": "Constructive Refusal",
        "badge_color": "#ef4444",
        "title": "Data Trap — Revenue Growth into Missing August",
        "question": "What was the revenue growth from July to August?",
        "datasets": ["sales_missing_august.csv"],
        "dataset_files": [
            str(BASE_DIR / "data" / "demo" / "missing_month" / "sales_missing_august.csv")
        ],
        "expected_response_type": "REFUSED",
        "expected_confidence": "LOW",
        "description": "Demonstrates constructive refusal when user requests revenue growth into an unavailable month (August).",
        "expected_behavior": "Pre-flight validator detects missing August data and constructively refuses with 3-part diagnostic (Reason, Data Issue, What Would Be Needed).",
    },
    "duplicate": {
        "id": "duplicate",
        "name": "4️⃣ Duplicate Impact",
        "tag": "Quality Policy",
        "badge_color": "#f59e0b",
        "title": "Duplicate Impact — Total Revenue with Duplicate Handling",
        "question": "What is the total revenue?",
        "datasets": ["sales_duplicates.csv"],
        "dataset_files": [
            str(BASE_DIR / "data" / "demo" / "duplicate" / "sales_duplicates.csv")
        ],
        "expected_response_type": "ANSWERED_WITH_ASSUMPTIONS",
        "expected_confidence": "MEDIUM",
        "description": "Demonstrates aggregation-sensitive duplicate row detection and explicit exclusion policy.",
        "expected_behavior": "Detects 3 exact duplicate rows, excludes them from total revenue, reports handling policy.",
    },
    "currency": {
        "id": "currency",
        "name": "5️⃣ Currency Trap",
        "tag": "Currency Conflict",
        "badge_color": "#ec4899",
        "title": "Currency Trap — Cross-Dataset Aggregation without Exchange Rate",
        "question": "What is the combined revenue across all datasets?",
        "datasets": ["sales_inr.csv", "sales_usd.csv"],
        "dataset_files": [
            str(BASE_DIR / "data" / "demo" / "currency" / "sales_inr.csv"),
            str(BASE_DIR / "data" / "demo" / "currency" / "sales_usd.csv"),
        ],
        "expected_response_type": "REFUSED",
        "expected_confidence": "LOW",
        "description": "Demonstrates refusal when user attempts aggregation across incompatible currencies (INR + USD).",
        "expected_behavior": "Refuses without inventing an exchange rate and explains required conversion parameters.",
    },
}
