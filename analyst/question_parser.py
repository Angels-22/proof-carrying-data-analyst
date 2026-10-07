"""
Question parsing orchestrator for VerifyAI Analyst.
Coordinates question understanding, query planning, validation, scoped trap checks, and code generation.
Architecture:
QUESTION -> PLAN -> PLAN VALIDATION -> IDENTIFY REQUIRED DATASETS -> TRAP DETECTION ON REQUIRED DATASETS ONLY -> CODE GENERATION.
"""

from typing import Any, Dict, List, Optional, Tuple
from profiler.profiler import MultiDatasetProfile
from traps.trap_detector import detect_data_traps
from traps.refusal import RefusalException, RefusalPayload
from llm.client import LLMClient
from .planner import QueryPlan, create_query_plan
from .code_generator import generate_analysis_code
from utils.logging import get_logger, log_event

logger = get_logger("VerifyAI.QuestionParser")


class AnalystEngine:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def process_question(
        self,
        question: str,
        multi_profile: MultiDatasetProfile,
        dataset_paths: Dict[str, str],
    ) -> Tuple[QueryPlan, str]:
        """
        Parses question and produces (QueryPlan, generated_python_code).
        Raises RefusalException if plan validation fails or a trap is detected on required data.
        """
        log_event("QUESTION_RECEIVED", {"question": question})

        # Step 1: Query Planning & Validation against profile invariants
        plan = create_query_plan(question, multi_profile, self.llm_client)

        # Step 2: Build Scoped Profile containing ONLY the required datasets
        scoped_datasets = {
            ds: multi_profile.datasets[ds]
            for ds in plan.datasets
            if ds in multi_profile.datasets
        }
        scoped_relationships = [
            r for r in multi_profile.relationships
            if r["dataset_a"] in plan.datasets and r["dataset_b"] in plan.datasets
        ]
        scoped_contradictions = [
            c for c in multi_profile.contradictions
            if c["dataset_a"] in plan.datasets and c["dataset_b"] in plan.datasets
        ]
        scoped_profile = MultiDatasetProfile(
            datasets=scoped_datasets,
            relationships=scoped_relationships,
            contradictions=scoped_contradictions,
            has_contradictions=len(scoped_contradictions) > 0,
        )

        # Step 3: Run Trap Detection ONLY on the required datasets
        trap_refusal = detect_data_traps(question, scoped_profile, plan=plan)
        if trap_refusal:
            logger.info(f"Question triggered data trap on required data: {trap_refusal.reason}")
            raise RefusalException(trap_refusal)

        # Step 4: Generate sandboxed Python code for the required datasets
        code = generate_analysis_code(plan, scoped_profile, dataset_paths, question, self.llm_client)

        return plan, code
