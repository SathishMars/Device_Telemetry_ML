"""
============================================================
SILVER LAYER - Data Cleaning & Standardization
============================================================
Reads Bronze Parquet files, cleans, deduplicates, type-casts,
and writes to Silver layer.
============================================================
"""

import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")


def read_bronze_table(table_name):
    """Read all parquet files from a bronze table directory."""
    table_dir = os.path.join(BRONZE_DIR, table_name)
    if not os.path.exists(table_dir):
        print(f"   [SKIP] Bronze table '{table_name}' not found")
        return None

    files = glob.glob(os.path.join(table_dir, "*.parquet"))
    if not files:
        return None

    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    return df


def clean_devices(df):
    """Clean device registry."""
    print("   Cleaning devices...")

    # Remove ingestion metadata columns
    meta_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=meta_cols, errors="ignore")

    # Deduplicate
    df = df.drop_duplicates(subset=["device_id"], keep="last")

    # Type casting
    df["install_date"] = pd.to_datetime(df["install_date"])
    df["age_days"] = df["age_days"].astype(int)
    df["warranty_remaining_days"] = df["warranty_remaining_days"].astype(int)
    df["failure_prone"] = df["failure_prone"].astype(int)

    # Standardize categories
    df["gate_type"] = df["gate_type"].str.strip().str.title()
    df["manufacturer"] = df["manufacturer"].str.strip().str.title()
    df["station"] = df["station"].str.strip().str.title()

    # Validate ranges
    df["age_days"] = df["age_days"].clip(0, 3650)  # Max 10 years
    df["warranty_remaining_days"] = df["warranty_remaining_days"].clip(0, 1825)

    print(f"   -> {len(df)} clean device records")
    return df


def clean_telemetry(df):
    """Clean daily telemetry data."""
    print("   Cleaning telemetry...")

    meta_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=meta_cols, errors="ignore")

    # Deduplicate (one record per device per day)
    df = df.drop_duplicates(subset=["device_id", "date"], keep="last")

    # Type casting
    df["date"] = pd.to_datetime(df["date"])
    df["failure_today"] = df["failure_today"].astype(int)

    # Validate and clip ranges
    df["tap_success_rate"] = df["tap_success_rate"].clip(0, 1.0)
    df["signal_strength_dbm"] = df["signal_strength_dbm"].clip(0, 100)
    df["temperature_c"] = df["temperature_c"].clip(-10, 80)
    df["response_time_ms"] = df["response_time_ms"].clip(10, 5000)
    df["network_latency_ms"] = df["network_latency_ms"].clip(1, 1000)
    df["power_voltage"] = df["power_voltage"].clip(2.0, 6.0)
    df["memory_usage_pct"] = df["memory_usage_pct"].clip(0, 100)
    df["cpu_usage_pct"] = df["cpu_usage_pct"].clip(0, 100)
    df["error_count"] = df["error_count"].clip(0, 100)
    df["reboot_count"] = df["reboot_count"].clip(0, 50)
    df["uptime_hours"] = df["uptime_hours"].clip(0, 24)

    # Fill missing values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

    print(f"   -> {len(df)} clean telemetry records")
    return df


def clean_error_logs(df):
    """Clean error log entries."""
    print("   Cleaning error logs...")

    meta_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=meta_cols, errors="ignore")

    # Type casting
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["resolved"] = df["resolved"].astype(int)

    # Standardize
    df["severity"] = df["severity"].str.upper().str.strip()
    df["error_code"] = df["error_code"].str.upper().str.strip()

    # Validate severity
    valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    df = df[df["severity"].isin(valid_severities)]

    # Fill resolution time for unresolved
    df["resolution_time_min"] = df["resolution_time_min"].fillna(-1)

    print(f"   -> {len(df)} clean error log records")
    return df


def clean_maintenance(df):
    """Clean maintenance records."""
    print("   Cleaning maintenance...")

    meta_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=meta_cols, errors="ignore")

    # Type casting
    df["date"] = pd.to_datetime(df["date"])
    df["sla_met"] = df["sla_met"].astype(int)
    df["parts_replaced"] = df["parts_replaced"].astype(int)

    # Standardize
    df["maintenance_type"] = df["maintenance_type"].str.strip().str.title()

    # Validate
    df["cost_gbp"] = df["cost_gbp"].clip(0, 10000)
    df["actual_resolution_hours"] = df["actual_resolution_hours"].clip(0, 168)

    print(f"   -> {len(df)} clean maintenance records")
    return df


def main():
    print("=" * 60)
    print("  SILVER LAYER - Data Cleaning & Standardization")
    print("=" * 60)
    os.makedirs(SILVER_DIR, exist_ok=True)

    tables = {
        "devices": clean_devices,
        "telemetry": clean_telemetry,
        "error_logs": clean_error_logs,
        "maintenance": clean_maintenance
    }

    for table_name, clean_fn in tables.items():
        df = read_bronze_table(table_name)
        if df is not None:
            cleaned = clean_fn(df)
            out_path = os.path.join(SILVER_DIR, f"{table_name}.parquet")
            cleaned.to_parquet(out_path, index=False, engine="pyarrow")
            print(f"   [SAVED] {out_path}")

    print("\n  Silver layer complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
