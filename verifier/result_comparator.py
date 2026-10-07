"""
Result comparator for VerifyAI.
Supports float tolerance comparisons (1e-9 abs, 1e-6 rel), nested dicts, lists, and strings.
"""

import math
from typing import Any, Tuple

ABS_TOL = 1e-9
REL_TOL = 1e-6


def compare_results(res1: Any, res2: Any) -> Tuple[bool, str]:
    """
    Compares two execution results with mathematical precision and tolerance.
    Returns: (match: bool, explanation: str)
    """
    # 1. Exact equality check (shortcut)
    if res1 == res2:
        return True, "Exact match."

    # 2. Integer comparison (exact)
    if isinstance(res1, int) and isinstance(res2, int) and not isinstance(res1, bool) and not isinstance(res2, bool):
        if res1 == res2:
            return True, "Exact integer match."
        return False, f"Integer mismatch: Run 1 yielded {res1}, Run 2 yielded {res2}."

    # 3. Floating-point comparison (with tolerance)
    if isinstance(res1, (int, float)) and isinstance(res2, (int, float)):
        if math.isnan(res1) and math.isnan(res2):
            return True, "Both outputs are NaN."
        if math.isinf(res1) and math.isinf(res2):
            return res1 == res2, "Both outputs are Infinity with matching sign."
        
        is_close = math.isclose(float(res1), float(res2), rel_tol=REL_TOL, abs_tol=ABS_TOL)
        if is_close:
            return True, f"Numeric match within tolerance (abs={ABS_TOL}, rel={REL_TOL})."
        else:
            diff = abs(float(res1) - float(res2))
            return False, f"Numeric mismatch: Run 1 yielded {res1}, Run 2 yielded {res2} (diff: {diff:.6e})."

    # 3. String numeric parsing fallback (e.g. if one was serialized as string)
    try:
        f1 = float(res1)
        f2 = float(res2)
        if math.isclose(f1, f2, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            return True, "Parsed numeric match within tolerance."
    except (ValueError, TypeError):
        pass

    # 4. Both are dictionaries
    if isinstance(res1, dict) and isinstance(res2, dict):
        common_keys = set(res1.keys()) & set(res2.keys())
        if not common_keys:
            return False, f"No common keys to compare: {set(res1.keys())} vs {set(res2.keys())}."

        core_val_keys = [k for k in ["value", "revenue", "sales", "category", "product_id", "product_name", "count"] if k in common_keys]
        keys_to_compare = core_val_keys if core_val_keys else list(common_keys)

        for k in keys_to_compare:
            match, reason = compare_results(res1[k], res2[k])
            if not match:
                return False, f"Mismatch in dict key '{k}': {reason}"
        return True, "All compared dictionary key-value pairs match within tolerance."


    # 5. Both are lists
    if isinstance(res1, list) and isinstance(res2, list):
        if len(res1) != len(res2):
            return False, f"List length mismatch: {len(res1)} vs {len(res2)}."
        for idx, (item1, item2) in enumerate(zip(res1, res2)):
            match, reason = compare_results(item1, item2)
            if not match:
                return False, f"Mismatch at list index {idx}: {reason}"
        return True, "All list elements match within tolerance."

    # 6. Fallback string representation
    if str(res1).strip() == str(res2).strip():
        return True, "String representation match."

    return False, f"Value mismatch: '{res1}' vs '{res2}'."
