"""
Ambiguity detector for VerifyAI.
Identifies ambiguous timeframes, ambiguous column references, and generates explicit assumptions.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from profiler.profiler import DatasetProfile, MultiDatasetProfile


MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
}


def analyze_ambiguity(question: str, multi_profile: MultiDatasetProfile) -> Dict[str, Any]:
    """
    Checks if a user question contains ambiguity that should either be:
    - Resolved with an explicit assumption (ANSWERED_WITH_ASSUMPTIONS)
    - Or refused if irreconcilable.
    """
    assumptions: List[str] = []
    q_lower = question.lower()

    # 1. Check month interpretation
    for m_name, m_num in MONTH_NAMES.items():
        pattern = rf"\b{m_name}\b"
        if re.search(pattern, q_lower):
            assumptions.append(f"{m_name.capitalize()} interpreted as calendar month {m_num}.")
            break

    # 2. Check year interpretation if year not specified
    has_year = any(re.search(rf"\b(19|20)\d\d\b", q_lower) for _ in [1])
    if not has_year:
        # Check if dataset has specific year
        years_found = set()
        for p in multi_profile.datasets.values():
            if p.date_range.min and len(p.date_range.min) >= 4:
                years_found.add(p.date_range.min[:4])
            if p.date_range.max and len(p.date_range.max) >= 4:
                years_found.add(p.date_range.max[:4])
        if len(years_found) == 1:
            assumptions.append(f"Year not specified in query; interpreted as year {list(years_found)[0]} from dataset date range.")
        elif len(years_found) > 1:
            assumptions.append(f"Multiple years present in dataset ({', '.join(sorted(years_found))}); analysis evaluates all available years unless filtered.")

    # 3. Check duplicate handling policy
    has_duplicates = any(p.duplicates > 0 for p in multi_profile.datasets.values())
    if has_duplicates:
        assumptions.append("Exact duplicate rows retained in raw computation as recorded; see data quality advisory for potential duplicate distortion.")

    return {
        "assumptions": assumptions,
        "has_assumptions": len(assumptions) > 0,
    }
