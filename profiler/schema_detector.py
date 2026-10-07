"""
Schema detector for VerifyAI.
Deterministically detects column types, numeric stats, ID candidates, and primary keys.
"""

from typing import Any, Dict, List
import numpy as np
import pandas as pd


def detect_schema(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyzes DataFrame schema deterministically.
    """
    row_count = len(df)
    columns = list(df.columns)
    
    numeric_cols = []
    categorical_cols = []
    stats: Dict[str, Dict[str, Any]] = {}
    id_candidates = []
    primary_key_candidates = []

    for col in columns:
        series = df[col]
        dtype_str = str(series.dtype)
        unique_cnt = int(series.nunique(dropna=True))
        
        # Check numeric
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            # Check if it's strictly an ID column disguised as numeric
            col_lower = str(col).lower()
            is_id_name = any(k in col_lower for k in ["_id", "id", "key", "code"]) and ("price" not in col_lower and "revenue" not in col_lower and "amount" not in col_lower)
            
            if is_id_name and unique_cnt == row_count and row_count > 0:
                id_candidates.append(col)
                if series.notna().all():
                    primary_key_candidates.append(col)
            
            numeric_cols.append(col)
            non_null = series.dropna()
            if len(non_null) > 0:
                stats[col] = {
                    "type": dtype_str,
                    "unique_values": unique_cnt,
                    "min": float(non_null.min()) if not isinstance(non_null.min(), (str, bool)) else str(non_null.min()),
                    "max": float(non_null.max()) if not isinstance(non_null.max(), (str, bool)) else str(non_null.max()),
                    "mean": float(non_null.mean()) if not isinstance(non_null.mean(), (str, bool)) else None,
                }
            else:
                stats[col] = {
                    "type": dtype_str,
                    "unique_values": 0,
                    "min": None,
                    "max": None,
                    "mean": None,
                }
        else:
            categorical_cols.append(col)
            col_lower = str(col).lower()
            is_id_name = any(k in col_lower for k in ["_id", "id", "uuid", "key", "code", "sku"])
            if (is_id_name or unique_cnt == row_count) and row_count > 0:
                id_candidates.append(col)
                if series.notna().all() and unique_cnt == row_count:
                    primary_key_candidates.append(col)

            stats[col] = {
                "type": dtype_str,
                "unique_values": unique_cnt,
                "min": None,
                "max": None,
                "mean": None,
            }

    return {
        "columns": columns,
        "data_types": {c: str(df[c].dtype) for c in columns},
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "stats": stats,
        "id_columns": id_candidates,
        "primary_key_candidates": primary_key_candidates,
    }
