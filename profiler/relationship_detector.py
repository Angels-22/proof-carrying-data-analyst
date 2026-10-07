"""
Relationship detector for VerifyAI.
Detects potential foreign keys, join relationships, and metric contradictions between datasets.
"""

from typing import Any, Dict, List, Tuple
import pandas as pd


def detect_relationships(datasets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Detects join keys between multiple datasets and flags possible cross-dataset contradictions.
    
    datasets: Dict[dataset_name_or_id, DataFrame]
    """
    relationships: List[Dict[str, Any]] = []
    contradictions: List[Dict[str, Any]] = []

    names = list(datasets.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_a, name_b = names[i], names[j]
            df_a, df_b = datasets[name_a], datasets[name_b]

            # 1. Join Key Detection
            common_cols = set(df_a.columns).intersection(set(df_b.columns))
            for col in common_cols:
                # Check overlap of values
                set_a = set(df_a[col].dropna().unique())
                set_b = set(df_b[col].dropna().unique())
                
                if set_a and set_b:
                    intersection = set_a.intersection(set_b)
                    overlap_ratio_a = len(intersection) / len(set_a)
                    overlap_ratio_b = len(intersection) / len(set_b)
                    
                    if overlap_ratio_a > 0.1 or overlap_ratio_b > 0.1:
                        relationships.append({
                            "dataset_a": name_a,
                            "dataset_b": name_b,
                            "join_key": col,
                            "overlap_count": len(intersection),
                            "overlap_ratio_a": round(overlap_ratio_a, 3),
                            "overlap_ratio_b": round(overlap_ratio_b, 3),
                            "is_recommended_join": overlap_ratio_a > 0.5 or overlap_ratio_b > 0.5,
                        })

            # 2. Contradiction Detection
            # Check currencies first: don't compare metrics across different currencies
            curr_a = "UNKNOWN"
            curr_b = "UNKNOWN"
            for c in df_a.columns:
                if "currency" in str(c).lower():
                    curr_a = str(df_a[c].dropna().iloc[0]) if len(df_a[c].dropna()) > 0 else "UNKNOWN"
            for c in df_b.columns:
                if "currency" in str(c).lower():
                    curr_b = str(df_b[c].dropna().iloc[0]) if len(df_b[c].dropna()) > 0 else "UNKNOWN"
            if "usd" in name_a.lower(): curr_a = "USD"
            if "usd" in name_b.lower(): curr_b = "USD"
            if "inr" in name_a.lower(): curr_a = "INR"
            if "inr" in name_b.lower(): curr_b = "INR"

            if curr_a.upper() != curr_b.upper():
                continue

            # Look for shared metrics like 'revenue', 'total_sales', 'total_revenue'
            rev_cols_a = [c for c in df_a.columns if any(k in str(c).lower() for k in ["revenue", "sales_total", "total_sales"])]
            rev_cols_b = [c for c in df_b.columns if any(k in str(c).lower() for k in ["revenue", "sales_total", "total_sales"])]

            if rev_cols_a and rev_cols_b:
                col_a = rev_cols_a[0]
                col_b = rev_cols_b[0]
                if pd.api.types.is_numeric_dtype(df_a[col_a]) and pd.api.types.is_numeric_dtype(df_b[col_b]):
                    sum_a = float(df_a[col_a].dropna().sum())
                    sum_b = float(df_b[col_b].dropna().sum())
                    
                    # If both datasets claim to represent total revenue but diverge by > 5%
                    diff = abs(sum_a - sum_b)
                    rel_diff = diff / max(sum_a, sum_b, 1.0)
                    if rel_diff > 0.05 and min(sum_a, sum_b) > 0:
                        contradictions.append({
                            "dataset_a": name_a,
                            "dataset_b": name_b,
                            "metric": "revenue",
                            "value_a": round(sum_a, 2),
                            "value_b": round(sum_b, 2),
                            "difference": round(diff, 2),
                            "percentage_difference": round(rel_diff * 100, 2),
                            "description": (
                                f"Contradiction detected: '{name_a}' reports total revenue {sum_a:,.2f}, "
                                f"while '{name_b}' reports {sum_b:,.2f} ({rel_diff*100:.1f}% mismatch)."
                            ),
                        })

    return {
        "relationships": relationships,
        "contradictions": contradictions,
        "has_contradictions": len(contradictions) > 0,
    }
