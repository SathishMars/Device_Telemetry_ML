"""
============================================================
MASTER PIPELINE - End-to-End Execution
============================================================
Runs the complete Device Telemetry ML pipeline:
  1. Generate sample data
  2. Bronze -> Silver -> Gold layers
  3. Feature Store
  4. PS-1 to PS-5 (all problem statements)
  5. Drift Detection
  6. Data Quality
  7. Start API (optional)
============================================================
"""

import os
import sys
import time
import subprocess
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def run_step(step_num, description, script_path):
    """Execute a pipeline step and report status."""
    print(f"\n{'='*60}")
    print(f"  STEP {step_num}: {description}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=BASE_DIR,
            capture_output=False,
            timeout=300  # 5 min timeout per step
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            print(f"\n  [OK] Step {step_num} completed in {elapsed:.1f}s")
            return True
        else:
            print(f"\n  [FAIL] Step {step_num} failed (exit code: {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        print(f"\n  [TIMEOUT] Step {step_num} exceeded 5 minute timeout")
        return False
    except Exception as e:
        print(f"\n  [ERROR] Step {step_num}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Device Telemetry ML Pipeline")
    parser.add_argument("--skip-data", action="store_true", help="Skip data generation")
    parser.add_argument("--skip-ml", action="store_true", help="Skip ML training")
    parser.add_argument("--start-api", action="store_true", help="Start API after pipeline")
    parser.add_argument("--ps", type=int, choices=[1,2,3,4,5], help="Run specific PS only")
    args = parser.parse_args()

    print("=" * 60)
    print("  DEVICE TELEMETRY ML PIPELINE")
    print("  London Metro Reader Monitoring System")
    print("=" * 60)

    pipeline_start = time.time()
    results = {}

    # ─── Data Pipeline ────────────────────────────────────
    if not args.skip_data:
        steps = [
            (1, "Generate Sample Data", os.path.join("data", "generate_sample_data.py")),
            (2, "Bronze Layer (Raw Ingestion)", os.path.join("notebooks", "01_bronze_layer.py")),
            (3, "Silver Layer (Cleaning)", os.path.join("notebooks", "02_silver_layer.py")),
            (4, "Gold Layer (Feature Engineering)", os.path.join("notebooks", "03_gold_layer.py")),
            (5, "Feature Store", os.path.join("notebooks", "04_feature_store.py")),
        ]

        for num, desc, script in steps:
            results[num] = run_step(num, desc, os.path.join(BASE_DIR, script))
            if not results[num]:
                print(f"\n  Pipeline stopped at step {num}. Fix the error and re-run.")
                sys.exit(1)

    # ─── ML Training ──────────────────────────────────────
    if not args.skip_ml:
        ml_steps = [
            (6, "PS-1: Failure Prediction (RF/XGBoost/CatBoost)", os.path.join("notebooks", "05_ps1_failure_prediction.py")),
            (7, "PS-2: Error Pattern Recognition (Apriori/Markov)", os.path.join("notebooks", "06_ps2_error_pattern.py")),
            (8, "PS-3: Root Cause Analysis (SHAP/Causal)", os.path.join("notebooks", "07_ps3_root_cause.py")),
            (9, "PS-4: Anomaly Detection (Isolation Forest/SPC)", os.path.join("notebooks", "08_ps4_anomaly_detection.py")),
            (10, "PS-5: SLA Risk Prediction (Weibull/Cox/RUL)", os.path.join("notebooks", "09_ps5_sla_risk.py")),
        ]

        if args.ps:
            ml_steps = [s for s in ml_steps if s[0] == args.ps + 5]

        for num, desc, script in ml_steps:
            results[num] = run_step(num, desc, os.path.join(BASE_DIR, script))

    # ─── Model Registration ─────────────────────────────
    if not args.skip_ml:
        results[11] = run_step(11, "Register Models (MLflow Registry)",
                               os.path.join(BASE_DIR, "scripts", "register_models.py"))

    # ─── Monitoring & Quality ─────────────────────────────
    monitor_steps = [
        (12, "Drift Detection (Evidently AI)", os.path.join("notebooks", "10_drift_detection.py")),
        (13, "Data Quality (Great Expectations)", os.path.join("scripts", "run_data_quality.py")),
    ]

    for num, desc, script in monitor_steps:
        results[num] = run_step(num, desc, os.path.join(BASE_DIR, script))

    # ─── Summary ──────────────────────────────────────────
    total_time = time.time() - pipeline_start
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Steps passed: {passed}/{len(results)}")
    print(f"  Steps failed: {failed}")
    print(f"  Total time:   {total_time:.1f}s ({total_time/60:.1f} min)")
    print()
    print(f"  Next steps:")
    print(f"    1. View MLflow UI:  mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000")
    print(f"    2. Start API:       python api/main.py")
    print(f"    3. Open Drift Reports: data/drift_reports/*.html")
    print(f"    4. Docker stack:    cd monitoring && docker compose up -d")
    print(f"{'='*60}")

    # ─── Start API (optional) ─────────────────────────────
    if args.start_api:
        print("\n  Starting API server...")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "api", "main.py")])


if __name__ == "__main__":
    main()
