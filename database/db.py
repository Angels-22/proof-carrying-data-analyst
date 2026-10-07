"""
Database connection and repository for VerifyAI.
Automatically initializes SQLite schema.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logging import get_logger

logger = get_logger("VerifyAI.Database")

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verifyai.db"
)


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            return
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_script = f.read()
        with self._get_connection() as conn:
            conn.executescript(sql_script)
            conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def save_dataset(
        self,
        dataset_id: str,
        filename: str,
        filepath: str,
        row_count: int,
        column_count: int,
        profile_json: str,
    ) -> str:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO datasets 
                (id, filename, filepath, upload_time, row_count, column_count, profile_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    filename,
                    filepath,
                    datetime.now().isoformat(),
                    row_count,
                    column_count,
                    profile_json,
                ),
            )
            conn.commit()
        return dataset_id

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None

    def list_datasets(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM datasets ORDER BY upload_time DESC")
            return [dict(r) for r in cur.fetchall()]

    def save_question(self, question: str, dataset_id: Optional[str] = None) -> str:
        q_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO questions (id, dataset_id, question, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (q_id, dataset_id, question, datetime.now().isoformat()),
            )
            conn.commit()
        return q_id

    def save_analysis(
        self,
        question_id: str,
        answer: Optional[str],
        response_type: str,
        confidence: str,
        code: Optional[str],
        assumptions: List[str],
        evidence: Dict[str, Any],
        verification_status: str,
    ) -> str:
        analysis_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO analysis_results 
                (id, question_id, answer, response_type, confidence, code, assumptions, evidence, verification_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    question_id,
                    str(answer) if answer is not None else None,
                    response_type,
                    confidence,
                    code,
                    json.dumps(assumptions),
                    json.dumps(evidence),
                    verification_status,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        return analysis_id

    def save_verification_history(
        self,
        analysis_id: str,
        execution_1: Any,
        execution_2: Any,
        match: bool,
        status: str,
    ) -> str:
        v_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO verification_history
                (id, analysis_id, execution_1, execution_2, match, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    v_id,
                    analysis_id,
                    json.dumps(execution_1, default=str),
                    json.dumps(execution_2, default=str),
                    1 if match else 0,
                    status,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        return v_id

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    a.id as analysis_id,
                    q.question,
                    q.dataset_id,
                    a.answer,
                    a.response_type,
                    a.confidence,
                    a.verification_status,
                    a.created_at,
                    v.execution_1,
                    v.execution_2,
                    v.match
                FROM analysis_results a
                JOIN questions q ON a.question_id = q.id
                LEFT JOIN verification_history v ON v.analysis_id = a.id
                ORDER BY a.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            return rows

    def record_audit_entry(
        self,
        run_id: str,
        dataset_hash: str,
        query_plan_json: str,
        code: Optional[str],
        primary_result: Any,
        secondary_result: Any,
        verification_status: str,
        confidence: str,
    ) -> str:
        """
        Records a tamper-evident audit ledger entry using SHA-256 hash chaining.
        """
        import hashlib
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        primary_str = json.dumps(primary_result) if primary_result is not None else ""
        sec_str = json.dumps(secondary_result) if secondary_result is not None else ""

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT record_hash FROM audit_ledger ORDER BY timestamp DESC LIMIT 1")
            last_row = cur.fetchone()
            prev_hash = last_row["record_hash"] if last_row else "GENESIS_BLOCK_000000000000"

            record_payload = f"{prev_hash}|{run_id}|{timestamp}|{dataset_hash}|{query_plan_json}|{primary_str}|{sec_str}|{verification_status}"
            record_hash = hashlib.sha256(record_payload.encode("utf-8")).hexdigest()

            conn.execute(
                """
                INSERT INTO audit_ledger (
                    id, run_id, timestamp, dataset_hash, query_plan_json,
                    code, primary_result, secondary_result, verification_status,
                    confidence, previous_hash, record_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id, run_id, timestamp, dataset_hash, query_plan_json,
                    code or "", primary_str, sec_str, verification_status,
                    confidence, prev_hash, record_hash
                ),
            )
            conn.commit()
            return record_hash

    def get_audit_ledger(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM audit_ledger ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]


# Global singleton instance
_db_instance = None


def get_db(db_path: Optional[str] = None) -> Database:
    global _db_instance
    if _db_instance is None or db_path is not None:
        _db_instance = Database(db_path)
    return _db_instance
