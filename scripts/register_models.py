"""
============================================================
MODEL REGISTRATION - MLflow Model Registry
============================================================
Registers all trained models from each Problem Statement
into MLflow Model Registry with proper versioning and
stage transitions (Staging → Production).
============================================================
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import mlflow
import mlflow.sklearn
import mlflow.xgboost
import mlflow.catboost
from mlflow.models.signature import infer_signature

ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts")
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")


def setup_mlflow():
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    mlflow.set_tracking_uri(mlflow_uri)
    return mlflow.tracking.MlflowClient()


def get_sample_data():
    """Load a small sample for model signature inference."""
    df = pd.read_parquet(os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet"))
    return df.head(5)


def register_ps1_models(client):
    """Register PS-1 Failure Prediction models."""
    print("\n   --- PS-1: Failure Prediction ---")

    from sklearn.preprocessing import LabelEncoder

    NUMERIC_FEATURES = [
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
    ]
    CATEGORICAL_FEATURES = [
        "manufacturer", "firmware_version", "gate_type",
        "is_old_device", "is_beta_firmware", "is_under_warranty",
        "is_high_traffic_station"
    ]

    model_path = os.path.join(ARTIFACTS_DIR, "ps1", "champion_model.pkl")
    if not os.path.exists(model_path):
        print("   [SKIP] No champion model found")
        return

    model = joblib.load(model_path)
    model_name = type(model).__name__

    # Prepare sample input for signature
    sample = get_sample_data()
    all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    available = [c for c in all_features if c in sample.columns]
    X_sample = sample[available].copy()
    for col in CATEGORICAL_FEATURES:
        if col in X_sample.columns and X_sample[col].dtype == object:
            le = LabelEncoder()
            X_sample[col] = le.fit_transform(X_sample[col].astype(str))
    X_sample = X_sample.fillna(0)

    y_sample = model.predict_proba(X_sample)[:, 1]
    signature = infer_signature(X_sample, y_sample)

    # Load champion metrics
    metrics_path = os.path.join(ARTIFACTS_DIR, "ps1", "champion_metrics.json")
    metrics = {}
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            metrics = json.load(f)

    mlflow.set_experiment("PS1_Failure_Prediction")
    with mlflow.start_run(run_name=f"PS1_Champion_{model_name}_Registered"):
        # Log model with signature
        mlflow.sklearn.log_model(
            model, "model",
            signature=signature,
            registered_model_name="device_failure_predictor"
        )

        # Log all metrics
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                mlflow.log_metric(k, v)

        mlflow.log_params({
            "model_type": model_name,
            "problem_statement": "PS-1 Failure Prediction",
            "champion": True,
            "n_features": len(available)
        })

        # Log artifacts
        for f in os.listdir(os.path.join(ARTIFACTS_DIR, "ps1")):
            fpath = os.path.join(ARTIFACTS_DIR, "ps1", f)
            if os.path.isfile(fpath):
                mlflow.log_artifact(fpath)

    print(f"   [OK] Registered 'device_failure_predictor' ({model_name})")
    print(f"   Metrics: AUC={metrics.get('auc', 'N/A')}, F1={metrics.get('f1', 'N/A')}")

    # Transition to Production
    try:
        versions = client.get_latest_versions("device_failure_predictor")
        if versions:
            latest = versions[0]
            client.transition_model_version_stage(
                name="device_failure_predictor",
                version=latest.version,
                stage="Production"
            )
            print(f"   [OK] Version {latest.version} -> Production")
    except Exception as e:
        print(f"   [WARN] Stage transition: {e}")


def register_ps4_model(client):
    """Register PS-4 Anomaly Detection model."""
    print("\n   --- PS-4: Anomaly Detection ---")

    model_path = os.path.join(ARTIFACTS_DIR, "ps4", "isolation_forest_model.pkl")
    if not os.path.exists(model_path):
        print("   [SKIP] No model found")
        return

    model_data = joblib.load(model_path)

    mlflow.set_experiment("PS4_Anomaly_Detection")
    with mlflow.start_run(run_name="PS4_IsolationForest_Registered"):
        mlflow.sklearn.log_model(
            model_data["model"], "model",
            registered_model_name="device_anomaly_detector"
        )

        mlflow.log_params({
            "model_type": "IsolationForest",
            "problem_statement": "PS-4 Anomaly Detection",
            "contamination": 0.08
        })

        # Log artifacts
        for f in os.listdir(os.path.join(ARTIFACTS_DIR, "ps4")):
            fpath = os.path.join(ARTIFACTS_DIR, "ps4", f)
            if os.path.isfile(fpath):
                mlflow.log_artifact(fpath)

    print(f"   [OK] Registered 'device_anomaly_detector'")

    try:
        versions = client.get_latest_versions("device_anomaly_detector")
        if versions:
            client.transition_model_version_stage(
                name="device_anomaly_detector",
                version=versions[0].version,
                stage="Production"
            )
            print(f"   [OK] Version {versions[0].version} -> Production")
    except Exception as e:
        print(f"   [WARN] Stage transition: {e}")


def register_ps5_model(client):
    """Register PS-5 SLA Risk artifacts."""
    print("\n   --- PS-5: SLA Risk Prediction ---")

    rul_path = os.path.join(ARTIFACTS_DIR, "ps5", "rul_estimates.csv")
    if not os.path.exists(rul_path):
        print("   [SKIP] No RUL estimates found")
        return

    mlflow.set_experiment("PS5_SLA_Risk_Prediction")
    with mlflow.start_run(run_name="PS5_SLA_Risk_Registered"):
        mlflow.log_params({
            "problem_statement": "PS-5 SLA Risk Prediction",
            "models": "Weibull, Cox PH, RUL"
        })

        # Log all PS5 artifacts
        for f in os.listdir(os.path.join(ARTIFACTS_DIR, "ps5")):
            fpath = os.path.join(ARTIFACTS_DIR, "ps5", f)
            if os.path.isfile(fpath):
                mlflow.log_artifact(fpath)

        # Log key metrics from RUL
        rul_df = pd.read_csv(rul_path)
        mlflow.log_metrics({
            "mean_rul_days": float(rul_df["rul_median_days"].mean()),
            "devices_critical": int((rul_df["risk_tier"] == "CRITICAL").sum()),
            "devices_high_risk": int((rul_df["risk_tier"] == "HIGH").sum()),
            "devices_medium_risk": int((rul_df["risk_tier"] == "MEDIUM").sum()),
            "devices_low_risk": int((rul_df["risk_tier"] == "LOW").sum()),
        })

    print(f"   [OK] PS-5 artifacts registered")


def register_ps2_ps3(client):
    """Register PS-2 and PS-3 artifacts."""
    for ps, name, exp_name in [
        ("ps2", "Error Pattern Recognition", "PS2_Error_Pattern_Recognition"),
        ("ps3", "Root Cause Analysis", "PS3_Root_Cause_Analysis")
    ]:
        print(f"\n   --- {name} ---")
        ps_dir = os.path.join(ARTIFACTS_DIR, ps)
        if not os.path.exists(ps_dir):
            print(f"   [SKIP] No {ps} artifacts found")
            continue

        mlflow.set_experiment(exp_name)
        with mlflow.start_run(run_name=f"{ps.upper()}_Registered"):
            mlflow.log_param("problem_statement", name)
            for f in os.listdir(ps_dir):
                fpath = os.path.join(ps_dir, f)
                if os.path.isfile(fpath):
                    mlflow.log_artifact(fpath)

        artifact_count = len([f for f in os.listdir(ps_dir) if os.path.isfile(os.path.join(ps_dir, f))])
        print(f"   [OK] {artifact_count} artifacts registered")


def print_registry_summary(client):
    """Print model registry summary."""
    print(f"\n{'='*60}")
    print(f"  MODEL REGISTRY SUMMARY")
    print(f"{'='*60}")

    try:
        models = client.search_registered_models()
        if not models:
            print("   No registered models")
            return

        for m in models:
            print(f"\n   Model: {m.name}")
            for v in m.latest_versions:
                print(f"     Version {v.version}: Stage={v.current_stage}, "
                      f"Run={v.run_id[:8]}...")
    except Exception as e:
        print(f"   Error: {e}")


def main():
    print("=" * 60)
    print("  MODEL REGISTRATION - MLflow Model Registry")
    print("=" * 60)

    client = setup_mlflow()

    register_ps1_models(client)
    register_ps2_ps3(client)
    register_ps4_model(client)
    register_ps5_model(client)

    print_registry_summary(client)

    print(f"\n  Registration complete.")
    print(f"  View in MLflow UI: http://localhost:5000")
    print(f"  Models tab shows registered models with versions")
    print("=" * 60)


if __name__ == "__main__":
    main()
