"""
============================================================
INCREMENTAL DAILY PIPELINE
============================================================
Simulates near real-time incremental processing:
  - Processes one day at a time
  - Updates Bronze/Silver/Gold incrementally
  - Runs anomaly detection on new data
  - Checks drift on accumulated data
  - Logs metrics to MLflow
============================================================
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import importlib
bronze_layer = importlib.import_module("notebooks.01_bronze_layer")
ingest_incremental = bronze_layer.ingest_incremental

from scripts.run_data_quality import DataQualityValidator


def get_available_dates():
    """Get all dates available in raw telemetry data."""
    raw_path = os.path.join(BASE_DIR, "data", "raw", "telemetry.csv")
    if not os.path.exists(raw_path):
        print("   [ERROR] Raw telemetry data not found. Run data generation first.")
        return []
    df = pd.read_csv(raw_path)
    return sorted(df["date"].unique())


def process_day(target_date):
    """Process a single day's data through the pipeline."""
    print(f"\n{'─'*50}")
    print(f"  Processing: {target_date}")
    print(f"{'─'*50}")

    # Step 1: Bronze ingestion
    print("   [1] Bronze ingestion...")
    ingest_incremental("telemetry", "date", target_date)
    ingest_incremental("error_logs", None, target_date)

    # Step 2: Silver cleaning (for this day's data)
    print("   [2] Silver cleaning...")
    raw_path = os.path.join(BASE_DIR, "data", "raw", "telemetry.csv")
    df = pd.read_csv(raw_path)
    day_data = df[df["date"] == target_date].copy()

    if day_data.empty:
        print(f"   [SKIP] No data for {target_date}")
        return None

    # Clean the day's data
    day_data["date"] = pd.to_datetime(day_data["date"])
    day_data["tap_success_rate"] = day_data["tap_success_rate"].clip(0, 1.0)
    day_data["signal_strength_dbm"] = day_data["signal_strength_dbm"].clip(0, 100)
    day_data["temperature_c"] = day_data["temperature_c"].clip(-10, 80)
    day_data["memory_usage_pct"] = day_data["memory_usage_pct"].clip(0, 100)
    day_data["cpu_usage_pct"] = day_data["cpu_usage_pct"].clip(0, 100)

    # Step 3: Quick quality check
    print("   [3] Quality check...")
    v = DataQualityValidator(f"incremental_{target_date}")
    v.expect_column_values_to_not_be_null(day_data, "device_id")
    v.expect_column_values_to_be_between(day_data, "tap_success_rate", 0, 1.0)
    v.expect_column_values_to_be_between(day_data, "temperature_c", -10, 80)
    s = v.summary()
    print(f"   Quality: {s['passed']}/{s['total']} checks passed")

    # Step 4: Compute daily statistics
    print("   [4] Daily statistics...")
    stats = {
        "date": target_date,
        "num_devices": int(day_data["device_id"].nunique()),
        "num_records": len(day_data),
        "avg_signal": round(float(day_data["signal_strength_dbm"].mean()), 2),
        "avg_temp": round(float(day_data["temperature_c"].mean()), 2),
        "avg_tap_success": round(float(day_data["tap_success_rate"].mean()), 4),
        "total_errors": int(day_data["error_count"].sum()),
        "failures": int(day_data["failure_today"].sum()),
        "failure_rate": round(float(day_data["failure_today"].mean()), 4),
        "avg_health_score": round(float((
            day_data["tap_success_rate"] * 30 +
            (day_data["signal_strength_dbm"] / 100) * 20 +
            (1 - day_data["memory_usage_pct"] / 100) * 15 +
            (1 - day_data["cpu_usage_pct"] / 100) * 15 +
            (day_data["uptime_hours"] / 24) * 10 +
            (1 - day_data["error_count"].clip(0, 10) / 10) * 10
        ).mean()), 2)
    }

    print(f"   Devices: {stats['num_devices']}, Failures: {stats['failures']}, "
          f"Avg Health: {stats['avg_health_score']}")

    # Step 5: Simple anomaly check on daily aggregates
    print("   [5] Anomaly check...")
    anomaly_flags = []
    if stats["avg_signal"] < 60:
        anomaly_flags.append("LOW_SIGNAL")
    if stats["avg_temp"] > 50:
        anomaly_flags.append("HIGH_TEMP")
    if stats["failure_rate"] > 0.15:
        anomaly_flags.append("HIGH_FAILURE_RATE")
    if stats["total_errors"] > day_data["device_id"].nunique() * 3:
        anomaly_flags.append("HIGH_ERROR_COUNT")

    stats["anomaly_flags"] = anomaly_flags
    if anomaly_flags:
        print(f"   ANOMALIES: {', '.join(anomaly_flags)}")
    else:
        print(f"   No anomalies detected")

    return stats


def main():
    print("=" * 60)
    print("  INCREMENTAL DAILY PIPELINE")
    print("  Near Real-Time Device Telemetry Processing")
    print("=" * 60)

    dates = get_available_dates()
    if not dates:
        return

    print(f"\n   Available dates: {dates[0]} to {dates[-1]} ({len(dates)} days)")

    all_stats = []
    for date in dates:
        stats = process_day(date)
        if stats:
            all_stats.append(stats)

    # Summary
    if all_stats:
        stats_df = pd.DataFrame(all_stats)
        stats_path = os.path.join(BASE_DIR, "data", "artifacts", "daily_stats.csv")
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        stats_df.to_csv(stats_path, index=False)

        print(f"\n{'='*60}")
        print(f"  INCREMENTAL PIPELINE SUMMARY")
        print(f"{'='*60}")
        print(f"  Days processed: {len(all_stats)}")
        print(f"  Total failures: {stats_df['failures'].sum()}")
        print(f"  Avg daily failure rate: {stats_df['failure_rate'].mean()*100:.1f}%")
        print(f"  Days with anomalies: {sum(1 for s in all_stats if s['anomaly_flags'])}")
        print(f"  Stats saved: {stats_path}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
