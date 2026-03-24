"""
============================================================
GOLD LAYER - Feature Engineering
============================================================
Joins Silver tables and engineers features for all 5 PS:
  PS-1: Failure Prediction features
  PS-2: Error Pattern features
  PS-3: Root Cause features
  PS-4: Anomaly Detection features
  PS-5: SLA/Reliability features
============================================================
"""

import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")


def load_silver():
    """Load all silver tables."""
    devices = pd.read_parquet(os.path.join(SILVER_DIR, "devices.parquet"))
    telemetry = pd.read_parquet(os.path.join(SILVER_DIR, "telemetry.parquet"))
    errors = pd.read_parquet(os.path.join(SILVER_DIR, "error_logs.parquet"))
    maintenance = pd.read_parquet(os.path.join(SILVER_DIR, "maintenance.parquet"))
    return devices, telemetry, errors, maintenance


def engineer_telemetry_features(telemetry):
    """Compute rolling and aggregate features from telemetry."""
    print("   Engineering telemetry features...")

    telemetry = telemetry.sort_values(["device_id", "date"])

    # Rolling window features (7-day)
    rolling_cols = [
        "signal_strength_dbm", "temperature_c", "response_time_ms",
        "network_latency_ms", "error_count", "tap_success_rate",
        "memory_usage_pct", "cpu_usage_pct"
    ]

    for col in rolling_cols:
        telemetry[f"{col}_7d_mean"] = (
            telemetry.groupby("device_id")[col]
            .transform(lambda x: x.rolling(7, min_periods=1).mean())
        )
        telemetry[f"{col}_7d_std"] = (
            telemetry.groupby("device_id")[col]
            .transform(lambda x: x.rolling(7, min_periods=1).std().fillna(0))
        )

    # Rate of change (day-over-day)
    for col in ["signal_strength_dbm", "temperature_c", "error_count", "response_time_ms"]:
        telemetry[f"{col}_delta"] = (
            telemetry.groupby("device_id")[col]
            .transform(lambda x: x.diff().fillna(0))
        )

    # Cumulative error count
    telemetry["cumulative_errors"] = (
        telemetry.groupby("device_id")["error_count"].cumsum()
    )

    # Cumulative reboot count
    telemetry["cumulative_reboots"] = (
        telemetry.groupby("device_id")["reboot_count"].cumsum()
    )

    # Days since last failure
    telemetry["failure_cumsum"] = (
        telemetry.groupby("device_id")["failure_today"].cumsum()
    )
    telemetry["days_since_last_failure"] = (
        telemetry.groupby("device_id")["failure_cumsum"]
        .transform(lambda x: x.groupby((x != x.shift()).cumsum()).cumcount())
    )

    # Health score (composite metric 0-100)
    telemetry["health_score"] = (
        telemetry["tap_success_rate"] * 30 +
        (telemetry["signal_strength_dbm"] / 100) * 20 +
        (1 - telemetry["memory_usage_pct"] / 100) * 15 +
        (1 - telemetry["cpu_usage_pct"] / 100) * 15 +
        (telemetry["uptime_hours"] / 24) * 10 +
        (1 - telemetry["error_count"].clip(0, 10) / 10) * 10
    ).round(2)

    # Failure in next 3 days (target for PS-1)
    telemetry["failure_next_3d"] = (
        telemetry.groupby("device_id")["failure_today"]
        .transform(lambda x: x.rolling(3, min_periods=1).max().shift(-1).fillna(0))
    ).astype(int)

    return telemetry


def engineer_error_features(errors, telemetry):
    """Aggregate error features per device per day."""
    print("   Engineering error features...")

    errors["date"] = errors["timestamp"].dt.date.astype(str)

    # Error counts by severity per device per day
    severity_pivot = (
        errors.groupby(["device_id", "date", "severity"]).size()
        .unstack(fill_value=0)
        .reset_index()
    )
    severity_pivot.columns = ["device_id", "date"] + [
        f"error_{s.lower()}_count" for s in severity_pivot.columns[2:]
    ]

    # Top error code per device per day
    top_errors = (
        errors.groupby(["device_id", "date"])["error_code"]
        .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "NONE")
        .reset_index()
        .rename(columns={"error_code": "top_error_code"})
    )

    # Unique error types per device per day
    unique_errors = (
        errors.groupby(["device_id", "date"])["error_code"]
        .nunique()
        .reset_index()
        .rename(columns={"error_code": "unique_error_types"})
    )

    # Resolution rate per device per day
    resolution = (
        errors.groupby(["device_id", "date"])["resolved"]
        .mean()
        .reset_index()
        .rename(columns={"resolved": "error_resolution_rate"})
    )

    # Merge all error features
    telemetry["date_str"] = telemetry["date"].dt.strftime("%Y-%m-%d")

    for feat_df in [severity_pivot, top_errors, unique_errors, resolution]:
        feat_df["date"] = feat_df["date"].astype(str)
        telemetry = telemetry.merge(
            feat_df, left_on=["device_id", "date_str"],
            right_on=["device_id", "date"], how="left", suffixes=("", "_err")
        )
        # Drop duplicate date columns from merge
        telemetry = telemetry.drop(columns=["date_err"], errors="ignore")
        if "date_y" in telemetry.columns:
            telemetry = telemetry.drop(columns=["date_y"])
            telemetry = telemetry.rename(columns={"date_x": "date"})

    # Fill missing error features with 0
    error_fill_cols = [c for c in telemetry.columns if c.startswith("error_") and c != "error_count"]
    telemetry[error_fill_cols] = telemetry[error_fill_cols].fillna(0)
    telemetry["unique_error_types"] = telemetry["unique_error_types"].fillna(0)
    telemetry["error_resolution_rate"] = telemetry["error_resolution_rate"].fillna(1.0)
    telemetry["top_error_code"] = telemetry["top_error_code"].fillna("NONE")

    telemetry = telemetry.drop(columns=["date_str"], errors="ignore")

    return telemetry


def engineer_maintenance_features(maintenance, telemetry):
    """Add maintenance-related features."""
    print("   Engineering maintenance features...")

    maint_agg = (
        maintenance.groupby("device_id").agg(
            total_maintenance_count=("date", "count"),
            corrective_count=("maintenance_type", lambda x: (x == "Corrective").sum()),
            emergency_count=("maintenance_type", lambda x: (x == "Emergency").sum()),
            avg_resolution_hours=("actual_resolution_hours", "mean"),
            sla_compliance_rate=("sla_met", "mean"),
            total_cost_gbp=("cost_gbp", "sum"),
            parts_replaced_count=("parts_replaced", "sum")
        ).reset_index()
    )

    telemetry = telemetry.merge(maint_agg, on="device_id", how="left")

    # Fill for devices with no maintenance
    maint_cols = maint_agg.columns.drop("device_id")
    telemetry[maint_cols] = telemetry[maint_cols].fillna(0)

    return telemetry


def engineer_device_features(devices, telemetry):
    """Join device static attributes."""
    print("   Engineering device features...")

    device_features = devices[[
        "device_id", "station", "gate_type", "manufacturer",
        "firmware_version", "age_days", "warranty_remaining_days", "failure_prone"
    ]]

    telemetry = telemetry.merge(device_features, on="device_id", how="left")

    # Derived features
    telemetry["is_old_device"] = (telemetry["age_days"] > 1000).astype(int)
    telemetry["is_beta_firmware"] = (telemetry["firmware_version"] == "v4.0.0-beta").astype(int)
    telemetry["is_under_warranty"] = (telemetry["warranty_remaining_days"] > 0).astype(int)
    telemetry["is_high_traffic_station"] = telemetry["station"].isin([
        "Kings Cross", "Victoria", "Waterloo", "Oxford Circus",
        "Bank", "Canary Wharf", "Liverpool Street"
    ]).astype(int)

    return telemetry


def main():
    print("=" * 60)
    print("  GOLD LAYER - Feature Engineering")
    print("=" * 60)
    os.makedirs(GOLD_DIR, exist_ok=True)

    devices, telemetry, errors, maintenance = load_silver()

    # Feature engineering pipeline
    telemetry = engineer_telemetry_features(telemetry)
    telemetry = engineer_error_features(errors, telemetry)
    telemetry = engineer_maintenance_features(maintenance, telemetry)
    telemetry = engineer_device_features(devices, telemetry)

    # Save gold dataset
    out_path = os.path.join(GOLD_DIR, "device_features.parquet")
    telemetry.to_parquet(out_path, index=False, engine="pyarrow")

    csv_path = os.path.join(GOLD_DIR, "device_features.csv")
    telemetry.to_csv(csv_path, index=False)

    print(f"\n   Gold dataset: {telemetry.shape[0]} rows x {telemetry.shape[1]} columns")
    print(f"   Failure rate (today): {telemetry['failure_today'].mean()*100:.1f}%")
    print(f"   Failure rate (next 3d): {telemetry['failure_next_3d'].mean()*100:.1f}%")
    print(f"   Saved: {out_path}")
    print("\n  Gold layer complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
