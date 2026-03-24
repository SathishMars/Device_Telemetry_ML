"""
============================================================
FEATURE STORE - Centralized Feature Repository
============================================================
Creates a versioned feature store from Gold layer,
ensuring training-serving consistency.
============================================================
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")


# Feature definitions for each problem statement
FEATURE_SETS = {
    "ps1_failure_prediction": {
        "numeric": [
            "signal_strength_dbm", "temperature_c", "response_time_ms",
            "network_latency_ms", "power_voltage", "memory_usage_pct",
            "cpu_usage_pct", "error_count", "reboot_count", "uptime_hours",
            "daily_taps", "tap_success_rate", "health_score",
            "signal_strength_dbm_7d_mean", "temperature_c_7d_mean",
            "error_count_7d_mean", "response_time_ms_7d_mean",
            "signal_strength_dbm_7d_std", "error_count_7d_std",
            "signal_strength_dbm_delta", "temperature_c_delta",
            "error_count_delta", "cumulative_errors", "cumulative_reboots",
            "days_since_last_failure", "age_days", "total_maintenance_count",
            "corrective_count", "emergency_count"
        ],
        "categorical": [
            "manufacturer", "firmware_version", "gate_type",
            "is_old_device", "is_beta_firmware", "is_under_warranty",
            "is_high_traffic_station"
        ],
        "target": "failure_next_3d"
    },
    "ps4_anomaly_detection": {
        "numeric": [
            "signal_strength_dbm", "temperature_c", "response_time_ms",
            "network_latency_ms", "power_voltage", "memory_usage_pct",
            "cpu_usage_pct", "error_count", "tap_success_rate",
            "uptime_hours", "health_score"
        ]
    },
    "ps5_sla_risk": {
        "numeric": [
            "age_days", "total_maintenance_count", "corrective_count",
            "emergency_count", "avg_resolution_hours", "sla_compliance_rate",
            "total_cost_gbp", "health_score", "cumulative_errors",
            "cumulative_reboots", "error_count_7d_mean"
        ],
        "categorical": [
            "manufacturer", "firmware_version", "is_old_device"
        ]
    }
}


def create_feature_store():
    """Create and persist feature store."""
    print("   Loading gold dataset...")
    gold_path = os.path.join(GOLD_DIR, "device_features.parquet")
    df = pd.read_parquet(gold_path)

    os.makedirs(FEATURE_STORE_DIR, exist_ok=True)

    # Save full feature table
    feature_path = os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet")
    df.to_parquet(feature_path, index=False, engine="pyarrow")
    print(f"   [SAVED] Full feature table: {df.shape}")

    # Save PS-specific feature sets
    for ps_name, config in FEATURE_SETS.items():
        cols = ["device_id", "date"]
        cols += config.get("numeric", [])
        cols += config.get("categorical", [])
        if "target" in config:
            cols.append(config["target"])

        # Filter to available columns
        available = [c for c in cols if c in df.columns]
        ps_df = df[available]

        ps_path = os.path.join(FEATURE_STORE_DIR, f"{ps_name}_features.parquet")
        ps_df.to_parquet(ps_path, index=False, engine="pyarrow")
        print(f"   [SAVED] {ps_name}: {ps_df.shape}")

    # Generate schema metadata
    schema = {
        "created_at": datetime.now().isoformat(),
        "total_features": len(df.columns),
        "total_records": len(df),
        "date_range": {
            "start": str(df["date"].min()),
            "end": str(df["date"].max())
        },
        "devices": int(df["device_id"].nunique()),
        "feature_sets": {},
        "columns": {}
    }

    for col in df.columns:
        col_info = {"dtype": str(df[col].dtype)}
        if df[col].dtype in [np.float64, np.int64, np.float32, np.int32]:
            col_info["min"] = float(df[col].min())
            col_info["max"] = float(df[col].max())
            col_info["mean"] = float(df[col].mean())
            col_info["null_pct"] = float(df[col].isnull().mean())
        elif df[col].dtype == object:
            col_info["unique_values"] = int(df[col].nunique())
            col_info["top_values"] = df[col].value_counts().head(5).to_dict()
        schema["columns"][col] = col_info

    for ps_name, config in FEATURE_SETS.items():
        schema["feature_sets"][ps_name] = {
            "numeric_features": len(config.get("numeric", [])),
            "categorical_features": len(config.get("categorical", [])),
            "target": config.get("target", "N/A")
        }

    schema_path = os.path.join(FEATURE_STORE_DIR, "feature_schema.json")
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2, default=str)
    print(f"   [SAVED] Schema: {schema_path}")

    return df


def main():
    print("=" * 60)
    print("  FEATURE STORE - Centralized Feature Repository")
    print("=" * 60)

    df = create_feature_store()

    print(f"\n   Total features: {len(df.columns)}")
    print(f"   Total records:  {len(df)}")
    print(f"   Feature sets:   {len(FEATURE_SETS)}")
    print("\n  Feature store complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
