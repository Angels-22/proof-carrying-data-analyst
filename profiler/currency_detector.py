"""
Currency detector for VerifyAI.
Detects currency symbols, ISO codes, and currency-related columns.
"""

from typing import Any, Dict, List, Optional
import pandas as pd

CURRENCY_SYMBOLS = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "A$": "AUD",
    "C$": "CAD",
}

CURRENCY_KEYWORDS = {
    "usd": "USD",
    "inr": "INR",
    "eur": "EUR",
    "gbp": "GBP",
    "jpy": "JPY",
    "dollar": "USD",
    "rupee": "INR",
    "rupees": "INR",
    "euro": "EUR",
    "pound": "GBP",
}


def detect_currency(df: pd.DataFrame, filename: str = "") -> Dict[str, Any]:
    """
    Detect currencies across columns and overall dataset.
    """
    detected_by_column: Dict[str, str] = {}
    detected_currencies: List[str] = []

    # Check filename first
    fn_lower = filename.lower()
    for kw, curr in CURRENCY_KEYWORDS.items():
        if kw in fn_lower and curr not in detected_currencies:
            detected_currencies.append(curr)

    for col in df.columns:
        col_lower = str(col).lower()
        col_currency = None

        # Check column name for currency clues
        for kw, curr in CURRENCY_KEYWORDS.items():
            if kw in col_lower:
                col_currency = curr
                break

        # Check values if object or string
        series = df[col]
        if col_currency is None and series.dtype == "object":
            samples = series.dropna().astype(str).head(50)
            for s in samples:
                for sym, curr in CURRENCY_SYMBOLS.items():
                    if sym in s:
                        col_currency = curr
                        break
                if col_currency:
                    break

        if col_currency:
            detected_by_column[col] = col_currency
            if col_currency not in detected_currencies:
                detected_currencies.append(col_currency)

    # If no currency indicator is detected, DO NOT default to USD
    primary_currency = detected_currencies[0] if detected_currencies else "UNKNOWN"

    return {
        "currencies": detected_currencies,
        "primary_currency": primary_currency,
        "column_currencies": detected_by_column,
        "is_multi_currency": len(set(detected_currencies)) > 1,
    }
