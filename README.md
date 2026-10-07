# HNX26PSI08: Proof-Carrying Data Analyst (Agentic GenAI)
Agentic GenAI · Data Analytics · Code Generation · Verification

Team Name: LogicLoom

Team Members: Manisha R - URK24CS1127, Angel S - URK24CS1143, Atisaya S - URK24CS1105.

"Don't blindly trust an AI-generated number. Verify the computation. Expose the assumptions. Refuse when evidence is insufficient."

Python 3.10+ License: MIT Streamlit Tests

Live demo / recorded demo: <add link here> Repository: <add public Git URL here>

Table of Contents
What the Project Does
Why It Matters (Problem Statement)
Technologies, Libraries & Models Used
Data Pipeline
Core Reasoning & Verification Logic
Installation
Configuration
Running the System End-to-End
Reproducing the Demonstrated Results
Sample Input & Output
Evidence & Explanation
Testing
Scope Note: MVP vs Stretch Goals
Repository Structure
Security & Sandboxing
Limitations & Responsible Disclosure
License
1. What the Project Does
The Proof-Carrying Data Analyst is a verification-first, agentic GenAI data analyst. You upload a CSV or Excel file, ask a business question in plain English, and receive a numeric answer together with the evidence needed to independently verify it.

For every question, the system:

Profiles the dataset deterministically (no LLM guesses row counts, types, or date ranges).
Checks for data traps before any computation: missing time periods, missing columns, currency conflicts (USD + INR), unit conflicts (kg + litres), and contradictory sources.
Plans the query into a structured, inspectable plan.
Generates sandboxed Pandas code.
Executes the code twice, in two separate, freshly spawned subprocesses.
Compares both results using strict equality for exact types and numeric tolerances for floats.
Sanity-checks the result (NaN/Inf, negative or zero totals, empty filters).
Returns one of three verdicts and logs everything to a SQLite ledger:
Verdict	Meaning
ANSWERED	Result computed and verified with no caveats.
ANSWERED_WITH_ASSUMPTIONS	Result verified, but assumptions are shown explicitly (e.g. duplicates, calendar vs fiscal months).
REFUSED	Data is insufficient or conflicting. The system explains why and what is needed instead of guessing.
Positioning: The verifier checks reproducibility and internal consistency. The system exposes assumptions and refuses when the available data cannot support an answer. It does not claim that the user asked the right business question.

2. Why It Matters (Problem Statement)
Organizations are adopting generative-AI analysts, but high-stakes decisions suffer from four recurring failures:

Hallucinated numbers: LLMs produce plausible but fabricated figures.
Silent assumptions: Missing months or ambiguous columns are quietly papered over.
Incompatible units and currencies: USD and INR (or kg and litres) get added together without warning.
No reproducibility: There is no way to confirm a number can be recomputed from the raw data.
This project addresses each one directly: numbers come from executed code (not model text), assumptions are surfaced, incompatible aggregations are refused, and every answer ships with re-executable evidence.

3. Technologies, Libraries & Models Used
Layer	Technology	Purpose
Language	Python 3.10+	Entire codebase
Data processing	Pandas, NumPy	Deterministic profiling and query execution
Excel support	openpyxl	Reading .xlsx uploads
UI	Streamlit (1.35+)	Executive dashboard
Persistence	SQLite (sqlite3)	Verification ledger (local .db file)
Schemas	Pydantic	Typed models for plans, results, and ledger rows
Sandboxing	subprocess, ast (stdlib)	Isolated execution and static code screening
Testing	unittest (stdlib)	Unit and adversarial tests
LLM (optional)	OpenAI API (model name set via .env)	Natural-language → structured query plan
LLM fallback	Embedded deterministic semantic planner (llm/client.py)	Runs the full system with no API key
Important: The LLM is used only for translating a question into a structured plan. It is never trusted to compute, count, or state a number. All numbers originate from executed Pandas code.

Install exact versions from requirements.txt.

4. Data Pipeline
This section shows how input data is collected → processed → passed through the system.


Stage	Module	What happens
1–2. Collect	utils/file_loader.py	Uploaded CSV/Excel is read with resilient encoding and delimiter handling and saved to data/uploads/.
3. Profile	profiler/	Pure-Pandas extraction of schema, types, null rates, duplicate rows, date span and missing months, currencies (ISO codes, $, ₹, €), physical units, and foreign keys.
4. Trap check	traps/	Compares the question against the profile. Detects temporal gaps, missing columns, currency/unit conflicts, ambiguity (calendar vs fiscal), and cross-table contradictions. Fatal traps short-circuit to a structured refusal.
5. Plan	analyst/planner.py, llm/client.py	Converts the question into a structured plan (metric, aggregation, filters, group-by). OpenAI if configured, otherwise the local deterministic planner.
6. Generate	analyst/code_generator.py	Emits Pandas code from the plan. Code is statically screened (AST) for forbidden modules.
7. Execute twice	verifier/executor.py	Runs the code in two independent subprocesses with scrubbed environment variables and a 10-second timeout.
8. Compare	verifier/result_comparator.py	Exact match for ints, strings, and keys; 1e-9 absolute / 1e-6 relative tolerance for floats.
9. Sanity	verifier/sanity_checks.py	Flags NaN/Inf, unexpected negatives, zero results from empty filters.
10. Persist	database/db.py	Stores question, plan, code, both execution results, and verdict in the SQLite ledger.
11. Present	analyst/response_parser.py, app.py	Packages the answer, verdict, assumptions, and re-executable code for display.
12. Core Reasoning & Verification Logic
The central idea is that an answer is only as trustworthy as its evidence. The system implements this as six layered guarantees:

Deterministic profiling: Facts about the data (row count, date range, units) come from code, never from a model.
Pre-flight trap interception: The system refuses before computing when the data cannot support the question (e.g. asking for August revenue when August is absent).
Dual-subprocess verification: Two clean processes run the identical generated code. Agreement proves the result is reproducible and not dependent on hidden state.
Tolerance-aware comparison: Floats are compared with explicit tolerances, avoiding traps like 0.1 + 0.2 != 0.3.
Sanity checks: Domain-level checks catch results that are reproducible but implausible.
Constructive refusal: When data is insufficient, the system returns a 3-part explanation instead of a guess.
Core logic lives in core.py (orchestrator), traps/trap_detector.py, and verifier/verifier.py.

6. Installation
Prerequisites
Python 3.10 or newer
pip
Git
Steps
# 1. Clone the repository
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

# 2. (Recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
7. Configuration
The system works out of the box with no configuration.

To optionally enable the OpenAI-backed planner:

cp .env.example .env
Then edit .env:

OPENAI_API_KEY=your_key_here
Mode	Condition	Behavior
Local Deterministic Mode	No OPENAI_API_KEY set	Embedded semantic planner; fully offline, fully reproducible.
LLM-Assisted Mode	OPENAI_API_KEY set	OpenAI plans the query; all computation and verification are still performed by the local pipeline.
API keys and secrets are scrubbed from the environment before any generated code runs.

8. Running the System End-to-End
# Step 1: generate the demo datasets
python data/demo/create_demo_data.py

# Step 2: launch the application
streamlit run app.py
Open http://localhost:8501, then:

Upload a dataset (or pick one generated in data/demo/).
Review the profile (schema, date range, duplicates, currencies, units).
Ask a question, for example "What is the total revenue?"
Inspect the verdict, assumptions, dual-execution evidence, and generated code.
Ask "What was the total revenue in August?" to see a constructive refusal.
9. Reproducing the Demonstrated Results
Anyone can reproduce the demo from a clean clone:

git clone https://github.com/<your-username>/<repo-name>.git && cd <repo-name>
pip install -r requirements.txt
python data/demo/create_demo_data.py
python -m unittest discover tests          # reproduces all 22 verified scenarios
streamlit run app.py                       # reproduces the interactive demo
The 20 adversarial scenarios in the table below are the same ones executed in the live demo. Each is encoded in tests/adversarial_tests.py, and the expected verdicts are asserted automatically.

#	Scenario	Query	Expected Verdict
1	Simple total	"What is the total revenue?"	ANSWERED
2	Average	"What is the average order quantity?"	ANSWERED
3	Maximum	"What is the maximum revenue in a single transaction?"	ANSWERED
4	Minimum	"What is the minimum unit price?"	ANSWERED
5	Group-by	"Which region generated the most revenue?"	ANSWERED
6	Sorting	"Sort regions by total sales volume"	ANSWERED
7	Date filter	"What was the total revenue in February?"	ANSWERED_WITH_ASSUMPTIONS
8	Trend / MoM	"What was the revenue trend between January and February?"	ANSWERED_WITH_ASSUMPTIONS
9	Missing month	"What was the total revenue in August?"	REFUSED
10	Missing column	"What is the customer satisfaction score (CSAT)?"	REFUSED
11	Duplicate handling	"What is the total revenue?"	ANSWERED_WITH_ASSUMPTIONS (duplicates flagged)
12	Currency mismatch	"What is combined revenue across USD and INR?"	REFUSED
13	Unit mismatch	"What is combined total of kg and litres?"	REFUSED
14	Ambiguous date	"Show revenue for February"	ANSWERED_WITH_ASSUMPTIONS
15	Contradictory sources	Conflicting revenue tables, no authoritative source	REFUSED
16	Empty filter	Filter returning zero rows	Sanity warning (0.0)
17	Nonexistent product	Filter on a non-existent product ID	Sanity warning (0.0)
18	Multi-table join	"Which product category generated the highest revenue?"	ANSWERED (joined on product_id)
19	Multi-step query	"Which customer purchased the most in North America?"	ANSWERED_WITH_ASSUMPTIONS
20	Impossible query	"What will Google's stock price be tomorrow?"	REFUSED
10. Sample Input & Output
Example A: Answered with verified evidence
Input

Dataset	data/demo/sales.csv
Question	What is the total revenue?
Output (representative; exact values depend on the generated demo data)

VERDICT: ANSWERED_WITH_ASSUMPTIONS

Answer: Total revenue = <value computed from sales.csv>

Assumptions:
  - N exact duplicate rows were detected; they were included/excluded as stated in the plan.

Verification:
  Run 1 (subprocess A): <value>
  Run 2 (fresh subprocess B): <value>
  Comparator: MATCH (abs tol 1e-9, rel tol 1e-6)
  Sanity checks: PASSED

Generated code:
  result = df["revenue"].sum()
Example B: Constructive refusal
Input

Dataset	data/demo/sales.csv
Question	What was the total revenue in August?
Output

REFUSED

Reason: August data is not present in the uploaded dataset 'sales.csv'.
        Available range is 2025-01-05 to 2025-11-26.

Data issue: Temporal gap: Month August missing from date column 'date'.

What would be needed: Provide dataset records for August to compute
                      metrics for this period.
Every refusal follows this 3-part structure: Reason → Data issue → What would be needed.

11. Evidence & Explanation
Every answer exposes the following, visible in the UI and stored permanently in the ledger:

Evidence	Where to find it
Dataset profile (types, nulls, duplicates, date span, units, currencies)	Profile panel / profiler/
Intermediate structured query plan	Plan panel / analyst/planner.py
Exact generated Pandas code	Code panel (re-executable by anyone)
Results of both subprocess executions	Verification panel
Comparator verdict and tolerances applied	Verification panel
Sanity-check results	Verification panel
Timestamped record of the full run	SQLite ledger (schema in database/schema.sql)
To audit past runs:

sqlite3 <ledger-file>.db "SELECT * FROM <table> ORDER BY rowid DESC LIMIT 5;"
(Use the ledger filename and table names defined in database/db.py and database/schema.sql.)

12. Testing
python -m unittest discover tests
File	Covers
tests/test_profiler.py	Schema, duplicate, missing, date, currency, unit, relationship detectors
tests/test_verifier.py	Dual-process execution, comparator, sanity checks
tests/test_traps.py	Trap detection and ambiguity handling
tests/test_refusal.py	Structured 3-part refusal payloads
tests/adversarial_tests.py	20 end-to-end adversarial scenarios (table in Section 9)
13. Scope Note: MVP vs Stretch Goals
✅ Minimum Viable Solution (implemented and demonstrated)
CSV/Excel upload and deterministic profiling
Pre-flight trap detection (missing month, missing column, currency/unit mismatch)
Structured query planning with a local deterministic planner (no API key needed)
Sandboxed Pandas code generation and dual-subprocess execution
Tolerance-aware result comparison and sanity checks
Three-verdict output with structured 3-part refusals
SQLite verification ledger
Streamlit dashboard
22 passing tests, including 20 adversarial scenarios
🚀 Stretch Goals (attempted / additional)
Optional OpenAI-backed planner with automatic fallback to local mode
Multi-table joins via detected foreign keys
Cross-table contradiction detection
Calendar-vs-fiscal ambiguity handling with explicit assumptions
AST-based static rejection of dangerous modules
Secret scrubbing in logs and subprocess environments
🔭 Not Implemented (future work)
Container-level isolation (Docker / gVisor)
DuckDB / Polars backends for datasets beyond ~5M rows
Semantic verification of whether the question matches business intent
14. Repository Structure
HNX26PSI08/
├── app.py                      # Streamlit executive dashboard
├── core.py                     # Pipeline orchestrator
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment configuration
├── README.md                   # This file
│
├── data/
│   ├── uploads/                # User-uploaded datasets
│   └── demo/                   # Demo datasets and generator script
│
├── database/
│   ├── db.py                   # SQLite repository and connection manager
│   ├── models.py               # Pydantic schemas / DB models
│   └── schema.sql              # Relational schema
│
├── profiler/                   # Deterministic profiling (no LLM)
│   ├── schema_detector.py
│   ├── duplicate_detector.py
│   ├── missing_detector.py
│   ├── date_detector.py
│   ├── currency_detector.py
│   ├── unit_detector.py
│   ├── relationship_detector.py
│   └── profiler.py
│
├── analyst/
│   ├── prompts.py              # Strict verification prompts
│   ├── planner.py              # Structured query planner
│   ├── code_generator.py       # Sandboxed Pandas code generator
│   ├── question_parser.py      # Question understanding orchestrator
│   └── response_parser.py      # Evidence packager and formatter
│
├── verifier/
│   ├── executor.py             # Subprocess runner
│   ├── result_comparator.py    # Tolerance-aware deep comparator
│   ├── sanity_checks.py        # NaN/Inf, sign, zero checks
│   └── verifier.py             # Dual-execution verification engine
│
├── traps/
│   ├── trap_detector.py        # Months, currencies, units
│   ├── ambiguity.py            # Calendar vs fiscal assumptions
│   ├── contradictions.py       # Cross-table conflict detector
│   └── refusal.py              # 3-part refusal payloads
│
├── llm/
│   └── client.py               # OpenAI abstraction + local fallback
│
├── utils/
│   ├── file_loader.py
│   ├── serialization.py
│   ├── logging.py
│   └── formatting.py
│
├── tests/
│   ├── test_profiler.py
│   ├── test_verifier.py
│   ├── test_traps.py
│   ├── test_refusal.py
│   └── adversarial_tests.py
│
└── docs/
    ├── architecture.md         # In-depth architecture and diagrams
    ├── demo.md                 # 5-minute demo script
    └── judge_questions.md      # Known weaknesses and FAQs
    
16. Security & Sandboxing
Subprocess isolation: Generated code never runs in the main application process.
Environment scrubbing: API keys, tokens, and credentials are removed before launching subprocesses.
AST blacklisting: Code importing forbidden modules (socket, urllib, requests) or calling destructive functions (shutil.rmtree) is rejected before execution.
Execution timeout: Subprocesses are terminated after 10 seconds.

18. Limitations & Responsible Disclosure
Verification scope: The system verifies execution reproducibility, internal consistency, and data presence. It cannot guarantee the user asked the right business question.
Sandbox strength: Subprocess isolation suits local analytics. For production, use isolated containers (Docker / gVisor).
Scale: In-memory Pandas is suited to datasets up to roughly 5 million rows; beyond that, DuckDB or Polars is recommended.
Heuristic detection: Currency, unit, and date detection are rule-based and may miss unusual formats.

20. License
This project is open-sourced under the MIT License.
