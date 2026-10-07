"""
Core VerifyAI pipeline orchestrator.
Executes the end-to-end verification-first workflow:
Profile -> Trap Check -> Plan -> CodeGen -> Exec 1 -> Fresh Exec 2 -> Compare -> Sanity -> Final Response.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from pydantic import BaseModel, Field

from profiler.profiler import (
    DatasetProfile,
    MultiDatasetProfile,
    profile_dataset,
    profile_multiple_datasets,
)
from traps.trap_detector import detect_data_traps
from traps.refusal import RefusalPayload, RefusalException
from analyst.question_parser import AnalystEngine
from analyst.planner import QueryPlan
from analyst.response_parser import parse_and_format_response
from verifier.verifier import verify_code, VerificationResult
from database.db import get_db, Database
from llm.client import LLMClient
from utils.logging import get_logger, log_event

logger = get_logger("VerifyAI.Core")


class AnalysisOutput(BaseModel):
    response_type: str  # ANSWERED | ANSWERED_WITH_ASSUMPTIONS | REFUSED
    confidence: str     # HIGH | MEDIUM | LOW
    answer: Optional[str] = None
    verification_status: str  # PASSED | FAILED | REFUSED
    evidence: Dict[str, Any] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)
    data_quality_issues: List[str] = Field(default_factory=list)
    sanity_warnings: List[str] = Field(default_factory=list)
    code: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    verification_details: Optional[Dict[str, Any]] = None
    refusal_reason: Optional[str] = None
    data_issue: Optional[str] = None
    what_would_be_needed: Optional[str] = None


class VerifyAIEngine:
    def __init__(self, db: Optional[Database] = None, llm_client: Optional[LLMClient] = None):
        self.db = db or get_db()
        self.llm_client = llm_client or LLMClient()
        self.analyst = AnalystEngine(self.llm_client)

    def run_pipeline(
        self,
        question: str,
        datasets: Dict[str, pd.DataFrame],
        dataset_paths: Dict[str, str],
        dataset_id: Optional[str] = None,
    ) -> AnalysisOutput:
        """
        Executes the full Verification-First pipeline.
        """
        # Save question to DB
        q_id = self.db.save_question(question, dataset_id=dataset_id)
        log_event("PIPELINE_RUN_STARTED", {"question": question, "datasets": list(datasets.keys())})

        # Step 1: Profiling
        multi_profile = profile_multiple_datasets(datasets)

        # Step 2: Query Planning, Scoped Trap Detection & Code Generation
        try:
            plan, code = self.analyst.process_question(question, multi_profile, dataset_paths)
        except RefusalException as re:
            payload = re.payload
            self.db.save_analysis(
                question_id=q_id,
                answer=None,
                response_type="REFUSED",
                confidence="LOW",
                code=payload.code,
                assumptions=list(dict.fromkeys(payload.assumptions)),
                evidence=payload.evidence,
                verification_status="NOT_EXECUTED",
            )
            return AnalysisOutput(
                response_type="REFUSED",
                confidence="LOW",
                answer=None,
                verification_status="REFUSED",
                refusal_reason=payload.reason,
                data_issue=payload.data_issue,
                what_would_be_needed=payload.what_would_be_needed,
                data_quality_issues=[payload.data_issue] if payload.data_issue else [],
                code=payload.code,
            )

        # Collect data quality issues for the required datasets only
        dq_issues = []
        for name in plan.datasets:
            if name in multi_profile.datasets:
                p = multi_profile.datasets[name]
                if p.duplicates > 0:
                    dq_issues.append(f"[{name}] {p.duplicates} duplicate rows detected ({p.duplicate_percentage}%).")
                if p.has_missing:
                    missing_summary = ", ".join(f"{c}: {cnt}" for c, cnt in p.missing_values.items() if cnt > 0)
                    dq_issues.append(f"[{name}] Missing values detected ({missing_summary}).")
                if p.date_ambiguities:
                    for amb in p.date_ambiguities:
                        dq_issues.append(f"[{name}] {amb}")

        # Step 3: Fresh Subprocess Execution & Verification
        try:
            ver_res: VerificationResult = verify_code(
                code=code,
                metric_name=plan.metric,
                dataset_name=plan.dataset,
                multi_profile=multi_profile,
                plan=plan,
                dataset_paths=dataset_paths,
            )
        except RefusalException as re:
            payload = re.payload
            self.db.save_analysis(
                question_id=q_id,
                answer=None,
                response_type="REFUSED",
                confidence="LOW",
                code=code,
                assumptions=plan.assumptions,
                evidence={"plan": plan.model_dump()},
                verification_status="FAILED",
            )
            return AnalysisOutput(
                response_type="REFUSED",
                confidence="LOW",
                answer=None,
                verification_status="FAILED",
                refusal_reason=payload.reason,
                data_issue=payload.data_issue,
                what_would_be_needed=payload.what_would_be_needed,
                data_quality_issues=dq_issues,
                code=code,
                plan=plan.model_dump(),
            )

        # Step 4: Verification Result Evaluation
        if not ver_res.match:
            # Verification failed: reproducibility mismatch
            refusal_payload = RefusalPayload(
                response_type="REFUSED",
                confidence="LOW",
                reason=f"Verification failed: Result could not be reproduced across independent execution runs. {ver_res.comparison_message}",
                data_issue="Non-deterministic computation or state discrepancy between fresh runs.",
                what_would_be_needed="Check calculation stability and deterministic sorting.",
                code=code,
            )
            self.db.save_analysis(
                question_id=q_id,
                answer=None,
                response_type="REFUSED",
                confidence="LOW",
                code=code,
                assumptions=plan.assumptions,
                evidence={"execution_1": ver_res.execution_1, "execution_2": ver_res.execution_2},
                verification_status="FAILED",
            )
            return AnalysisOutput(
                response_type="REFUSED",
                confidence="LOW",
                answer=None,
                verification_status="FAILED",
                refusal_reason=refusal_payload.reason,
                data_issue=refusal_payload.data_issue,
                what_would_be_needed=refusal_payload.what_would_be_needed,
                data_quality_issues=dq_issues,
                code=code,
                plan=plan.model_dump(),
                verification_details=ver_res.model_dump(),
            )

        # Step 5: Format Final Response
        answer_text, resp_type, confidence, evidence = parse_and_format_response(
            ver_res.execution_1,
            plan,
            multi_profile,
            ver_res.sanity_warnings,
        )

        import hashlib
        dataset_meta = "|".join(f"{k}:{len(v)}" for k, v in sorted(datasets.items()))
        ds_hash = hashlib.sha256(dataset_meta.encode("utf-8")).hexdigest()[:16]

        # Save to DB
        analysis_id = self.db.save_analysis(
            question_id=q_id,
            answer=answer_text,
            response_type=resp_type,
            confidence=confidence,
            code=code,
            assumptions=plan.assumptions,
            evidence=evidence,
            verification_status="PASSED",
        )
        self.db.save_verification_history(
            analysis_id=analysis_id,
            execution_1=ver_res.execution_1,
            execution_2=ver_res.execution_2,
            match=True,
            status="PASSED",
        )
        self.db.record_audit_entry(
            run_id=q_id,
            dataset_hash=ds_hash,
            query_plan_json=plan.model_dump_json(),
            code=code,
            primary_result=ver_res.execution_1,
            secondary_result=ver_res.execution_2,
            verification_status="PASSED",
            confidence=confidence,
        )

        return AnalysisOutput(
            response_type=resp_type,
            confidence=confidence,
            answer=answer_text,
            verification_status="PASSED",
            evidence=evidence,
            assumptions=plan.assumptions,
            data_quality_issues=dq_issues,
            sanity_warnings=ver_res.sanity_warnings,
            code=code,
            plan=plan.model_dump(),
            verification_details=ver_res.model_dump(),
        )
