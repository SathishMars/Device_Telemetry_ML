"""
============================================================
PS-2: ERROR PATTERN RECOGNITION
============================================================
Models:
  - Association Rules (Apriori) for co-occurring errors
  - Markov Chain for error sequence transitions
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
from collections import defaultdict

from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

import mlflow

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts", "ps2")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def load_error_data():
    """Load error logs from silver layer."""
    print("   Loading error data...")
    errors = pd.read_parquet(os.path.join(SILVER_DIR, "error_logs.parquet"))
    errors["date"] = errors["timestamp"].dt.date.astype(str)
    print(f"   Error records: {len(errors)}")
    print(f"   Unique error codes: {errors['error_code'].nunique()}")
    return errors


# ─── Association Rules (Apriori) ──────────────────────────

def run_association_rules(errors):
    """Find co-occurring error patterns using Apriori algorithm."""
    print("\n   --- Association Rules (Apriori) ---")

    # Create transactions: each device-day is a transaction of error codes
    transactions = (
        errors.groupby(["device_id", "date"])["error_code"]
        .apply(list).tolist()
    )

    # Filter transactions with 2+ errors (patterns require co-occurrence)
    transactions = [t for t in transactions if len(t) >= 2]
    # Deduplicate within transactions
    transactions = [list(set(t)) for t in transactions]

    print(f"   Transactions with 2+ errors: {len(transactions)}")

    if len(transactions) < 10:
        print("   [WARN] Too few transactions for meaningful rules")
        return pd.DataFrame()

    # Encode transactions
    te = TransactionEncoder()
    te_array = te.fit(transactions).transform(transactions)
    df_encoded = pd.DataFrame(te_array, columns=te.columns_)

    # Find frequent itemsets
    frequent_itemsets = apriori(
        df_encoded, min_support=0.05, use_colnames=True, max_len=3
    )

    if frequent_itemsets.empty:
        print("   [WARN] No frequent itemsets found")
        return pd.DataFrame()

    print(f"   Frequent itemsets: {len(frequent_itemsets)}")

    # Generate association rules
    rules = association_rules(
        frequent_itemsets, metric="confidence", min_threshold=0.3,
        num_itemsets=len(frequent_itemsets)
    )

    if rules.empty:
        print("   [WARN] No association rules found")
        return pd.DataFrame()

    # Format rules for readability
    rules["antecedents"] = rules["antecedents"].apply(lambda x: ", ".join(list(x)))
    rules["consequents"] = rules["consequents"].apply(lambda x: ", ".join(list(x)))
    rules = rules.sort_values("lift", ascending=False)

    print(f"   Association rules found: {len(rules)}")
    print(f"\n   Top 5 rules by lift:")
    for _, row in rules.head(5).iterrows():
        print(f"     {row['antecedents']} => {row['consequents']} "
              f"(conf={row['confidence']:.2f}, lift={row['lift']:.2f}, sup={row['support']:.3f})")

    # Save rules
    rules_path = os.path.join(ARTIFACTS_DIR, "association_rules.csv")
    rules.to_csv(rules_path, index=False)

    # Plot top rules
    if len(rules) > 0:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Support vs Confidence scatter
        top_rules = rules.head(20)
        scatter = axes[0].scatter(
            top_rules["support"], top_rules["confidence"],
            c=top_rules["lift"], cmap="YlOrRd", s=100, alpha=0.7
        )
        axes[0].set_xlabel("Support")
        axes[0].set_ylabel("Confidence")
        axes[0].set_title("Association Rules: Support vs Confidence")
        plt.colorbar(scatter, ax=axes[0], label="Lift")

        # Top rules by lift
        top5 = rules.head(10)
        rule_labels = [f"{a[:20]}=>{c[:20]}" for a, c in zip(top5["antecedents"], top5["consequents"])]
        axes[1].barh(range(len(top5)), top5["lift"])
        axes[1].set_yticks(range(len(top5)))
        axes[1].set_yticklabels(rule_labels, fontsize=8)
        axes[1].set_xlabel("Lift")
        axes[1].set_title("Top Association Rules by Lift")

        plt.tight_layout()
        plot_path = os.path.join(ARTIFACTS_DIR, "association_rules_plot.png")
        plt.savefig(plot_path, dpi=150)
        plt.close()

    return rules


# ─── Markov Chain ─────────────────────────────────────────

def run_markov_chain(errors):
    """Build Markov transition model for error sequences."""
    print("\n   --- Markov Chain Error Transitions ---")

    # Sort errors by device and time
    errors_sorted = errors.sort_values(["device_id", "timestamp"])

    # Build transition counts
    error_codes = errors_sorted["error_code"].unique()
    n_states = len(error_codes)
    state_idx = {code: i for i, code in enumerate(error_codes)}

    transition_counts = np.zeros((n_states, n_states))

    for device_id, group in errors_sorted.groupby("device_id"):
        codes = group["error_code"].values
        for i in range(len(codes) - 1):
            from_idx = state_idx[codes[i]]
            to_idx = state_idx[codes[i + 1]]
            transition_counts[from_idx, to_idx] += 1

    # Normalize to get transition probabilities
    row_sums = transition_counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    transition_matrix = transition_counts / row_sums

    # Create DataFrame
    tm_df = pd.DataFrame(
        transition_matrix,
        index=error_codes,
        columns=error_codes
    )

    print(f"   States (error codes): {n_states}")
    print(f"   Total transitions: {int(transition_counts.sum())}")

    # Find highest probability transitions
    transitions = []
    for i, from_code in enumerate(error_codes):
        for j, to_code in enumerate(error_codes):
            if transition_matrix[i, j] > 0.1:  # Only significant transitions
                transitions.append({
                    "from_error": from_code,
                    "to_error": to_code,
                    "probability": round(transition_matrix[i, j], 4),
                    "count": int(transition_counts[i, j])
                })

    transitions_df = pd.DataFrame(transitions).sort_values("probability", ascending=False)

    print(f"\n   Top error transitions (prob > 0.1):")
    for _, row in transitions_df.head(10).iterrows():
        print(f"     {row['from_error']} -> {row['to_error']} "
              f"(prob={row['probability']:.3f}, n={row['count']})")

    # Save artifacts
    tm_df.to_csv(os.path.join(ARTIFACTS_DIR, "transition_matrix.csv"))
    transitions_df.to_csv(os.path.join(ARTIFACTS_DIR, "top_transitions.csv"), index=False)

    # Plot transition heatmap
    fig, ax = plt.subplots(figsize=(12, 10))
    # Shorten labels for display
    short_labels = [c.split("_", 1)[0] + "_" + c.split("_")[-1][:8] if "_" in c else c[:12]
                    for c in error_codes]
    sns.heatmap(
        tm_df.values, annot=True, fmt=".2f", cmap="YlOrRd",
        xticklabels=short_labels, yticklabels=short_labels,
        ax=ax, vmin=0, vmax=0.5
    )
    ax.set_title("Markov Transition Matrix: Error Code Sequences")
    ax.set_xlabel("To Error")
    ax.set_ylabel("From Error")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    heatmap_path = os.path.join(ARTIFACTS_DIR, "markov_heatmap.png")
    plt.savefig(heatmap_path, dpi=150)
    plt.close()

    # Stationary distribution (long-run error probabilities)
    eigenvalues, eigenvectors = np.linalg.eig(transition_matrix.T)
    idx = np.argmin(np.abs(eigenvalues - 1))
    stationary = np.real(eigenvectors[:, idx])
    stationary = stationary / stationary.sum()

    stationary_df = pd.DataFrame({
        "error_code": error_codes,
        "stationary_probability": np.abs(stationary)
    }).sort_values("stationary_probability", ascending=False)

    print(f"\n   Stationary distribution (long-run error likelihood):")
    for _, row in stationary_df.head(5).iterrows():
        print(f"     {row['error_code']}: {row['stationary_probability']:.4f}")

    stationary_df.to_csv(os.path.join(ARTIFACTS_DIR, "stationary_distribution.csv"), index=False)

    return tm_df, transitions_df, stationary_df


# ─── Severity Pattern Analysis ────────────────────────────

def analyze_severity_escalation(errors):
    """Analyze patterns of error severity escalation."""
    print("\n   --- Severity Escalation Analysis ---")

    severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    errors_sorted = errors.sort_values(["device_id", "timestamp"])
    errors_sorted["severity_num"] = errors_sorted["severity"].map(severity_order)

    escalations = []
    for device_id, group in errors_sorted.groupby("device_id"):
        severities = group["severity_num"].values
        for i in range(len(severities) - 1):
            if severities[i + 1] > severities[i]:
                escalations.append({
                    "device_id": device_id,
                    "from_severity": group.iloc[i]["severity"],
                    "to_severity": group.iloc[i + 1]["severity"],
                    "from_error": group.iloc[i]["error_code"],
                    "to_error": group.iloc[i + 1]["error_code"]
                })

    esc_df = pd.DataFrame(escalations)
    if not esc_df.empty:
        print(f"   Severity escalations detected: {len(esc_df)}")
        esc_summary = esc_df.groupby(["from_severity", "to_severity"]).size().reset_index(name="count")
        esc_summary = esc_summary.sort_values("count", ascending=False)
        print(f"   Top escalation paths:")
        for _, row in esc_summary.head(5).iterrows():
            print(f"     {row['from_severity']} -> {row['to_severity']}: {row['count']} times")

        esc_summary.to_csv(os.path.join(ARTIFACTS_DIR, "severity_escalations.csv"), index=False)

    return esc_df


def main():
    print("=" * 60)
    print("  PS-2: ERROR PATTERN RECOGNITION")
    print("  Models: Association Rules (Apriori), Markov Chain")
    print("=" * 60)

    # Setup MLflow
    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    os.makedirs(os.path.join(BASE_DIR, "mlruns"), exist_ok=True)
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("PS2_Error_Pattern_Recognition")

    errors = load_error_data()

    with mlflow.start_run(run_name="PS2_Error_Patterns"):
        # Association Rules
        rules = run_association_rules(errors)
        if not rules.empty:
            mlflow.log_metric("num_association_rules", len(rules))
            mlflow.log_metric("max_lift", float(rules["lift"].max()))
            mlflow.log_metric("avg_confidence", float(rules["confidence"].mean()))
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, "association_rules.csv"))
            if os.path.exists(os.path.join(ARTIFACTS_DIR, "association_rules_plot.png")):
                mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, "association_rules_plot.png"))

        # Markov Chain
        tm_df, transitions_df, stationary_df = run_markov_chain(errors)
        mlflow.log_metric("num_error_states", len(tm_df))
        mlflow.log_metric("num_significant_transitions", len(transitions_df))
        mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, "markov_heatmap.png"))
        mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, "transition_matrix.csv"))

        # Severity escalation
        esc_df = analyze_severity_escalation(errors)
        if not esc_df.empty:
            mlflow.log_metric("total_escalations", len(esc_df))

        mlflow.log_params({
            "problem_statement": "PS-2 Error Pattern Recognition",
            "total_error_records": len(errors),
            "unique_error_codes": int(errors["error_code"].nunique()),
            "unique_devices": int(errors["device_id"].nunique())
        })

    print("\n  PS-2 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
