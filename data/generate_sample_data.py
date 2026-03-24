"""
============================================================
Device Telemetry Sample Data Generator
London Metro Contactless Reader Monitoring System
============================================================
Generates realistic synthetic data for 200 reader devices
across 30 days (~1000+ telemetry records per day).

Tables Generated:
  1. devices.csv        - Device registry (200 devices)
  2. telemetry.csv      - Daily device telemetry (6000 records, 30 days)
  3. error_logs.csv     - Error/event logs (~1500 records)
  4. maintenance.csv    - Maintenance & SLA records (~400 records)
============================================================
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ─── Configuration ────────────────────────────────────────
np.random.seed(42)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
os.makedirs(RAW_DIR, exist_ok=True)

NUM_DEVICES = 200
NUM_DAYS = 30
START_DATE = datetime(2025, 1, 1)

# London Metro Stations
STATIONS = [
    "Kings Cross", "Victoria", "Waterloo", "Paddington", "Liverpool Street",
    "Bank", "Oxford Circus", "Canary Wharf", "Stratford", "Westminster",
    "Baker Street", "Euston", "London Bridge", "Brixton", "Camden Town",
    "Angel", "Clapham Common", "Hammersmith", "Shepherds Bush", "Finsbury Park"
]

GATE_TYPES = ["Entry", "Exit", "Wide_Entry", "Wide_Exit"]
MANUFACTURERS = ["Cubic", "Thales", "Scheidt_Bachmann", "Vix_Technology"]
FIRMWARE_VERSIONS = ["v3.1.0", "v3.2.1", "v3.3.0", "v4.0.0-beta"]
ERROR_CODES = [
    "E001_NFC_TIMEOUT", "E002_CARD_READ_FAIL", "E003_NETWORK_LOSS",
    "E004_PAYMENT_DECLINE", "E005_SENSOR_MALFUNCTION", "E006_DOOR_JAM",
    "E007_DISPLAY_ERROR", "E008_OVERTEMP", "E009_POWER_FLUCTUATION",
    "E010_FIRMWARE_CRASH", "E011_MEMORY_OVERFLOW", "E012_COMM_TIMEOUT"
]
ERROR_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
MAINTENANCE_TYPES = ["Preventive", "Corrective", "Emergency", "Firmware_Update"]


def generate_devices():
    """Generate device registry with static attributes."""
    print("[1/4] Generating device registry...")

    devices = []
    for i in range(NUM_DEVICES):
        device_id = f"LMR_{i+1:04d}"
        install_date = START_DATE - timedelta(days=np.random.randint(30, 1800))
        age_days = (START_DATE - install_date).days
        manufacturer = np.random.choice(MANUFACTURERS, p=[0.35, 0.30, 0.20, 0.15])
        firmware = np.random.choice(FIRMWARE_VERSIONS, p=[0.20, 0.35, 0.30, 0.15])

        # Older devices and beta firmware are more failure-prone
        failure_prone = (age_days > 1000) or (firmware == "v4.0.0-beta")

        devices.append({
            "device_id": device_id,
            "station": np.random.choice(STATIONS),
            "gate_type": np.random.choice(GATE_TYPES),
            "manufacturer": manufacturer,
            "firmware_version": firmware,
            "install_date": install_date.strftime("%Y-%m-%d"),
            "age_days": age_days,
            "warranty_remaining_days": max(0, 730 - age_days),
            "failure_prone": int(failure_prone)
        })

    df = pd.DataFrame(devices)
    df.to_csv(os.path.join(RAW_DIR, "devices.csv"), index=False)
    print(f"   -> {len(df)} devices generated")
    print(f"   -> Failure-prone devices: {df['failure_prone'].sum()} ({df['failure_prone'].mean()*100:.1f}%)")
    return df


def generate_telemetry(devices_df):
    """Generate daily telemetry readings for each device over 30 days."""
    print("[2/4] Generating telemetry data...")

    records = []
    for _, device in devices_df.iterrows():
        device_id = device["device_id"]
        is_prone = device["failure_prone"]
        age = device["age_days"]

        # Base parameters - failure-prone devices have worse baselines
        base_signal = 85 if not is_prone else 65
        base_temp = 35 if not is_prone else 42
        base_response_ms = 120 if not is_prone else 200
        base_tap_success = 0.97 if not is_prone else 0.88
        base_network_latency = 15 if not is_prone else 35

        for day in range(NUM_DAYS):
            date = START_DATE + timedelta(days=day)

            # Gradual degradation for failure-prone devices
            degradation = (day / NUM_DAYS) * 0.15 if is_prone else (day / NUM_DAYS) * 0.02

            # Daily variation (weekday vs weekend traffic)
            is_weekend = date.weekday() >= 5
            traffic_mult = 0.6 if is_weekend else 1.0
            daily_taps = int(np.random.normal(800 * traffic_mult, 150))
            daily_taps = max(100, daily_taps)

            # Telemetry readings with noise
            signal_strength = max(20, min(100, np.random.normal(
                base_signal - degradation * 100, 5)))
            temperature_c = max(15, min(70, np.random.normal(
                base_temp + degradation * 30, 3)))
            response_time_ms = max(50, np.random.normal(
                base_response_ms + degradation * 200, 20))
            tap_success_rate = min(1.0, max(0.5, np.random.normal(
                base_tap_success - degradation, 0.02)))
            network_latency_ms = max(5, np.random.normal(
                base_network_latency + degradation * 50, 5))
            power_voltage = max(3.0, min(5.5, np.random.normal(
                5.0 - degradation * 2, 0.2)))
            memory_usage_pct = min(99, max(10, np.random.normal(
                45 + degradation * 200, 8)))
            cpu_usage_pct = min(100, max(5, np.random.normal(
                30 + degradation * 150, 10)))
            error_count = max(0, int(np.random.poisson(
                1 + degradation * 20 if is_prone else 0.3)))
            reboot_count = max(0, int(np.random.poisson(
                degradation * 3 if is_prone else 0.05)))

            # Failed indicator (device went down at some point during the day)
            failure_today = int(
                (signal_strength < 40) or
                (temperature_c > 55) or
                (tap_success_rate < 0.7) or
                (error_count > 8) or
                (memory_usage_pct > 90 and cpu_usage_pct > 85)
            )

            records.append({
                "device_id": device_id,
                "date": date.strftime("%Y-%m-%d"),
                "daily_taps": daily_taps,
                "tap_success_rate": round(tap_success_rate, 4),
                "signal_strength_dbm": round(signal_strength, 1),
                "temperature_c": round(temperature_c, 1),
                "response_time_ms": round(response_time_ms, 1),
                "network_latency_ms": round(network_latency_ms, 1),
                "power_voltage": round(power_voltage, 2),
                "memory_usage_pct": round(memory_usage_pct, 1),
                "cpu_usage_pct": round(cpu_usage_pct, 1),
                "error_count": error_count,
                "reboot_count": reboot_count,
                "uptime_hours": round(max(0, 24 - reboot_count * np.random.uniform(0.5, 3)), 1),
                "failure_today": failure_today
            })

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(RAW_DIR, "telemetry.csv"), index=False)
    print(f"   -> {len(df)} telemetry records generated ({NUM_DEVICES} devices x {NUM_DAYS} days)")
    print(f"   -> Failure days: {df['failure_today'].sum()} ({df['failure_today'].mean()*100:.1f}%)")
    return df


def generate_error_logs(devices_df, telemetry_df):
    """Generate detailed error/event logs from telemetry."""
    print("[3/4] Generating error logs...")

    records = []
    for _, row in telemetry_df[telemetry_df["error_count"] > 0].iterrows():
        device = devices_df[devices_df["device_id"] == row["device_id"]].iloc[0]

        for _ in range(int(row["error_count"])):
            error_code = np.random.choice(ERROR_CODES, p=[
                0.18, 0.15, 0.12, 0.10, 0.08, 0.07,
                0.06, 0.06, 0.05, 0.05, 0.04, 0.04
            ])

            # Severity correlates with device health
            if row["failure_today"]:
                severity = np.random.choice(ERROR_SEVERITIES, p=[0.1, 0.2, 0.4, 0.3])
            else:
                severity = np.random.choice(ERROR_SEVERITIES, p=[0.4, 0.35, 0.2, 0.05])

            hour = np.random.choice(range(5, 24), p=[
                0.02, 0.05, 0.08, 0.12, 0.12, 0.08, 0.06, 0.06,
                0.05, 0.04, 0.04, 0.04, 0.04, 0.05, 0.06, 0.04,
                0.03, 0.01, 0.01
            ])

            records.append({
                "device_id": row["device_id"],
                "timestamp": f"{row['date']} {hour:02d}:{np.random.randint(0,60):02d}:{np.random.randint(0,60):02d}",
                "error_code": error_code,
                "severity": severity,
                "station": device["station"],
                "gate_type": device["gate_type"],
                "firmware_version": device["firmware_version"],
                "resolved": int(np.random.random() > 0.15),
                "resolution_time_min": round(np.random.exponential(45), 1) if np.random.random() > 0.15 else None
            })

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(RAW_DIR, "error_logs.csv"), index=False)
    print(f"   -> {len(df)} error log entries generated")
    print(f"   -> Severity distribution: {df['severity'].value_counts().to_dict()}")
    return df


def generate_maintenance(devices_df, telemetry_df):
    """Generate maintenance and SLA records."""
    print("[4/4] Generating maintenance records...")

    records = []
    # Generate maintenance events based on failures and periodic schedule
    for _, device in devices_df.iterrows():
        device_id = device["device_id"]
        device_telemetry = telemetry_df[telemetry_df["device_id"] == device_id]
        failure_days = device_telemetry[device_telemetry["failure_today"] == 1]

        # Corrective maintenance after failures
        for _, fail_row in failure_days.iterrows():
            if np.random.random() > 0.3:  # 70% of failures trigger maintenance
                sla_target_hours = np.random.choice([4, 8, 24], p=[0.3, 0.5, 0.2])
                actual_hours = round(np.random.exponential(sla_target_hours * 0.8), 1)
                sla_met = int(actual_hours <= sla_target_hours)

                records.append({
                    "device_id": device_id,
                    "date": fail_row["date"],
                    "maintenance_type": np.random.choice(
                        ["Corrective", "Emergency"], p=[0.6, 0.4]),
                    "issue_description": np.random.choice([
                        "NFC module replacement", "Network card reset",
                        "Firmware rollback", "Sensor recalibration",
                        "Power supply repair", "Full unit replacement",
                        "Memory module swap", "Display unit repair"
                    ]),
                    "sla_target_hours": sla_target_hours,
                    "actual_resolution_hours": actual_hours,
                    "sla_met": sla_met,
                    "cost_gbp": round(np.random.uniform(50, 2000), 2),
                    "technician_id": f"TECH_{np.random.randint(1, 21):03d}",
                    "parts_replaced": int(np.random.random() > 0.4),
                    "device_age_at_failure": device["age_days"]
                })

        # Periodic preventive maintenance (every ~15 days)
        for day in [7, 22]:
            if np.random.random() > 0.4:
                date = (START_DATE + timedelta(days=day)).strftime("%Y-%m-%d")
                records.append({
                    "device_id": device_id,
                    "date": date,
                    "maintenance_type": np.random.choice(
                        ["Preventive", "Firmware_Update"], p=[0.7, 0.3]),
                    "issue_description": np.random.choice([
                        "Routine inspection", "Cleaning and calibration",
                        "Firmware update", "Preventive sensor check"
                    ]),
                    "sla_target_hours": 24,
                    "actual_resolution_hours": round(np.random.uniform(0.5, 4), 1),
                    "sla_met": 1,
                    "cost_gbp": round(np.random.uniform(20, 200), 2),
                    "technician_id": f"TECH_{np.random.randint(1, 21):03d}",
                    "parts_replaced": 0,
                    "device_age_at_failure": device["age_days"]
                })

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(RAW_DIR, "maintenance.csv"), index=False)
    print(f"   -> {len(df)} maintenance records generated")
    print(f"   -> SLA met: {df['sla_met'].mean()*100:.1f}%")
    print(f"   -> Type distribution: {df['maintenance_type'].value_counts().to_dict()}")
    return df


def main():
    print("=" * 60)
    print("  DEVICE TELEMETRY - SAMPLE DATA GENERATOR")
    print("  London Metro Contactless Reader Monitoring")
    print("=" * 60)
    print()

    devices_df = generate_devices()
    telemetry_df = generate_telemetry(devices_df)
    error_logs_df = generate_error_logs(devices_df, telemetry_df)
    maintenance_df = generate_maintenance(devices_df, telemetry_df)

    print()
    print("=" * 60)
    print("  DATA GENERATION COMPLETE")
    print("=" * 60)
    print(f"  Devices:     {len(devices_df):>6} records")
    print(f"  Telemetry:   {len(telemetry_df):>6} records")
    print(f"  Error Logs:  {len(error_logs_df):>6} records")
    print(f"  Maintenance: {len(maintenance_df):>6} records")
    print(f"  Output Dir:  {RAW_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
