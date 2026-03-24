"""
============================================================
PS-5: SLA RISK PREDICTION
============================================================
Models:
  - Weibull Distribution (time-to-failure modeling)
  - Cox Proportional Hazards (survival analysis with covariates)
  - Remaining Useful Life (RUL) estimation
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

from lifelines import (
    WeibullFitter, CoxPHFitter, KaplanMeierFitter
)
from lifelines.utils import concordance_index
from sklearn.preprocessing import LabelEncoder

import mlflow

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts", "ps5")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def prepare_survival_data():
    """Prepare time-to-failure data for survival analysis."""
    print("   Preparing survival data...")

    features_df = pd.read_parquet(
        os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet"))
    maintenance = pd.read_parquet(os.path.join(SILVER_DIR, "maintenance.parquet"))

    # For each device, compute time-to-first-failure
    device_events = []
    for device_id in features_df["device_id"].unique():
        device_data = features_df[features_df["device_id"] == device_id].sort_values("date")

        # Time to first failure (in days from start of observation)
        failure_days = device_data[device_data["failure_today"] == 1]

        if len(failure_days) > 0:
            first_failure_date = failure_days["date"].min()
            start_date = device_data["date"].min()
            duration = (first_failure_date - start_date).days + 1
            event = 1  # Failure observed
        else:
            duration = len(device_data)  # Censored: no failure observed
            event = 0

        # Get latest device metrics as covariates
        latest = device_data.iloc[-1]

        device_events.append({
            "device_id": device_id,
            "duration_days": max(1, duration),
            "event": event,
            "age_days": latest.get("age_days", 0),
            "health_score": latest.get("health_score", 50),
            "error_count_7d_mean": latest.get("error_count_7d_mean", 0),
            "signal_strength_dbm_7d_mean": latest.get("signal_strength_dbm_7d_mean", 80),
            "temperature_c_7d_mean": latest.get("temperature_c_7d_mean", 35),
            "cumulative_errors": latest.get("cumulative_errors", 0),
            "total_maintenance_count": latest.get("total_maintenance_count", 0),
            "is_old_device": latest.get("is_old_device", 0),
            "is_beta_firmware": latest.get("is_beta_firmware", 0),
            "sla_compliance_rate": latest.get("sla_compliance_rate", 1.0),
        })

    survival_df = pd.DataFrame(device_events)
    print(f"   Survival data: {len(survival_df)} devices, "
          f"{survival_df['event'].sum()} failures ({survival_df['event'].mean()*100:.1f}%)")

    # Also prepare SLA data from maintenance
    sla_data = maintenance.copy()
    sla_data["sla_breach"] = 1 - sla_data["sla_met"]

    return survival_df, sla_data


# ─── Weibull Analysis ─────────────────────────────────────

def run_weibull_analysis(survival_df):
    """Fit Weibull distribution to time-to-failure data."""
    print("\n   --- Weibull Distribution Analysis ---")

    wf = WeibullFitter()
    wf.fit(survival_df["duration_days"], event_observed=survival_df["event"])

    # Weibull parameters
    lambda_param = wf.lambda_  # Scale parameter
    rho_param = wf.rho_        # Shape parameter

    print(f"   Weibull Parameters:")
    print(f"     Lambda (scale): {lambda_param:.4f}")
    print(f"     Rho (shape):    {rho_param:.4f}")

    if rho_param > 1:
        print(f"     Interpretation: Increasing failure rate (wear-out)")
    elif rho_param < 1:
        print(f"     Interpretation: Decreasing failure rate (infant mortality)")
    else:
        print(f"     Interpretation: Constant failure rate (random)")

    # Survival function plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Survival curve
    wf.plot_survival_function(ax=axes[0])
    axes[0].set_title("Weibull Survival Function")
    axes[0].set_xlabel("Days")
    axes[0].set_ylabel("Survival Probability")

    # Hazard function
    wf.plot_hazard(ax=axes[1])
    axes[1].set_title("Weibull Hazard Function")
    axes[1].set_xlabel("Days")
    axes[1].set_ylabel("Hazard Rate")

    # Cumulative hazard
    wf.plot_cumulative_hazard(ax=axes[2])
    axes[2].set_title("Weibull Cumulative Hazard")
    axes[2].set_xlabel("Days")
    axes[2].set_ylabel("Cumulative Hazard")

    plt.tight_layout()
    weibull_path = os.path.join(ARTIFACTS_DIR, "weibull_analysis.png")
    plt.savefig(weibull_path, dpi=150)
    plt.close()

    # Reliability at key timepoints
    timepoints = [7, 14, 21, 30]
    reliability = {}
    for t in timepoints:
        surv_prob = float(wf.predict(t))
        reliability[f"reliability_{t}d"] = round(surv_prob, 4)
        print(f"     R({t}d) = {surv_prob:.4f} ({surv_prob*100:.1f}% survive {t} days)")

    # Kaplan-Meier for comparison
    kmf = KaplanMeierFitter()
    kmf.fit(survival_df["duration_days"], event_observed=survival_df["event"])

    fig, ax = plt.subplots(figsize=(10, 6))
    kmf.plot_survival_function(ax=ax, label="Kaplan-Meier (non-parametric)")
    wf.plot_survival_function(ax=ax, label="Weibull (parametric)")
    ax.set_title("Device Survival: Kaplan-Meier vs Weibull")
    ax.set_xlabel("Days")
    ax.set_ylabel("Survival Probability")
    ax.legend()
    plt.tight_layout()
    km_path = os.path.join(ARTIFACTS_DIR, "km_vs_weibull.png")
    plt.savefig(km_path, dpi=150)
    plt.close()

    return wf, lambda_param, rho_param, reliability


# ─── Cox Proportional Hazards ─────────────────────────────

def run_cox_model(survival_df):
    """Fit Cox PH model with device covariates."""
    print("\n   --- Cox Proportional Hazards Model ---")

    # Prepare covariates
    cox_features = [
        "duration_days", "event",
        "age_days", "health_score", "error_count_7d_mean",
        "signal_strength_dbm_7d_mean", "temperature_c_7d_mean",
        "cumulative_errors", "total_maintenance_count",
        "is_old_device", "is_beta_firmware"
    ]

    cox_df = survival_df[cox_features].copy()
    cox_df = cox_df.fillna(0)

    # Standardize numeric features for stable fitting
    for col in cox_df.columns:
        if col not in ["duration_days", "event", "is_old_device", "is_beta_firmware"]:
            mean = cox_df[col].mean()
            std = cox_df[col].std()
            if std > 0:
                cox_df[col] = (cox_df[col] - mean) / std

    # Fit Cox model
    cph = CoxPHFitter(penalizer=0.1)
    cph.fit(cox_df, duration_col="duration_days", event_col="event")

    # Print summary
    print(f"\n   Cox PH Model Summary:")
    summary = cph.summary
    print(f"   Concordance Index: {cph.concordance_index_:.4f}")

    print(f"\n   Significant covariates (p < 0.05):")
    sig_covariates = summary[summary["p"] < 0.05]
    for idx, row in sig_covariates.iterrows():
        hr = np.exp(row["coef"])
        direction = "increases" if hr > 1 else "decreases"
        print(f"     {idx}: HR={hr:.3f} ({direction} failure risk), p={row['p']:.4f}")

    # Save summary
    summary.to_csv(os.path.join(ARTIFACTS_DIR, "cox_summary.csv"))

    # Plot hazard ratios
    fig, ax = plt.subplots(figsize=(10, 6))
    cph.plot(ax=ax)
    ax.set_title("Cox PH Model - Covariate Effects on Failure Risk")
    plt.tight_layout()
    cox_path = os.path.join(ARTIFACTS_DIR, "cox_hazard_ratios.png")
    plt.savefig(cox_path, dpi=150)
    plt.close()

    # Plot survival curves for high-risk vs low-risk devices
    fig, ax = plt.subplots(figsize=(10, 6))
    median_risk = cph.predict_partial_hazard(cox_df).median()
    high_risk = cox_df[cph.predict_partial_hazard(cox_df).values.flatten() > median_risk]
    low_risk = cox_df[cph.predict_partial_hazard(cox_df).values.flatten() <= median_risk]

    kmf_high = KaplanMeierFitter()
    kmf_low = KaplanMeierFitter()
    kmf_high.fit(high_risk["duration_days"], event_observed=high_risk["event"], label="High Risk")
    kmf_low.fit(low_risk["duration_days"], event_observed=low_risk["event"], label="Low Risk")

    kmf_high.plot_survival_function(ax=ax)
    kmf_low.plot_survival_function(ax=ax)
    ax.set_title("Survival Curves: High Risk vs Low Risk Devices")
    ax.set_xlabel("Days")
    ax.set_ylabel("Survival Probability")
    plt.tight_layout()
    risk_path = os.path.join(ARTIFACTS_DIR, "cox_risk_stratification.png")
    plt.savefig(risk_path, dpi=150)
    plt.close()

    return cph


# ─── Remaining Useful Life (RUL) ─────────────────────────

def estimate_rul(survival_df, wf, cph):
    """Estimate Remaining Useful Life for each device."""
    print("\n   --- Remaining Useful Life (RUL) Estimation ---")

    rul_results = []

    for _, device in survival_df.iterrows():
        device_id = device["device_id"]
        current_age = device["duration_days"]

        # Weibull-based RUL: E[T|T > t] - t
        # Using conditional survival
        survival_probs = []
        for t in range(current_age, current_age + 90):
            surv = float(wf.predict(t))
            survival_probs.append(surv)

        # Median remaining life (when survival drops to 50% of current)
        current_surv = float(wf.predict(current_age))
        target_surv = current_surv * 0.5

        rul_median = 0
        for t_offset, surv in enumerate(survival_probs):
            if surv < target_surv:
                rul_median = t_offset
                break
        else:
            rul_median = 90  # Exceeds 90-day horizon

        # Risk tier based on RUL
        if rul_median <= 7:
            risk_tier = "CRITICAL"
        elif rul_median <= 14:
            risk_tier = "HIGH"
        elif rul_median <= 30:
            risk_tier = "MEDIUM"
        else:
            risk_tier = "LOW"

        rul_results.append({
            "device_id": device_id,
            "current_age_days": current_age,
            "rul_median_days": rul_median,
            "current_survival_prob": round(current_surv, 4),
            "event_observed": device["event"],
            "health_score": device["health_score"],
            "risk_tier": risk_tier
        })

    rul_df = pd.DataFrame(rul_results)

    print(f"\n   RUL Summary:")
    print(f"   Risk tier distribution:")
    for tier, count in rul_df["risk_tier"].value_counts().items():
        print(f"     {tier}: {count} devices ({count/len(rul_df)*100:.0f}%)")

    print(f"   Mean RUL: {rul_df['rul_median_days'].mean():.1f} days")
    print(f"   Devices needing attention (RUL < 14d): "
          f"{(rul_df['rul_median_days'] < 14).sum()}")

    rul_df.to_csv(os.path.join(ARTIFACTS_DIR, "rul_estimates.csv"), index=False)

    # Plot RUL distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(rul_df["rul_median_days"], bins=30, alpha=0.7, color="steelblue", edgecolor="white")
    axes[0].axvline(x=14, color="red", linestyle="--", label="14-day threshold")
    axes[0].set_xlabel("RUL (days)")
    axes[0].set_ylabel("Number of Devices")
    axes[0].set_title("Remaining Useful Life Distribution")
    axes[0].legend()

    tier_counts = rul_df["risk_tier"].value_counts()
    colors = {"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "gold", "LOW": "green"}
    tier_colors = [colors.get(t, "gray") for t in tier_counts.index]
    axes[1].bar(tier_counts.index, tier_counts.values, color=tier_colors, edgecolor="white")
    axes[1].set_xlabel("Risk Tier")
    axes[1].set_ylabel("Number of Devices")
    axes[1].set_title("Device Risk Tier Distribution")

    plt.tight_layout()
    rul_path = os.path.join(ARTIFACTS_DIR, "rul_distribution.png")
    plt.savefig(rul_path, dpi=150)
    plt.close()

    return rul_df


# ─── SLA Risk Scoring ─────────────────────────────────────

def sla_risk_scoring(survival_df, rul_df, sla_data):
    """Combine models into SLA risk score."""
    print("\n   --- SLA Risk Scoring ---")

    merged = survival_df.merge(
        rul_df[["device_id", "rul_median_days", "risk_tier"]],
        on="device_id", how="left"
    )

    # SLA breach probability (simplified logistic model)
    # Higher risk = higher SLA breach probability
    merged["sla_breach_prob"] = 1 / (1 + np.exp(0.1 * (merged["rul_median_days"] - 15)))
    merged["sla_breach_prob"] = merged["sla_breach_prob"].round(4)

    # Overall SLA risk score (0-100)
    merged["sla_risk_score"] = (
        (1 - merged["health_score"] / 100) * 30 +
        merged["sla_breach_prob"] * 40 +
        (merged["cumulative_errors"] / merged["cumulative_errors"].max()) * 20 +
        merged["is_old_device"] * 10
    ).clip(0, 100).round(1)

    merged = merged.sort_values("sla_risk_score", ascending=False)

    print(f"\n   Top 5 SLA risk devices:")
    for _, row in merged.head(5).iterrows():
        print(f"     {row['device_id']}: Score={row['sla_risk_score']:.1f}, "
              f"RUL={row['rul_median_days']}d, Breach Prob={row['sla_breach_prob']:.3f}")

    merged.to_csv(os.path.join(ARTIFACTS_DIR, "sla_risk_scores.csv"), index=False)

    return merged


def main():
    print("=" * 60)
    print("  PS-5: SLA RISK PREDICTION")
    print("  Models: Weibull, Cox PH, Remaining Useful Life")
    print("=" * 60)

    # Setup MLflow
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    os.makedirs(os.path.join(BASE_DIR, "mlruns"), exist_ok=True)
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("PS5_SLA_Risk_Prediction")

    survival_df, sla_data = prepare_survival_data()

    with mlflow.start_run(run_name="PS5_SLA_Risk"):
        # Weibull Analysis
        wf, lambda_param, rho_param, reliability = run_weibull_analysis(survival_df)
        mlflow.log_metrics({
            "weibull_lambda": lambda_param,
            "weibull_rho": rho_param,
            **reliability
        })

        # Cox PH Model
        cph = run_cox_model(survival_df)
        mlflow.log_metric("cox_concordance_index", cph.concordance_index_)

        # RUL Estimation
        rul_df = estimate_rul(survival_df, wf, cph)
        mlflow.log_metrics({
            "mean_rul_days": float(rul_df["rul_median_days"].mean()),
            "critical_devices": int((rul_df["risk_tier"] == "CRITICAL").sum()),
            "high_risk_devices": int((rul_df["risk_tier"] == "HIGH").sum()),
        })

        # SLA Risk Scoring
        risk_df = sla_risk_scoring(survival_df, rul_df, sla_data)
        mlflow.log_metric("mean_sla_risk_score", float(risk_df["sla_risk_score"].mean()))

        mlflow.log_params({
            "problem_statement": "PS-5 SLA Risk Prediction",
            "total_devices": len(survival_df),
            "failure_events": int(survival_df["event"].sum()),
        })

        # Log all artifacts
        for f in os.listdir(ARTIFACTS_DIR):
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, f))

    print("\n  PS-5 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
