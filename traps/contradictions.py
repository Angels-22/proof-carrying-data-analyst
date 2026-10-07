"""
Contradiction detector for VerifyAI.
Evaluates cross-dataset conflicting metrics and determines if queries touching those metrics must be refused.
"""

from typing import Any, Dict, List, Optional
from profiler.profiler import MultiDatasetProfile
from .refusal import RefusalPayload


def check_query_contradictions(
    question: str, multi_profile: MultiDatasetProfile
) -> Optional[RefusalPayload]:
    """
    If datasets have severe conflicting claims on a requested metric without an authoritative source specified,
    generate a refusal payload.
    """
    if not multi_profile.has_contradictions:
        return None

    q_lower = question.lower()
    for contra in multi_profile.contradictions:
        metric = contra["metric"].lower()
        if metric in q_lower or ("total" in q_lower and "revenue" in q_lower):
            # Check if user specified which dataset to trust
            name_a = contra["dataset_a"].lower()
            name_b = contra["dataset_b"].lower()
            if name_a not in q_lower and name_b not in q_lower:
                return RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=(
                        f"Potential metric contradiction detected between '{contra['dataset_a']}' and '{contra['dataset_b']}' "
                        f"for {contra['metric']}. '{contra['dataset_a']}' reports {contra['value_a']:,} "
                        f"while '{contra['dataset_b']}' reports {contra['value_b']:,} "
                        f"({contra['percentage_difference']:.1f}% mismatch)."
                    ),
                    data_issue="Unresolved contradictory source records across uploaded datasets.",
                    what_would_be_needed=(
                        f"Clarify which dataset is authoritative ('{contra['dataset_a']}' or '{contra['dataset_b']}') "
                        f"or provide a reconciliation mapping."
                    ),
                )

    return None
