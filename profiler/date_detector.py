"""
Date detector for VerifyAI.
Detects datetime columns, date ranges, missing intervals/months, and format ambiguities.
"""

from typing import Any, Dict, List, Optional
import pandas as pd


def detect_dates(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect and inspect date columns, ranges, missing months, and ambiguities.
    """
    date_columns: List[str] = []
    date_ranges: Dict[str, Dict[str, Optional[str]]] = {}
    missing_months_by_col: Dict[str, List[str]] = {}
    present_months_by_col: Dict[str, List[str]] = {}
    ambiguities: List[str] = []

    for col in df.columns:
        series = df[col]
        col_lower = str(col).lower()
        is_date_named = any(k in col_lower for k in ["date", "time", "created_at", "timestamp", "period", "month", "day", "year"])
        
        # Test if it can be parsed as dates
        parsed_dates = None
        if pd.api.types.is_datetime64_any_dtype(series):
            parsed_dates = series
            date_columns.append(col)
        elif series.dtype == "object" or is_date_named:
            non_null = series.dropna()
            if len(non_null) > 0:
                try:
                    # Sample up to 100 values to avoid slow parse
                    sample = non_null.head(100)
                    parsed = pd.to_datetime(sample, format="mixed", errors="coerce")
                    valid_ratio = parsed.notna().sum() / len(sample)
                    if valid_ratio >= 0.7:
                        date_columns.append(col)
                        parsed_dates = pd.to_datetime(series, format="mixed", errors="coerce")
                except Exception:
                    pass

        if parsed_dates is not None:
            valid_dates = parsed_dates.dropna()
            if len(valid_dates) > 0:
                min_d = valid_dates.min().strftime("%Y-%m-%d")
                max_d = valid_dates.max().strftime("%Y-%m-%d")
                date_ranges[col] = {"min": min_d, "max": max_d}

                # Extract existing months
                try:
                    periods = valid_dates.dt.to_period("M").drop_duplicates().sort_values()
                    present_m = [str(p) for p in periods]
                    present_months_by_col[col] = present_m

                    if len(periods) > 1:
                        full_range = pd.period_range(start=periods.min(), end=periods.max(), freq="M")
                        missing_p = [str(p) for p in full_range if p not in periods.values]
                        if missing_p:
                            missing_months_by_col[col] = missing_p
                            ambiguities.append(
                                f"Column '{col}' has discontinuous month coverage. Missing periods: {', '.join(missing_p)}."
                            )
                except Exception:
                    pass

            # Check potential format ambiguity (e.g. DD/MM vs MM/DD)
            if series.dtype == "object":
                sample_strs = series.dropna().head(20).astype(str).tolist()
                for s in sample_strs:
                    if "/" in s:
                        parts = s.split("/")
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            p1, p2 = int(parts[0]), int(parts[1])
                            if 1 <= p1 <= 12 and 1 <= p2 <= 12 and p1 != p2:
                                ambiguities.append(
                                    f"Column '{col}' contains ambiguous dates (e.g. '{s}') which could be MM/DD or DD/MM."
                                )
                                break

    primary_date_range = next(iter(date_ranges.values())) if date_ranges else {"min": None, "max": None}

    return {
        "date_columns": date_columns,
        "date_ranges": date_ranges,
        "primary_date_range": primary_date_range,
        "present_months": present_months_by_col,
        "missing_months": missing_months_by_col,
        "date_ambiguities": list(set(ambiguities)),
    }
