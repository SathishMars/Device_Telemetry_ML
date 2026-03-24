"""
============================================================
PS-3: ROOT CAUSE ANALYSIS
============================================================
Models:
  - SHAP (SHapley Additive exPlanations) on PS-1 champion model
  - Causal Inference using DoWhy framework
MLflow: Experiment tracking
============================================================
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import joblib
import shap

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

import mlflow

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")
PS1_ARTIFACTS = os.path.join(BASE_DIR, "data", "artifacts", "ps1")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts", "ps3")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

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

TARGET = "failure_next_3d"


def load_data():
    """Load data and champion model."""
    print("   Loading data and champion model...")
    df = pd.read_parquet(os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet"))

    all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    available = [c for c in all_features if c in df.columns]
    X = df[available].copy()
    y = df[TARGET].copy()

    for col in CATEGORICAL_FEATURES:
        if col in X.columns and X[col].dtype == object:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))

    X = X.fillna(0)

    # Load champion model
    model_path = os.path.join(PS1_ARTIFACTS, "champion_model.pkl")
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        print(f"   Champion model loaded: {type(model).__name__}")
    else:
        print("   [WARN] No champion model found. Training XGBoost fallback...")
        from xgboost import XGBClassifier
        model = XGBClassifier(n_estimators=100, max_depth=6, random_state=42, verbosity=0)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model.fit(X_train, y_train)

    return X, y, model


# ─── SHAP Analysis ────────────────────────────────────────

def run_shap_analysis(X, model, feature_names):
    """Compute SHAP values for global and local explanations."""
    print("\n   --- SHAP Analysis ---")

    # Use a sample for SHAP (speed)
    sample_size = min(500, len(X))
    X_sample = X.sample(n=sample_size, random_state=42)

    # Compute SHAP values
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    # Global feature importance (mean |SHAP|)
    if isinstance(shap_values, list):
        shap_vals = shap_values[1]  # For binary classification, class 1
    else:
        shap_vals = shap_values

    mean_shap = np.abs(shap_vals).mean(axis=0)
    importance_df = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap": mean_shap
    }).sort_values("mean_abs_shap", ascending=False)

    print(f"\n   Top 10 Root Causes (SHAP feature importance):")
    for i, row in importance_df.head(10).iterrows():
        print(f"     {row['feature']}: {row['mean_abs_shap']:.4f}")

    importance_df.to_csv(os.path.join(ARTIFACTS_DIR, "shap_importance.csv"), index=False)

    # SHAP Summary Plot (beeswarm)
    fig, ax = plt.subplots(figsize=(10, 8))
    shap.summary_plot(shap_vals, X_sample, feature_names=feature_names,
                      show=False, max_display=15)
    plt.title("PS-3: SHAP Summary - Root Cause Analysis")
    plt.tight_layout()
    summary_path = os.path.join(ARTIFACTS_DIR, "shap_summary.png")
    plt.savefig(summary_path, dpi=150, bbox_inches="tight")
    plt.close("all")

    # SHAP Bar Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    shap.summary_plot(shap_vals, X_sample, feature_names=feature_names,
                      plot_type="bar", show=False, max_display=15)
    plt.title("PS-3: Mean |SHAP| - Feature Impact on Failure")
    plt.tight_layout()
    bar_path = os.path.join(ARTIFACTS_DIR, "shap_bar.png")
    plt.savefig(bar_path, dpi=150, bbox_inches="tight")
    plt.close("all")

    # SHAP dependence plot for top feature
    top_feature = importance_df.iloc[0]["feature"]
    top_idx = feature_names.index(top_feature)
    fig, ax = plt.subplots(figsize=(8, 6))
    shap.dependence_plot(top_idx, shap_vals, X_sample,
                         feature_names=feature_names, show=False)
    plt.title(f"SHAP Dependence: {top_feature}")
    plt.tight_layout()
    dep_path = os.path.join(ARTIFACTS_DIR, f"shap_dependence_{top_feature}.png")
    plt.savefig(dep_path, dpi=150, bbox_inches="tight")
    plt.close("all")

    # Local explanation (single device prediction)
    idx = X_sample.index[0]
    local_shap = shap_vals[0]
    local_df = pd.DataFrame({
        "feature": feature_names,
        "shap_value": local_shap,
        "feature_value": X_sample.iloc[0].values
    }).sort_values("shap_value", key=abs, ascending=False)

    print(f"\n   Local explanation (sample device):")
    for _, row in local_df.head(5).iterrows():
        direction = "+" if row["shap_value"] > 0 else "-"
        print(f"     {direction} {row['feature']}={row['feature_value']:.2f} "
              f"(SHAP={row['shap_value']:.4f})")

    local_df.to_csv(os.path.join(ARTIFACTS_DIR, "shap_local_explanation.csv"), index=False)

    return importance_df, shap_vals


# ─── Causal Inference ─────────────────────────────────────

def run_causal_inference(X, y, feature_names):
    """Estimate causal effects of key features on failure."""
    print("\n   --- Causal Inference (DoWhy) ---")

    try:
        import dowhy
        from dowhy import CausalModel
    except ImportError:
        print("   [WARN] DoWhy not installed. Running simplified causal analysis...")
        return run_simplified_causal(X, y, feature_names)

    # Prepare data
    df = X.copy()
    df["failure"] = y.values

    # Test causal hypotheses
    hypotheses = [
        ("error_count", "High error count causes failures"),
        ("temperature_c", "High temperature causes failures"),
        ("signal_strength_dbm", "Low signal strength causes failures"),
        ("memory_usage_pct", "High memory usage causes failures"),
        ("age_days", "Device age causes failures"),
    ]

    causal_results = []
    for treatment, description in hypotheses:
        if treatment not in df.columns:
            continue

        print(f"\n   Testing: {description}")

        # Binarize treatment (above/below median)
        median_val = df[treatment].median()
        df[f"{treatment}_high"] = (df[treatment] > median_val).astype(int)

        try:
            # Define causal model
            model = CausalModel(
                data=df,
                treatment=f"{treatment}_high",
                outcome="failure",
                common_causes=[c for c in feature_names if c != treatment][:5]  # Limit confounders
            )

            # Identify estimand
            identified = model.identify_effect(proceed_when_unidentifiable=True)

            # Estimate effect
            estimate = model.estimate_effect(
                identified,
                method_name="backdoor.propensity_score_matching",
                target_units="ate"
            )

            ate = float(estimate.value)
            causal_results.append({
                "treatment": treatment,
                "hypothesis": description,
                "ate": round(ate, 4),
                "significant": abs(ate) > 0.01
            })

            print(f"     ATE = {ate:.4f} {'(significant)' if abs(ate) > 0.01 else '(not significant)'}")

            # Cleanup
            df = df.drop(columns=[f"{treatment}_high"])

        except Exception as e:
            print(f"     [ERROR] {str(e)[:80]}")
            df = df.drop(columns=[f"{treatment}_high"], errors="ignore")
            causal_results.append({
                "treatment": treatment,
                "hypothesis": description,
                "ate": None,
                "significant": None
            })

    results_df = pd.DataFrame(causal_results)
    results_df.to_csv(os.path.join(ARTIFACTS_DIR, "causal_results.csv"), index=False)

    return results_df


def run_simplified_causal(X, y, feature_names):
    """Simplified causal analysis without DoWhy."""
    print("   Running correlation-based causal proxy analysis...")

    df = X.copy()
    df["failure"] = y.values

    results = []
    for feature in ["error_count", "temperature_c", "signal_strength_dbm",
                     "memory_usage_pct", "age_days", "response_time_ms"]:
        if feature not in df.columns:
            continue

        median_val = df[feature].median()
        high_group = df[df[feature] > median_val]["failure"].mean()
        low_group = df[df[feature] <= median_val]["failure"].mean()
        diff = high_group - low_group

        results.append({
            "treatment": feature,
            "failure_rate_high": round(high_group, 4),
            "failure_rate_low": round(low_group, 4),
            "difference": round(diff, 4),
            "risk_ratio": round(high_group / max(low_group, 0.001), 2)
        })

        print(f"     {feature}: high={high_group:.3f}, low={low_group:.3f}, "
              f"diff={diff:.3f}, RR={results[-1]['risk_ratio']:.2f}")

    results_df = pd.DataFrame(results).sort_values("difference", key=abs, ascending=False)
    results_df.to_csv(os.path.join(ARTIFACTS_DIR, "causal_results.csv"), index=False)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    x_pos = range(len(results_df))
    colors = ["red" if d > 0 else "green" for d in results_df["difference"]]
    ax.bar(x_pos, results_df["difference"], color=colors, alpha=0.7)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(results_df["treatment"], rotation=45, ha="right")
    ax.set_ylabel("Failure Rate Difference (High - Low)")
    ax.set_title("PS-3: Causal Analysis - Feature Impact on Failure Rate")
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    plt.tight_layout()
    causal_path = os.path.join(ARTIFACTS_DIR, "causal_analysis.png")
    plt.savefig(causal_path, dpi=150)
    plt.close()

    return results_df


def main():
    print("=" * 60)
    print("  PS-3: ROOT CAUSE ANALYSIS")
    print("  Models: SHAP, Causal Inference (DoWhy)")
    print("=" * 60)

    # Setup MLflow
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    os.makedirs(os.path.join(BASE_DIR, "mlruns"), exist_ok=True)
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("PS3_Root_Cause_Analysis")

    X, y, model = load_data()
    feature_names = list(X.columns)

    with mlflow.start_run(run_name="PS3_Root_Cause"):
        # SHAP Analysis
        importance_df, shap_vals = run_shap_analysis(X, model, feature_names)

        mlflow.log_metric("top_feature_shap", float(importance_df.iloc[0]["mean_abs_shap"]))
        mlflow.log_param("top_root_cause", importance_df.iloc[0]["feature"])
        mlflow.log_param("problem_statement", "PS-3 Root Cause Analysis")

        # Log SHAP artifacts
        for f in os.listdir(ARTIFACTS_DIR):
            if f.startswith("shap_"):
                mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, f))

        # Causal Inference
        causal_df = run_causal_inference(X, y, feature_names)
        mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, "causal_results.csv"))
        if os.path.exists(os.path.join(ARTIFACTS_DIR, "causal_analysis.png")):
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, "causal_analysis.png"))

    print("\n  PS-3 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
