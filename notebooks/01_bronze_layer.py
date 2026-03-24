"""
============================================================
BRONZE LAYER - Raw Data Ingestion
============================================================
Ingests CSV files from data/raw/ into Parquet format
with metadata (immutable audit layer).

Supports incremental ingestion: processes only new dates
not already in bronze layer.
============================================================
"""

import os
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")


def ingest_table(table_name, date_col=None):
    """Ingest a CSV into Bronze as Parquet with metadata."""
    csv_path = os.path.join(RAW_DIR, f"{table_name}.csv")
    if not os.path.exists(csv_path):
        print(f"   [SKIP] {csv_path} not found")
        return None

    df = pd.read_csv(csv_path)

    # Add ingestion metadata
    df["_ingested_at"] = datetime.now().isoformat()
    df["_source_file"] = f"{table_name}.csv"
    df["_row_count"] = len(df)

    # Save as partitioned parquet
    table_dir = os.path.join(BRONZE_DIR, table_name)
    os.makedirs(table_dir, exist_ok=True)

    if date_col and date_col in df.columns:
        # Partition by date for incremental processing
        for date_val, group in df.groupby(date_col):
            date_str = str(date_val).replace("-", "")
            out_path = os.path.join(table_dir, f"data_{date_str}.parquet")
            group.to_parquet(out_path, index=False, engine="pyarrow")
    else:
        out_path = os.path.join(table_dir, f"data_{datetime.now().strftime('%Y%m%d')}.parquet")
        df.to_parquet(out_path, index=False, engine="pyarrow")

    print(f"   [OK] {table_name}: {len(df)} rows -> {table_dir}")
    return df


def ingest_incremental(table_name, date_col, target_date=None):
    """Ingest only new data for a specific date (incremental mode)."""
    csv_path = os.path.join(RAW_DIR, f"{table_name}.csv")
    if not os.path.exists(csv_path):
        return None

    df = pd.read_csv(csv_path)

    if target_date and date_col:
        df = df[df[date_col] == target_date]
        if df.empty:
            print(f"   [SKIP] No data for {target_date} in {table_name}")
            return None

    df["_ingested_at"] = datetime.now().isoformat()
    df["_source_file"] = f"{table_name}.csv"

    table_dir = os.path.join(BRONZE_DIR, table_name)
    os.makedirs(table_dir, exist_ok=True)

    date_str = target_date.replace("-", "") if target_date else datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(table_dir, f"data_{date_str}.parquet")
    df.to_parquet(out_path, index=False, engine="pyarrow")
    print(f"   [OK] {table_name} ({target_date}): {len(df)} rows ingested")
    return df


def create_manifest():
    """Create ingestion manifest for audit trail."""
    manifest = {
        "ingestion_time": datetime.now().isoformat(),
        "tables": {}
    }
    for table in ["devices", "telemetry", "error_logs", "maintenance"]:
        table_dir = os.path.join(BRONZE_DIR, table)
        if os.path.exists(table_dir):
            files = [f for f in os.listdir(table_dir) if f.endswith(".parquet")]
            manifest["tables"][table] = {
                "file_count": len(files),
                "files": files
            }

    manifest_df = pd.DataFrame([
        {"table": k, "file_count": v["file_count"]}
        for k, v in manifest["tables"].items()
    ])
    manifest_df.to_csv(os.path.join(BRONZE_DIR, "manifest.csv"), index=False)
    print(f"\n   Manifest: {len(manifest['tables'])} tables cataloged")


def main():
    print("=" * 60)
    print("  BRONZE LAYER - Raw Data Ingestion")
    print("=" * 60)
    os.makedirs(BRONZE_DIR, exist_ok=True)

    ingest_table("devices")
    ingest_table("telemetry", date_col="date")
    ingest_table("error_logs")
    ingest_table("maintenance", date_col="date")

    create_manifest()
    print("\n  Bronze layer complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
