"""
============================================================
FASTAPI PREDICTION SERVICE
============================================================
Serves predictions for all 5 problem statements:
  - /predict/failure     (PS-1: Failure Prediction)
  - /predict/anomaly     (PS-4: Anomaly Detection)
  - /predict/sla-risk    (PS-5: SLA Risk)
  - /health, /metrics    (Monitoring)
============================================================
"""

import os
import time
import json
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)
from starlette.responses import Response
from starlette.middleware.cors import CORSMiddleware

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "data", "artifacts")

# ─── FastAPI App ──────────────────────────────────────────
app = FastAPI(
    title="Device Telemetry ML API",
    description="London Metro Reader Monitoring - Prediction Service",
    version="1.0.0"
)

# ─── CORS (for React dashboard) ───────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:5173", "http://127.0.0.1:3001", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Prometheus Metrics ───────────────────────────────────

# --- Request Metrics ---
PREDICTIONS_TOTAL = Counter(
    "predictions_total", "Total predictions", ["problem_statement", "risk_tier"]
)
PREDICTION_LATENCY = Histogram(
    "prediction_latency_seconds", "Prediction latency",
    ["problem_statement"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)
HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests", ["method", "endpoint", "status"]
)
ERRORS_TOTAL = Counter("errors_total", "Total errors", ["error_type"])
REQUESTS_IN_PROGRESS = Gauge(
    "requests_in_progress", "Requests currently being processed", ["problem_statement"]
)

# --- Model Performance Metrics ---
FAILURE_PROB_GAUGE = Gauge(
    "failure_probability_last", "Last failure probability prediction"
)
FAILURE_PROB_HISTOGRAM = Histogram(
    "failure_probability_distribution", "Distribution of failure probabilities",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)
ANOMALY_RATE_GAUGE = Gauge(
    "anomaly_rate_current", "Current anomaly detection rate"
)
ANOMALY_SCORE_HISTOGRAM = Histogram(
    "anomaly_score_distribution", "Distribution of anomaly scores",
    buckets=[-0.5, -0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.5]
)
SLA_RISK_HISTOGRAM = Histogram(
    "sla_risk_score_distribution", "Distribution of SLA risk scores",
    buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)
RUL_ESTIMATE_HISTOGRAM = Histogram(
    "rul_estimate_days_distribution", "Distribution of RUL estimates",
    buckets=[7, 14, 21, 30, 45, 60, 90]
)

# --- Risk Tier Counters ---
RISK_TIER_TOTAL = Counter(
    "risk_tier_total", "Total predictions by risk tier", ["tier"]
)

# --- System / Model Metrics ---
MODEL_INFO = Gauge("model_loaded", "Model loaded status", ["problem_statement"])
MODEL_LOAD_TIME = Gauge(
    "model_load_time_seconds", "Time taken to load model", ["problem_statement"]
)
FEATURE_COUNT = Gauge(
    "feature_count", "Number of features used by model", ["problem_statement"]
)

# --- Data / Drift Metrics ---
DRIFT_SHARE_GAUGE = Gauge(
    "drift_share_current", "Current data drift share (0-1)"
)
DATA_QUALITY_PASS_RATE = Gauge(
    "data_quality_pass_rate", "Data quality check pass rate (0-100)"
)
RETRAINING_TRIGGERED = Counter(
    "retraining_triggered_total", "Number of times retraining was triggered"
)

# --- Business Metrics ---
DEVICES_AT_RISK = Gauge(
    "devices_at_risk", "Number of devices in CRITICAL or HIGH risk tier"
)
MEAN_HEALTH_SCORE = Gauge(
    "mean_health_score", "Average device health score across fleet"
)
SLA_BREACH_PROBABILITY_AVG = Gauge(
    "sla_breach_probability_avg", "Average SLA breach probability"
)

# ─── Global State ─────────────────────────────────────────
startup_time = time.time()
prediction_count = {"ps1": 0, "ps4": 0, "ps5": 0}
models = {}


# ─── Request/Response Schemas ─────────────────────────────

class DeviceTelemetry(BaseModel):
    device_id: str = Field(..., example="LMR_0001")
    signal_strength_dbm: float = Field(80.0, ge=0, le=100)
    temperature_c: float = Field(35.0, ge=-10, le=80)
    response_time_ms: float = Field(120.0, ge=10)
    network_latency_ms: float = Field(15.0, ge=1)
    power_voltage: float = Field(5.0, ge=2.0, le=6.0)
    memory_usage_pct: float = Field(45.0, ge=0, le=100)
    cpu_usage_pct: float = Field(30.0, ge=0, le=100)
    error_count: int = Field(0, ge=0)
    reboot_count: int = Field(0, ge=0)
    uptime_hours: float = Field(24.0, ge=0, le=24)
    daily_taps: int = Field(800, ge=0)
    tap_success_rate: float = Field(0.97, ge=0, le=1.0)
    health_score: float = Field(80.0, ge=0, le=100)
    age_days: int = Field(365, ge=0)
    cumulative_errors: int = Field(10, ge=0)
    cumulative_reboots: int = Field(2, ge=0)
    total_maintenance_count: int = Field(3, ge=0)
    corrective_count: int = Field(1, ge=0)
    emergency_count: int = Field(0, ge=0)


class FailurePredictionResponse(BaseModel):
    device_id: str
    failure_probability: float
    failure_prediction: int
    risk_tier: str
    confidence: str
    recommended_action: str
    prediction_time_ms: float


class AnomalyResponse(BaseModel):
    device_id: str
    is_anomaly: bool
    anomaly_score: float
    anomaly_features: dict
    prediction_time_ms: float


class SLARiskResponse(BaseModel):
    device_id: str
    sla_risk_score: float
    risk_tier: str
    rul_estimate_days: int
    recommended_action: str
    prediction_time_ms: float


class BatchRequest(BaseModel):
    devices: List[DeviceTelemetry]


# ─── Model Loading ────────────────────────────────────────

def load_models():
    """Load all trained models at startup."""
    global models

    # PS-1: Failure Prediction
    ps1_path = os.path.join(ARTIFACTS_DIR, "ps1", "champion_model.pkl")
    if os.path.exists(ps1_path):
        import joblib
        models["ps1"] = joblib.load(ps1_path)
        MODEL_INFO.labels(problem_statement="ps1_failure").set(1)
        print(f"   [OK] PS-1 model loaded: {type(models['ps1']).__name__}")
    else:
        print(f"   [WARN] PS-1 model not found at {ps1_path}")

    # PS-4: Anomaly Detection
    ps4_path = os.path.join(ARTIFACTS_DIR, "ps4", "isolation_forest_model.pkl")
    if os.path.exists(ps4_path):
        import joblib
        models["ps4"] = joblib.load(ps4_path)
        MODEL_INFO.labels(problem_statement="ps4_anomaly").set(1)
        print(f"   [OK] PS-4 model loaded")
    else:
        print(f"   [WARN] PS-4 model not found at {ps4_path}")

    # PS-5: SLA Risk (rule-based from RUL estimates)
    rul_path = os.path.join(ARTIFACTS_DIR, "ps5", "rul_estimates.csv")
    if os.path.exists(rul_path):
        models["ps5_rul"] = pd.read_csv(rul_path)
        MODEL_INFO.labels(problem_statement="ps5_sla").set(1)
        print(f"   [OK] PS-5 RUL data loaded")
    else:
        print(f"   [WARN] PS-5 RUL data not found")


@app.on_event("startup")
async def startup():
    print("=" * 50)
    print("  Loading models...")
    load_models()

    # Load drift and quality metrics into Prometheus gauges
    drift_path = os.path.join(BASE_DIR, "data", "drift_reports", "drift_decision.json")
    if os.path.exists(drift_path):
        with open(drift_path) as f:
            drift = json.load(f)
        DRIFT_SHARE_GAUGE.set(drift.get("drift_share", 0))

    quality_path = os.path.join(BASE_DIR, "data", "quality_reports", "quality_summary.json")
    if os.path.exists(quality_path):
        with open(quality_path) as f:
            quality = json.load(f)
        DATA_QUALITY_PASS_RATE.set(quality.get("overall_pass_rate", 0))

    print("  API ready.")
    print("=" * 50)


# ─── Helper Functions ─────────────────────────────────────

def get_risk_tier(prob):
    if prob >= 0.7:
        return "CRITICAL", "HIGH", "EMERGENCY: Immediate replacement needed"
    elif prob >= 0.4:
        return "HIGH", "HIGH", "Schedule corrective maintenance within 48h"
    elif prob >= 0.2:
        return "MEDIUM", "MEDIUM", "Monitor closely, plan preventive maintenance"
    else:
        return "LOW", "HIGH", "No immediate action needed"


def prepare_features(telemetry: DeviceTelemetry):
    """Convert telemetry to feature vector."""
    feature_dict = telemetry.model_dump()
    feature_dict.pop("device_id", None)

    # Add derived features expected by models
    feature_dict.setdefault("signal_strength_dbm_7d_mean", feature_dict["signal_strength_dbm"])
    feature_dict.setdefault("temperature_c_7d_mean", feature_dict["temperature_c"])
    feature_dict.setdefault("error_count_7d_mean", feature_dict["error_count"])
    feature_dict.setdefault("response_time_ms_7d_mean", feature_dict["response_time_ms"])
    feature_dict.setdefault("signal_strength_dbm_7d_std", 3.0)
    feature_dict.setdefault("error_count_7d_std", 1.0)
    feature_dict.setdefault("signal_strength_dbm_delta", 0.0)
    feature_dict.setdefault("temperature_c_delta", 0.0)
    feature_dict.setdefault("error_count_delta", 0.0)
    feature_dict.setdefault("days_since_last_failure", 10)
    feature_dict.setdefault("manufacturer", 0)
    feature_dict.setdefault("firmware_version", 0)
    feature_dict.setdefault("gate_type", 0)
    feature_dict.setdefault("is_old_device", int(feature_dict["age_days"] > 1000))
    feature_dict.setdefault("is_beta_firmware", 0)
    feature_dict.setdefault("is_under_warranty", int(feature_dict["age_days"] < 730))
    feature_dict.setdefault("is_high_traffic_station", 0)

    return feature_dict


# ─── API Endpoints ────────────────────────────────────────

@app.get("/")
async def root():
    HTTP_REQUESTS.labels(method="GET", endpoint="/", status="200").inc()
    return {
        "service": "Device Telemetry ML API",
        "version": "1.0.0",
        "problem_statements": [
            "PS-1: Failure Prediction (RF/XGBoost/CatBoost)",
            "PS-2: Error Pattern Recognition (Association Rules/Markov)",
            "PS-3: Root Cause Analysis (SHAP/Causal Inference)",
            "PS-4: Anomaly Detection (Isolation Forest/SPC)",
            "PS-5: SLA Risk Prediction (Weibull/Cox/RUL)"
        ],
        "endpoints": ["/predict/failure", "/predict/anomaly", "/predict/sla-risk",
                       "/health", "/metrics"]
    }


@app.get("/health")
async def health():
    uptime = time.time() - startup_time
    HTTP_REQUESTS.labels(method="GET", endpoint="/health", status="200").inc()
    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 1),
        "models_loaded": list(models.keys()),
        "total_predictions": sum(prediction_count.values())
    }


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/model/info")
async def model_info():
    info = {}
    if "ps1" in models:
        metrics_path = os.path.join(ARTIFACTS_DIR, "ps1", "champion_metrics.json")
        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                info["ps1_failure_prediction"] = json.load(f)

    spc_path = os.path.join(ARTIFACTS_DIR, "ps4", "spc_limits.json")
    if os.path.exists(spc_path):
        with open(spc_path) as f:
            info["ps4_spc_limits"] = json.load(f)

    return info


@app.post("/predict/failure", response_model=FailurePredictionResponse)
async def predict_failure(telemetry: DeviceTelemetry):
    """PS-1: Predict device failure probability."""
    start_time = time.time()

    if "ps1" not in models:
        raise HTTPException(status_code=503, detail="PS-1 model not loaded")

    try:
        features = prepare_features(telemetry)
        model = models["ps1"]

        # Get expected feature order from model
        feature_values = []
        if hasattr(model, "feature_names_in_"):
            for fname in model.feature_names_in_:
                feature_values.append(features.get(fname, 0))
        else:
            feature_values = list(features.values())

        X = np.array([feature_values])
        prob = float(model.predict_proba(X)[0, 1])
        prediction = int(prob >= 0.5)

        risk_tier, confidence, action = get_risk_tier(prob)
        elapsed_ms = (time.time() - start_time) * 1000

        prediction_count["ps1"] += 1
        PREDICTIONS_TOTAL.labels(problem_statement="ps1", risk_tier=risk_tier).inc()
        PREDICTION_LATENCY.labels(problem_statement="ps1").observe(elapsed_ms / 1000)
        FAILURE_PROB_GAUGE.set(prob)
        FAILURE_PROB_HISTOGRAM.observe(prob)
        RISK_TIER_TOTAL.labels(tier=risk_tier).inc()
        MEAN_HEALTH_SCORE.set(telemetry.health_score)

        return FailurePredictionResponse(
            device_id=telemetry.device_id,
            failure_probability=round(prob, 4),
            failure_prediction=prediction,
            risk_tier=risk_tier,
            confidence=confidence,
            recommended_action=action,
            prediction_time_ms=round(elapsed_ms, 2)
        )

    except Exception as e:
        ERRORS_TOTAL.labels(error_type="ps1_prediction").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/anomaly", response_model=AnomalyResponse)
async def predict_anomaly(telemetry: DeviceTelemetry):
    """PS-4: Detect if device telemetry is anomalous."""
    start_time = time.time()

    if "ps4" not in models:
        raise HTTPException(status_code=503, detail="PS-4 model not loaded")

    try:
        iso_data = models["ps4"]
        iso_model = iso_data["model"]
        scaler = iso_data["scaler"]

        feature_keys = [
            "signal_strength_dbm", "temperature_c", "response_time_ms",
            "network_latency_ms", "power_voltage", "memory_usage_pct",
            "cpu_usage_pct", "error_count", "tap_success_rate",
            "uptime_hours", "health_score"
        ]

        features = telemetry.model_dump()
        X = np.array([[features.get(k, 0) for k in feature_keys]])
        X_scaled = scaler.transform(X)

        prediction = iso_model.predict(X_scaled)[0]
        score = float(iso_model.decision_function(X_scaled)[0])
        is_anomaly = prediction == -1

        # Identify anomalous features
        anomaly_features = {}
        if is_anomaly:
            for k in feature_keys:
                val = features.get(k, 0)
                anomaly_features[k] = round(val, 2)

        elapsed_ms = (time.time() - start_time) * 1000
        prediction_count["ps4"] += 1
        PREDICTIONS_TOTAL.labels(
            problem_statement="ps4",
            risk_tier="ANOMALY" if is_anomaly else "NORMAL"
        ).inc()
        PREDICTION_LATENCY.labels(problem_statement="ps4").observe(elapsed_ms / 1000)
        ANOMALY_SCORE_HISTOGRAM.observe(score)
        if is_anomaly:
            ANOMALY_RATE_GAUGE.inc()

        return AnomalyResponse(
            device_id=telemetry.device_id,
            is_anomaly=is_anomaly,
            anomaly_score=round(score, 4),
            anomaly_features=anomaly_features,
            prediction_time_ms=round(elapsed_ms, 2)
        )

    except Exception as e:
        ERRORS_TOTAL.labels(error_type="ps4_prediction").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/sla-risk", response_model=SLARiskResponse)
async def predict_sla_risk(telemetry: DeviceTelemetry):
    """PS-5: Predict SLA breach risk and remaining useful life."""
    start_time = time.time()

    try:
        features = telemetry.model_dump()

        # Rule-based SLA risk scoring
        health = features.get("health_score", 50)
        errors = features.get("cumulative_errors", 0)
        age = features.get("age_days", 0)
        maint_count = features.get("total_maintenance_count", 0)

        # SLA risk score (0-100)
        sla_risk = (
            (1 - health / 100) * 35 +
            min(errors / 50, 1) * 25 +
            min(age / 1500, 1) * 20 +
            min(maint_count / 10, 1) * 10 +
            (features.get("emergency_count", 0) > 0) * 10
        )
        sla_risk = min(100, max(0, sla_risk))

        # RUL estimate
        rul = max(1, int(90 * (1 - sla_risk / 100)))

        # Risk tier
        if sla_risk >= 70:
            risk_tier = "CRITICAL"
            action = "EMERGENCY: Schedule immediate replacement"
        elif sla_risk >= 50:
            risk_tier = "HIGH"
            action = "Schedule maintenance within 48 hours"
        elif sla_risk >= 30:
            risk_tier = "MEDIUM"
            action = "Plan preventive maintenance within 1 week"
        else:
            risk_tier = "LOW"
            action = "Continue standard monitoring"

        elapsed_ms = (time.time() - start_time) * 1000
        prediction_count["ps5"] += 1
        PREDICTIONS_TOTAL.labels(problem_statement="ps5", risk_tier=risk_tier).inc()
        PREDICTION_LATENCY.labels(problem_statement="ps5").observe(elapsed_ms / 1000)
        SLA_RISK_HISTOGRAM.observe(sla_risk)
        RUL_ESTIMATE_HISTOGRAM.observe(rul)
        RISK_TIER_TOTAL.labels(tier=risk_tier).inc()
        SLA_BREACH_PROBABILITY_AVG.set(1 / (1 + np.exp(0.1 * (rul - 15))))
        if risk_tier in ("CRITICAL", "HIGH"):
            DEVICES_AT_RISK.inc()

        return SLARiskResponse(
            device_id=telemetry.device_id,
            sla_risk_score=round(sla_risk, 1),
            risk_tier=risk_tier,
            rul_estimate_days=rul,
            recommended_action=action,
            prediction_time_ms=round(elapsed_ms, 2)
        )

    except Exception as e:
        ERRORS_TOTAL.labels(error_type="ps5_prediction").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/failure/batch")
async def predict_failure_batch(batch: BatchRequest):
    """Batch failure predictions for multiple devices."""
    if "ps1" not in models:
        raise HTTPException(status_code=503, detail="PS-1 model not loaded")

    results = []
    for device in batch.devices:
        result = await predict_failure(device)
        results.append(result)

    return {
        "predictions": results,
        "count": len(results),
        "summary": {
            "critical": sum(1 for r in results if r.risk_tier == "CRITICAL"),
            "high": sum(1 for r in results if r.risk_tier == "HIGH"),
            "medium": sum(1 for r in results if r.risk_tier == "MEDIUM"),
            "low": sum(1 for r in results if r.risk_tier == "LOW")
        }
    }


@app.post("/predict/batch/all")
async def predict_batch_all_ps(batch: BatchRequest):
    """
    Run ALL 5 Problem Statements on a batch of devices.
    Returns combined results: PS-1 to PS-5 for every device.
    """
    start_time = time.time()

    all_results = []

    for device in batch.devices:
        device_result = {"device_id": device.device_id}

        # ── PS-1: Failure Prediction ──
        if "ps1" in models:
            try:
                ps1_resp = await predict_failure(device)
                device_result["ps1_failure"] = {
                    "failure_probability": ps1_resp.failure_probability,
                    "failure_prediction": ps1_resp.failure_prediction,
                    "risk_tier": ps1_resp.risk_tier,
                    "confidence": ps1_resp.confidence,
                    "recommended_action": ps1_resp.recommended_action
                }
            except Exception as e:
                device_result["ps1_failure"] = {"error": str(e)}

        # ── PS-2: Error Pattern Recognition ──
        # PS-2 is fleet-level analysis, so we compute per-device error risk indicators
        device_result["ps2_error_patterns"] = {
            "error_count": device.error_count,
            "error_rate_per_day": round(device.cumulative_errors / max(device.age_days, 1), 4),
            "error_severity": "HIGH" if device.error_count >= 5 else
                              "MEDIUM" if device.error_count >= 2 else "LOW",
            "reboot_frequency": round(device.cumulative_reboots / max(device.age_days, 1) * 30, 2),
            "likely_escalation": device.error_count >= 3 and device.emergency_count >= 1
        }

        # ── PS-3: Root Cause Analysis ──
        # Compute top contributing factors for this device's risk
        risk_factors = []
        if device.signal_strength_dbm < 60:
            risk_factors.append({"factor": "Low signal strength", "value": device.signal_strength_dbm, "impact": "HIGH"})
        if device.temperature_c > 50:
            risk_factors.append({"factor": "High temperature", "value": device.temperature_c, "impact": "HIGH"})
        if device.error_count >= 5:
            risk_factors.append({"factor": "High error count", "value": device.error_count, "impact": "HIGH"})
        if device.memory_usage_pct > 80:
            risk_factors.append({"factor": "High memory usage", "value": device.memory_usage_pct, "impact": "MEDIUM"})
        if device.cpu_usage_pct > 75:
            risk_factors.append({"factor": "High CPU usage", "value": device.cpu_usage_pct, "impact": "MEDIUM"})
        if device.tap_success_rate < 0.85:
            risk_factors.append({"factor": "Low tap success rate", "value": device.tap_success_rate, "impact": "HIGH"})
        if device.response_time_ms > 300:
            risk_factors.append({"factor": "Slow response time", "value": device.response_time_ms, "impact": "MEDIUM"})
        if device.age_days > 1000:
            risk_factors.append({"factor": "Old device", "value": device.age_days, "impact": "MEDIUM"})
        if device.uptime_hours < 20:
            risk_factors.append({"factor": "Low uptime", "value": device.uptime_hours, "impact": "MEDIUM"})

        device_result["ps3_root_cause"] = {
            "risk_factors": sorted(risk_factors, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["impact"]]),
            "total_risk_factors": len(risk_factors),
            "primary_cause": risk_factors[0]["factor"] if risk_factors else "No significant risk factors"
        }

        # ── PS-4: Anomaly Detection ──
        if "ps4" in models:
            try:
                ps4_resp = await predict_anomaly(device)
                device_result["ps4_anomaly"] = {
                    "is_anomaly": ps4_resp.is_anomaly,
                    "anomaly_score": ps4_resp.anomaly_score,
                    "anomaly_features": ps4_resp.anomaly_features
                }
            except Exception as e:
                device_result["ps4_anomaly"] = {"error": str(e)}

        # ── PS-5: SLA Risk ──
        if "ps5_rul" in models:
            try:
                ps5_resp = await predict_sla_risk(device)
                device_result["ps5_sla_risk"] = {
                    "sla_risk_score": ps5_resp.sla_risk_score,
                    "risk_tier": ps5_resp.risk_tier,
                    "rul_estimate_days": ps5_resp.rul_estimate_days,
                    "recommended_action": ps5_resp.recommended_action
                }
            except Exception as e:
                device_result["ps5_sla_risk"] = {"error": str(e)}

        all_results.append(device_result)

    elapsed = (time.time() - start_time) * 1000

    # Fleet-wide PS-2 summary (error co-occurrence across the batch)
    error_devices = [d for d in batch.devices if d.error_count >= 3]
    high_error_devices = [d for d in batch.devices if d.error_count >= 5]

    # Fleet-wide summary
    summary = {
        "total_devices": len(batch.devices),
        "processing_time_ms": round(elapsed, 1),
        "ps1_summary": {
            "critical": sum(1 for r in all_results if r.get("ps1_failure", {}).get("risk_tier") == "CRITICAL"),
            "high": sum(1 for r in all_results if r.get("ps1_failure", {}).get("risk_tier") == "HIGH"),
            "medium": sum(1 for r in all_results if r.get("ps1_failure", {}).get("risk_tier") == "MEDIUM"),
            "low": sum(1 for r in all_results if r.get("ps1_failure", {}).get("risk_tier") == "LOW"),
        },
        "ps2_summary": {
            "devices_with_errors": len(error_devices),
            "devices_high_error": len(high_error_devices),
            "fleet_avg_error_count": round(sum(d.error_count for d in batch.devices) / len(batch.devices), 2)
        },
        "ps3_summary": {
            "devices_with_risk_factors": sum(1 for r in all_results if r["ps3_root_cause"]["total_risk_factors"] > 0),
            "top_cause_across_fleet": _get_top_fleet_cause(all_results)
        },
        "ps4_summary": {
            "anomalies": sum(1 for r in all_results if r.get("ps4_anomaly", {}).get("is_anomaly", False)),
            "normal": sum(1 for r in all_results if not r.get("ps4_anomaly", {}).get("is_anomaly", True)),
        },
        "ps5_summary": {
            "critical": sum(1 for r in all_results if r.get("ps5_sla_risk", {}).get("risk_tier") == "CRITICAL"),
            "high": sum(1 for r in all_results if r.get("ps5_sla_risk", {}).get("risk_tier") == "HIGH"),
            "avg_rul_days": round(np.mean([r["ps5_sla_risk"]["rul_estimate_days"]
                                            for r in all_results
                                            if "rul_estimate_days" in r.get("ps5_sla_risk", {})]) if all_results else 0, 1)
        }
    }

    return {
        "devices": all_results,
        "summary": summary
    }


def _get_top_fleet_cause(results):
    """Find the most common root cause across all devices."""
    causes = {}
    for r in results:
        for factor in r.get("ps3_root_cause", {}).get("risk_factors", []):
            name = factor["factor"]
            causes[name] = causes.get(name, 0) + 1
    if causes:
        top = sorted(causes.items(), key=lambda x: -x[1])[0]
        return {"cause": top[0], "affected_devices": top[1]}
    return {"cause": "None", "affected_devices": 0}


# ─── Dashboard Data Endpoints ─────────────────────────────

def _read_csv_safe(path):
    """Read CSV and return as list of dicts, or empty list."""
    if os.path.exists(path):
        df = pd.read_csv(path)
        df = df.fillna(0)
        # Replace inf/-inf with 0 for JSON serialization
        df = df.replace([np.inf, -np.inf], 0)
        return df.to_dict(orient="records")
    return []


def _read_json_safe(path):
    """Read JSON file or return empty dict."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


@app.get("/dashboard/summary")
async def dashboard_summary():
    """Overview summary for all 5 problem statements."""
    ps1_metrics = _read_json_safe(os.path.join(ARTIFACTS_DIR, "ps1", "champion_metrics.json"))
    spc_results = _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps4", "spc_results.csv"))
    rul_data = _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps5", "rul_estimates.csv"))
    drift_decision = _read_json_safe(os.path.join(BASE_DIR, "data", "drift_reports", "drift_decision.json"))
    quality_summary = _read_json_safe(os.path.join(BASE_DIR, "data", "quality_reports", "quality_summary.json"))

    rul_df = pd.DataFrame(rul_data) if rul_data else pd.DataFrame()

    return {
        "ps1_failure_prediction": {
            "champion_model": ps1_metrics.get("model", "N/A"),
            "auc": ps1_metrics.get("auc", 0),
            "f1": ps1_metrics.get("f1", 0),
            "recall": ps1_metrics.get("recall", 0),
            "precision": ps1_metrics.get("precision", 0),
        },
        "ps2_error_patterns": {
            "association_rules": len(_read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "association_rules.csv"))),
            "top_transitions": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "top_transitions.csv"))[:10],
            "severity_escalations": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "severity_escalations.csv")),
        },
        "ps3_root_cause": {
            "shap_importance": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps3", "shap_importance.csv"))[:10],
            "causal_results": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps3", "causal_results.csv")),
        },
        "ps4_anomaly_detection": {
            "anomaly_summary": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps4", "device_anomaly_summary.csv"))[:10],
            "spc_results": spc_results,
            "feature_diff": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps4", "anomaly_feature_diff.csv")),
        },
        "ps5_sla_risk": {
            "rul_estimates": rul_data[:10] if rul_data else [],
            "risk_distribution": rul_df["risk_tier"].value_counts().to_dict() if not rul_df.empty else {},
            "mean_rul_days": round(float(rul_df["rul_median_days"].mean()), 1) if not rul_df.empty else 0,
            "sla_risk_scores": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps5", "sla_risk_scores.csv"))[:10],
        },
        "drift_detection": drift_decision,
        "data_quality": quality_summary,
        "api_status": {
            "models_loaded": list(models.keys()),
            "total_predictions": sum(prediction_count.values()),
            "uptime_seconds": round(time.time() - startup_time, 1),
        }
    }


@app.get("/dashboard/ps1")
async def dashboard_ps1():
    """PS-1: Failure Prediction details."""
    return {
        "champion_metrics": _read_json_safe(os.path.join(ARTIFACTS_DIR, "ps1", "champion_metrics.json")),
        "description": "Predicts device failure in next 3 days using RF, XGBoost, CatBoost",
        "models_compared": ["Random Forest", "XGBoost", "CatBoost"],
        "target": "failure_next_3d",
    }


@app.get("/dashboard/ps2")
async def dashboard_ps2():
    """PS-2: Error Pattern Recognition details."""
    return {
        "association_rules": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "association_rules.csv"))[:20],
        "top_transitions": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "top_transitions.csv"))[:20],
        "severity_escalations": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "severity_escalations.csv")),
        "stationary_distribution": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps2", "stationary_distribution.csv")),
        "description": "Discovers co-occurring errors (Apriori) and error sequences (Markov Chain)",
    }


@app.get("/dashboard/ps3")
async def dashboard_ps3():
    """PS-3: Root Cause Analysis details."""
    return {
        "shap_importance": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps3", "shap_importance.csv")),
        "causal_results": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps3", "causal_results.csv")),
        "local_explanation": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps3", "shap_local_explanation.csv"))[:10],
        "description": "Identifies root causes using SHAP values and Causal Inference (DoWhy)",
    }


@app.get("/dashboard/ps4")
async def dashboard_ps4():
    """PS-4: Anomaly Detection details."""
    return {
        "device_anomaly_summary": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps4", "device_anomaly_summary.csv"))[:20],
        "spc_results": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps4", "spc_results.csv")),
        "spc_limits": _read_json_safe(os.path.join(ARTIFACTS_DIR, "ps4", "spc_limits.json")),
        "feature_diff": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps4", "anomaly_feature_diff.csv")),
        "description": "Detects anomalous device behavior using Isolation Forest and SPC Control Charts",
    }


@app.get("/dashboard/ps5")
async def dashboard_ps5():
    """PS-5: SLA Risk Prediction details."""
    return {
        "rul_estimates": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps5", "rul_estimates.csv")),
        "sla_risk_scores": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps5", "sla_risk_scores.csv"))[:20],
        "cox_summary": _read_csv_safe(os.path.join(ARTIFACTS_DIR, "ps5", "cox_summary.csv")),
        "description": "Estimates Remaining Useful Life and SLA breach risk using Weibull, Cox PH",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
