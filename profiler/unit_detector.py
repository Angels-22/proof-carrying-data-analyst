"""
Unit detector for VerifyAI.
Detects physical and measurement units from column names and values.
"""

from typing import Any, Dict, List
import pandas as pd

KNOWN_UNITS = {
    "kg": "kilograms",
    "kilogram": "kilograms",
    "kilograms": "kilograms",
    "g": "grams",
    "gram": "grams",
    "grams": "grams",
    "lbs": "pounds",
    "pound": "pounds",
    "oz": "ounces",
    "liter": "litres",
    "liters": "litres",
    "litres": "litres",
    "l": "litres",
    "ml": "millilitres",
    "meter": "meters",
    "meters": "meters",
    "m": "meters",
    "km": "kilometres",
    "pcs": "pieces",
    "pieces": "pieces",
    "units": "units",
}


def detect_units(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect physical units across dataset columns.
    """
    detected_by_column: Dict[str, str] = {}
    
    for col in df.columns:
        col_lower = str(col).lower()
        # Look for (unit) or _unit
        for u_str, standard_u in KNOWN_UNITS.items():
            if f"({u_str})" in col_lower or f"_{u_str}" in col_lower or f"[{u_str}]" in col_lower:
                detected_by_column[col] = standard_u
                break
        
        # If not in name, check string values for unit suffixes
        if col not in detected_by_column and df[col].dtype == "object":
            samples = df[col].dropna().astype(str).head(30)
            for s in samples:
                s_lower = s.strip().lower()
                for u_str, standard_u in KNOWN_UNITS.items():
                    if s_lower.endswith(f" {u_str}") or s_lower.endswith(f"{u_str}"):
                        detected_by_column[col] = standard_u
                        break
                if col in detected_by_column:
                    break

    return {
        "column_units": detected_by_column,
        "has_units": len(detected_by_column) > 0,
    }
