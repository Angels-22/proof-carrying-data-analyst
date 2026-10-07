"""
Trap detector for VerifyAI.
Intercepts data traps on the REQUIRED datasets for a query:
- Incompatible currencies across required datasets (e.g., INR + USD)
- Missing critical time periods (e.g., August missing when calculating July to August growth)
- Incompatible measurement units (e.g., kg + litres)
- Unresolved potential contradictions between required sources
"""

import re
from typing import Any, Dict, List, Optional
from profiler.profiler import MultiDatasetProfile
from .refusal import RefusalPayload
from .ambiguity import MONTH_NAMES
from .contradictions import check_query_contradictions


def detect_data_traps(
    question: str,
    multi_profile: MultiDatasetProfile,
    plan: Optional[Any] = None,
) -> Optional[RefusalPayload]:
    """
    Evaluates whether the question falls into any fatal data traps.
    Operates strictly on the scoped datasets required for the query.
    """
    q_lower = question.lower()

    # 1. Multi-Currency Mismatch Trap
    # Only triggered if the required datasets for this query actually span multiple currencies!
    known_currencies = set()
    for p in multi_profile.datasets.values():
        if p.currency and p.currency.upper() not in ["UNKNOWN", "NONE"]:
            known_currencies.add(p.currency.upper())

    if len(known_currencies) > 1:
        curr_list = sorted(list(known_currencies))
        return RefusalPayload(
            response_type="REFUSED",
            confidence="LOW",
            reason=(
                f"Datasets use different currencies ({' and '.join(curr_list)}), and no verified exchange rate was provided."
            ),
            data_issue="Incompatible currencies across required datasets without conversion parameters.",
            what_would_be_needed=(
                f"Provide an explicit verified exchange rate between {' and '.join(curr_list)} or analyze each currency separately."
            ),
        )

    # 2. Check for potential contradictory datasets (only among required datasets)
    contra_refusal = check_query_contradictions(question, multi_profile)
    if contra_refusal:
        return contra_refusal

    # 3. Missing Month / Temporal Gap Trap
    for m_name, m_num in MONTH_NAMES.items():
        pattern = rf"\b{m_name}\b"
        if re.search(pattern, q_lower):
            month_str_2digit = f"{m_num:02d}"
            # Check if this month is present in the required datasets with date columns
            for ds_name, p in multi_profile.datasets.items():
                if p.date_columns:
                    for col in p.date_columns:
                        present = p.present_months.get(col, [])
                        has_month = any(
                            p_entry.endswith(f"-{month_str_2digit}")
                            for p_entry in present
                        )
                        if not has_month:
                            if "growth" in q_lower or "to" in q_lower or "trend" in q_lower or "between" in q_lower:
                                reason_text = f"{m_name.capitalize()} data is unavailable, so month-over-month growth cannot be calculated reliably."
                            else:
                                reason_text = (
                                    f"{m_name.capitalize()} data is not present in the uploaded dataset '{ds_name}'. "
                                    f"Available range is {p.date_range.min or 'N/A'} to {p.date_range.max or 'N/A'}."
                                )

                            return RefusalPayload(
                                response_type="REFUSED",
                                confidence="LOW",
                                reason=reason_text,
                                data_issue=f"Temporal gap: Month {m_name.capitalize()} missing from date column '{col}'.",
                                what_would_be_needed=(
                                    f"Provide dataset records for {m_name.capitalize()} to compute metrics for this period."
                                ),
                            )

    # 4. Incompatible Units Trap (only among required datasets)
    units_found = set()
    for p in multi_profile.datasets.values():
        for u in p.column_units.values():
            units_found.add(u)
    if len(units_found) > 1 and any(w in q_lower for w in ["combined", "total", "sum", "add", "all"]):
        unit_types = set()
        for u in units_found:
            if u in ["kilograms", "grams", "pounds", "ounces"]:
                unit_types.add("weight")
            elif u in ["litres", "millilitres"]:
                unit_types.add("volume")
            elif u in ["meters", "kilometres"]:
                unit_types.add("length")
        if len(unit_types) > 1:
            return RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=f"Question attempts to aggregate incompatible measurement units ({', '.join(sorted(units_found))}).",
                data_issue="Physical dimension mismatch across metric columns.",
                what_would_be_needed="Specify conversion factors between incompatible measurement dimensions.",
            )

    # 5. Unsupported/Absent Business Metrics
    for unsupported_metric in ["churn", "nps", "satisfaction", "ebitda", "bounce rate"]:
        if unsupported_metric in q_lower:
            all_cols = []
            for p in multi_profile.datasets.values():
                all_cols.extend([c.lower() for c in p.column_names])
            if not any(unsupported_metric in c for c in all_cols):
                return RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=(
                        f"The requested metric '{unsupported_metric}' cannot be calculated because no relevant columns exist."
                    ),
                    data_issue=f"Missing required metric column '{unsupported_metric}'.",
                    what_would_be_needed=f"Upload a dataset containing '{unsupported_metric}' data.",
                )

    return None
