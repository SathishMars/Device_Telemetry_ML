"""
============================================================
DRIFT DETECTION - Evidently AI
============================================================
Monitors data drift and model performance drift using
Evidently AI. Generates HTML reports and JSON summaries.
Triggers retraining if drift exceeds threshold.
============================================================
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")

from evidently import Report
from evidently.presets import DataDriftPreset, DataSummaryPreset

import mlflow

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")
DRIFT_DIR = os.path.join(BASE_DIR, "data", "drift_reports")
os.makedirs(DRIFT_DIR, exist_ok=True)

DRIFT_THRESHOLD = 0.30  # 30% of features drifted triggers retraining

MONITOR_FEATURES = [
    "signal_strength_dbm", "temperature_c", "response_time_ms",
    "network_latency_ms", "power_voltage", "memory_usage_pct",
    "cpu_usage_pct", "error_count", "tap_success_rate",
    "uptime_hours", "health_score", "daily_taps",
    "signal_strength_dbm_7d_mean", "error_count_7d_mean",
    "cumulative_errors"
]


def load_reference_and_current():
    """Split data into reference (training) and current (production) periods."""
    print("   Loading feature store data...")
    df = pd.read_parquet(os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet"))

    available = [c for c in MONITOR_FEATURES if c in df.columns]
    df = df[["device_id", "date"] + available].copy()

    # Reference: first 20 days, Current: last 10 days
    dates = sorted(df["date"].unique())
    split_date = dates[20]

    reference = df[df["date"] < split_date][available]
    current = df[df["date"] >= split_date][available]

    print(f"   Reference period: {len(reference)} records (first 20 days)")
    print(f"   Current period:   {len(current)} records (last 10 days)")

    return reference, current


def simulate_drift(current, drift_intensity=0.0):
    """Simulate data drift by shifting feature distributions."""
    if drift_intensity <= 0:
        return current

    print(f"   Simulating drift (intensity={drift_intensity})...")
    drifted = current.copy()

    for col in drifted.select_dtypes(include=[np.number]).columns:
        shift = np.random.normal(
            drift_intensity * drifted[col].std(),
            drift_intensity * drifted[col].std() * 0.5,
            len(drifted)
        )
        drifted[col] = drifted[col] + shift

    return drifted


def run_drift_detection(reference, current, scenario_name="production"):
    """Run Evidently AI drift detection."""
    print(f"\n   --- Drift Detection ({scenario_name}) ---")

    # Data Drift Report
    drift_report = Report(metrics=[DataDriftPreset()])
    snapshot = drift_report.run(reference_data=reference, current_data=current)

    # Save HTML report
    html_path = os.path.join(DRIFT_DIR, f"data_drift_{scenario_name}.html")
    snapshot.save_html(html_path)
    print(f"   Drift report saved: {html_path}")

    # Extract drift results from snapshot dict
    report_dict = snapshot.dict()
    metrics = report_dict.get("metrics", [])

    drift_summary = {
        "scenario": scenario_name,
        "drifted_features": 0,
        "total_features": 0,
        "drift_share": 0.0,
        "feature_drift": {}
    }

    for metric in metrics:
        metric_name = metric.get("metric_name", "")
        config = metric.get("config", {})
        value = metric.get("value", {})

        # DriftedColumnsCount holds overall drift summary
        if "DriftedColumnsCount" in metric_name:
            if isinstance(value, dict):
                drift_summary["drifted_features"] = int(value.get("count", 0))
                drift_summary["drift_share"] = float(value.get("share", 0))
            drift_summary["total_features"] = len(MONITOR_FEATURES)

        # ValueDrift holds per-column drift scores (p-values)
        elif "ValueDrift" in metric_name:
            col_name = config.get("column", "unknown")
            drift_score = float(value) if isinstance(value, (int, float)) else 0
            threshold = config.get("threshold", 0.05)
            drift_summary["feature_drift"][col_name] = {
                "drifted": drift_score < threshold,
                "drift_score": round(drift_score, 6),
                "method": config.get("method", "unknown")
            }

    # Count drifted from per-feature results if DriftedColumnsCount wasn't found
    if drift_summary["drifted_features"] == 0 and drift_summary["feature_drift"]:
        n_drifted = sum(1 for v in drift_summary["feature_drift"].values() if v["drifted"])
        n_total = len(drift_summary["feature_drift"])
        drift_summary["drifted_features"] = n_drifted
        drift_summary["total_features"] = n_total
        drift_summary["drift_share"] = n_drifted / max(n_total, 1)

    drift_pct = drift_summary["drift_share"] * 100
    print(f"\n   Drift Results ({scenario_name}):")
    print(f"   Drifted features: {drift_summary['drifted_features']}/{drift_summary['total_features']}")
    print(f"   Drift share: {drift_pct:.1f}%")

    if drift_summary.get("feature_drift"):
        drifted = {k: v for k, v in drift_summary["feature_drift"].items() if v.get("drifted")}
        if drifted:
            print(f"   Drifted features:")
            for fname, fdata in list(drifted.items())[:5]:
                print(f"     {fname}: p-value={fdata['drift_score']:.6f} ({fdata['method']})")

    # Data Summary Report
    quality_report = Report(metrics=[DataSummaryPreset()])
    quality_snapshot = quality_report.run(reference_data=reference, current_data=current)
    quality_html = os.path.join(DRIFT_DIR, f"data_quality_{scenario_name}.html")
    quality_snapshot.save_html(quality_html)
    print(f"   Quality report saved: {quality_html}")

    return drift_summary


def make_retraining_decision(drift_summary):
    """Decide whether to trigger model retraining."""
    drift_share = drift_summary.get("drift_share", 0)

    print(f"\n   --- Retraining Decision ---")
    print(f"   Drift share: {drift_share*100:.1f}%")
    print(f"   Threshold:   {DRIFT_THRESHOLD*100:.0f}%")

    should_retrain = drift_share > DRIFT_THRESHOLD

    if should_retrain:
        print(f"   DECISION: RETRAIN MODEL (drift exceeds threshold)")
    else:
        print(f"   DECISION: NO RETRAINING NEEDED (drift within limits)")

    decision = {
        "should_retrain": should_retrain,
        "drift_share": drift_share,
        "threshold": DRIFT_THRESHOLD,
        "reason": f"Drift share {drift_share*100:.1f}% {'exceeds' if should_retrain else 'within'} "
                  f"{DRIFT_THRESHOLD*100:.0f}% threshold"
    }

    decision_path = os.path.join(DRIFT_DIR, "drift_decision.json")
    with open(decision_path, "w") as f:
        json.dump(decision, f, indent=2)

    return decision


def main():
    print("=" * 60)
    print("  DRIFT DETECTION - Evidently AI")
    print("=" * 60)

    # Setup MLflow
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    os.makedirs(os.path.join(BASE_DIR, "mlruns"), exist_ok=True)
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("Drift_Detection")

    reference, current = load_reference_and_current()

    with mlflow.start_run(run_name="Drift_Detection"):
        # Scenario A: No artificial drift (real production data)
        summary_a = run_drift_detection(reference, current, "no_drift")
        mlflow.log_metric("drift_share_no_drift", summary_a["drift_share"])

        # Scenario B: Simulated drift
        drifted_current = simulate_drift(current, drift_intensity=0.5)
        summary_b = run_drift_detection(reference, drifted_current, "simulated_drift")
        mlflow.log_metric("drift_share_simulated", summary_b["drift_share"])

        # Retraining decision (on real data)
        decision = make_retraining_decision(summary_a)
        mlflow.log_metric("should_retrain", int(decision["should_retrain"]))
        mlflow.log_param("drift_threshold", DRIFT_THRESHOLD)

        # Log reports
        for f in os.listdir(DRIFT_DIR):
            mlflow.log_artifact(os.path.join(DRIFT_DIR, f))

    print("\n  Drift detection complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
