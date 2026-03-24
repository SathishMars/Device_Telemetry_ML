# Sprint Plan — Device Telemetry MLOps
## ML & MLOps Team Tasks

**Project:** London Metro Contactless Reader Monitoring
**Team:** ML Engineering & MLOps
**Sprint Duration:** 2 weeks per sprint

---

## Sprint 1: Data Foundation & Infrastructure (Week 1-2)

**Goal:** Establish data pipeline, infrastructure, and development environment.

| # | Task | Owner | Story Points | Priority | Acceptance Criteria |
|---|------|-------|-------------|----------|-------------------|
| 1.1 | Set up Azure Resource Group, Data Lake Gen2, and Key Vault using Terraform | MLOps | 5 | P0 | All resources provisioned, accessible via CLI |
| 1.2 | Set up Databricks workspace and configure cluster | MLOps | 3 | P0 | Cluster running, libraries installed, mount points configured |
| 1.3 | Set up MLflow tracking server on Databricks | MLOps | 2 | P0 | Experiments created, test run logged successfully |
| 1.4 | Ingest raw telemetry data into Data Lake (raw layer) | ML | 3 | P0 | 4 CSV files in raw container, validated row counts |
| 1.5 | Build Bronze layer pipeline (CSV → Parquet, date-partitioned) | ML | 3 | P0 | Parquet files in bronze container with ingestion metadata |
| 1.6 | Build Silver layer pipeline (cleaning, dedup, type casting) | ML | 5 | P0 | Clean parquet in silver, all validations passing |
| 1.7 | Build Gold layer pipeline (feature engineering, 80+ features) | ML | 8 | P0 | Gold dataset with rolling, delta, composite features |
| 1.8 | Create Feature Store with PS-specific feature tables | ML | 3 | P1 | Feature store parquet + schema JSON, versioned |
| 1.9 | Set up Great Expectations data quality checks (Bronze/Silver/Gold) | MLOps | 5 | P1 | Quality validation passing at all 3 layers |
| 1.10 | Set up Git repo, branching strategy, and PR templates | MLOps | 2 | P0 | Repo created, branch protection rules enabled |

**Sprint 1 Total:** 39 story points

---

## Sprint 2: ML Model Development — PS-1 & PS-2 (Week 3-4)

**Goal:** Deliver Failure Prediction and Error Pattern Recognition models.

| # | Task | Owner | Story Points | Priority | Acceptance Criteria |
|---|------|-------|-------------|----------|-------------------|
| 2.1 | PS-1: EDA on failure patterns (class distribution, correlations) | ML | 3 | P0 | EDA notebook with insights documented |
| 2.2 | PS-1: Train Random Forest baseline model | ML | 3 | P0 | Model trained, metrics logged to MLflow |
| 2.3 | PS-1: Train XGBoost with hyperparameter tuning | ML | 5 | P0 | Tuned model, AUC > 0.90, logged to MLflow |
| 2.4 | PS-1: Train CatBoost model | ML | 3 | P0 | Model trained, metrics logged to MLflow |
| 2.5 | PS-1: Compare models, select champion, register in MLflow | ML | 3 | P0 | Champion registered as Production in Model Registry |
| 2.6 | PS-1: Generate ROC curves, confusion matrices, feature importance plots | ML | 2 | P1 | All plots saved as MLflow artifacts |
| 2.7 | PS-2: Build Apriori association rules for error co-occurrence | ML | 5 | P0 | Rules with support, confidence, lift; CSV output |
| 2.8 | PS-2: Build Markov Chain transition model for error sequences | ML | 5 | P0 | Transition matrix, stationary distribution computed |
| 2.9 | PS-2: Severity escalation analysis | ML | 3 | P1 | Escalation paths identified and documented |
| 2.10 | Set up incremental daily pipeline (day-wise processing) | MLOps | 5 | P1 | Pipeline processes 1 day at a time, quality checks pass |

**Sprint 2 Total:** 37 story points

---

## Sprint 3: ML Model Development — PS-3, PS-4, PS-5 (Week 5-6)

**Goal:** Deliver Root Cause Analysis, Anomaly Detection, and SLA Risk models.

| # | Task | Owner | Story Points | Priority | Acceptance Criteria |
|---|------|-------|-------------|----------|-------------------|
| 3.1 | PS-3: SHAP analysis on PS-1 champion model (global + local) | ML | 5 | P0 | SHAP summary, bar, dependence plots; top 10 features |
| 3.2 | PS-3: Causal inference using DoWhy (5 treatment hypotheses) | ML | 5 | P0 | ATE estimates for top features, significance tested |
| 3.3 | PS-4: Train Isolation Forest anomaly detector | ML | 5 | P0 | Model trained, anomaly rate ~8%, device ranking |
| 3.4 | PS-4: Implement SPC control charts (6 features, 3-sigma) | ML | 5 | P0 | Control limits computed, violations flagged |
| 3.5 | PS-5: Fit Weibull time-to-failure distribution | ML | 5 | P0 | Lambda, rho parameters; survival/hazard curves |
| 3.6 | PS-5: Fit Cox Proportional Hazards with covariates | ML | 5 | P0 | Concordance index > 0.7, significant covariates identified |
| 3.7 | PS-5: Estimate Remaining Useful Life (RUL) per device | ML | 5 | P0 | Per-device RUL, risk tier assignment (CRITICAL/HIGH/MEDIUM/LOW) |
| 3.8 | PS-5: Build SLA risk scoring model | ML | 3 | P0 | SLA risk score (0-100), breach probability per device |
| 3.9 | Register PS-4 Isolation Forest in MLflow Model Registry | MLOps | 2 | P1 | Model registered as Production |
| 3.10 | Set up Evidently AI drift detection pipeline | MLOps | 5 | P0 | HTML reports generated, retraining decision automated |

**Sprint 3 Total:** 45 story points

---

## Sprint 4: API Serving & Monitoring (Week 7-8)

**Goal:** Deploy prediction API, set up monitoring, and build dashboard.

| # | Task | Owner | Story Points | Priority | Acceptance Criteria |
|---|------|-------|-------------|----------|-------------------|
| 4.1 | Build FastAPI prediction service (/predict/failure, /anomaly, /sla-risk) | MLOps | 8 | P0 | All 3 endpoints working, Swagger UI available |
| 4.2 | Add Prometheus metrics to API (counters, histograms, gauges) | MLOps | 3 | P0 | /metrics endpoint exposing prediction counts, latency |
| 4.3 | Create Dockerfile and build container image | MLOps | 3 | P0 | Image builds, runs, passes health check |
| 4.4 | Push image to Azure Container Registry | MLOps | 2 | P0 | Image available in ACR |
| 4.5 | Deploy API to Azure Container Apps | MLOps | 5 | P0 | API accessible via public URL, health check passing |
| 4.6 | Set up Prometheus + Grafana monitoring stack (Docker) | MLOps | 5 | P1 | Dashboards showing predictions/min, latency, error rate |
| 4.7 | Configure Azure Application Insights | MLOps | 3 | P1 | Traces, metrics, and logs flowing to App Insights |
| 4.8 | Build React dashboard — Overview and PS-1 tabs | ML | 5 | P1 | KPI cards, model metrics, charts rendering correctly |
| 4.9 | Build React dashboard — PS-2, PS-3, PS-4, PS-5 tabs | ML | 8 | P1 | All tabs showing data from API endpoints |
| 4.10 | Deploy React dashboard to Azure Static Web Apps | MLOps | 3 | P1 | Dashboard accessible via public URL |
| 4.11 | Write API integration tests | MLOps | 3 | P1 | pytest tests passing for all endpoints |

**Sprint 4 Total:** 48 story points

---

## Sprint 5: Production Readiness & CI/CD (Week 9-10)

**Goal:** Production-grade deployment, CI/CD, and operational readiness.

| # | Task | Owner | Story Points | Priority | Acceptance Criteria |
|---|------|-------|-------------|----------|-------------------|
| 5.1 | Set up Blue-Green deployment with Container Apps revisions | MLOps | 5 | P0 | Two revisions running, traffic split configurable |
| 5.2 | Implement Canary deployment strategy (5% → 20% → 50% → 100%) | MLOps | 5 | P1 | Gradual rollout tested, rollback verified |
| 5.3 | Set up GitHub Actions CI/CD pipeline (build → test → deploy) | MLOps | 8 | P0 | Push to main triggers auto-deploy |
| 5.4 | Set up automated drift detection (daily Databricks job) | MLOps | 5 | P0 | Job runs daily, triggers retraining if drift > 30% |
| 5.5 | Implement automated retraining pipeline | MLOps | 8 | P0 | Drift detected → retrain → register → deploy (end-to-end) |
| 5.6 | Set up Databricks Workflows (scheduled pipeline orchestration) | MLOps | 5 | P0 | Daily job: ingest → process → predict → monitor |
| 5.7 | Configure budget alerts and cost monitoring | MLOps | 2 | P1 | Alerts at 80% and 100% of monthly budget |
| 5.8 | Security review: Key Vault, CORS, managed identity, VNET | MLOps | 5 | P0 | All secrets in Key Vault, no hardcoded credentials |
| 5.9 | Load testing: verify API handles 50 RPS | MLOps | 3 | P1 | P99 latency < 500ms at 50 RPS |
| 5.10 | Champion vs Challenger A/B test framework | ML | 5 | P1 | Canary deploys new model, metrics compared automatically |
| 5.11 | Create runbook: incident response, rollback procedures | MLOps | 3 | P1 | Documented steps for common failure scenarios |

**Sprint 5 Total:** 54 story points

---

## Sprint 6: Optimization & Handover (Week 11-12)

**Goal:** Optimize models, finalize documentation, and handover.

| # | Task | Owner | Story Points | Priority | Acceptance Criteria |
|---|------|-------|-------------|----------|-------------------|
| 6.1 | PS-1: Hyperparameter optimization (Optuna/Bayesian search) | ML | 5 | P1 | AUC improved by ≥ 2% over baseline champion |
| 6.2 | PS-4: Tune Isolation Forest contamination and SPC thresholds | ML | 3 | P1 | False positive rate < 5%, true positive rate > 80% |
| 6.3 | PS-5: Validate RUL predictions against actual maintenance data | ML | 5 | P1 | RUL accuracy within ±7 days for 80% of devices |
| 6.4 | Model monitoring: prediction distribution drift alerting | MLOps | 5 | P1 | Alerts fire when prediction distribution shifts significantly |
| 6.5 | Feature importance monitoring (SHAP drift over time) | ML | 3 | P2 | Weekly SHAP comparison reports |
| 6.6 | Performance optimization: batch prediction pipeline | MLOps | 5 | P2 | Batch 1000 devices in < 10 seconds |
| 6.7 | Documentation: architecture diagrams, data dictionary | ML | 3 | P1 | All docs reviewed and complete |
| 6.8 | Documentation: HOW_TO_RUN, Terraform, Azure deployment | MLOps | 3 | P1 | Team can deploy from scratch using docs alone |
| 6.9 | Knowledge transfer sessions (2x 1-hour) | ML + MLOps | 2 | P0 | Team trained on pipeline, monitoring, and troubleshooting |
| 6.10 | Retrospective: lessons learned, technical debt backlog | ML + MLOps | 2 | P1 | Retro document with action items |

**Sprint 6 Total:** 36 story points

---

## Summary

| Sprint | Focus | Points | Duration |
|--------|-------|--------|----------|
| Sprint 1 | Data Foundation & Infrastructure | 39 | Week 1-2 |
| Sprint 2 | PS-1 Failure Prediction + PS-2 Error Patterns | 37 | Week 3-4 |
| Sprint 3 | PS-3 Root Cause + PS-4 Anomaly + PS-5 SLA Risk | 45 | Week 5-6 |
| Sprint 4 | API Serving, Monitoring, Dashboard | 48 | Week 7-8 |
| Sprint 5 | Production Readiness & CI/CD | 54 | Week 9-10 |
| Sprint 6 | Optimization & Handover | 36 | Week 11-12 |
| **Total** | | **259 points** | **12 weeks** |

---

## Team Allocation

| Role | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 | Sprint 5 | Sprint 6 |
|------|----------|----------|----------|----------|----------|----------|
| **ML Engineer** | Data pipeline, Feature engineering | PS-1, PS-2 models | PS-3, PS-4, PS-5 models | React dashboard | A/B testing | Model optimization |
| **MLOps Engineer** | Terraform, Databricks, MLflow setup | Incremental pipeline, Quality checks | Drift detection, Model registry | API, Docker, Monitoring | CI/CD, Blue-Green, Security | Monitoring, Docs |

---

## Definition of Done (DoD)

Each task is considered **done** when:

- [ ] Code is committed to Git with a descriptive message
- [ ] Unit tests pass (where applicable)
- [ ] MLflow experiment has logged metrics and artifacts
- [ ] Pipeline runs end-to-end without errors
- [ ] PR reviewed and approved by at least 1 team member
- [ ] Documentation updated (if applicable)
- [ ] No hardcoded secrets or credentials in code

---

## Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Databricks cluster costs exceed budget | High | Medium | Use spot instances, auto-terminate after 30 min idle |
| Model drift in production | High | High | Automated drift detection (Sprint 3), retraining pipeline (Sprint 5) |
| API latency > SLA | Medium | Low | Auto-scaling (1-5 replicas), load testing (Sprint 5) |
| Data quality issues in raw feed | High | Medium | Great Expectations gates at each layer (Sprint 1) |
| Team member unavailable | Medium | Low | Cross-training, documented runbooks (Sprint 6) |
| Azure service outage | High | Low | Multi-region failover (future sprint) |
