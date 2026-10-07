# VerifyAI — 5-Minute Hackathon Demo Script

This guide outlines the exact 5-minute pitch and live demo flow designed to impress hackathon judges.

---

## 🎤 Opening Hook (30 Seconds)
> *"Judges, every company today is deploying AI data analysts. But here is the dirty secret: standard AI analysts hallucinate numbers, silently guess missing dates, and cannot prove whether their answers can actually be reproduced.*
>
> *We built **VerifyAI: The Verification-First Data Analyst**. In VerifyAI, no number is ever shown to a user unless it is backed by executable Python code and independently verified in fresh, isolated execution environments."*

---

## 🚀 Live Demo Walkthrough (4 Minutes)

### Scenario 1: Normal Query with Verified Code (45s)
- **Action**: In the Streamlit UI, click **1️⃣ Normal Query** or type:
  ```text
  What was the total revenue in February?
  ```
- **Show Judges**:
  - The answer is displayed with a **🟢 VERIFICATION PASSED** badge.
  - Expand **"View Generated Code"**: Show the clean, sandboxed Pandas script that filtered February and computed the sum.
  - Expand **"View Fresh Dual-Execution Verification Audit"**: Show that Execution 1 and Execution 2 both executed in fresh subprocesses and matched exactly.
  - Point out the **Explicit Assumption**: *"February interpreted as calendar month 2"*.

---

### Scenario 2: Multi-Table Foreign Key Join (45s)
- **Action**: Click **2️⃣ Multi-Table Join** or type:
  ```text
  Which product category generated the highest revenue?
  ```
- **Show Judges**:
  - The dataset `sales.csv` contains `product_id`, but category names are stored in `products.csv`.
  - The system automatically detected the foreign key relationship on `product_id`.
  - Expand **"View Generated Code"**: Show `pd.merge(sales, products, on="product_id")` generated and executed deterministically.
  - Evidence box clearly shows: `datasets_joined: ['sales.csv', 'products.csv']`, `join_key: 'product_id'`.

---

### Scenario 3: Data Trap Interception — Missing Time Period (60s)
- **Action**: Click **3️⃣ Data Trap** or type:
  ```text
  What was the total revenue in August?
  ```
- **The Problem**: August 2025 data was omitted from `sales.csv`. A traditional LLM analyst would either hallucinate a number or guess an interpolation.
- **VerifyAI Response**:
  - **🛑 RESPONSE: REFUSED**
  - **Reason**: *"August data is not present in the uploaded dataset 'sales.csv'. Available range is 2025-01-05 to 2025-11-26."*
  - **Data Issue**: *"Temporal gap: Month August missing from date column 'date'."*
  - **What Would Be Needed**: *"Provide dataset records for August to compute metrics for this period."*
- **Key Judge Takeaway**: Real analysts refuse when data is missing. VerifyAI is refusal-aware.

---

### Scenario 4: Duplicate Row Detection & Quality Advisory (45s)
- **Action**: Click **4️⃣ Duplicate Impact** or type:
  ```text
  What is the total revenue?
  ```
- **Show Judges**:
  - The profiler detected 3 exact duplicate rows (3.61% of data).
  - In the response, VerifyAI shows the total revenue but attaches an explicit **Data Quality Advisory**:
    *"Detected 3 duplicate row(s). Aggregation queries (sums, counts) may double-count values unless deduplication is clarified."*
  - Policy: Never silently drop duplicates, and never hide their presence.

---

### Scenario 5: Multi-Currency Conflict Trap (45s)
- **Action**: Click **5️⃣ Currency Trap** or type:
  ```text
  What is the combined total revenue across all datasets?
  ```
- **Show Judges**:
  - `sales.csv` is denominated in **USD**, while `sales_inr.csv` is denominated in **INR**.
  - A naive AI would sum `150,000 + 1,300,000 = 1,450,000`, creating meaningless financial garbage.
  - VerifyAI immediately **REFUSES**:
    *"Datasets use different currencies (INR, USD) and no verified exchange rate was provided. What would be needed: Provide an explicit exchange rate between INR and USD."*

---

## 🏆 Closing Summary (30 Seconds)
> *"VerifyAI delivers three non-negotiables for high-stakes enterprise decisions:
> 1. Every number has executable code.
> 2. Every computation is re-executed in an isolated subprocess to verify reproducibility.
> 3. The system exposes assumptions and refuses when evidence is insufficient."*
