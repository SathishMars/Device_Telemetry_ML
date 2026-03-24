"""
============================================================
PS-4: ANOMALY DETECTION
============================================================
Models:
  - Isolation Forest (unsupervised anomaly detection)
  - Statistical Process Control (SPC) - control charts
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
import seaborn as sns

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

import mlflow

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts", "ps4")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

SPC_FEATURES = [
    "signal_strength_dbm", "temperature_c", "response_time_ms",
    "network_latency_ms", "power_voltage", "memory_usage_pct",
    "cpu_usage_pct", "error_count", "tap_success_rate",
    "uptime_hours", "health_score"
]


def load_data():
    """Load telemetry features for anomaly detection."""
    print("   Loading feature store data...")
    df = pd.read_parquet(os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet"))

    available = [c for c in SPC_FEATURES if c in df.columns]
    X = df[available].copy().fillna(0)

    print(f"   Data shape: {X.shape}")
    return df, X


# ─── Isolation Forest ─────────────────────────────────────

def run_isolation_forest(df, X):
    """Detect anomalies using Isolation Forest."""
    print("\n   --- Isolation Forest ---")

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train Isolation Forest
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.08,  # Expected ~8% anomaly rate
        max_samples="auto",
        random_state=42,
        n_jobs=-1
    )

    # Predict anomalies (-1 = anomaly, 1 = normal)
    predictions = iso_forest.fit_predict(X_scaled)
    anomaly_scores = iso_forest.decision_function(X_scaled)

    df["anomaly_label"] = (predictions == -1).astype(int)
    df["anomaly_score"] = anomaly_scores

    n_anomalies = df["anomaly_label"].sum()
    anomaly_rate = n_anomalies / len(df) * 100

    print(f"   Anomalies detected: {n_anomalies} ({anomaly_rate:.1f}%)")

    # Anomaly distribution by device
    device_anomalies = (
        df.groupby("device_id")["anomaly_label"]
        .agg(["sum", "count"])
        .reset_index()
    )
    device_anomalies.columns = ["device_id", "anomaly_count", "total_days"]
    device_anomalies["anomaly_rate"] = device_anomalies["anomaly_count"] / device_anomalies["total_days"]
    device_anomalies = device_anomalies.sort_values("anomaly_count", ascending=False)

    print(f"\n   Top 5 anomalous devices:")
    for _, row in device_anomalies.head(5).iterrows():
        print(f"     {row['device_id']}: {row['anomaly_count']} anomalies "
              f"({row['anomaly_rate']*100:.0f}% of days)")

    device_anomalies.to_csv(os.path.join(ARTIFACTS_DIR, "device_anomaly_summary.csv"), index=False)

    # Feature importance for anomalies
    anomalous = df[df["anomaly_label"] == 1][SPC_FEATURES].mean()
    normal = df[df["anomaly_label"] == 0][SPC_FEATURES].mean()
    diff = (anomalous - normal) / normal.replace(0, 1) * 100

    feature_diff = pd.DataFrame({
        "feature": SPC_FEATURES,
        "anomaly_mean": anomalous.values,
        "normal_mean": normal.values,
        "pct_diff": diff.values
    }).sort_values("pct_diff", key=abs, ascending=False)

    print(f"\n   Feature differences (anomaly vs normal):")
    for _, row in feature_diff.head(5).iterrows():
        print(f"     {row['feature']}: {row['pct_diff']:+.1f}% "
              f"(anomaly={row['anomaly_mean']:.1f}, normal={row['normal_mean']:.1f})")

    feature_diff.to_csv(os.path.join(ARTIFACTS_DIR, "anomaly_feature_diff.csv"), index=False)

    # Plot anomaly score distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(anomaly_scores, bins=50, alpha=0.7, color="steelblue", edgecolor="white")
    threshold = np.percentile(anomaly_scores, 8)
    axes[0].axvline(x=threshold, color="red", linestyle="--", label=f"Threshold ({threshold:.3f})")
    axes[0].set_xlabel("Anomaly Score")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title("Isolation Forest - Anomaly Score Distribution")
    axes[0].legend()

    # Anomalies over time
    daily_anomalies = df.groupby("date")["anomaly_label"].mean() * 100
    axes[1].plot(daily_anomalies.index, daily_anomalies.values, "b-o", markersize=3)
    axes[1].axhline(y=anomaly_rate, color="red", linestyle="--", alpha=0.5, label=f"Avg: {anomaly_rate:.1f}%")
    axes[1].set_xlabel("Date")
    axes[1].set_ylabel("Anomaly Rate (%)")
    axes[1].set_title("Daily Anomaly Rate Over Time")
    axes[1].legend()
    plt.xticks(rotation=45)

    plt.tight_layout()
    iso_path = os.path.join(ARTIFACTS_DIR, "isolation_forest_results.png")
    plt.savefig(iso_path, dpi=150)
    plt.close()

    # Save model
    import joblib
    model_path = os.path.join(ARTIFACTS_DIR, "isolation_forest_model.pkl")
    joblib.dump({"model": iso_forest, "scaler": scaler}, model_path)

    return df, iso_forest, n_anomalies, anomaly_rate


# ─── Statistical Process Control (SPC) ───────────────────

def run_spc(df):
    """Implement SPC control charts for key metrics."""
    print("\n   --- Statistical Process Control (SPC) ---")

    spc_features = ["signal_strength_dbm", "temperature_c", "response_time_ms",
                     "error_count", "tap_success_rate", "health_score"]
    available = [f for f in spc_features if f in df.columns]

    spc_results = []
    spc_violations = {}

    fig, axes = plt.subplots(len(available), 1, figsize=(14, 4 * len(available)))
    if len(available) == 1:
        axes = [axes]

    for i, feature in enumerate(available):
        # Compute control limits using first 7 days as baseline
        daily_mean = df.groupby("date")[feature].mean()
        baseline = daily_mean.iloc[:7]

        center_line = baseline.mean()
        std = baseline.std()
        ucl = center_line + 3 * std  # Upper Control Limit
        lcl = center_line - 3 * std  # Lower Control Limit
        uwl = center_line + 2 * std  # Upper Warning Limit
        lwl = center_line - 2 * std  # Lower Warning Limit

        # Detect violations
        violations = daily_mean[(daily_mean > ucl) | (daily_mean < lcl)]
        warnings_detected = daily_mean[
            ((daily_mean > uwl) & (daily_mean <= ucl)) |
            ((daily_mean < lwl) & (daily_mean >= lcl))
        ]

        spc_violations[feature] = {
            "violations": len(violations),
            "warnings": len(warnings_detected),
            "center_line": round(center_line, 3),
            "ucl": round(ucl, 3),
            "lcl": round(lcl, 3)
        }

        print(f"   {feature}: CL={center_line:.2f}, UCL={ucl:.2f}, LCL={lcl:.2f}, "
              f"Violations={len(violations)}, Warnings={len(warnings_detected)}")

        # Plot control chart
        ax = axes[i]
        dates = range(len(daily_mean))
        ax.plot(dates, daily_mean.values, "b-o", markersize=3, label="Daily Mean")
        ax.axhline(y=center_line, color="green", linestyle="-", alpha=0.7, label="CL")
        ax.axhline(y=ucl, color="red", linestyle="--", alpha=0.7, label="UCL (3σ)")
        ax.axhline(y=lcl, color="red", linestyle="--", alpha=0.7, label="LCL (3σ)")
        ax.axhline(y=uwl, color="orange", linestyle=":", alpha=0.5, label="UWL (2σ)")
        ax.axhline(y=lwl, color="orange", linestyle=":", alpha=0.5, label="LWL (2σ)")

        # Mark violations
        for v_date in violations.index:
            v_idx = list(daily_mean.index).index(v_date)
            ax.scatter(v_idx, violations[v_date], color="red", s=100, zorder=5, marker="x")

        ax.fill_between(dates, lcl, ucl, alpha=0.05, color="green")
        ax.set_ylabel(feature)
        ax.set_title(f"SPC Control Chart: {feature}")
        if i == 0:
            ax.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    spc_path = os.path.join(ARTIFACTS_DIR, "spc_control_charts.png")
    plt.savefig(spc_path, dpi=150)
    plt.close()

    # Western Electric Rules
    print(f"\n   SPC Summary:")
    total_violations = sum(v["violations"] for v in spc_violations.values())
    total_warnings = sum(v["warnings"] for v in spc_violations.values())
    print(f"   Total violations (3σ): {total_violations}")
    print(f"   Total warnings (2σ):   {total_warnings}")

    # Save SPC results
    spc_df = pd.DataFrame([
        {"feature": k, **v} for k, v in spc_violations.items()
    ])
    spc_df.to_csv(os.path.join(ARTIFACTS_DIR, "spc_results.csv"), index=False)

    with open(os.path.join(ARTIFACTS_DIR, "spc_limits.json"), "w") as f:
        json.dump(spc_violations, f, indent=2)

    return spc_violations, total_violations, total_warnings


def main():
    print("=" * 60)
    print("  PS-4: ANOMALY DETECTION")
    print("  Models: Isolation Forest, Statistical Process Control")
    print("=" * 60)

    # Setup MLflow
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    os.makedirs(os.path.join(BASE_DIR, "mlruns"), exist_ok=True)
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("PS4_Anomaly_Detection")

    df, X = load_data()

    with mlflow.start_run(run_name="PS4_Anomaly_Detection"):
        # Isolation Forest
        df, iso_model, n_anomalies, anomaly_rate = run_isolation_forest(df, X)

        mlflow.log_metrics({
            "anomalies_detected": n_anomalies,
            "anomaly_rate_pct": round(anomaly_rate, 2),
        })

        # SPC Control Charts
        spc_results, total_violations, total_warnings = run_spc(df)

        mlflow.log_metrics({
            "spc_total_violations": total_violations,
            "spc_total_warnings": total_warnings,
        })

        mlflow.log_params({
            "problem_statement": "PS-4 Anomaly Detection",
            "isolation_forest_contamination": 0.08,
            "spc_sigma_level": 3,
            "n_features": len(SPC_FEATURES)
        })

        # Log all artifacts
        for f in os.listdir(ARTIFACTS_DIR):
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, f))

    # Save annotated dataset with anomaly labels
    out_path = os.path.join(ARTIFACTS_DIR, "telemetry_with_anomalies.parquet")
    df.to_parquet(out_path, index=False, engine="pyarrow")
    print(f"\n   Annotated data saved: {out_path}")

    print("\n  PS-4 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
