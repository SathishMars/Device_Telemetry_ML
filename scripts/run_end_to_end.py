"""
============================================================
END-TO-END ORCHESTRATOR
============================================================
Runs full pipeline + incremental daily processing.
============================================================
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    print("=" * 60)
    print("  END-TO-END ORCHESTRATOR")
    print("=" * 60)

    # Step 1: Run full pipeline
    print("\n[PHASE 1] Full pipeline execution...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "run_pipeline.py")], cwd=BASE_DIR)

    # Step 2: Run incremental daily processing
    print("\n[PHASE 2] Incremental daily processing...")
    subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "scripts", "run_incremental_daily.py")],
        cwd=BASE_DIR
    )

    print("\n" + "=" * 60)
    print("  END-TO-END EXECUTION COMPLETE")
    print("=" * 60)
    print("  Next:")
    print("    mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000")
    print("    python api/main.py")
    print("    cd monitoring && docker compose up -d")
    print("=" * 60)


if __name__ == "__main__":
    main()
