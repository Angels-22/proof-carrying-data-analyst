"""
Main profiling engine for VerifyAI.
Combines schema, duplicate, missing, date, unit, currency, and relationship detectors
into a deterministic, fully structured Pydantic profile.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from pydantic import BaseModel, Field

from .schema_detector import detect_schema
from .duplicate_detector import detect_duplicates
from .missing_detector import detect_missing_values
from .date_detector import detect_dates
from .currency_detector import detect_currency
from .unit_detector import detect_units
from .relationship_detector import detect_relationships
from utils.logging import get_logger, log_event

logger = get_logger("VerifyAI.Profiler")


class DateRange(BaseModel):
    min: Optional[str] = None
    max: Optional[str] = None


class DatasetProfile(BaseModel):
    filename: str
    rows: int
    columns: int
    column_names: List[str]
    data_types: Dict[str, str]
    numeric_columns: List[str]
    categorical_columns: List[str]
    duplicates: int
    duplicate_percentage: float
    duplicate_policy: str
    missing_values: Dict[str, int]
    missing_percentages: Dict[str, float]
    has_missing: bool
    date_columns: List[str]
    date_range: DateRange
    present_months: Dict[str, List[str]] = Field(default_factory=dict)
    missing_months: Dict[str, List[str]] = Field(default_factory=dict)
    date_ambiguities: List[str] = Field(default_factory=list)
    currency: str
    column_currencies: Dict[str, str] = Field(default_factory=dict)
    column_units: Dict[str, str] = Field(default_factory=dict)
    id_columns: List[str] = Field(default_factory=list)
    primary_key_candidates: List[str] = Field(default_factory=list)
    stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def summary_text(self) -> str:
        """Concise summary for prompts or UI."""
        return (
            f"Dataset: {self.filename} | Rows: {self.rows:,} | Cols: {self.columns} | "
            f"Duplicates: {self.duplicates} | Missing Values: {sum(self.missing_values.values())} | "
            f"Date Range: {self.date_range.min or 'N/A'} to {self.date_range.max or 'N/A'} | "
            f"Currency: {self.currency}"
        )


class MultiDatasetProfile(BaseModel):
    datasets: Dict[str, DatasetProfile]
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    has_contradictions: bool = False


def profile_dataset(df: pd.DataFrame, filename: str) -> DatasetProfile:
    """
    Profile a single dataset DataFrame deterministically.
    """
    schema_info = detect_schema(df)
    dup_info = detect_duplicates(df)
    missing_info = detect_missing_values(df)
    date_info = detect_dates(df)
    curr_info = detect_currency(df, filename=filename)
    unit_info = detect_units(df)

    p_range = date_info.get("primary_date_range", {})
    date_range_obj = DateRange(min=p_range.get("min"), max=p_range.get("max"))

    profile = DatasetProfile(
        filename=filename,
        rows=len(df),
        columns=len(df.columns),
        column_names=schema_info["columns"],
        data_types=schema_info["data_types"],
        numeric_columns=schema_info["numeric_columns"],
        categorical_columns=schema_info["categorical_columns"],
        duplicates=dup_info["duplicate_count"],
        duplicate_percentage=dup_info["duplicate_percentage"],
        duplicate_policy=dup_info["policy_advisory"],
        missing_values=missing_info["missing_counts"],
        missing_percentages=missing_info["missing_percentages"],
        has_missing=missing_info["has_missing"],
        date_columns=date_info["date_columns"],
        date_range=date_range_obj,
        present_months=date_info.get("present_months", {}),
        missing_months=date_info.get("missing_months", {}),
        date_ambiguities=date_info.get("date_ambiguities", []),
        currency=curr_info["primary_currency"],
        column_currencies=curr_info.get("column_currencies", {}),
        column_units=unit_info.get("column_units", {}),
        id_columns=schema_info["id_columns"],
        primary_key_candidates=schema_info["primary_key_candidates"],
        stats=schema_info["stats"],
    )

    log_event("DATASET_PROFILED", {
        "filename": filename,
        "rows": profile.rows,
        "cols": profile.columns,
        "duplicates": profile.duplicates,
        "currency": profile.currency,
    })

    return profile


def profile_multiple_datasets(dfs: Dict[str, pd.DataFrame]) -> MultiDatasetProfile:
    """
    Profile a dictionary of datasets and analyze cross-table relationships.
    """
    profiles: Dict[str, DatasetProfile] = {}
    for name, df in dfs.items():
        profiles[name] = profile_dataset(df, filename=name)

    rel_info = detect_relationships(dfs)

    return MultiDatasetProfile(
        datasets=profiles,
        relationships=rel_info.get("relationships", []),
        contradictions=rel_info.get("contradictions", []),
        has_contradictions=rel_info.get("has_contradictions", False),
    )
