"""
============================================================
DATA QUALITY - Great Expectations
============================================================
Validates data at Bronze, Silver, and Gold layers using
Great Expectations validation suites.
============================================================
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
QUALITY_DIR = os.path.join(BASE_DIR, "data", "quality_reports")
os.makedirs(QUALITY_DIR, exist_ok=True)


class DataQualityValidator:
    """Validates data quality using Great Expectations-style checks."""

    def __init__(self, layer_name):
        self.layer_name = layer_name
        self.results = []
        self.passed = 0
        self.failed = 0

    def expect_column_to_exist(self, df, column):
        success = column in df.columns
        self._record(f"Column '{column}' exists", success)

    def expect_column_values_to_not_be_null(self, df, column, mostly=1.0):
        if column not in df.columns:
            self._record(f"Column '{column}' not null (column missing)", False)
            return
        null_rate = df[column].isnull().mean()
        success = (1 - null_rate) >= mostly
        self._record(f"Column '{column}' not null (null_rate={null_rate:.3f}, threshold={1-mostly:.3f})", success)

    def expect_column_values_to_be_between(self, df, column, min_val, max_val):
        if column not in df.columns:
            self._record(f"Column '{column}' in range [{min_val}, {max_val}] (column missing)", False)
            return
        valid = df[column].dropna()
        success = (valid.min() >= min_val) and (valid.max() <= max_val)
        self._record(
            f"Column '{column}' in range [{min_val}, {max_val}] "
            f"(actual: [{valid.min():.2f}, {valid.max():.2f}])",
            success
        )

    def expect_column_values_to_be_in_set(self, df, column, value_set):
        if column not in df.columns:
            self._record(f"Column '{column}' in set (column missing)", False)
            return
        actual = set(df[column].dropna().unique())
        success = actual.issubset(set(value_set))
        extra = actual - set(value_set)
        self._record(
            f"Column '{column}' values in set (extra: {extra if extra else 'none'})",
            success
        )

    def expect_column_values_to_be_unique(self, df, column):
        if column not in df.columns:
            self._record(f"Column '{column}' unique (column missing)", False)
            return
        n_unique = df[column].nunique()
        n_total = len(df[column].dropna())
        success = n_unique == n_total
        self._record(
            f"Column '{column}' unique (unique={n_unique}, total={n_total})",
            success
        )

    def expect_table_row_count_to_be_between(self, df, min_val, max_val):
        n_rows = len(df)
        success = min_val <= n_rows <= max_val
        self._record(f"Row count in [{min_val}, {max_val}] (actual: {n_rows})", success)

    def expect_column_mean_to_be_between(self, df, column, min_val, max_val):
        if column not in df.columns:
            self._record(f"Column '{column}' mean in range (column missing)", False)
            return
        mean_val = df[column].mean()
        success = min_val <= mean_val <= max_val
        self._record(
            f"Column '{column}' mean in [{min_val}, {max_val}] (actual: {mean_val:.3f})",
            success
        )

    def _record(self, description, success):
        self.results.append({
            "layer": self.layer_name,
            "expectation": description,
            "success": success
        })
        if success:
            self.passed += 1
        else:
            self.failed += 1

    def summary(self):
        total = self.passed + self.failed
        return {
            "layer": self.layer_name,
            "total": total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.passed / max(total, 1) * 100
        }


def validate_bronze():
    """Validate Bronze layer data quality."""
    print("\n   --- Bronze Layer Validation ---")
    v = DataQualityValidator("bronze")

    # Validate telemetry
    telemetry_dir = os.path.join(BRONZE_DIR, "telemetry")
    if os.path.exists(telemetry_dir):
        import glob
        files = glob.glob(os.path.join(telemetry_dir, "*.parquet"))
        if files:
            df = pd.concat([pd.read_parquet(f) for f in files[:5]])

            v.expect_column_to_exist(df, "device_id")
            v.expect_column_to_exist(df, "date")
            v.expect_column_to_exist(df, "signal_strength_dbm")
            v.expect_column_values_to_not_be_null(df, "device_id")
            v.expect_column_values_to_not_be_null(df, "date")
            v.expect_table_row_count_to_be_between(df, 100, 100000)

    # Validate devices
    devices_dir = os.path.join(BRONZE_DIR, "devices")
    if os.path.exists(devices_dir):
        files = [f for f in os.listdir(devices_dir) if f.endswith(".parquet")]
        if files:
            df = pd.read_parquet(os.path.join(devices_dir, files[0]))
            v.expect_column_to_exist(df, "device_id")
            v.expect_column_values_to_be_unique(df, "device_id")
            v.expect_table_row_count_to_be_between(df, 50, 1000)

    s = v.summary()
    print(f"   Results: {s['passed']}/{s['total']} passed ({s['pass_rate']:.0f}%)")
    return v


def validate_silver():
    """Validate Silver layer data quality."""
    print("\n   --- Silver Layer Validation ---")
    v = DataQualityValidator("silver")

    # Telemetry
    telemetry_path = os.path.join(SILVER_DIR, "telemetry.parquet")
    if os.path.exists(telemetry_path):
        df = pd.read_parquet(telemetry_path)

        v.expect_column_values_to_not_be_null(df, "device_id")
        v.expect_column_values_to_not_be_null(df, "date")
        v.expect_column_values_to_not_be_null(df, "signal_strength_dbm", mostly=0.99)
        v.expect_column_values_to_be_between(df, "tap_success_rate", 0, 1.0)
        v.expect_column_values_to_be_between(df, "signal_strength_dbm", 0, 100)
        v.expect_column_values_to_be_between(df, "temperature_c", -10, 80)
        v.expect_column_values_to_be_between(df, "cpu_usage_pct", 0, 100)
        v.expect_column_values_to_be_between(df, "memory_usage_pct", 0, 100)
        v.expect_column_values_to_be_between(df, "uptime_hours", 0, 24)

    # Devices
    devices_path = os.path.join(SILVER_DIR, "devices.parquet")
    if os.path.exists(devices_path):
        df = pd.read_parquet(devices_path)

        v.expect_column_values_to_be_unique(df, "device_id")
        v.expect_column_values_to_not_be_null(df, "station")
        v.expect_column_values_to_be_between(df, "age_days", 0, 3650)
        v.expect_column_values_to_be_in_set(df, "gate_type",
            ["Entry", "Exit", "Wide_Entry", "Wide_Exit"])

    s = v.summary()
    print(f"   Results: {s['passed']}/{s['total']} passed ({s['pass_rate']:.0f}%)")
    return v


def validate_gold():
    """Validate Gold layer data quality."""
    print("\n   --- Gold Layer Validation ---")
    v = DataQualityValidator("gold")

    gold_path = os.path.join(GOLD_DIR, "device_features.parquet")
    if os.path.exists(gold_path):
        df = pd.read_parquet(gold_path)

        v.expect_table_row_count_to_be_between(df, 1000, 100000)
        v.expect_column_to_exist(df, "failure_today")
        v.expect_column_to_exist(df, "failure_next_3d")
        v.expect_column_to_exist(df, "health_score")
        v.expect_column_values_to_not_be_null(df, "device_id")
        v.expect_column_values_to_not_be_null(df, "health_score", mostly=0.95)

        # Failure rate sanity check (should be 5-40%)
        v.expect_column_mean_to_be_between(df, "failure_today", 0.02, 0.40)
        v.expect_column_mean_to_be_between(df, "failure_next_3d", 0.02, 0.50)

        # Feature completeness
        v.expect_column_values_to_be_between(df, "health_score", 0, 100)
        v.expect_column_values_to_be_between(df, "tap_success_rate", 0, 1.0)

        # No infinite values
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        has_inf = np.isinf(df[numeric_cols].values).any()
        v._record("No infinite values in numeric columns", not has_inf)

    s = v.summary()
    print(f"   Results: {s['passed']}/{s['total']} passed ({s['pass_rate']:.0f}%)")
    return v


def main():
    print("=" * 60)
    print("  DATA QUALITY - Great Expectations Style Validation")
    print("=" * 60)

    validators = []
    validators.append(validate_bronze())
    validators.append(validate_silver())
    validators.append(validate_gold())

    # Combined report
    all_results = []
    for v in validators:
        all_results.extend(v.results)

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(os.path.join(QUALITY_DIR, "quality_report.csv"), index=False)

    # Summary
    print("\n" + "=" * 60)
    print("  DATA QUALITY SUMMARY")
    print("=" * 60)
    total_passed = sum(v.passed for v in validators)
    total_failed = sum(v.failed for v in validators)
    total = total_passed + total_failed

    for v in validators:
        s = v.summary()
        status = "PASS" if s["failed"] == 0 else "WARN"
        print(f"   [{status}] {s['layer'].upper()}: {s['passed']}/{s['total']} ({s['pass_rate']:.0f}%)")

    overall_rate = total_passed / max(total, 1) * 100
    print(f"\n   Overall: {total_passed}/{total} expectations passed ({overall_rate:.0f}%)")

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "overall_pass_rate": overall_rate,
        "total_expectations": total,
        "passed": total_passed,
        "failed": total_failed,
        "layers": {v.layer_name: v.summary() for v in validators}
    }

    with open(os.path.join(QUALITY_DIR, "quality_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"   Report: {QUALITY_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
