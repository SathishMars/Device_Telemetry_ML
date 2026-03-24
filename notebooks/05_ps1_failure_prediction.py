"""
============================================================
PS-1: FAILURE PREDICTION
============================================================
Models: Random Forest, XGBoost, CatBoost
Target: failure_next_3d (binary: will device fail in next 3 days?)
MLflow: Full experiment tracking & model registry
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

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    roc_curve, precision_recall_curve, average_precision_score
)
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from catboost import CatBoostClassifier

import mlflow
import mlflow.sklearn
import mlflow.xgboost
import mlflow.catboost

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts", "ps1")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


# ─── Feature Configuration ───────────────────────────────
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
    """Load and prepare data from feature store."""
    print("   Loading feature store data...")
    df = pd.read_parquet(os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet"))

    # Select features
    all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    available = [c for c in all_features if c in df.columns]
    X = df[available].copy()
    y = df[TARGET].copy()

    # Encode categoricals
    label_encoders = {}
    for col in CATEGORICAL_FEATURES:
        if col in X.columns and X[col].dtype == object:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            label_encoders[col] = le

    # Fill NaN
    X = X.fillna(0)

    print(f"   Data shape: {X.shape}, Target balance: {y.mean()*100:.1f}% positive")
    return X, y, label_encoders


def plot_roc_curves(results, y_test):
    """Plot ROC curves for all models."""
    fig, ax = plt.subplots(figsize=(8, 6))
    for name, res in results.items():
        fpr, tpr, _ = roc_curve(y_test, res["y_prob"])
        ax.plot(fpr, tpr, label=f"{name} (AUC={res['auc']:.3f})")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("PS-1: Failure Prediction - ROC Curves")
    ax.legend()
    plt.tight_layout()
    path = os.path.join(ARTIFACTS_DIR, "roc_curves.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def plot_feature_importance(model, feature_names, model_name):
    """Plot feature importance."""
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        idx = np.argsort(importances)[-15:]
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(range(len(idx)), importances[idx])
        ax.set_yticks(range(len(idx)))
        ax.set_yticklabels([feature_names[i] for i in idx])
        ax.set_title(f"{model_name} - Top 15 Feature Importance")
        plt.tight_layout()
        path = os.path.join(ARTIFACTS_DIR, f"feature_importance_{model_name.lower().replace(' ', '_')}.png")
        plt.savefig(path, dpi=150)
        plt.close()
        return path
    return None


def train_and_evaluate(X_train, X_test, y_train, y_test, feature_names):
    """Train RF, XGBoost, CatBoost and log to MLflow."""

    # Calculate scale_pos_weight for imbalanced data
    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_weight = neg_count / max(pos_count, 1)

    models = {
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_split=5,
            class_weight="balanced", random_state=42, n_jobs=-1
        ),
        "XGBoost": XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            scale_pos_weight=scale_weight, eval_metric="logloss",
            random_state=42, verbosity=0
        ),
        "CatBoost": CatBoostClassifier(
            iterations=200, depth=6, learning_rate=0.1,
            auto_class_weights="Balanced", random_seed=42, verbose=0
        )
    }

    results = {}

    for name, model in models.items():
        print(f"\n   Training {name}...")

        with mlflow.start_run(run_name=f"PS1_{name.replace(' ', '_')}"):
            # Train
            model.fit(X_train, y_train)

            # Predict
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]

            # Metrics
            metrics = {
                "accuracy": accuracy_score(y_test, y_pred),
                "precision": precision_score(y_test, y_pred, zero_division=0),
                "recall": recall_score(y_test, y_pred, zero_division=0),
                "f1": f1_score(y_test, y_pred, zero_division=0),
                "auc": roc_auc_score(y_test, y_prob),
                "avg_precision": average_precision_score(y_test, y_prob)
            }

            # Log to MLflow
            mlflow.log_params({
                "model_type": name,
                "n_features": X_train.shape[1],
                "train_size": len(X_train),
                "test_size": len(X_test),
                "positive_rate": float(y_train.mean()),
                "problem_statement": "PS-1 Failure Prediction"
            })
            mlflow.log_metrics(metrics)

            # Log model
            if name == "XGBoost":
                mlflow.xgboost.log_model(model, "model")
            elif name == "CatBoost":
                mlflow.catboost.log_model(model, "model")
            else:
                mlflow.sklearn.log_model(model, "model")

            # Log feature importance
            fi_path = plot_feature_importance(model, feature_names, name)
            if fi_path:
                mlflow.log_artifact(fi_path)

            # Log confusion matrix
            cm = confusion_matrix(y_test, y_pred)
            fig, ax = plt.subplots(figsize=(6, 5))
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax)
            ax.set_title(f"{name} - Confusion Matrix")
            ax.set_xlabel("Predicted")
            ax.set_ylabel("Actual")
            cm_path = os.path.join(ARTIFACTS_DIR, f"cm_{name.lower().replace(' ', '_')}.png")
            plt.tight_layout()
            plt.savefig(cm_path, dpi=150)
            plt.close()
            mlflow.log_artifact(cm_path)

            results[name] = {
                "model": model, "metrics": metrics,
                "y_pred": y_pred, "y_prob": y_prob, "auc": metrics["auc"]
            }

            print(f"   {name}: AUC={metrics['auc']:.4f}, F1={metrics['f1']:.4f}, "
                  f"Recall={metrics['recall']:.4f}")

    return results


def select_champion(results):
    """Select best model and register in MLflow."""
    best_name = max(results, key=lambda k: results[k]["auc"])
    best_model = results[best_name]["model"]
    best_metrics = results[best_name]["metrics"]

    print(f"\n   Champion Model: {best_name} (AUC={best_metrics['auc']:.4f})")

    # Save model artifact
    import joblib
    model_path = os.path.join(ARTIFACTS_DIR, "champion_model.pkl")
    joblib.dump(best_model, model_path)

    # Save metrics
    metrics_path = os.path.join(ARTIFACTS_DIR, "champion_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump({"model": best_name, **best_metrics}, f, indent=2)

    return best_name, best_model


def main():
    print("=" * 60)
    print("  PS-1: FAILURE PREDICTION")
    print("  Models: Random Forest, XGBoost, CatBoost")
    print("=" * 60)

    # Setup MLflow
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    os.makedirs(os.path.join(BASE_DIR, "mlruns"), exist_ok=True)
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("PS1_Failure_Prediction")

    # Load data
    X, y, encoders = load_data()
    feature_names = list(X.columns)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"   Train: {len(X_train)}, Test: {len(X_test)}")

    # Train models
    results = train_and_evaluate(X_train, X_test, y_train, y_test, feature_names)

    # Plot ROC curves
    roc_path = plot_roc_curves(results, y_test)
    print(f"   ROC curves saved: {roc_path}")

    # Select champion
    champion_name, champion_model = select_champion(results)

    print("\n  PS-1 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
