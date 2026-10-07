"""
File loader utility for CSV and Excel files.
Handles various encodings, malformed headers, empty files, and provides clear errors.
"""

import os
from pathlib import Path
from typing import Tuple
import pandas as pd

from .logging import get_logger

logger = get_logger("VerifyAI.FileLoader")


class DatasetFileError(Exception):
    """Raised when an uploaded file cannot be parsed or is invalid."""
    pass


def load_dataset_file(file_path: str) -> Tuple[pd.DataFrame, str]:
    """
    Load a dataset file into a pandas DataFrame.
    
    Supports: .csv, .tsv, .xlsx, .xls
    Returns: (DataFrame, format_string)
    Raises: DatasetFileError with human-readable diagnostic message.
    """
    path = Path(file_path)
    if not path.exists():
        raise DatasetFileError(f"File not found: '{file_path}'")

    if path.stat().st_size == 0:
        raise DatasetFileError(f"Uploaded file '{path.name}' is empty (0 bytes).")

    ext = path.suffix.lower()

    if ext in [".csv", ".tsv", ".txt"]:
        sep = "\t" if ext == ".tsv" else ","
        encodings_to_try = ["utf-8", "utf-8-sig", "latin1", "cp1252", "iso-8859-1"]
        last_error = None
        for enc in encodings_to_try:
            try:
                df = pd.read_csv(file_path, sep=sep, encoding=enc)
                if df.empty and len(df.columns) == 0:
                    raise DatasetFileError(f"File '{path.name}' contains no readable data rows or columns.")
                logger.info(f"Loaded '{path.name}' successfully ({len(df)} rows, {len(df.columns)} cols) with encoding {enc}")
                return df, "csv"
            except UnicodeDecodeError as ude:
                last_error = ude
                continue
            except pd.errors.EmptyDataError:
                raise DatasetFileError(f"File '{path.name}' is empty or contains no valid rows.")
            except Exception as e:
                last_error = e
                # Fall through to retry or raise
        raise DatasetFileError(f"Failed to read CSV '{path.name}': {str(last_error)}")

    elif ext in [".xlsx", ".xls"]:
        try:
            df = pd.read_excel(file_path, engine="openpyxl" if ext == ".xlsx" else None)
            if df.empty and len(df.columns) == 0:
                raise DatasetFileError(f"Excel file '{path.name}' contains no data on its primary sheet.")
            logger.info(f"Loaded Excel '{path.name}' successfully ({len(df)} rows, {len(df.columns)} cols)")
            return df, "excel"
        except Exception as e:
            raise DatasetFileError(f"Corrupt or unreadable Excel file '{path.name}': {str(e)}")

    elif ext == ".parquet":
        try:
            df = pd.read_parquet(file_path)
            if df.empty and len(df.columns) == 0:
                raise DatasetFileError(f"Parquet file '{path.name}' contains no readable rows or columns.")
            logger.info(f"Loaded Parquet '{path.name}' successfully ({len(df)} rows, {len(df.columns)} cols)")
            return df, "parquet"
        except Exception as e:
            raise DatasetFileError(f"Corrupt or unreadable Parquet file '{path.name}': {str(e)}")

    else:
        raise DatasetFileError(f"Unsupported file format '{ext}'. VerifyAI supports .csv, .tsv, .xlsx, .xls, and .parquet.")

