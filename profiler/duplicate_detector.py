"""
Duplicate row detector for VerifyAI.
Identifies exact duplicate rows and potential impact on aggregation metrics.
"""

from typing import Any, Dict, List
import pandas as pd


def detect_duplicates(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detects duplicate rows and provides a clear policy advisory.
    """
    row_count = len(df)
    if row_count == 0:
        return {
            "duplicate_count": 0,
            "duplicate_percentage": 0.0,
            "has_duplicates": False,
            "policy_advisory": "Dataset is empty.",
            "duplicate_sample_indices": [],
        }

    duplicate_mask = df.duplicated(keep="first")
    duplicate_count = int(duplicate_mask.sum())
    duplicate_pct = round((duplicate_count / row_count) * 100.0, 2)
    has_dups = duplicate_count > 0

    sample_indices = df[duplicate_mask].index[:5].tolist()

    if has_dups:
        advisory = (
            f"Detected {duplicate_count} duplicate row(s) ({duplicate_pct}% of dataset). "
            f"Aggregation queries (sums, counts) may double-count values unless deduplication is clarified. "
            f"VerifyAI policy: Never silently drop duplicates; acknowledge retained duplicates or evaluate explicit deduplication."
        )
    else:
        advisory = "Dataset contains no duplicate rows. All records are unique."

    return {
        "duplicate_count": duplicate_count,
        "duplicate_percentage": duplicate_pct,
        "has_duplicates": has_dups,
        "policy_advisory": advisory,
        "duplicate_sample_indices": sample_indices,
    }
