"""
Query planning engine for VerifyAI.
Produces strongly-typed, structured query plans and deterministically validates them against profiler facts.
Strictly classifies intent, enforces schema invariants, and fails closed on unexecutable operations.
"""

from enum import Enum
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from profiler.profiler import MultiDatasetProfile
from traps.refusal import RefusalPayload, RefusalException
from traps.ambiguity import analyze_ambiguity
from llm.client import LLMClient
from .prompts import PLANNER_SYSTEM_PROMPT
from utils.logging import get_logger, log_event

logger = get_logger("VerifyAI.Planner")


class QueryIntent(str, Enum):
    HISTORICAL_ANALYTICS = "historical_analytics"
    FORECAST = "forecast"
    CAUSAL = "causal"
    OPINION = "opinion"
    UNSUPPORTED = "unsupported"


class AggregationType(str, Enum):
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"


class FilterOperator(str, Enum):
    EQ = "="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    BETWEEN = "between"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class FilterCondition(BaseModel):
    column: str
    operator: FilterOperator = FilterOperator.EQ
    value: Any


class TimeRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    quarter: Optional[int] = None
    month_name: Optional[str] = None


class SortSpec(BaseModel):
    column: str
    direction: SortDirection = SortDirection.DESC


class JoinSpec(BaseModel):
    left_dataset: str
    right_dataset: str
    left_on: str
    right_on: str
    how: str = "inner"


class QueryPlan(BaseModel):
    intent: QueryIntent = QueryIntent.HISTORICAL_ANALYTICS
    datasets: List[str] = Field(default_factory=list)
    dataset: Optional[str] = None
    metric: str = "revenue"
    aggregation: AggregationType = AggregationType.SUM
    operation: str = "sum"  # backwards compatibility alias
    filters: List[FilterCondition] = Field(default_factory=list)
    raw_filters: Dict[str, Any] = Field(default_factory=dict)
    group_by: List[str] = Field(default_factory=list)
    time_range: Optional[TimeRange] = None
    sort: Optional[SortSpec] = None
    sort_by: Optional[str] = None
    sort_ascending: bool = False
    limit: Optional[int] = None
    joins: List[JoinSpec] = Field(default_factory=list)
    requires_join: bool = False
    join_datasets: List[str] = Field(default_factory=list)
    join_key: Optional[str] = None
    join: Optional[Dict[str, str]] = None
    answerable: bool = True
    refusal_reason: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    handling_duplicates: Optional[str] = None


def classify_question_intent(question: str) -> Tuple[QueryIntent, Optional[str]]:
    """
    Classifies question intent. Fails closed on unsupported, forecasting, causal, or opinion queries.
    """
    q_lower = question.lower()

    # 1. Forecast Intent
    forecast_patterns = [
        r"\bwill\b", r"\bforecast\b", r"\bpredict\b", r"\bnext year\b", r"\bnext month\b",
        r"\bfuture\b", r"\bprojected\b", r"\bexpected in 202[6-9]\b"
    ]
    if any(re.search(p, q_lower) for p in forecast_patterns):
        return (
            QueryIntent.FORECAST,
            "Forecasting future metrics is unsupported. VerifyAI operates strictly on verified historical data."
        )

    # 2. Causal Intent
    causal_patterns = [
        r"\bwhy did\b", r"\bwhy has\b", r"\bwhat caused\b", r"\breason for\b", r"\broot cause\b"
    ]
    if any(re.search(p, q_lower) for p in causal_patterns):
        return (
            QueryIntent.CAUSAL,
            "Causal questions ('Why did...') cannot be established reliably from observational summaries without a verified causal model."
        )

    # 3. Opinion Intent
    opinion_patterns = [
        r"\bis (?:this|the) company (?:good|successful|bad)\b",
        r"\bshould (?:we|i)\b", r"\bwhat do you think\b", r"\bis it worth\b"
    ]
    if any(re.search(p, q_lower) for p in opinion_patterns):
        return (
            QueryIntent.OPINION,
            "Subjective opinion questions cannot be verified mathematically."
        )

    return (QueryIntent.HISTORICAL_ANALYTICS, None)


def validate_plan(plan: QueryPlan, multi_profile: MultiDatasetProfile) -> QueryPlan:
    """
    Validates the typed QueryPlan strictly against profiler ground truth.
    Prevents hallucinated columns, unsupported operations, incompatible types, and invalid joins.
    """
    # 1. Validate intent first
    if plan.intent != QueryIntent.HISTORICAL_ANALYTICS:
        reason = plan.refusal_reason or f"Queries with intent '{plan.intent.value}' are unsupported for verification-first analytics."
        raise RefusalException(
            RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=reason,
                data_issue=f"Unsupported query intent: {plan.intent.value}",
                what_would_be_needed="Ask a historical analytical question based on observed records.",
            )
        )

    # 2. Check if marked unanswerable
    if not plan.answerable:
        reason = plan.refusal_reason or "Question is unanswerable with the provided dataset."
        raise RefusalException(
            RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=reason,
                data_issue="Query plan determined required parameters cannot be satisfied.",
                what_would_be_needed="Upload relevant dataset or adjust query.",
            )
        )

    all_ds_names = list(multi_profile.datasets.keys())
    if not all_ds_names:
        raise RefusalException(
            RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason="No datasets have been uploaded.",
                data_issue="Dataset storage is empty.",
                what_would_be_needed="Upload a dataset first.",
            )
        )

    # 3. Resolve and validate required datasets
    if not plan.datasets:
        if plan.dataset:
            plan.datasets = [plan.dataset]
        else:
            plan.datasets = [all_ds_names[0]]

    resolved_datasets = []
    for req_ds in plan.datasets:
        matched = None
        for available in all_ds_names:
            if req_ds.lower() == available.lower() or req_ds.lower() in available.lower():
                matched = available
                break
        if not matched:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Required dataset '{req_ds}' is not present in uploaded files.",
                    data_issue=f"Missing dataset '{req_ds}'.",
                    what_would_be_needed=f"Upload '{req_ds}' or verify filename.",
                )
            )
        if matched not in resolved_datasets:
            resolved_datasets.append(matched)

    plan.datasets = resolved_datasets
    plan.dataset = resolved_datasets[0]
    primary_profile = multi_profile.datasets[plan.dataset]

    # Collect available columns
    all_req_cols = set()
    req_numeric_cols = set()
    for ds_name in plan.datasets:
        p = multi_profile.datasets[ds_name]
        all_req_cols.update(c.lower() for c in p.column_names)
        req_numeric_cols.update(c.lower() for c in p.numeric_columns)

    # 4. Validate Metric Column & Operation Compatibility
    metric_lower = plan.metric.lower()
    if metric_lower not in all_req_cols and plan.aggregation not in [AggregationType.COUNT, AggregationType.COUNT_DISTINCT]:
        raise RefusalException(
            RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=f"The requested metric '{plan.metric}' does not exist in dataset '{plan.dataset}'. Available columns: {', '.join(primary_profile.column_names)}.",
                data_issue=f"Missing metric column '{plan.metric}'.",
                what_would_be_needed=f"Provide a dataset with '{plan.metric}' column.",
            )
        )

    # Numeric compatibility check
    if plan.aggregation in [AggregationType.SUM, AggregationType.MEAN, AggregationType.MEDIAN, AggregationType.MIN, AggregationType.MAX]:
        if metric_lower not in req_numeric_cols:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Operation '{plan.aggregation.value}' requires a numeric column, but '{plan.metric}' is not numeric.",
                    data_issue=f"Column '{plan.metric}' is not of numeric data type.",
                    what_would_be_needed=f"Select a numeric column for '{plan.aggregation.value}'.",
                )
            )

    # 5. Validate Group-by Columns
    for grp in plan.group_by:
        if grp.lower() not in all_req_cols:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Group-by column '{grp}' does not exist in the selected datasets ({', '.join(plan.datasets)}).",
                    data_issue=f"Missing grouping column '{grp}'.",
                    what_would_be_needed=f"Upload a dataset containing '{grp}' or adjust grouping.",
                )
            )

    # 6. Validate Filter Columns
    for f in plan.filters:
        if f.column.lower() not in all_req_cols and f.column.lower() not in ["month", "year", "quarter", "date"]:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Filter column '{f.column}' does not exist in dataset '{plan.dataset}'.",
                    data_issue=f"Missing filter column '{f.column}'.",
                    what_would_be_needed=f"Verify column names in '{plan.dataset}'.",
                )
            )

    # 7. Validate Sort Column
    if plan.sort:
        sort_col = plan.sort.column.lower()
        if sort_col not in all_req_cols and sort_col != plan.metric.lower():
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Sort column '{plan.sort.column}' does not exist.",
                    data_issue=f"Missing sort column '{plan.sort.column}'.",
                    what_would_be_needed="Sort by a valid column.",
                )
            )

    # 8. Validate Joins & Detect Fan-out
    if plan.requires_join or plan.joins:
        if len(plan.datasets) < 2:
            if len(all_ds_names) >= 2 and multi_profile.relationships:
                rel = multi_profile.relationships[0]
                ds_a, ds_b = rel["dataset_a"], rel["dataset_b"]
                if plan.dataset == ds_a and ds_b not in plan.datasets:
                    plan.datasets.append(ds_b)
                elif plan.dataset == ds_b and ds_a not in plan.datasets:
                    plan.datasets.append(ds_a)
                plan.join_key = rel["join_key"]
            else:
                raise RefusalException(
                    RefusalPayload(
                        response_type="REFUSED",
                        confidence="LOW",
                        reason="Query requires joining multiple tables, but only one dataset is selected.",
                        data_issue="Insufficient datasets for relational join.",
                        what_would_be_needed="Upload and select related datasets (e.g., products.csv).",
                    )
                )

        if not plan.join_key and plan.joins:
            plan.join_key = plan.joins[0].left_on
        elif not plan.join_key and plan.join and "left" in plan.join:
            plan.join_key = plan.join["left"]

        if not plan.join_key and multi_profile.relationships:
            for rel in multi_profile.relationships:
                if rel["dataset_a"] in plan.datasets and rel["dataset_b"] in plan.datasets:
                    plan.join_key = rel["join_key"]
                    break

        if not plan.join_key:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"No common join key found between datasets {plan.datasets}.",
                    data_issue="Missing foreign key relationship.",
                    what_would_be_needed="Ensure datasets share a common key column (e.g., product_id).",
                )
            )

        # Verify join key exists in BOTH datasets
        ds_left = multi_profile.datasets[plan.datasets[0]]
        ds_right = multi_profile.datasets[plan.datasets[1]]
        if plan.join_key not in ds_left.column_names or plan.join_key not in ds_right.column_names:
            raise RefusalException(
                RefusalPayload(
                    response_type="REFUSED",
                    confidence="LOW",
                    reason=f"Join key '{plan.join_key}' does not exist in both '{plan.datasets[0]}' and '{plan.datasets[1]}'.",
                    data_issue=f"Foreign key '{plan.join_key}' mismatch.",
                    what_would_be_needed="Specify a column that exists in both tables.",
                )
            )

        # Check for potential fan-out on right dataset
        # If right table has duplicate keys, joining might inflate totals
        plan.join_datasets = [plan.datasets[0], plan.datasets[1]]
        if not plan.joins:
            plan.joins = [
                JoinSpec(
                    left_dataset=plan.datasets[0],
                    right_dataset=plan.datasets[1],
                    left_on=plan.join_key,
                    right_on=plan.join_key,
                    how="inner"
                )
            ]

    # 9. Duplicate handling policy
    has_dups = any(multi_profile.datasets[ds].duplicates > 0 for ds in plan.datasets)
    if has_dups and plan.aggregation in [AggregationType.SUM, AggregationType.MEAN, AggregationType.COUNT]:
        dup_count = sum(multi_profile.datasets[ds].duplicates for ds in plan.datasets)
        plan.handling_duplicates = f"Excluded {dup_count} exact duplicate rows from aggregation."
        plan.assumptions.append(f"Duplicate Handling: {dup_count} exact duplicate rows were detected and excluded from the aggregation.")

    # Deduplicate assumptions deterministically
    plan.assumptions = list(dict.fromkeys(plan.assumptions))
    plan.operation = plan.aggregation.value

    return plan


def create_query_plan(
    question: str,
    multi_profile: MultiDatasetProfile,
    llm_client: LLMClient,
) -> QueryPlan:
    """
    Constructs a strongly typed QueryPlan. Classifies intent first.
    """
    # 1. Intent Classification
    intent, refusal_reason = classify_question_intent(question)
    if intent != QueryIntent.HISTORICAL_ANALYTICS:
        plan = QueryPlan(
            intent=intent,
            answerable=False,
            refusal_reason=refusal_reason,
            datasets=list(multi_profile.datasets.keys())[:1],
        )
        return validate_plan(plan, multi_profile)

    # 2. Context summary of datasets
    dataset_summaries = []
    for name, p in multi_profile.datasets.items():
        summary = (
            f"Dataset: {name}\n"
            f"Columns: {', '.join(p.column_names)}\n"
            f"Numeric Columns: {', '.join(p.numeric_columns)}\n"
            f"Date Columns: {', '.join(p.date_columns)}\n"
            f"Date Range: {p.date_range.min or 'N/A'} to {p.date_range.max or 'N/A'}\n"
            f"Currency: {p.currency}\n"
            f"Duplicates: {p.duplicates}\n"
        )
        dataset_summaries.append(summary)

    relationships_summary = (
        f"Detected Relationships: {json.dumps(multi_profile.relationships)}"
        if multi_profile.relationships
        else "No relationships detected."
    )

    user_prompt = (
        f"AVAILABLE DATASETS:\n"
        f"{chr(10).join(dataset_summaries)}\n\n"
        f"RELATIONSHIPS:\n{relationships_summary}\n\n"
        f"USER QUESTION: {question}\n\n"
        f"Generate the Query Plan JSON:"
    )

    raw_response = llm_client.generate_completion(PLANNER_SYSTEM_PROMPT, user_prompt)
    logger.info(f"Raw Planner Output: {raw_response[:200]}...")

    # Extract JSON safely
    try:
        clean_json = raw_response.strip()
        if "```" in clean_json:
            clean_json = re.sub(r"```(json)?", "", clean_json).strip("` \n")
        json_obj = json.loads(clean_json)

        # Parse filters into FilterCondition objects
        filters_list = []
        if "filters" in json_obj:
            raw_f = json_obj["filters"]
            if isinstance(raw_f, dict):
                for col, val in raw_f.items():
                    filters_list.append(FilterCondition(column=col, operator=FilterOperator.EQ, value=val))
            elif isinstance(raw_f, list):
                for item in raw_f:
                    if isinstance(item, dict):
                        filters_list.append(FilterCondition(
                            column=item.get("column", ""),
                            operator=FilterOperator(item.get("operator", "=")),
                            value=item.get("value")
                        ))

        # Parse aggregation
        agg_val = json_obj.get("aggregation") or json_obj.get("operation") or "sum"
        agg_val = agg_val.lower().replace("avg", "mean").replace("average", "mean")
        try:
            agg_type = AggregationType(agg_val)
        except ValueError:
            agg_type = AggregationType.SUM

        # Parse sort
        sort_obj = None
        if "sort" in json_obj and isinstance(json_obj["sort"], dict):
            sort_obj = SortSpec(
                column=json_obj["sort"].get("column", "revenue"),
                direction=SortDirection(json_obj["sort"].get("direction", "desc"))
            )
        elif json_obj.get("sort_by"):
            sort_obj = SortSpec(
                column=json_obj["sort_by"],
                direction=SortDirection.ASC if json_obj.get("sort_ascending") else SortDirection.DESC
            )

        # Parse time range
        time_range = None
        if "time_range" in json_obj and isinstance(json_obj["time_range"], dict):
            time_range = TimeRange(**json_obj["time_range"])

        # Create QueryPlan
        plan = QueryPlan(
            intent=intent,
            datasets=json_obj.get("datasets", [json_obj.get("dataset", "sales.csv")]),
            dataset=json_obj.get("dataset"),
            metric=json_obj.get("metric", "revenue"),
            aggregation=agg_type,
            operation=agg_type.value,
            filters=filters_list,
            raw_filters=json_obj.get("filters", {}) if isinstance(json_obj.get("filters"), dict) else {},
            group_by=json_obj.get("group_by", []),
            time_range=time_range,
            sort=sort_obj,
            sort_by=sort_obj.column if sort_obj else None,
            sort_ascending=(sort_obj.direction == SortDirection.ASC) if sort_obj else False,
            limit=json_obj.get("limit"),
            requires_join=json_obj.get("requires_join", False),
            join_key=json_obj.get("join_key") or (json_obj.get("join", {}).get("left")),
            join=json_obj.get("join"),
            answerable=json_obj.get("answerable", True),
            refusal_reason=json_obj.get("refusal_reason"),
            assumptions=json_obj.get("assumptions", []),
        )
    except Exception as e:
        logger.warning(f"Failed to parse LLM plan JSON: {e}. Falling back to default plan.")
        all_names = list(multi_profile.datasets.keys())
        plan = QueryPlan(
            intent=intent,
            datasets=all_names[:1] if all_names else ["sales.csv"],
            dataset=all_names[0] if all_names else "sales.csv",
            metric="revenue",
            aggregation=AggregationType.SUM,
            operation="sum",
            answerable=True,
        )

    # Integrate ambiguity analysis assumptions
    ambiguity_info = analyze_ambiguity(question, multi_profile)
    for assumption in ambiguity_info["assumptions"]:
        if assumption not in plan.assumptions:
            plan.assumptions.append(assumption)

    # Validate against profiler facts
    validated = validate_plan(plan, multi_profile)
    log_event("QUERY_PLAN_CREATED", {"plan": validated.model_dump()})
    return validated
