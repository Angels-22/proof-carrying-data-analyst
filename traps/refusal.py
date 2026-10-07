"""
Refusal engine for VerifyAI.
Structured refusal payload that explains why an answer cannot be provided,
what data issue was detected, and what information would be required.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RefusalPayload(BaseModel):
    response_type: str = "REFUSED"
    confidence: str = "LOW"
    reason: str
    data_issue: str
    what_would_be_needed: str
    verification_status: str = "NOT_EXECUTED"
    assumptions: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    code: Optional[str] = None
    answer: Optional[str] = None

    def formatted_text(self) -> str:
        return (
            f"REFUSED\n\n"
            f"Reason: {self.reason}\n\n"
            f"Data issue: {self.data_issue}\n\n"
            f"What would be needed: {self.what_would_be_needed}"
        )


class RefusalException(Exception):
    """Raised when an unanswerable, contradictory, or invalid query must be refused."""
    def __init__(self, payload: RefusalPayload):
        super().__init__(payload.reason)
        self.payload = payload
