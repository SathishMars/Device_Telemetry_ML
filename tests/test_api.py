"""
============================================================
API TESTS
============================================================
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


SAMPLE_DEVICE = {
    "device_id": "LMR_0001",
    "signal_strength_dbm": 82.5,
    "temperature_c": 36.2,
    "response_time_ms": 125.0,
    "network_latency_ms": 12.5,
    "power_voltage": 4.9,
    "memory_usage_pct": 42.0,
    "cpu_usage_pct": 28.5,
    "error_count": 1,
    "reboot_count": 0,
    "uptime_hours": 23.8,
    "daily_taps": 856,
    "tap_success_rate": 0.97,
    "health_score": 82.3,
    "age_days": 365,
    "cumulative_errors": 12,
    "cumulative_reboots": 2,
    "total_maintenance_count": 3,
    "corrective_count": 1,
    "emergency_count": 0
}


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "problem_statements" in data
    assert len(data["problem_statements"]) == 5


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "predictions_total" in resp.text or "http_requests_total" in resp.text


def test_predict_sla_risk(client):
    resp = client.post("/predict/sla-risk", json=SAMPLE_DEVICE)
    assert resp.status_code == 200
    data = resp.json()
    assert "sla_risk_score" in data
    assert "risk_tier" in data
    assert "rul_estimate_days" in data
    assert data["risk_tier"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def test_predict_failure_requires_model(client):
    """Failure prediction needs trained model - may return 503 if not loaded."""
    resp = client.post("/predict/failure", json=SAMPLE_DEVICE)
    assert resp.status_code in [200, 503]


def test_predict_anomaly_requires_model(client):
    """Anomaly detection needs trained model - may return 503 if not loaded."""
    resp = client.post("/predict/anomaly", json=SAMPLE_DEVICE)
    assert resp.status_code in [200, 503]
