"""
============================================================
TRAFFIC GENERATOR - Load Testing for Monitoring
============================================================
Generates synthetic API traffic for Prometheus/Grafana dashboards.
============================================================
"""

import time
import random
import requests
import argparse

API_URL = "http://localhost:8000"


def generate_device_payload():
    """Generate a random device telemetry payload."""
    is_failing = random.random() < 0.15

    if is_failing:
        return {
            "device_id": f"LMR_{random.randint(1, 200):04d}",
            "signal_strength_dbm": random.uniform(20, 50),
            "temperature_c": random.uniform(45, 65),
            "response_time_ms": random.uniform(300, 800),
            "network_latency_ms": random.uniform(30, 100),
            "power_voltage": random.uniform(3.0, 4.0),
            "memory_usage_pct": random.uniform(70, 98),
            "cpu_usage_pct": random.uniform(60, 95),
            "error_count": random.randint(5, 20),
            "reboot_count": random.randint(1, 5),
            "uptime_hours": random.uniform(10, 22),
            "daily_taps": random.randint(200, 600),
            "tap_success_rate": random.uniform(0.6, 0.85),
            "health_score": random.uniform(20, 50),
            "age_days": random.randint(500, 1800),
            "cumulative_errors": random.randint(50, 200),
            "cumulative_reboots": random.randint(10, 50),
            "total_maintenance_count": random.randint(5, 20),
            "corrective_count": random.randint(3, 10),
            "emergency_count": random.randint(1, 5)
        }
    else:
        return {
            "device_id": f"LMR_{random.randint(1, 200):04d}",
            "signal_strength_dbm": random.uniform(70, 95),
            "temperature_c": random.uniform(25, 40),
            "response_time_ms": random.uniform(80, 180),
            "network_latency_ms": random.uniform(5, 25),
            "power_voltage": random.uniform(4.5, 5.5),
            "memory_usage_pct": random.uniform(20, 55),
            "cpu_usage_pct": random.uniform(10, 40),
            "error_count": random.randint(0, 2),
            "reboot_count": 0,
            "uptime_hours": random.uniform(23, 24),
            "daily_taps": random.randint(600, 1200),
            "tap_success_rate": random.uniform(0.95, 0.99),
            "health_score": random.uniform(70, 95),
            "age_days": random.randint(30, 800),
            "cumulative_errors": random.randint(0, 20),
            "cumulative_reboots": random.randint(0, 3),
            "total_maintenance_count": random.randint(0, 5),
            "corrective_count": random.randint(0, 2),
            "emergency_count": 0
        }


def main():
    parser = argparse.ArgumentParser(description="API Traffic Generator")
    parser.add_argument("--rps", type=float, default=2, help="Requests per second")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--url", type=str, default=API_URL, help="API base URL")
    args = parser.parse_args()

    endpoints = [
        "/predict/failure",
        "/predict/anomaly",
        "/predict/sla-risk"
    ]

    print(f"Generating traffic to {args.url}")
    print(f"Rate: {args.rps} RPS, Duration: {args.duration}s")
    print("-" * 40)

    total = 0
    errors = 0
    start = time.time()

    while time.time() - start < args.duration:
        endpoint = random.choice(endpoints)
        payload = generate_device_payload()

        try:
            resp = requests.post(f"{args.url}{endpoint}", json=payload, timeout=5)
            total += 1
            if resp.status_code != 200:
                errors += 1
            if total % 10 == 0:
                print(f"  Sent: {total}, Errors: {errors}, Endpoint: {endpoint}")
        except requests.exceptions.ConnectionError:
            errors += 1
            print(f"  [ERROR] Connection refused - is the API running?")
            break
        except Exception as e:
            errors += 1

        time.sleep(1.0 / args.rps)

    elapsed = time.time() - start
    print(f"\nTraffic generation complete:")
    print(f"  Total requests: {total}")
    print(f"  Errors: {errors}")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Effective RPS: {total/elapsed:.1f}")


if __name__ == "__main__":
    main()
