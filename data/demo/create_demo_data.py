"""
Demo dataset generator for VerifyAI.
Generates isolated, modular demo datasets for each judge scenario:
- clean/ (sales.csv, products.csv, customers.csv) -> Clean, continuous months, no duplicates, USD.
- duplicate/ (sales_duplicates.csv) -> Contains 3 exact duplicate rows.
- missing_month/ (sales_missing_august.csv) -> July present, August completely missing.
- currency/ (sales_inr.csv, sales_usd.csv) -> Incompatible currencies (INR and USD).
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np


def generate_all_demo_data(base_dir: str = "data/demo"):
    base_path = Path(base_dir)
    clean_dir = base_path / "clean"
    dup_dir = base_path / "duplicate"
    missing_dir = base_path / "missing_month"
    curr_dir = base_path / "currency"

    for d in [clean_dir, dup_dir, missing_dir, curr_dir, base_path]:
        d.mkdir(parents=True, exist_ok=True)

    np.random.seed(42)

    # 1. Clean Products Dataset
    products_data = [
        {"product_id": "P101", "product_name": "Cloud Analytics Pro", "category": "Software", "base_price": 499.0},
        {"product_id": "P102", "product_name": "AI Vision Scanner", "category": "Electronics", "base_price": 899.0},
        {"product_id": "P103", "product_name": "ErgoDesk Ultra", "category": "Furniture", "base_price": 650.0},
        {"product_id": "P104", "product_name": "Security Gateway X", "category": "Electronics", "base_price": 1200.0},
        {"product_id": "P105", "product_name": "DevOps Toolkit Suite", "category": "Software", "base_price": 299.0},
        {"product_id": "P106", "product_name": "Comfort Mesh Chair", "category": "Furniture", "base_price": 320.0},
    ]
    df_products = pd.DataFrame(products_data)
    df_products.to_csv(clean_dir / "products.csv", index=False)
    df_products.to_csv(base_path / "products.csv", index=False)

    # 2. Clean Customers Dataset
    customers_data = [
        {"customer_id": "C001", "customer_name": "Apex Global Corp", "country": "United States", "segment": "Enterprise"},
        {"customer_id": "C002", "customer_name": "BlueWave Innovations", "country": "United States", "segment": "SMB"},
        {"customer_id": "C003", "customer_name": "Crestline Logistics", "country": "Canada", "segment": "Enterprise"},
        {"customer_id": "C004", "customer_name": "Delta Tech Labs", "country": "United States", "segment": "SMB"},
        {"customer_id": "C005", "customer_name": "Echo Media Group", "country": "United Kingdom", "segment": "Enterprise"},
    ]
    df_customers = pd.DataFrame(customers_data)
    df_customers.to_csv(clean_dir / "customers.csv", index=False)
    df_customers.to_csv(base_path / "customers.csv", index=False)

    # 3. Clean Sales Dataset (100% clean, continuous Jan-Nov dates, NO duplicates, single currency USD)
    dates_pool_clean = []
    for m in range(1, 12):
        for d in [5, 12, 19, 26]:
            dates_pool_clean.append(f"2025-{m:02d}-{d:02d}")

    sales_records_clean = []
    prod_ids = [p["product_id"] for p in products_data]
    cust_ids = [c["customer_id"] for c in customers_data]
    regions = ["North America", "Europe", "Asia-Pacific", "Latin America"]

    order_counter = 1001
    for dt in dates_pool_clean:
        for _ in range(2):
            pid = np.random.choice(prod_ids)
            base_p = next(p["base_price"] for p in products_data if p["product_id"] == pid)
            qty = int(np.random.randint(1, 5))
            rev = float(round(qty * base_p, 2))
            cid = np.random.choice(cust_ids)
            reg = np.random.choice(regions)

            sales_records_clean.append({
                "order_id": f"ORD-{order_counter}",
                "date": dt,
                "customer_id": cid,
                "product_id": pid,
                "region": reg,
                "quantity": qty,
                "unit_price": base_p,
                "revenue": rev,
            })
            order_counter += 1

    df_sales_clean = pd.DataFrame(sales_records_clean)
    df_sales_clean.to_csv(clean_dir / "sales.csv", index=False)
    df_sales_clean.to_csv(base_path / "sales.csv", index=False)

    # 4. Duplicate Sales Dataset (sales_duplicates.csv with 3 deliberate exact duplicates)
    df_sales_dup = df_sales_clean.copy()
    dup_rows = df_sales_dup.iloc[[2, 5, 8]].copy()
    df_sales_dup = pd.concat([df_sales_dup, dup_rows], ignore_index=True)
    df_sales_dup.to_csv(dup_dir / "sales_duplicates.csv", index=False)

    # 5. Missing Month Dataset (July present, August missing)
    dates_pool_missing = []
    for m in [1, 2, 3, 4, 5, 6, 7, 9, 10, 11]:  # Notice 8 (August) is completely omitted!
        for d in [5, 12, 19, 26]:
            dates_pool_missing.append(f"2025-{m:02d}-{d:02d}")

    sales_missing_records = []
    order_counter = 2001
    for dt in dates_pool_missing:
        for _ in range(2):
            pid = np.random.choice(prod_ids)
            base_p = next(p["base_price"] for p in products_data if p["product_id"] == pid)
            qty = int(np.random.randint(1, 4))
            rev = float(round(qty * base_p, 2))
            cid = np.random.choice(cust_ids)
            reg = np.random.choice(regions)

            sales_missing_records.append({
                "order_id": f"ORD-{order_counter}",
                "date": dt,
                "customer_id": cid,
                "product_id": pid,
                "region": reg,
                "quantity": qty,
                "unit_price": base_p,
                "revenue": rev,
            })
            order_counter += 1

    df_sales_missing = pd.DataFrame(sales_missing_records)
    df_sales_missing.to_csv(missing_dir / "sales_missing_august.csv", index=False)

    # 6. Currency Datasets (sales_inr.csv and sales_usd.csv)
    inr_records = [
        {"order_id": "IND-101", "date": "2025-02-10", "revenue": 850000.0, "currency": "INR"},
        {"order_id": "IND-102", "date": "2025-02-15", "revenue": 450000.0, "currency": "INR"},
        {"order_id": "IND-103", "date": "2025-02-20", "revenue": 320000.0, "currency": "INR"},
    ]
    df_inr = pd.DataFrame(inr_records)
    df_inr.to_csv(curr_dir / "sales_inr.csv", index=False)
    df_inr.to_csv(base_path / "sales_inr.csv", index=False)

    usd_records = [
        {"order_id": "USA-201", "date": "2025-02-12", "revenue": 12500.0, "currency": "USD"},
        {"order_id": "USA-202", "date": "2025-02-18", "revenue": 8400.0, "currency": "USD"},
    ]
    df_usd = pd.DataFrame(usd_records)
    df_usd.to_csv(curr_dir / "sales_usd.csv", index=False)

    # 7. Contradictory Summary Dataset
    summary_data = [
        {"metric": "total_revenue", "revenue": 1200000.0, "source": "Quarterly Executive Estimate"},
        {"metric": "total_orders", "revenue": 5000.0, "source": "Marketing Deck"},
    ]
    df_summary = pd.DataFrame(summary_data)
    df_summary.to_csv(base_path / "summary_contradictory.csv", index=False)

    print("Demo datasets generated successfully in structured subdirectories:")
    print(f"  - clean/: sales.csv ({len(df_sales_clean)} rows), products.csv ({len(df_products)}), customers.csv ({len(df_customers)})")
    print(f"  - duplicate/: sales_duplicates.csv ({len(df_sales_dup)} rows, 3 exact duplicates)")
    print(f"  - missing_month/: sales_missing_august.csv ({len(df_sales_missing)} rows, August missing)")
    print(f"  - currency/: sales_inr.csv ({len(df_inr)} rows, INR), sales_usd.csv ({len(df_usd)} rows, USD)")


if __name__ == "__main__":
    generate_all_demo_data()
