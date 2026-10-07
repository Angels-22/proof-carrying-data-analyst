-- VerifyAI Database Schema

CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    upload_time TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    profile_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    dataset_id TEXT,
    question TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(dataset_id) REFERENCES datasets(id)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    answer TEXT,
    response_type TEXT NOT NULL, -- ANSWERED, ANSWERED_WITH_ASSUMPTIONS, REFUSED
    confidence TEXT NOT NULL,     -- HIGH, MEDIUM, LOW
    code TEXT,
    assumptions TEXT,            -- JSON list
    evidence TEXT,               -- JSON dict/string
    verification_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(question_id) REFERENCES questions(id)
);

CREATE TABLE IF NOT EXISTS verification_history (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL,
    execution_1 TEXT,
    execution_2 TEXT,
    match INTEGER NOT NULL,      -- 1 (True) or 0 (False)
    status TEXT NOT NULL,        -- PASSED, FAILED, REFUSED
    timestamp TEXT NOT NULL,
    FOREIGN KEY(analysis_id) REFERENCES analysis_results(id)
);

-- Tamper-evident Audit Ledger with Hash Chaining (Phase 6)
CREATE TABLE IF NOT EXISTS audit_ledger (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    dataset_hash TEXT NOT NULL,
    query_plan_json TEXT NOT NULL,
    code TEXT,
    primary_result TEXT,
    secondary_result TEXT,
    verification_status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_run_id ON audit_ledger(run_id);
