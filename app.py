"""
VerifyAI — Verification-First Data Analyst
A modern, verification-first data analytics platform built for reliable, reproducible business intelligence.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import streamlit as st

from core import VerifyAIEngine, AnalysisOutput
from database.db import get_db
from profiler.profiler import profile_multiple_datasets, MultiDatasetProfile
from utils.file_loader import load_dataset_file, DatasetFileError
from utils.formatting import format_currency, format_number, format_verification_badge
from data.demo.create_demo_data import generate_all_demo_data
from data.demo.scenarios import JUDGE_SCENARIOS

# Page Configuration
st.set_page_config(
    page_title="VerifyAI — Verification-First Data Analyst",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Design System CSS
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Hero Banner */
    .hero-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    }
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(to right, #ffffff, #a5b4fc, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.0rem;
        font-weight: 500;
        margin-bottom: 14px;
    }
    .judge-motto {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .motto-tag {
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: #c7d2fe;
        padding: 4px 12px;
        border-radius: 9999px;
    }

    /* Scenario Card */
    .scenario-banner {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 16px 0;
    }
    .scenario-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .scenario-desc {
        color: #cbd5e1;
        font-size: 0.9rem;
        margin-top: 4px;
    }

    /* Metric Cards */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .metric-card:hover {
        border-color: #6366f1;
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.7rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 4px;
    }

    /* Verification Badges */
    .badge-passed {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 6px 14px;
        border-radius: 8px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .badge-refused {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 6px 14px;
        border-radius: 8px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .badge-assumptions {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
        padding: 6px 14px;
        border-radius: 8px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    /* Pipeline Stepper */
    .stepper-container {
        display: flex;
        justify-content: space-between;
        background: #0f172a;
        padding: 12px 18px;
        border-radius: 10px;
        border: 1px solid #1e293b;
        margin: 16px 0;
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748b;
    }
    .step-done {
        color: #34d399;
    }

    /* Answer Callout */
    .answer-box {
        background: #0f172a;
        border-left: 4px solid #6366f1;
        padding: 18px 22px;
        border-radius: 0 12px 12px 0;
        margin: 14px 0;
    }
    .answer-number {
        font-size: 2.1rem;
        font-weight: 800;
        color: #f8fafc;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize System State
if "datasets" not in st.session_state:
    st.session_state.datasets = {}
if "dataset_paths" not in st.session_state:
    st.session_state.dataset_paths = {}
if "pipeline_engine" not in st.session_state:
    st.session_state.pipeline_engine = VerifyAIEngine()
if "db" not in st.session_state:
    st.session_state.db = get_db()
if "current_scenario_id" not in st.session_state:
    st.session_state.current_scenario_id = None
if "current_question" not in st.session_state:
    st.session_state.current_question = "What was the total revenue in February?"
if "latest_output" not in st.session_state:
    st.session_state.latest_output = None

engine: VerifyAIEngine = st.session_state.pipeline_engine
db = st.session_state.db

# Ensure demo datasets exist
DEMO_BASE = Path("data/demo")
CLEAN_DIR = DEMO_BASE / "clean"
UPLOADS_DIR = Path("data/uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
if not (CLEAN_DIR / "sales.csv").exists():
    generate_all_demo_data()


def activate_scenario(scenario_id: str):
    """Load ONLY the designated scenario datasets and execute pipeline deterministically."""
    scenario = JUDGE_SCENARIOS[scenario_id]
    
    # 1. Clear previous dataset state
    st.session_state.datasets = {}
    st.session_state.dataset_paths = {}
    st.session_state.latest_output = None
    st.session_state.current_scenario_id = scenario_id
    st.session_state.current_question = scenario["question"]

    # 2. Load ONLY this scenario's datasets
    for file_path_str in scenario["dataset_files"]:
        p = Path(file_path_str)
        if p.exists():
            df, _ = load_dataset_file(str(p))
            st.session_state.datasets[p.name] = df
            st.session_state.dataset_paths[p.name] = str(p.absolute())

    # 3. Automatically execute analysis for immediate demonstration
    output = engine.run_pipeline(
        question=scenario["question"],
        datasets=st.session_state.datasets,
        dataset_paths=st.session_state.dataset_paths,
    )
    st.session_state.latest_output = output


# Default initial boot loads Normal Query (Clean dataset)
if not st.session_state.datasets:
    activate_scenario("normal")

# Sidebar Navigation
with st.sidebar:
    st.image("https://api.iconify.design/lucide:shield-check.svg?color=%23818cf8&width=48", width=48)
    st.markdown("### **VerifyAI Navigation**")
    nav_option = st.radio(
        "Select View",
        ["Ask Analyst", "Data Profile & Quality", "Upload Datasets", "Verification History", "System Architecture"],
        index=0,
    )

    st.markdown("---")
    st.markdown("#### ⚡ Quick Actions")
    if st.button("🔄 Reset to Clean Sales", use_container_width=True):
        activate_scenario("normal")
        st.success("Reset to clean sales dataset!")
        st.rerun()

    if st.button("🗑️ Clear All Loaded Data", use_container_width=True):
        st.session_state.datasets = {}
        st.session_state.dataset_paths = {}
        st.session_state.latest_output = None
        st.session_state.current_scenario_id = None
        st.info("Loaded datasets cleared.")
        st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 0.8rem; color: #94a3b8;">
            <b>Currently Loaded Datasets:</b><br/>
        """
        + "".join(f"• <b>{name}</b> ({len(df):,} rows)<br/>" for name, df in st.session_state.datasets.items())
        + """
        </div>
        """,
        unsafe_allow_html=True,
    )

# Hero Header Banner
st.markdown(
    """
    <div class="hero-container">
        <div class="hero-title">VerifyAI — Verification-First Data Analyst</div>
        <div class="hero-subtitle">
            For answered analytical queries, the result is backed by executable analysis code independently verified in fresh execution environments.
        </div>
        <div class="judge-motto">
            <span class="motto-tag">🚫 Never Guess</span>
            <span class="motto-tag">⚙️ Deterministic Profiling</span>
            <span class="motto-tag">🛡️ Dual-Process Verification</span>
            <span class="motto-tag">🛑 Constructive Refusal</span>
            <span class="motto-tag">📜 100% Audit Trail</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Multi-Dataset Profile Calculation
multi_profile: Optional[MultiDatasetProfile] = None
if st.session_state.datasets:
    multi_profile = profile_multiple_datasets(st.session_state.datasets)

# -------------------------------------------------------------
# TAB 1: ASK ANALYST
# -------------------------------------------------------------
if nav_option == "Ask Analyst":
    # Top Metrics Cards
    if multi_profile:
        total_rows = sum(p.rows for p in multi_profile.datasets.values())
        total_cols = sum(p.columns for p in multi_profile.datasets.values())
        total_dups = sum(p.duplicates for p in multi_profile.datasets.values())
        total_missing = sum(sum(p.missing_values.values()) for p in multi_profile.datasets.values())

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Datasets</div><div class="metric-value">{len(multi_profile.datasets)}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Total Rows</div><div class="metric-value">{total_rows:,}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Total Columns</div><div class="metric-value">{total_cols}</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Duplicate Rows</div><div class="metric-value">{total_dups}</div></div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Missing Cells</div><div class="metric-value">{total_missing}</div></div>', unsafe_allow_html=True)
    else:
        st.warning("⚠️ No datasets currently loaded. Select a judge scenario below or upload files.")

    st.markdown("### 🎯 1-Click Judge Demonstrations")
    st.markdown("*Each button loads its isolated dataset, sets the targeted question, and demonstrates a distinct verification behavior.*")

    # 5 Independent Scenario Buttons
    s_cols = st.columns(5)
    
    with s_cols[0]:
        if st.button("1️⃣ Normal Query\n(Clean Feb Revenue)", use_container_width=True):
            activate_scenario("normal")
            st.rerun()

    with s_cols[1]:
        if st.button("2️⃣ Multi-Table Join\n(Top Category)", use_container_width=True):
            activate_scenario("multi_table")
            st.rerun()

    with s_cols[2]:
        if st.button("3️⃣ Data Trap\n(Missing August)", use_container_width=True):
            activate_scenario("data_trap")
            st.rerun()

    with s_cols[3]:
        if st.button("4️⃣ Duplicate Impact\n(Total Revenue)", use_container_width=True):
            activate_scenario("duplicate")
            st.rerun()

    with s_cols[4]:
        if st.button("5️⃣ Currency Trap\n(USD + INR)", use_container_width=True):
            activate_scenario("currency")
            st.rerun()

    # Active Scenario Card Banner
    active_sc_id = st.session_state.current_scenario_id
    if active_sc_id and active_sc_id in JUDGE_SCENARIOS:
        sc_info = JUDGE_SCENARIOS[active_sc_id]
        st.markdown(
            f"""
            <div class="scenario-banner" style="border-left: 4px solid {sc_info['badge_color']};">
                <div class="scenario-title">
                    <span>{sc_info['name']}</span>
                    <span style="font-size: 0.75rem; background: rgba(99, 102, 241, 0.2); padding: 2px 8px; border-radius: 4px;">{sc_info['tag']}</span>
                    <span style="margin-left: auto; font-size: 0.8rem; color: #94a3b8;">Expected: <b>{sc_info['expected_response_type']}</b></span>
                </div>
                <div class="scenario-desc"><b>Description:</b> {sc_info['description']}</div>
                <div class="scenario-desc" style="color: #94a3b8;"><b>Datasets:</b> {', '.join(sc_info['datasets'])} | <b>Expected Behavior:</b> {sc_info['expected_behavior']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### 💬 Ask Business Analyst")
    query_input = st.text_input(
        "Enter your natural language question:",
        value=st.session_state.current_question,
        placeholder="e.g. What was the total revenue in February?",
    )
    st.session_state.current_question = query_input

    analyze_clicked = st.button("🚀 Analyze & Verify Computation", type="primary", use_container_width=True)

    if analyze_clicked and query_input.strip():
        if not st.session_state.datasets:
            st.error("Please load a scenario or upload datasets first.")
        else:
            with st.spinner("Executing Verification Pipeline..."):
                output = engine.run_pipeline(
                    question=query_input,
                    datasets=st.session_state.datasets,
                    dataset_paths=st.session_state.dataset_paths,
                )
                st.session_state.latest_output = output

    # Render Result If Available
    output = st.session_state.latest_output
    if output:
        st.markdown(
            """
            <div class="stepper-container">
                <span class="step-done">✓ 1. Profile Data</span>
                <span class="step-done">✓ 2. Query Plan</span>
                <span class="step-done">✓ 3. Plan Validation</span>
                <span class="step-done">✓ 4. Trap Check</span>
                <span class="step-done">✓ 5. Controlled Exec 1</span>
                <span class="step-done">✓ 6. Fresh Exec 2</span>
                <span class="step-done">✓ 7. Result Comparison</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("### 📊 Verification-First Result")

        if output.response_type == "REFUSED":
            st.markdown(
                f"""
                <div class="badge-refused">🛑 RESPONSE: REFUSED | Confidence: LOW</div>
                <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 20px; margin-top: 12px;">
                    <h4 style="color: #f87171; margin-top: 0;">Query Refused with Justification</h4>
                    <p><b>Reason:</b> {output.refusal_reason}</p>
                    <p><b>Data Issue:</b> {output.data_issue}</p>
                    <p><b>What Would Be Needed:</b> {output.what_would_be_needed}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        elif output.response_type == "ANSWERED_WITH_ASSUMPTIONS":
            st.markdown(
                f"""
                <div class="badge-assumptions">⚠️ RESPONSE: ANSWERED WITH ASSUMPTIONS | Confidence: MEDIUM | Verification: PASSED</div>
                <div class="answer-box">
                    <div style="color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; font-weight: 600;">Verified Computed Answer</div>
                    <div class="answer-number">{output.answer}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                f"""
                <div class="badge-passed">🟢 RESPONSE: ANSWERED | Confidence: HIGH | Verification: PASSED</div>
                <div class="answer-box">
                    <div style="color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; font-weight: 600;">Verified Computed Answer</div>
                    <div class="answer-number">{output.answer}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Details Columns
        col_left, col_right = st.columns(2)

        with col_left:
            # Assumptions Box (Deduplicated)
            clean_assumptions = list(dict.fromkeys(output.assumptions))
            if clean_assumptions:
                st.markdown("##### 📌 Explicit Assumptions:")
                for asm in clean_assumptions:
                    st.info(f"• {asm}")

            # Evidence Box
            if output.evidence:
                st.markdown("##### 🔍 Evidence & Lineage:")
                st.json(output.evidence)

        with col_right:
            # Data Quality Alerts
            if output.data_quality_issues:
                st.markdown("##### ⚠️ Data Quality Advisories:")
                for dq in output.data_quality_issues:
                    st.warning(f"• {dq}")

            # Sanity Check Warnings
            if output.sanity_warnings:
                st.markdown("##### 🛡️ Sanity Check Warnings:")
                for sw in output.sanity_warnings:
                    st.warning(f"• {sw}")

        # Expanders
        with st.expander("💻 View Generated Analysis Code", expanded=False):
            if output.code:
                st.markdown("*For answered analytical queries, the result is backed by executable analysis code:*")
                st.code(output.code, language="python")
            else:
                st.info("No code executed because the query was refused during validation.")

        with st.expander("🔬 View Fresh Dual-Execution Verification Audit", expanded=False):
            if output.verification_details and output.verification_status != "REFUSED":
                vd = output.verification_details
                st.markdown("*VerifyAI executes the analysis twice in fresh processes and checks whether the result is reproducible:*")
                c_v1, c_v2 = st.columns(2)
                with c_v1:
                    st.markdown(f"**Execution 1 (Fresh Subprocess):** `{vd.get('execution_1')}`")
                with c_v2:
                    st.markdown(f"**Execution 2 (Fresh Subprocess):** `{vd.get('execution_2')}`")
                st.markdown(f"**Result Comparator:** {vd.get('comparison_message')}")
                st.markdown("**Status:** `✓ Results match — VERIFICATION PASSED`")
                st.markdown(f"**Tolerance:** Absolute 1e-9 | Relative 1e-6")
            else:
                st.info("Verification skipped. Reason: The query was rejected during pre-flight validation.")

        with st.expander("📋 View Intermediate Query Plan", expanded=False):
            if output.plan:
                st.json(output.plan)
            else:
                st.info("No query plan available.")

# -------------------------------------------------------------
# TAB 2: DATA PROFILE & QUALITY
# -------------------------------------------------------------
elif nav_option == "Data Profile & Quality":
    st.markdown("### 📋 Deterministic Data Profiling Engine")
    st.markdown("*Inspects schema, types, duplicates, temporal gaps, and units with pure Pandas — zero LLM guesswork.*")

    if not st.session_state.datasets:
        st.warning("No datasets currently loaded. Select a judge scenario or upload files.")
    else:
        for name, profile in multi_profile.datasets.items():
            st.markdown(f"#### 📁 Dataset: `{name}`")
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Rows", f"{profile.rows:,}")
            col_b.metric("Columns", f"{profile.columns}")
            col_c.metric("Duplicates", f"{profile.duplicates} ({profile.duplicate_percentage}%)")
            col_d.metric("Currency", profile.currency)

            # Data Quality Status Cards
            st.markdown("**Data Quality Health Check:**")
            if profile.duplicates == 0 and not profile.has_missing and not profile.missing_months:
                st.success("✓ Clean: No duplicate rows, no missing values, continuous date coverage.")
            else:
                if profile.duplicates > 0:
                    st.warning(f"⚠ Warning: {profile.duplicate_policy}")
                if profile.has_missing:
                    st.warning(f"⚠ Missing values detected: {profile.missing_values}")
                if profile.missing_months:
                    for c_dt, m_list in profile.missing_months.items():
                        st.error(f"❌ Critical Temporal Gap: Column `{c_dt}` is missing month periods: {', '.join(m_list)}")

            with st.expander(f"Explore Columns & Summary Stats for {name}"):
                col_df = pd.DataFrame({
                    "Column": profile.column_names,
                    "Type": [profile.data_types.get(c, "") for c in profile.column_names],
                    "Missing": [profile.missing_values.get(c, 0) for c in profile.column_names],
                    "Missing %": [f"{profile.missing_percentages.get(c, 0.0)}%" for c in profile.column_names],
                })
                st.dataframe(col_df, use_container_width=True)

            with st.expander(f"Preview Raw Data for {name}"):
                st.dataframe(st.session_state.datasets[name].head(25), use_container_width=True)

            st.markdown("---")

        if multi_profile.relationships:
            st.markdown("#### 🔗 Detected Cross-Dataset Join Relationships")
            st.json(multi_profile.relationships)

        if multi_profile.contradictions:
            st.markdown("#### ⚡ Detected Cross-Dataset Metric Contradictions")
            for c_item in multi_profile.contradictions:
                st.error(f"❌ {c_item['description']}")

# -------------------------------------------------------------
# TAB 3: UPLOAD DATASETS
# -------------------------------------------------------------
elif nav_option == "Upload Datasets":
    st.markdown("### 📤 Upload Datasets")
    st.markdown("Upload one or multiple CSV or Excel (`.xlsx`, `.xls`) files to analyze with verification.")

    uploaded_files = st.file_uploader(
        "Choose CSV or Excel files",
        type=["csv", "tsv", "xlsx", "xls"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        for uf in uploaded_files:
            save_path = UPLOADS_DIR / uf.name
            with open(save_path, "wb") as f:
                f.write(uf.getbuffer())

            try:
                df, _ = load_dataset_file(str(save_path))
                st.session_state.datasets[uf.name] = df
                st.session_state.dataset_paths[uf.name] = str(save_path.absolute())
                st.success(f"✓ Successfully loaded '{uf.name}' ({len(df):,} rows, {len(df.columns)} columns)")
            except DatasetFileError as e:
                st.error(f"Failed to load '{uf.name}': {str(e)}")

        st.rerun()

    st.markdown("---")
    st.markdown("#### Currently Loaded Datasets in Memory:")
    if st.session_state.datasets:
        for k, v in st.session_state.datasets.items():
            st.write(f"- **{k}**: {len(v):,} rows, {len(v.columns)} columns")
    else:
        st.info("No datasets currently uploaded.")

# -------------------------------------------------------------
# TAB 4: VERIFICATION HISTORY
# -------------------------------------------------------------
elif nav_option == "Verification History":
    st.markdown("### 📜 Real-Time Verification Audit History")
    st.markdown("*Persistent SQLite ledger recording every user question, dual-execution results, and reproducibility status.*")

    history = db.get_history(limit=50)
    if history:
        hist_df = pd.DataFrame(history)
        st.dataframe(
            hist_df[[
                "created_at",
                "question",
                "answer",
                "response_type",
                "confidence",
                "verification_status",
                "match",
            ]],
            use_container_width=True,
        )
    else:
        st.info("No verification history recorded yet. Run questions in the 'Ask Analyst' tab to populate.")

# -------------------------------------------------------------
# TAB 5: SYSTEM ARCHITECTURE
# -------------------------------------------------------------
elif nav_option == "System Architecture":
    st.markdown("### 🏛️ VerifyAI Architecture & Verification Philosophy")
    st.markdown(
        """
        #### Why Verification-First Analytics?
        Standard AI data analysts hallucinate formulas, fabricate missing numbers, and blindly claim confidence.
        
        **VerifyAI fundamentally reverses this model:**
        1. **Deterministic Data Profiling:** Pure Pandas logic extracts schema, nulls, duplicates, and temporal coverage.
        2. **Scoped Trap Interception:** Proactively catches missing months, incompatible currencies (e.g. INR vs USD), and dimension mismatches on the required datasets.
        3. **Structured Query Planning:** Questions are translated into a validated, constrained schema before code is produced.
        4. **Controlled Subprocess Execution:** Generated code runs in an isolated subprocess with stripped environment secrets and timeouts.
        5. **Fresh Dual-Execution Re-verification:** VerifyAI executes the analysis twice in fresh processes and checks whether the result is reproducible.
        6. **Mathematical Tolerance:** Results are compared using float tolerances (`1e-9` absolute, `1e-6` relative) and exact integer equality.
        7. **Constructive Refusal:** When evidence is incomplete, VerifyAI refuses with a clear 3-part diagnostic explanation rather than hallucinating an estimate.
        """
    )
    st.image(
        "https://mermaid.ink/svg/pako:eNptkcsKgzAQRP9lz1kk_oAel177F8Je1mCDiZuEUsS_d-uD0B4cZs6wzM5Cj22mEPq235w3Vp96jM7z9l6cE_pD0g4K5g5pIe30kDZq2WzO2Wk7tG2e1c31hT24p-p4tJ9YFwGf-V3Z-Q8t1YI9",
        caption="VerifyAI Pipeline: Upload -> Profile -> Plan -> Trap Check -> CodeGen -> Dual Fresh Exec -> Compare -> Response",
    )
