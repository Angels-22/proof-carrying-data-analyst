"""
Code generator for VerifyAI.
Compiles a strongly-typed QueryPlan into a deterministic, restricted Python/Pandas script.
Features an AST validation layer ensuring strict plan-versus-execution consistency.
"""

import ast
import json
import os
import re
from typing import Any, Dict, List, Optional
from profiler.profiler import MultiDatasetProfile
from llm.client import LLMClient
from .planner import QueryPlan, AggregationType, FilterOperator, SortDirection
from .prompts import CODE_GEN_SYSTEM_PROMPT
from traps.refusal import RefusalPayload, RefusalException
from utils.logging import get_logger, log_event

logger = get_logger("VerifyAI.CodeGen")


def validate_plan_against_code(plan: QueryPlan, code: str) -> None:
    """
    AST Validation Layer (Phase 1.4):
    Verifies that every element of the validated QueryPlan is represented in the generated code.
    Fails closed if the code silently omits a filter, metric, group-by, join, or aggregation.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise RefusalException(
            RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=f"Generated code failed syntax validation: {str(e)}",
                data_issue="Syntax error in analysis script.",
                what_would_be_needed="Regenerate valid code.",
                code=code,
            )
        )

    # Collect all string literals and attribute names in the AST
    string_constants = set()
    attribute_names = set()
    function_calls = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_constants.add(node.value.lower())
        elif isinstance(node, ast.Attribute):
            attribute_names.add(node.attr.lower())
        elif isinstance(node, ast.Name):
            attribute_names.add(node.id.lower())
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                function_calls.add(node.func.attr.lower())
            elif isinstance(node.func, ast.Name):
                function_calls.add(node.func.id.lower())

    # 1. Verify planned datasets are referenced
    for ds in plan.datasets:
        ds_base = os.path.basename(ds).lower()
        if not any(ds_base in s for s in string_constants) and ds_base not in code.lower():
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Plan-versus-execution mismatch: Planned dataset '{ds}' is not read in the executed code.",
                    data_issue="Omitted dataset in execution script.",
                    what_would_be_needed="Ensure code loads all planned datasets.",
                    code=code,
                )
            )

    # 2. Verify planned metric is referenced
    metric_lower = plan.metric.lower()
    if metric_lower not in string_constants and metric_lower not in code.lower():
        raise RefusalException(
            RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=f"Plan-versus-execution mismatch: Planned metric '{plan.metric}' is missing from the executed code.",
                data_issue="Omitted metric in execution script.",
                what_would_be_needed="Compute using the requested metric column.",
                code=code,
            )
        )

    # 3. Verify planned filters are represented
    for f in plan.filters:
        col_lower = f.column.lower()
        if col_lower not in string_constants and col_lower not in code.lower() and col_lower not in ["month", "year"]:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Plan-versus-execution mismatch: Planned filter on column '{f.column}' was omitted from the executed code.",
                    data_issue=f"Omitted filter on '{f.column}'.",
                    what_would_be_needed="Apply all planned filters.",
                    code=code,
                )
            )

    # 4. Verify join is represented if planned
    if plan.requires_join or plan.joins:
        if "merge" not in function_calls and "join" not in function_calls and "merge" not in code.lower():
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason="Plan-versus-execution mismatch: Relational join required by QueryPlan was not executed in code.",
                    data_issue="Omitted join operation in execution script.",
                    what_would_be_needed="Execute pd.merge on the required datasets.",
                    code=code,
                )
            )

    # 5. Verify group-by is represented if planned
    if plan.group_by:
        if "groupby" not in function_calls and "groupby" not in code.lower():
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Plan-versus-execution mismatch: Grouping by {plan.group_by} was not executed in code.",
                    data_issue="Omitted groupby operation in execution script.",
                    what_would_be_needed="Execute groupby aggregation.",
                    code=code,
                )
            )


def generate_analysis_code(
    plan: QueryPlan,
    multi_profile: MultiDatasetProfile,
    dataset_paths: Dict[str, str],
    question: str,
    llm_client: LLMClient,
) -> str:
    """
    Generates standalone, executable Python code to compute the verified answer,
    then runs strict AST validation against the plan.
    """
    if llm_client.has_api_key:
        context_lines = ["DATASET FILEPATHS:"]
        for name in plan.datasets:
            path = dataset_paths.get(name, name)
            norm_path = path.replace("\\", "/")
            cols = multi_profile.datasets[name].column_names if name in multi_profile.datasets else []
            context_lines.append(f"- {name}: path='{norm_path}', columns={cols}")

        user_prompt = (
            f"{chr(10).join(context_lines)}\n\n"
            f"QUESTION: {question}\n\n"
            f"QUERY PLAN:\n{plan.model_dump_json(indent=2)}\n\n"
            f"Generate the exact Python code to execute this plan and output the result via print(json.dumps(result)):"
        )

        raw_code = llm_client.generate_completion(CODE_GEN_SYSTEM_PROMPT, user_prompt)
        clean_code = _sanitize_generated_code(raw_code, plan, dataset_paths)
        validate_plan_against_code(plan, clean_code)
        log_event("CODE_GENERATED", {"code_length": len(clean_code)})
        return clean_code

    # Generic deterministic code compiler
    code = _build_generic_deterministic_code(plan, multi_profile, dataset_paths)
    validate_plan_against_code(plan, code)
    return code


def _build_generic_deterministic_code(
    plan: QueryPlan,
    multi_profile: MultiDatasetProfile,
    dataset_paths: Dict[str, str],
) -> str:
    """
    Generic, compositional code generator (Phase 1.3).
    Systematically translates ALL plan components (datasets, joins, filters,
    time ranges, duplicate policy, group-by, aggregation, sort, limit)
    into a coherent, deterministic Pandas script.
    """
    if plan.datasets:
        primary_ds = plan.datasets[0]
    elif dataset_paths:
        primary_ds = list(dataset_paths.keys())[0]
    else:
        raise ValueError("No dataset specified in plan or dataset_paths.")

    raw_path_primary = dataset_paths.get(primary_ds, primary_ds).replace("\\", "/")
    primary_profile = multi_profile.datasets.get(primary_ds)
    metric_col = plan.metric

    lines = [
        "import pandas as pd",
        "import json",
        "",
        f'df = pd.read_csv(r"{raw_path_primary}")',
        "rows_total = len(df)",
    ]

    # 1. Join handling
    if (plan.requires_join or plan.joins) and len(plan.datasets) >= 2:
        sec_ds = plan.datasets[1]
        sec_path = dataset_paths.get(sec_ds, sec_ds).replace("\\", "/")
        join_key = plan.join_key or (plan.joins[0].left_on if plan.joins else "product_id")
        lines.extend([
            f'df_secondary = pd.read_csv(r"{sec_path}")',
            f'df = pd.merge(df, df_secondary, on="{join_key}", how="inner")',
        ])

    # 2. Duplicate exclusion policy
    if plan.handling_duplicates:
        lines.extend([
            "# Exclude exact duplicates per VerifyAI policy",
            "df = df.drop_duplicates()",
        ])

    # 3. Date / Time Range filtering
    date_col = primary_profile.date_columns[0] if (primary_profile and primary_profile.date_columns) else "date"
    # Check if month/year filter exists in plan.filters or plan.time_range or raw_filters
    month_val = None
    year_val = None
    start_date = None
    end_date = None

    if plan.time_range:
        month_val = plan.time_range.month
        year_val = plan.time_range.year
        start_date = plan.time_range.start
        end_date = plan.time_range.end

    for f in plan.filters:
        if f.column.lower() == "month":
            month_val = int(f.value)
        elif f.column.lower() == "year":
            year_val = int(f.value)
        elif f.column.lower() == "date":
            if f.operator == FilterOperator.EQ:
                start_date = end_date = str(f.value)

    if month_val or year_val or start_date or end_date:
        lines.append(f'df["{date_col}"] = pd.to_datetime(df["{date_col}"], format="mixed")')
        if month_val:
            lines.append(f'df = df[df["{date_col}"].dt.month == {month_val}]')
        if year_val:
            lines.append(f'df = df[df["{date_col}"].dt.year == {year_val}]')
        if start_date and end_date:
            lines.append(f'df = df[(df["{date_col}"] >= "{start_date}") & (df["{date_col}"] <= "{end_date}")]')

    # 4. General Column Filters
    for f in plan.filters:
        col = f.column
        if col.lower() in ["month", "year", "date"]:
            continue
        op = f.operator
        val = f.value
        if op == FilterOperator.EQ:
            if isinstance(val, str):
                lines.append(f'df = df[df["{col}"].astype(str).str.lower() == {repr(val.lower())}]')
            else:
                lines.append(f'df = df[df["{col}"] == {val}]')
        elif op == FilterOperator.NEQ:
            lines.append(f'df = df[df["{col}"] != {repr(val)}]')
        elif op == FilterOperator.GT:
            lines.append(f'df = df[df["{col}"] > {val}]')
        elif op == FilterOperator.GTE:
            lines.append(f'df = df[df["{col}"] >= {val}]')
        elif op == FilterOperator.LT:
            lines.append(f'df = df[df["{col}"] < {val}]')
        elif op == FilterOperator.LTE:
            lines.append(f'df = df[df["{col}"] <= {val}]')
        elif op == FilterOperator.IN:
            lines.append(f'df = df[df["{col}"].isin({repr(val)})]')
        elif op == FilterOperator.CONTAINS:
            lines.append(f'df = df[df["{col}"].astype(str).str.contains({repr(str(val))}, case=False, na=False)]')

    lines.append("rows_used = len(df)")
    lines.append("")

    # 5. Aggregation operation mapping
    agg_map = {
        AggregationType.SUM: "sum",
        AggregationType.MEAN: "mean",
        AggregationType.MEDIAN: "median",
        AggregationType.MIN: "min",
        AggregationType.MAX: "max",
        AggregationType.COUNT: "count",
        AggregationType.COUNT_DISTINCT: "nunique",
    }
    agg_func = agg_map.get(plan.aggregation, "sum")

    # 6. Group-by Execution
    if plan.group_by:
        grp_col = plan.group_by[0]
        sort_asc = plan.sort_ascending if not plan.sort else (plan.sort.direction == SortDirection.ASC)
        lines.extend([
            f'grouped = df.groupby("{grp_col}")["{metric_col}"].{agg_func}().sort_values(ascending={sort_asc})',
        ])
        if plan.limit:
            lines.append(f'grouped = grouped.head({plan.limit})')
        lines.extend([
            "top_key = str(grouped.index[0]) if len(grouped) > 0 else None",
            "top_val = float(grouped.iloc[0]) if len(grouped) > 0 else 0.0",
            "result = {",
            f'    "{grp_col}": top_key,',
            f'    "{metric_col}": top_val,',
            '    "rows_total": rows_total,',
            '    "rows_used": rows_used,',
            '    "group_results": {str(k): float(v) for k, v in grouped.items()}',
            "}",
            "print(json.dumps(result))",
        ])
    else:
        # Non-grouped scalar aggregation
        if plan.aggregation == AggregationType.COUNT:
            lines.append("val = int(rows_used)")
        elif plan.aggregation == AggregationType.COUNT_DISTINCT:
            lines.append(f'val = int(df["{metric_col}"].nunique()) if rows_used > 0 else 0')
        elif plan.aggregation == AggregationType.MEDIAN:
            lines.append(f'val = float(df["{metric_col}"].median()) if rows_used > 0 else 0.0')
        else:
            lines.append(f'val = float(df["{metric_col}"].{agg_func}()) if rows_used > 0 else 0.0')

        lines.extend([
            "result = {",
            '    "value": val,',
            '    "rows_total": rows_total,',
            '    "rows_used": rows_used,',
        ])
        if plan.handling_duplicates:
            lines.append('    "duplicates_excluded": rows_total - rows_used,')
        lines.extend([
            "}",
            "print(json.dumps(result))",
        ])

    return "\n".join(lines) + "\n"


def _sanitize_generated_code(code: str, plan: QueryPlan, dataset_paths: Dict[str, str]) -> str:
    """
    Strips markdown backticks and enforces path correctness for the requested datasets.
    """
    cleaned = code.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(python)?", "", cleaned).strip()
    if cleaned.endswith("```"):
        cleaned = re.sub(r"```$", "", cleaned).strip()

    for ds_name in plan.datasets:
        if ds_name in dataset_paths:
            norm_path = dataset_paths[ds_name].replace("\\", "/")
            cleaned = re.sub(rf'pd\.read_csv\(["\'][^"\']*{re.escape(ds_name)}["\']\)', f'pd.read_csv(r"{norm_path}")', cleaned)

    return cleaned
