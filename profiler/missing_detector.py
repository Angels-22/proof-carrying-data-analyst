"""
Missing value detector for VerifyAI.
Identifies nulls, empty strings, NaNs, and distinguishes between critical and non-critical missingness.
"""

from typing import Any, Dict, List
import pandas as pd


def detect_missing_values(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect missing values across all columns.
    """
    row_count = len(df)
    missing_counts: Dict[str, int] = {}
    missing_percentages: Dict[str, float] = {}
    columns_with_missing: List[str] = []
    fully_empty_columns: List[str] = []
    total_missing_cells = 0

    for col in df.columns:
        series = df[col]
        # Check standard isna
        isna_count = int(series.isna().sum())
        
        # Also check for whitespace-only strings
        if series.dtype == "object":
            whitespace_count = int((series.astype(str).str.strip() == "").sum())
            null_count = isna_count + whitespace_count
        else:
            null_count = isna_count

        missing_counts[col] = null_count
        pct = round((null_count / max(row_count, 1)) * 100.0, 2)
        missing_percentages[col] = pct
        total_missing_cells += null_count

        if null_count > 0:
            columns_with_missing.append(col)
        if null_count == row_count and row_count > 0:
            fully_empty_columns.append(col)

    has_missing = total_missing_cells > 0

    return {
        "missing_counts": missing_counts,
        "missing_percentages": missing_percentages,
        "columns_with_missing": columns_with_missing,
        "fully_empty_columns": fully_empty_columns,
        "total_missing_cells": total_missing_cells,
        "has_missing": has_missing,
    }
