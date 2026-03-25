"""
============================================================
DAILY SCHEDULED PIPELINE (Runs at 6 AM)
============================================================
Processes new incremental data arriving daily (~500 records)
with Watermark tracking and Change Data Capture (CDC):

  1. Watermark check — identify unprocessed data
  2. CDC — detect inserts, updates, deletes
  3. Ingest new/changed data → Bronze
  4. Clean → Silver
  5. Engineer features → Gold
  6. ALL 5 PS predictions on new data:
     - PS-1: Failure probability per device
     - PS-2: Error pattern update (Apriori + Markov)
     - PS-3: Root cause explanation (SHAP for today's predictions)
     - PS-4: Anomaly detection per device
     - PS-5: SLA risk score + RUL update
  7. Check drift (compare new vs reference)
  8. Every 15 days: retrain models with accumulated data

Usage:
  python scripts/daily_scheduled_pipeline.py              # Run for today
  python scripts/daily_scheduled_pipeline.py --date 2025-02-01
  python scripts/daily_scheduled_pipeline.py --force-retrain
============================================================
"""

import os
import sys
import json
import time
import hashlib
import argparse
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import mlflow

# Directories
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
FEATURE_STORE_DIR = os.path.join(BASE_DIR, "data", "feature_store")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts")
PREDICTIONS_DIR = os.path.join(BASE_DIR, "data", "predictions")
DRIFT_DIR = os.path.join(BASE_DIR, "data", "drift_reports")
WATERMARK_FILE = os.path.join(BASE_DIR, "data", "watermark.json")
CDC_LOG_FILE = os.path.join(BASE_DIR, "data", "cdc_log.json")
TRAINING_LOG = os.path.join(BASE_DIR, "data", "training_log.json")

for d in [PREDICTIONS_DIR, DRIFT_DIR]:
    os.makedirs(d, exist_ok=True)

# Config
RETRAIN_INTERVAL_DAYS = 15
DRIFT_THRESHOLD = 0.30
EXPECTED_DAILY_RECORDS = 500


# ═══════════════════════════════════════════════════════════
# WATERMARK — Tracks what data has been processed
# ═══════════════════════════════════════════════════════════

def load_watermark():
    """
    Watermark = a bookmark of the LAST processed state.
    Prevents re-processing data that was already ingested.

    Example watermark.json:
    {
      "telemetry": {"last_date": "2025-01-15", "last_row_count": 3000, "last_hash": "abc123"},
      "error_logs": {"last_date": "2025-01-15", "last_row_count": 450, "last_hash": "def456"}
    }
    """
    if os.path.exists(WATERMARK_FILE):
        with open(WATERMARK_FILE) as f:
            return json.load(f)
    return {}


def save_watermark(watermark):
    with open(WATERMARK_FILE, "w") as f:
        json.dump(watermark, f, indent=2)


def compute_data_hash(df):
    """Compute hash of dataframe to detect changes."""
    content = pd.util.hash_pandas_object(df).values.tobytes()
    return hashlib.md5(content).hexdigest()


# ═══════════════════════════════════════════════════════════
# CDC — Change Data Capture (detect inserts/updates/deletes)
# ═══════════════════════════════════════════════════════════

def detect_changes(table_name, new_df, key_columns=None):
    """
    CDC: Compare new data against existing Silver layer
    to identify:
      - INSERTS: New records (key not in Silver)
      - UPDATES: Changed records (key exists, values differ)
      - DELETES: Removed records (key in Silver, not in new)

    Returns dict with insert/update/delete dataframes.
    """
    silver_path = os.path.join(SILVER_DIR, f"{table_name}.parquet")

    if not os.path.exists(silver_path):
        # No existing data — everything is an INSERT
        return {
            "inserts": new_df,
            "updates": pd.DataFrame(),
            "deletes": pd.DataFrame(),
            "summary": f"First load: {len(new_df)} inserts"
        }

    existing_df = pd.read_parquet(silver_path)

    if key_columns is None:
        key_columns = ["device_id", "date"] if "date" in new_df.columns else ["device_id"]

    # Ensure key columns exist
    available_keys = [k for k in key_columns if k in new_df.columns and k in existing_df.columns]
    if not available_keys:
        return {
            "inserts": new_df,
            "updates": pd.DataFrame(),
            "deletes": pd.DataFrame(),
            "summary": f"No key columns found, treating all {len(new_df)} as inserts"
        }

    # Create composite key for comparison
    new_df = new_df.copy()
    existing_df = existing_df.copy()
    new_df["_cdc_key"] = new_df[available_keys].astype(str).agg("||".join, axis=1)
    existing_df["_cdc_key"] = existing_df[available_keys].astype(str).agg("||".join, axis=1)

    existing_keys = set(existing_df["_cdc_key"])
    new_keys = set(new_df["_cdc_key"])

    # INSERTS: keys in new but not in existing
    insert_keys = new_keys - existing_keys
    inserts = new_df[new_df["_cdc_key"].isin(insert_keys)].drop(columns=["_cdc_key"])

    # UPDATES: keys in both, but values changed (compare hash of non-key columns)
    common_keys = new_keys & existing_keys
    updates = pd.DataFrame()
    if common_keys:
        new_common = new_df[new_df["_cdc_key"].isin(common_keys)].copy()
        existing_common = existing_df[existing_df["_cdc_key"].isin(common_keys)].copy()

        # Compare value columns (exclude metadata)
        value_cols = [c for c in new_common.columns
                      if c not in available_keys + ["_cdc_key", "_ingested_at", "_source_file"]]

        if value_cols:
            new_vals = new_common.set_index("_cdc_key")[value_cols].fillna(0)
            existing_vals = existing_common.set_index("_cdc_key")[value_cols].fillna(0)

            # Find rows where values differ
            common_idx = new_vals.index.intersection(existing_vals.index)
            if len(common_idx) > 0:
                diff_mask = (new_vals.loc[common_idx] != existing_vals.loc[common_idx]).any(axis=1)
                updated_keys = diff_mask[diff_mask].index
                updates = new_common[new_common["_cdc_key"].isin(updated_keys)].drop(columns=["_cdc_key"])

    # DELETES: keys in existing but not in new (for this date only)
    delete_keys = existing_keys - new_keys
    deletes = existing_df[existing_df["_cdc_key"].isin(delete_keys)].drop(columns=["_cdc_key"])

    summary = f"INS:{len(inserts)} UPD:{len(updates)} DEL:{len(deletes)}"

    return {
        "inserts": inserts,
        "updates": updates,
        "deletes": deletes,
        "summary": summary
    }


def log_cdc_event(table_name, target_date, changes):
    """Log CDC events for audit trail."""
    log = []
    if os.path.exists(CDC_LOG_FILE):
        with open(CDC_LOG_FILE) as f:
            log = json.load(f)

    log.append({
        "table": table_name,
        "date": target_date,
        "inserts": len(changes["inserts"]),
        "updates": len(changes["updates"]),
        "deletes": len(changes["deletes"]),
        "timestamp": datetime.now().isoformat()
    })

    # Keep last 90 days of CDC log
    log = log[-90:]

    with open(CDC_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


# ═══════════════════════════════════════════════════════════
# TRAINING LOG
# ═══════════════════════════════════════════════════════════

def get_last_retrain_date():
    if os.path.exists(TRAINING_LOG):
        with open(TRAINING_LOG) as f:
            return json.load(f).get("last_retrain_date", None)
    return None


def update_training_log(retrain_date, reason):
    log = {}
    if os.path.exists(TRAINING_LOG):
        with open(TRAINING_LOG) as f:
            log = json.load(f)

    history = log.get("retrain_history", [])
    history.append({"date": retrain_date, "reason": reason, "timestamp": datetime.now().isoformat()})
    log.update({"last_retrain_date": retrain_date, "retrain_history": history, "total_retrains": len(history)})

    with open(TRAINING_LOG, "w") as f:
        json.dump(log, f, indent=2)


def should_retrain(current_date, force=False):
    if force:
        return True, "Forced retraining"

    last_retrain = get_last_retrain_date()
    if last_retrain is None:
        return True, "First training (no previous record)"

    days_since = (pd.to_datetime(current_date) - pd.to_datetime(last_retrain)).days
    if days_since >= RETRAIN_INTERVAL_DAYS:
        return True, f"Scheduled retrain ({days_since} days since last)"

    drift_path = os.path.join(DRIFT_DIR, "drift_decision.json")
    if os.path.exists(drift_path):
        with open(drift_path) as f:
            drift = json.load(f)
        if drift.get("should_retrain", False):
            return True, f"Drift detected ({drift.get('drift_share', 0)*100:.1f}% > {DRIFT_THRESHOLD*100:.0f}%)"

    return False, f"Not due ({days_since}/{RETRAIN_INTERVAL_DAYS} days, no drift)"


# ═══════════════════════════════════════════════════════════
# STEP 1: Watermark Check + Bronze Ingestion
# ═══════════════════════════════════════════════════════════

def step1_watermark_and_ingest(target_date):
    """Check watermark, detect new data, ingest to Bronze."""
    print(f"\n   [Step 1] Watermark Check + Bronze Ingestion — {target_date}")

    watermark = load_watermark()
    total_ingested = 0

    for table, date_col in [("telemetry", "date"), ("error_logs", "timestamp")]:
        csv_path = os.path.join(RAW_DIR, f"{table}.csv")
        if not os.path.exists(csv_path):
            continue

        df = pd.read_csv(csv_path)

        # Watermark check: only process data AFTER the last processed date
        table_wm = watermark.get(table, {})
        last_processed = table_wm.get("last_date", None)

        if date_col and date_col in df.columns:
            new_data = df[df[date_col] == target_date]
        else:
            new_data = df

        if new_data.empty:
            print(f"   [{table}] No new data for {target_date}")
            continue

        # Check if this date was already processed (watermark)
        if last_processed and last_processed >= target_date:
            data_hash = compute_data_hash(new_data)
            if data_hash == table_wm.get("last_hash"):
                print(f"   [{table}] Already processed (watermark match) — skipping")
                continue
            else:
                print(f"   [{table}] Data changed since last run (CDC detected)")

        # Save to Bronze (date-partitioned)
        new_data = new_data.copy()
        new_data["_ingested_at"] = datetime.now().isoformat()
        new_data["_source_file"] = f"{table}.csv"

        table_dir = os.path.join(BRONZE_DIR, table)
        os.makedirs(table_dir, exist_ok=True)
        date_str = target_date.replace("-", "")
        new_data.to_parquet(os.path.join(table_dir, f"data_{date_str}.parquet"), index=False)

        total_ingested += len(new_data)
        print(f"   [{table}] {len(new_data)} records → Bronze")

        # Update watermark
        watermark[table] = {
            "last_date": target_date,
            "last_row_count": len(new_data),
            "last_hash": compute_data_hash(new_data),
            "updated_at": datetime.now().isoformat()
        }

    save_watermark(watermark)
    print(f"   Total ingested: {total_ingested} | Watermark updated")
    return total_ingested


# ═══════════════════════════════════════════════════════════
# STEP 2: CDC + Silver Cleaning
# ═══════════════════════════════════════════════════════════

def step2_cdc_and_clean(target_date):
    """Detect changes (CDC) and merge into Silver."""
    print(f"\n   [Step 2] CDC + Silver Cleaning — {target_date}")

    telemetry_dir = os.path.join(BRONZE_DIR, "telemetry")
    if not os.path.exists(telemetry_dir):
        print("   [SKIP] No bronze telemetry data")
        return None

    date_str = target_date.replace("-", "")
    parquet_path = os.path.join(telemetry_dir, f"data_{date_str}.parquet")

    if not os.path.exists(parquet_path):
        print(f"   [SKIP] No bronze file for {target_date}")
        return None

    new_data = pd.read_parquet(parquet_path)

    # Basic cleaning
    new_data = new_data.drop_duplicates()
    for col in new_data.select_dtypes(include=[np.number]).columns:
        new_data[col] = new_data[col].fillna(new_data[col].median())

    # Range validation
    if "tap_success_rate" in new_data.columns:
        new_data["tap_success_rate"] = new_data["tap_success_rate"].clip(0, 1.0)
    if "signal_strength_dbm" in new_data.columns:
        new_data["signal_strength_dbm"] = new_data["signal_strength_dbm"].clip(0, 100)
    if "temperature_c" in new_data.columns:
        new_data["temperature_c"] = new_data["temperature_c"].clip(-10, 80)

    # CDC: Detect changes against existing Silver
    changes = detect_changes("telemetry", new_data, key_columns=["device_id", "date"])
    log_cdc_event("telemetry", target_date, changes)
    print(f"   CDC: {changes['summary']}")

    # Merge into Silver (apply inserts + updates)
    silver_path = os.path.join(SILVER_DIR, "telemetry.parquet")
    os.makedirs(SILVER_DIR, exist_ok=True)

    if os.path.exists(silver_path):
        existing = pd.read_parquet(silver_path)

        # Remove updated/deleted rows from existing
        if not changes["updates"].empty or not changes["deletes"].empty:
            keys_to_remove = pd.concat([changes["updates"], changes["deletes"]])
            if "device_id" in keys_to_remove.columns and "date" in keys_to_remove.columns:
                remove_keys = set(keys_to_remove["device_id"].astype(str) + "||" +
                                  keys_to_remove["date"].astype(str))
                existing_keys = existing["device_id"].astype(str) + "||" + existing["date"].astype(str)
                existing = existing[~existing_keys.isin(remove_keys)]

        # Append inserts + updates
        to_add = pd.concat([changes["inserts"], changes["updates"]], ignore_index=True)
        df = pd.concat([existing, to_add], ignore_index=True).drop_duplicates()
    else:
        df = new_data

    df.to_parquet(silver_path, index=False)
    print(f"   Silver total: {len(df)} records")
    return df


# ═══════════════════════════════════════════════════════════
# STEP 3: Gold Feature Engineering
# ═══════════════════════════════════════════════════════════

def step3_feature_engineering(target_date):
    """Engineer features on accumulated data."""
    print(f"\n   [Step 3] Gold Feature Engineering — {target_date}")

    silver_path = os.path.join(SILVER_DIR, "telemetry.parquet")
    if not os.path.exists(silver_path):
        print("   [SKIP] No silver data")
        return None

    df = pd.read_parquet(silver_path)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        cutoff = pd.to_datetime(target_date) - timedelta(days=30)
        df = df[df["date"] >= cutoff]

    print(f"   Computing features on {len(df)} records")

    # Rolling features (7-day window)
    rolling_cols = ["signal_strength_dbm", "temperature_c", "error_count", "response_time_ms"]
    if "device_id" in df.columns and "date" in df.columns:
        df = df.sort_values(["device_id", "date"])
        for col in rolling_cols:
            if col in df.columns:
                df[f"{col}_7d_mean"] = df.groupby("device_id")[col].transform(
                    lambda x: x.rolling(7, min_periods=1).mean())
                df[f"{col}_7d_std"] = df.groupby("device_id")[col].transform(
                    lambda x: x.rolling(7, min_periods=1).std().fillna(0))
                df[f"{col}_delta"] = df.groupby("device_id")[col].diff().fillna(0)

        if "error_count" in df.columns:
            df["cumulative_errors"] = df.groupby("device_id")["error_count"].cumsum()
        if "reboot_count" in df.columns:
            df["cumulative_reboots"] = df.groupby("device_id")["reboot_count"].cumsum()

    # Health score
    required = ["tap_success_rate", "signal_strength_dbm", "memory_usage_pct",
                 "cpu_usage_pct", "uptime_hours", "error_count"]
    if all(c in df.columns for c in required):
        df["health_score"] = (
            df["tap_success_rate"] * 30 +
            (df["signal_strength_dbm"].clip(0, 100) / 100) * 20 +
            (1 - df["memory_usage_pct"] / 100) * 15 +
            (1 - df["cpu_usage_pct"] / 100) * 15 +
            (df["uptime_hours"].clip(0, 24) / 24) * 10 +
            (1 - df["error_count"].clip(0, 10) / 10) * 10
        )

    gold_path = os.path.join(GOLD_DIR, "device_features.parquet")
    os.makedirs(GOLD_DIR, exist_ok=True)
    df.to_parquet(gold_path, index=False)

    fs_path = os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet")
    os.makedirs(FEATURE_STORE_DIR, exist_ok=True)
    df.to_parquet(fs_path, index=False)

    print(f"   Gold: {len(df)} records, {len(df.columns)} columns")
    return df


# ═══════════════════════════════════════════════════════════
# STEP 4: ALL 5 PS Predictions
# ═══════════════════════════════════════════════════════════

def step4_all_predictions(target_date):
    """Run ALL 5 problem statement predictions on today's data."""
    print(f"\n   [Step 4] All 5 PS Predictions — {target_date}")

    import joblib

    gold_path = os.path.join(GOLD_DIR, "device_features.parquet")
    if not os.path.exists(gold_path):
        print("   [SKIP] No gold features")
        return None

    df = pd.read_parquet(gold_path)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        today_df = df[df["date"] == target_date].copy()
    else:
        today_df = df.tail(EXPECTED_DAILY_RECORDS).copy()

    if today_df.empty:
        print("   [SKIP] No data for today")
        return None

    results = {}

    # ── PS-1: Failure Prediction ─────────────────────────
    ps1_path = os.path.join(ARTIFACTS_DIR, "ps1", "champion_model.pkl")
    if os.path.exists(ps1_path):
        model = joblib.load(ps1_path)
        feature_cols = [c for c in model.feature_names_in_ if c in today_df.columns] \
            if hasattr(model, "feature_names_in_") else []

        if feature_cols:
            X = today_df[feature_cols].fillna(0)
            probs = model.predict_proba(X)[:, 1]
            today_df["failure_probability"] = probs
            today_df["failure_risk_tier"] = pd.cut(
                probs, bins=[-0.01, 0.2, 0.4, 0.7, 1.01],
                labels=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
            n_high = (probs >= 0.4).sum()
            results["ps1_high_risk"] = int(n_high)
            print(f"   PS-1 Failure:  {len(today_df)} devices | {n_high} HIGH/CRITICAL")

    # ── PS-2: Error Pattern Recognition ──────────────────
    error_csv = os.path.join(RAW_DIR, "error_logs.csv")
    if os.path.exists(error_csv):
        errors = pd.read_csv(error_csv)
        if "timestamp" in errors.columns:
            errors["date"] = pd.to_datetime(errors["timestamp"]).dt.strftime("%Y-%m-%d")
            today_errors = errors[errors["date"] == target_date]
        else:
            today_errors = errors.tail(100)

        if not today_errors.empty and "error_code" in today_errors.columns:
            # Apriori: Find co-occurring errors per device today
            if "device_id" in today_errors.columns:
                device_errors = today_errors.groupby("device_id")["error_code"].apply(list)
                co_occurrences = {}
                for device_id, error_list in device_errors.items():
                    unique_errors = list(set(error_list))
                    for i in range(len(unique_errors)):
                        for j in range(i + 1, len(unique_errors)):
                            pair = tuple(sorted([unique_errors[i], unique_errors[j]]))
                            co_occurrences[pair] = co_occurrences.get(pair, 0) + 1

                top_pairs = sorted(co_occurrences.items(), key=lambda x: -x[1])[:5]
                results["ps2_top_error_pairs"] = [
                    {"errors": list(k), "count": v} for k, v in top_pairs
                ]

            # Markov: Transition probabilities for today's error sequences
            if "severity" in today_errors.columns:
                transitions = today_errors.groupby("device_id")["severity"].apply(list)
                escalations = 0
                for seq in transitions:
                    for i in range(len(seq) - 1):
                        sev_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
                        if sev_order.get(seq[i + 1], 0) > sev_order.get(seq[i], 0):
                            escalations += 1
                results["ps2_escalations"] = escalations

            n_errors = len(today_errors)
            n_devices = today_errors["device_id"].nunique() if "device_id" in today_errors.columns else 0
            print(f"   PS-2 Patterns: {n_errors} errors across {n_devices} devices | "
                  f"{results.get('ps2_escalations', 0)} escalations")
        else:
            print(f"   PS-2 Patterns: No errors today")
    else:
        print(f"   PS-2 Patterns: [SKIP] No error_logs.csv")

    # ── PS-3: Root Cause Analysis (SHAP on today's predictions) ──
    if "failure_probability" in today_df.columns and os.path.exists(ps1_path):
        try:
            import shap
            model = joblib.load(ps1_path)
            feature_cols = [c for c in model.feature_names_in_ if c in today_df.columns] \
                if hasattr(model, "feature_names_in_") else []

            if feature_cols:
                X = today_df[feature_cols].fillna(0)
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(X)

                # Handle binary classification SHAP output
                if isinstance(shap_values, list):
                    shap_values = shap_values[1]

                # Global importance for today
                mean_abs_shap = np.abs(shap_values).mean(axis=0)
                top_features = sorted(zip(feature_cols, mean_abs_shap),
                                      key=lambda x: -x[1])[:10]
                results["ps3_top_causes"] = [
                    {"feature": f, "importance": round(float(v), 4)} for f, v in top_features
                ]

                # Local explanation for highest risk device
                high_risk = today_df[today_df["failure_probability"] ==
                                     today_df["failure_probability"].max()]
                if not high_risk.empty:
                    idx = high_risk.index[0] - today_df.index[0]
                    if 0 <= idx < len(shap_values):
                        device_shap = sorted(
                            zip(feature_cols, shap_values[idx]),
                            key=lambda x: -abs(x[1]))[:5]
                        results["ps3_worst_device"] = {
                            "device_id": str(high_risk["device_id"].values[0])
                            if "device_id" in high_risk.columns else "unknown",
                            "failure_prob": round(float(high_risk["failure_probability"].values[0]), 4),
                            "top_causes": [{"feature": f, "shap_value": round(float(v), 4)}
                                           for f, v in device_shap]
                        }

                print(f"   PS-3 Root Cause: Top driver = {top_features[0][0]} "
                      f"(SHAP={top_features[0][1]:.3f})")
        except Exception as e:
            print(f"   PS-3 Root Cause: [WARN] {e}")
    else:
        print(f"   PS-3 Root Cause: [SKIP] No failure predictions to explain")

    # ── PS-4: Anomaly Detection ──────────────────────────
    ps4_path = os.path.join(ARTIFACTS_DIR, "ps4", "isolation_forest_model.pkl")
    if os.path.exists(ps4_path):
        model_data = joblib.load(ps4_path)
        iso_model = model_data["model"]
        scaler = model_data["scaler"]
        iso_features = model_data.get("features", [])
        available = [c for c in iso_features if c in today_df.columns]

        if available:
            X = today_df[available].fillna(0)
            X_scaled = scaler.transform(X)
            today_df["anomaly_label"] = iso_model.predict(X_scaled)
            today_df["anomaly_score"] = iso_model.decision_function(X_scaled)
            n_anomaly = (today_df["anomaly_label"] == -1).sum()
            results["ps4_anomalies"] = int(n_anomaly)

            # SPC check: flag features outside 3-sigma
            spc_path = os.path.join(ARTIFACTS_DIR, "ps4", "spc_limits.json")
            spc_violations = 0
            if os.path.exists(spc_path):
                with open(spc_path) as f:
                    spc_limits = json.load(f)
                for feat, limits in spc_limits.items():
                    if feat in today_df.columns:
                        ucl = limits.get("ucl", float("inf"))
                        lcl = limits.get("lcl", float("-inf"))
                        violations = ((today_df[feat] > ucl) | (today_df[feat] < lcl)).sum()
                        spc_violations += int(violations)
            results["ps4_spc_violations"] = spc_violations

            print(f"   PS-4 Anomaly:  {n_anomaly}/{len(today_df)} anomalies "
                  f"({n_anomaly/len(today_df)*100:.1f}%) | {spc_violations} SPC violations")

    # ── PS-5: SLA Risk + RUL ─────────────────────────────
    rul_path = os.path.join(ARTIFACTS_DIR, "ps5", "rul_estimates.csv")
    if os.path.exists(rul_path) and "device_id" in today_df.columns:
        rul_df = pd.read_csv(rul_path)
        today_df = today_df.merge(
            rul_df[["device_id", "rul_median_days", "risk_tier", "sla_risk_score"]].rename(
                columns={"risk_tier": "sla_risk_tier"}),
            on="device_id", how="left")

        n_critical = (today_df.get("sla_risk_tier", pd.Series()) == "CRITICAL").sum()
        n_high = (today_df.get("sla_risk_tier", pd.Series()) == "HIGH").sum()
        avg_rul = today_df["rul_median_days"].mean() if "rul_median_days" in today_df.columns else 0
        results["ps5_critical"] = int(n_critical)
        results["ps5_high"] = int(n_high)
        results["ps5_avg_rul"] = round(float(avg_rul), 1)
        print(f"   PS-5 SLA Risk: {n_critical} CRITICAL, {n_high} HIGH | Avg RUL={avg_rul:.0f} days")

    # ── Save All Predictions ─────────────────────────────
    pred_path = os.path.join(PREDICTIONS_DIR, f"predictions_{target_date.replace('-', '')}.parquet")
    today_df.to_parquet(pred_path, index=False)

    # Save readable CSV
    csv_cols = ["device_id"]
    for col in ["failure_probability", "failure_risk_tier", "anomaly_label", "anomaly_score",
                 "rul_median_days", "sla_risk_tier", "sla_risk_score"]:
        if col in today_df.columns:
            csv_cols.append(col)
    latest_csv = os.path.join(PREDICTIONS_DIR, "latest_predictions.csv")
    today_df[csv_cols].to_csv(latest_csv, index=False)

    # Save PS results summary
    results_path = os.path.join(PREDICTIONS_DIR, f"ps_results_{target_date.replace('-', '')}.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n   All predictions saved: {pred_path}")
    return today_df, results


# ═══════════════════════════════════════════════════════════
# STEP 5: Drift Check
# ═══════════════════════════════════════════════════════════

def step5_drift_check():
    """Check if data has drifted from training distribution."""
    print(f"\n   [Step 5] Drift Detection")

    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset

        fs_path = os.path.join(FEATURE_STORE_DIR, "device_telemetry_features.parquet")
        if not os.path.exists(fs_path):
            print("   [SKIP] No feature store data")
            return 0.0

        df = pd.read_parquet(fs_path)
        numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c != "device_id"]

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            dates = sorted(df["date"].unique())
            if len(dates) < 10:
                print("   [SKIP] Not enough dates for drift detection")
                return 0.0
            split = dates[int(len(dates) * 0.7)]
            reference = df[df["date"] < split][numeric_cols]
            current = df[df["date"] >= split][numeric_cols]
        else:
            split_idx = int(len(df) * 0.7)
            reference = df.iloc[:split_idx][numeric_cols]
            current = df.iloc[split_idx:][numeric_cols]

        drift_report = Report(metrics=[DataDriftPreset()])
        snapshot = drift_report.run(reference_data=reference, current_data=current)

        html_path = os.path.join(DRIFT_DIR, "data_drift_daily.html")
        snapshot.save_html(html_path)

        report_dict = snapshot.dict()
        drift_share = 0.0
        for metric in report_dict.get("metrics", []):
            if "DriftedColumnsCount" in metric.get("metric_name", ""):
                value = metric.get("value", {})
                if isinstance(value, dict):
                    drift_share = float(value.get("share", 0))
                break

        if drift_share == 0:
            drifted = total = 0
            for metric in report_dict.get("metrics", []):
                if "ValueDrift" in metric.get("metric_name", ""):
                    total += 1
                    val = metric.get("value", 1)
                    threshold = metric.get("config", {}).get("threshold", 0.05)
                    if isinstance(val, (int, float)) and val < threshold:
                        drifted += 1
            if total > 0:
                drift_share = drifted / total

        decision = {
            "should_retrain": drift_share > DRIFT_THRESHOLD,
            "drift_share": round(drift_share, 4),
            "threshold": DRIFT_THRESHOLD,
            "checked_at": datetime.now().isoformat()
        }
        with open(os.path.join(DRIFT_DIR, "drift_decision.json"), "w") as f:
            json.dump(decision, f, indent=2)

        print(f"   Drift share: {drift_share*100:.1f}% ({'RETRAIN NEEDED' if decision['should_retrain'] else 'OK'})")
        return drift_share

    except Exception as e:
        print(f"   [WARN] Drift check failed: {e}")
        return 0.0


# ═══════════════════════════════════════════════════════════
# STEP 6: Retrain (every 15 days or on drift)
# ═══════════════════════════════════════════════════════════

def step6_retrain(current_date, reason):
    """Retrain all models with accumulated data."""
    print(f"\n   [Step 6] RETRAINING ALL MODELS")
    print(f"   Reason: {reason}")

    import subprocess

    scripts = [
        ("PS-1: Failure Prediction", "notebooks/05_ps1_failure_prediction.py"),
        ("PS-2: Error Patterns", "notebooks/06_ps2_error_pattern.py"),
        ("PS-3: Root Cause", "notebooks/07_ps3_root_cause.py"),
        ("PS-4: Anomaly Detection", "notebooks/08_ps4_anomaly_detection.py"),
        ("PS-5: SLA Risk", "notebooks/09_ps5_sla_risk.py"),
    ]

    for name, script in scripts:
        print(f"\n   Retraining {name}...")
        result = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, script)],
            capture_output=True, text=True, cwd=BASE_DIR)
        if result.returncode == 0:
            print(f"   [OK] {name}")
        else:
            print(f"   [FAIL] {name}: {result.stderr[-200:] if result.stderr else 'unknown'}")

    # Register models
    print(f"\n   Registering models...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "scripts", "register_models.py")],
                   capture_output=True, cwd=BASE_DIR)

    update_training_log(current_date, reason)
    print(f"\n   [OK] Retraining complete. Next scheduled: +{RETRAIN_INTERVAL_DAYS} days")


# ═══════════════════════════════════════════════════════════
# STEP 7: Log to MLflow
# ═══════════════════════════════════════════════════════════

def step7_log_metrics(target_date, stats):
    """Log daily pipeline metrics to MLflow."""
    print(f"\n   [Step 7] Logging to MLflow")

    mlflow_uri = f"sqlite:///{os.path.join(BASE_DIR, 'mlruns', 'mlflow.db')}"
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("Daily_Pipeline")

    with mlflow.start_run(run_name=f"daily_{target_date}"):
        mlflow.log_param("date", target_date)
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                mlflow.log_metric(key, value)

    print(f"   [OK] Logged to 'Daily_Pipeline' experiment")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Daily Scheduled Pipeline")
    parser.add_argument("--date", type=str, default=None, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--force-retrain", action="store_true", help="Force model retraining")
    args = parser.parse_args()

    target_date = args.date or datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"  DAILY PIPELINE — {target_date}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    stats = {}
    start_time = time.time()

    # Step 1: Watermark + Bronze
    records = step1_watermark_and_ingest(target_date)
    stats["records_ingested"] = records or 0

    # Step 2: CDC + Silver
    step2_cdc_and_clean(target_date)

    # Step 3: Gold features
    step3_feature_engineering(target_date)

    # Step 4: All 5 PS predictions
    result = step4_all_predictions(target_date)
    if result:
        today_df, ps_results = result
        stats["predictions_made"] = len(today_df)
        stats.update({k: v for k, v in ps_results.items() if isinstance(v, (int, float))})

    # Step 5: Drift check
    stats["drift_share"] = step5_drift_check()

    # Step 6: Retrain check
    retrain_needed, reason = should_retrain(target_date, force=args.force_retrain)
    stats["retrained"] = int(retrain_needed)
    if retrain_needed:
        step6_retrain(target_date, reason)
    else:
        print(f"\n   [Step 6] No retraining needed: {reason}")

    # Step 7: Log to MLflow
    stats["pipeline_duration_seconds"] = round(time.time() - start_time, 1)
    step7_log_metrics(target_date, stats)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  DAILY PIPELINE COMPLETE — {target_date}")
    print(f"{'─' * 60}")
    print(f"  Duration:        {stats['pipeline_duration_seconds']}s")
    print(f"  Records ingested:{stats.get('records_ingested', 0)}")
    print(f"  Predictions:     {stats.get('predictions_made', 0)}")
    print(f"  PS-1 High Risk:  {stats.get('ps1_high_risk', 0)}")
    print(f"  PS-2 Escalations:{stats.get('ps2_escalations', 0)}")
    print(f"  PS-4 Anomalies:  {stats.get('ps4_anomalies', 0)}")
    print(f"  PS-5 Critical:   {stats.get('ps5_critical', 0)}")
    print(f"  Drift share:     {stats.get('drift_share', 0)*100:.1f}%")
    print(f"  Retrained:       {'YES' if retrain_needed else 'NO'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
