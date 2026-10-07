"""
VerifyAI - Verification-First Data Analyst
"""

import sys
from pathlib import Path

# Add root directory to sys.path
root_dir = str(Path(__file__).parent.parent.absolute())
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from core import VerifyAIEngine, AnalysisOutput
from profiler import profile_dataset, profile_multiple_datasets, DatasetProfile, MultiDatasetProfile
from verifier import verify_code, VerificationResult

__all__ = [
    "VerifyAIEngine",
    "AnalysisOutput",
    "profile_dataset",
    "profile_multiple_datasets",
    "DatasetProfile",
    "MultiDatasetProfile",
    "verify_code",
    "VerificationResult",
]
