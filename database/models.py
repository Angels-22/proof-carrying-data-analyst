"""
Database models and Pydantic schemas for VerifyAI.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetRecord(BaseModel):
    id: str
    filename: str
    filepath: str
    upload_time: str
    row_count: int
    column_count: int
    profile_json: str


class QuestionRecord(BaseModel):
    id: str
    dataset_id: Optional[str] = None
    question: str
    created_at: str


class AnalysisRecord(BaseModel):
    id: str
    question_id: str
    answer: Optional[str] = None
    response_type: str  # ANSWERED, ANSWERED_WITH_ASSUMPTIONS, REFUSED
    confidence: str     # HIGH, MEDIUM, LOW
    code: Optional[str] = None
    assumptions: str    # JSON string
    evidence: str       # JSON string
    verification_status: str
    created_at: str


class VerificationRecord(BaseModel):
    id: str
    analysis_id: str
    execution_1: Optional[str] = None
    execution_2: Optional[str] = None
    match: int          # 1 or 0
    status: str         # PASSED, FAILED, REFUSED
    timestamp: str
