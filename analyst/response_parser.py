"""
Response parser for VerifyAI.
Formats execution results, evidence payloads, assumptions, and confidence levels.
Deduplicates assumptions, tracks both total rows and rows used in calculation,
and enforces explicit duplicate handling policies.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from profiler.profiler import MultiDatasetProfile
from utils.formatting import format_currency, format_number
from .planner import QueryPlan


def parse_and_format_response(
    result_data: Any,
    plan: QueryPlan,
    multi_profile: MultiDatasetProfile,
    sanity_warnings: List[str],
) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Translates raw computation result into a clear, executive-grade answer.
    
    Returns:
    - answer_text (str)
    - response_type ("ANSWERED" | "ANSWERED_WITH_ASSUMPTIONS")
    - confidence ("HIGH" | "MEDIUM" | "LOW")
    - evidence (dict)
    """
    primary_ds = plan.dataset or (plan.datasets[0] if plan.datasets else "sales.csv")
    profile = multi_profile.datasets.get(primary_ds)
    currency = profile.currency if profile else "UNKNOWN"
    total_rows = profile.rows if profile else 0
    rows_used = total_rows

    # Deduplicate assumptions deterministically
    plan.assumptions = list(dict.fromkeys(plan.assumptions))

    # Unwrap result data if packaged with row counts
    extracted_val = result_data
    duplicates_excluded = 0

    if isinstance(result_data, dict):
        if "value" in result_data:
            extracted_val = result_data["value"]
            if "rows_total" in result_data:
                total_rows = result_data["rows_total"]
            if "rows_used" in result_data:
                rows_used = result_data["rows_used"]
            if "duplicates_excluded" in result_data:
                duplicates_excluded = result_data["duplicates_excluded"]
        elif "revenue" in result_data and any(k in result_data for k in ["category", "region", "product_name"]):
            # Group by / Join dictionary
            if "rows_total" in result_data:
                total_rows = result_data["rows_total"]
            if "rows_used" in result_data:
                rows_used = result_data["rows_used"]

    # Format answer text based on result shape
    if isinstance(extracted_val, (int, float)):
        if any(k in plan.metric.lower() for k in ["revenue", "price", "sales", "amount", "cost"]):
            answer_text = format_currency(extracted_val, currency)
        else:
            answer_text = format_number(extracted_val)
    elif isinstance(extracted_val, dict):
        parts = []
        for k, v in extracted_val.items():
            if k in ["rows_total", "rows_used", "duplicates_excluded"]:
                continue
            if isinstance(v, (int, float)) and any(r in str(k).lower() for r in ["rev", "price", "sales"]):
                val_str = format_currency(v, currency)
            else:
                val_str = format_number(v)
            parts.append(f"**{k.replace('_', ' ').capitalize()}**: {val_str}")
        answer_text = " | ".join(parts) if parts else str(extracted_val)
    elif isinstance(extracted_val, list):
        answer_text = f"Top results: {', '.join(str(x) for x in extracted_val[:5])}"
    else:
        answer_text = str(extracted_val)

    # Determine confidence and response type
    # Scenario 1 (Normal Query) has calendar assumption, but should be ANSWERED with HIGH confidence
    # Scenario 4 (Duplicate impact) has duplicate policy -> ANSWERED_WITH_ASSUMPTIONS with MEDIUM confidence
    has_dup_handling = bool(plan.handling_duplicates) or duplicates_excluded > 0
    has_heavy_warnings = len(sanity_warnings) > 0

    if has_dup_handling or has_heavy_warnings:
        response_type = "ANSWERED_WITH_ASSUMPTIONS"
        confidence = "MEDIUM"
    else:
        response_type = "ANSWERED"
        confidence = "HIGH"

    # Clean serializable filters
    filters_dict = {}
    if isinstance(plan.filters, list):
        for f in plan.filters:
            if hasattr(f, "column") and hasattr(f, "value"):
                filters_dict[f.column] = f.value
            elif isinstance(f, dict):
                filters_dict[f.get("column", "filter")] = f.get("value")
    elif isinstance(plan.filters, dict):
        filters_dict = plan.filters

    evidence = {
        "primary_dataset": primary_ds,
        "datasets_used": plan.datasets,
        "total_dataset_rows": total_rows,
        "rows_used_in_calculation": rows_used,
        "operation": plan.operation,
        "metric": plan.metric,
        "filters_applied": filters_dict if filters_dict else "None",
        "columns_used": list(dict.fromkeys([plan.metric] + plan.group_by)),
        "datasets_joined": plan.join_datasets if (plan.requires_join or plan.joins) else [],
        "join_key": plan.join_key if (plan.requires_join or plan.joins) else None,
    }

    if has_dup_handling:
        evidence["duplicate_handling"] = plan.handling_duplicates or f"Excluded {duplicates_excluded} exact duplicate rows from aggregation."

    return answer_text, response_type, confidence, evidence
