# Docker Compose vs Kubernetes — Migration Guide

**Device Telemetry MLOps — What Changes, What Stays the Same**

---

## Quick Summary

| Aspect | Docker Compose (Current) | Kubernetes + Helm (New) |
|--------|--------------------------|-------------------------|
| **Orchestration** | `docker-compose up` (single machine) | `helm install` (cluster-aware) |
| **Scaling** | Manual — edit `replicas:` in compose file | Automatic — HPA scales on CPU/memory |
| **Self-healing** | Container restarts on failure | Pod restarts + reschedules to healthy node |
| **Traffic routing** | `nginx.conf` + `docker-compose.blue-green.yml` | Ingress controller + Service selectors |
| **Config management** | `.env` files or inline in compose YAML | ConfigMaps + Secrets (base64-encoded) |
| **Persistent storage** | Docker volumes (host-local) | PersistentVolumeClaims (cluster-wide) |
| **Rolling updates** | `docker compose up --build` (brief downtime) | Zero-downtime RollingUpdate strategy |
| **Blue-Green** | Duplicate compose file + Nginx swap | Patch Service selector, no extra Nginx |
| **Local dev** | `docker compose up` — works anywhere | Requires Minikube or a K8s cluster |
| **Monitoring** | Prometheus scrapes `localhost:8000` | Annotations on pods, auto-discovered |
| **Secrets** | Plaintext in compose file | K8s Secrets (+ External Secrets / Key Vault) |

---

## What Changes

### 1. No More `docker-compose.yml`

**Before (monitoring/docker-compose.yml):**
```yaml
services:
  telemetry-api:
    build: { context: .., dockerfile: api/Dockerfile }
    ports: ["8000:8000"]

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
```

**After (Helm values.yaml + Chart.yaml dependency):**
```yaml
# values.yaml defines all the same services
# kube-prometheus-stack dependency handles Prometheus + Grafana together
# No port-mapping needed — Ingress routes all traffic
```

**Key difference:** Docker Compose binds ports to the host machine. Kubernetes uses internal DNS (`telemetry-api.telemetry-mlops.svc.cluster.local`) and exposes only what you specify through the Ingress.

---

### 2. Dockerfile — No Changes Required

The existing [api/Dockerfile](../api/Dockerfile) works unchanged:

```dockerfile
FROM python:3.10-slim          # Same base
WORKDIR /app
COPY requirements.txt .
RUN pip install ...
COPY api/ ./api/
COPY data/artifacts/ ./data/artifacts/
COPY data/feature_store/ ./data/feature_store/
RUN useradd -m appuser ...     # Non-root user — K8s security context also enforces this
USER appuser
EXPOSE 8000
HEALTHCHECK ...                # K8s uses livenessProbe/readinessProbe instead (overlapping)
CMD ["uvicorn", "api.main:app", ...]
```

> **Tip:** The `HEALTHCHECK` instruction in the Dockerfile is ignored by Kubernetes. K8s uses its own `livenessProbe` and `readinessProbe` defined in the Deployment template. Both check the same `/health` endpoint.

---

### 3. `prometheus.yml` — No Longer Needed as a File

**Before (monitoring/prometheus.yml):**
```yaml
# Mounted as a volume into the prometheus container
scrape_configs:
  - job_name: 'telemetry-api'
    static_configs:
      - targets: ['localhost:8000']
```

**After:** Prometheus discovers scrape targets automatically via pod annotations:
```yaml
# In api/deployment.yaml template (already included)
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

The `additionalScrapeConfigs` in `values.yaml` provides a fallback static config, but annotation-based discovery is preferred in K8s.

---

### 4. `nginx.conf` (Blue-Green) — Replaced by K8s Services

**Before (monitoring/nginx.conf):**
```nginx
upstream blue  { server telemetry-api-blue:8000; }
upstream green { server telemetry-api-green:8000; }

# Traffic split controlled here — manual file edit required
location / { proxy_pass http://blue; }
```

**After:** No Nginx needed for routing. Kubernetes Service selectors switch traffic:
```bash
# Switch all traffic from blue to green — zero-downtime, no config file edit
kubectl patch svc telemetry-api -n telemetry-mlops-prod \
  -p '{"spec":{"selector":{"version":"green"}}}'
```

The Nginx Ingress controller (installed as a K8s addon) replaces the standalone Nginx container.

---

### 5. GitHub Actions CI/CD — Add `helm upgrade` Step

**Current `ci-cd.yml` deploy step (Azure Container Apps):**
```yaml
- name: Deploy to Azure Container Apps
  run: az containerapp update --name telemetry-api ...
  if: env.AZURE_ENABLED == 'true'
```

**New step (Kubernetes/Helm):**
```yaml
- name: Setup kubectl + helm
  uses: azure/setup-kubectl@v4
  # OR: uses: google-github-actions/setup-gcloud@v2 for GKE

- name: Deploy with Helm
  run: |
    helm upgrade --install telemetry-prod helm/telemetry-mlops \
      --namespace telemetry-mlops-prod \
      --create-namespace \
      --values helm/telemetry-mlops/values-prod.yaml \
      --set global.imageRegistry=${{ secrets.ACR_REGISTRY }} \
      --set api.image.tag=${{ github.sha }} \
      --atomic \
      --timeout 5m
```

**What `--atomic` does:** If the upgrade fails (pods crash, readiness probe fails), Helm automatically rolls back to the previous release. This replaces the manual rollback logic in the current workflow.

---

### 6. Environment Variables / Config

**Before (Docker Compose):**
```yaml
# Inline in docker-compose.yml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=admin
```

**After (Kubernetes):**
```bash
# Non-sensitive: ConfigMap
kubectl create configmap telemetry-api-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=WORKERS=2

# Sensitive: Secret
kubectl create secret generic telemetry-secrets \
  --from-literal=MLFLOW_TRACKING_URI=http://mlflow:5000

# Production: use External Secrets Operator → Azure Key Vault
```

---

### 7. Persistent Storage

**Before (Docker Compose):**
```yaml
volumes:
  prometheus-data:     # Lives on the Docker host, lost if host fails
  grafana-data:
```

**After (Kubernetes PVC):**
```yaml
# PersistentVolumeClaim backed by cloud storage (AzureDisk, EBS, GCE PD)
# Survives pod restarts, node failures, and cluster upgrades
storageClassName: managed-premium   # Azure SSD
size: 50Gi
```

---

## What Stays the Same

| Component | Status | Notes |
|-----------|--------|-------|
| `api/Dockerfile` | **No change** | Same image, same CMD |
| `api/main.py` (FastAPI) | **No change** | Same endpoints, same Prometheus metrics |
| `requirements.txt` | **No change** | Same Python dependencies |
| Prometheus metrics (28) | **No change** | Same `/metrics` endpoint |
| Grafana dashboards JSON | **No change** | Loaded via ConfigMap instead of volume |
| `tests/test_api.py` | **No change** | Test against the same API |
| React dashboard | **No change** | Still served from `npm run dev` or a CDN |
| MLflow tracking | **No change** | Same SQLite backend, now in a PVC |
| `.github/workflows/retrain.yml` | **Minor change** | Add `helm upgrade` for new image |

---

## Feature Comparison Table

| Feature | Docker Compose | Kubernetes + Helm |
|---------|----------------|-------------------|
| **Start all services** | `docker compose up -d` | `helm install telemetry-dev helm/telemetry-mlops` |
| **Stop all services** | `docker compose down` | `helm uninstall telemetry-dev` |
| **Scale API to 5 replicas** | Edit compose file, restart | `kubectl scale deployment telemetry-api --replicas=5` |
| **Auto-scale on CPU** | Not supported | HPA (automatic, no manual step) |
| **Rolling update** | Brief downtime | Zero-downtime (`maxUnavailable: 0`) |
| **Roll back a bad deploy** | `docker compose up` old image | `helm rollback telemetry-prod 1` |
| **Blue-Green traffic switch** | Edit `nginx.conf` + restart | `kubectl patch svc` — instant |
| **Health checks** | `HEALTHCHECK` in Dockerfile | `livenessProbe` + `readinessProbe` in Deployment |
| **Pod self-healing** | Container restart only | Pod reschedules to another node |
| **Resource limits** | `mem_limit` / `cpus` in compose | `resources.limits` + `requests` per container |
| **Namespace isolation** | No isolation between services | Dedicated namespace per environment |
| **Multi-environment** | Duplicate compose files | `values-dev.yaml`, `values-prod.yaml` |
| **Secret management** | Plaintext in compose / `.env` | K8s Secrets → External Secrets (Key Vault) |
| **Storage** | Host-local Docker volumes | PVCs backed by cloud storage |
| **Service discovery** | Container name DNS | K8s internal DNS (pod-to-pod) |
| **Load balancing** | None (single container) | K8s Service distributes across all replicas |
| **Ingress / TLS** | Nginx container + config file | Nginx Ingress Controller + cert-manager |
| **Deploy history** | No history | `helm history telemetry-prod` (full audit) |
| **Dry-run before apply** | Not supported | `helm upgrade --dry-run` |

---

## Migration Steps (Docker Compose → Kubernetes)

```bash
# Step 1: Stop Docker Compose stack
cd monitoring
docker compose down

# Step 2: Build and tag the existing image
docker build -t telemetry-api:latest -f api/Dockerfile .
minikube image load telemetry-api:latest

# Step 3: Add Helm repo and update dependencies
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm dependency update helm/telemetry-mlops

# Step 4: Install (dev)
helm install telemetry-dev helm/telemetry-mlops \
  --namespace telemetry-mlops \
  --create-namespace \
  --values helm/telemetry-mlops/values-dev.yaml

# Step 5: Import existing Grafana dashboards
kubectl create configmap grafana-dashboards-cm \
  --from-file=monitoring/grafana/dashboards/ \
  --namespace telemetry-mlops

# Step 6: Verify everything works
kubectl get pods -n telemetry-mlops
kubectl port-forward svc/telemetry-api 8000:80 -n telemetry-mlops
curl http://localhost:8000/health
```

---

## When to Use Which

| Use Docker Compose when | Use Kubernetes when |
|------------------------|---------------------|
| Local development / laptop | Staging / production |
| Quick demo or single-machine | Multi-node HA cluster |
| No Kubernetes cluster available | Auto-scaling is required |
| Team unfamiliar with K8s | Zero-downtime deploys required |
| Simplicity > features | Need deployment history + rollback |

> **Recommended:** Keep Docker Compose for local development (`docker compose up` is faster to start). Use Kubernetes + Helm for staging and production. Both use the same `api/Dockerfile` — no duplication.

---

## Files Summary

| File | Action |
|------|--------|
| `monitoring/docker-compose.yml` | Keep for local dev |
| `monitoring/docker-compose.blue-green.yml` | Replaced by K8s Service patching |
| `monitoring/nginx.conf` | Replaced by Nginx Ingress Controller |
| `monitoring/prometheus.yml` | Replaced by pod annotations + values.yaml |
| `api/Dockerfile` | No change |
| `api/main.py` | No change |
| `.github/workflows/ci-cd.yml` | Add `helm upgrade` step |
| `.github/workflows/retrain.yml` | Add `helm upgrade` step after retrain |
| `helm/telemetry-mlops/` | **New** — see KUBERNETES_DEPLOYMENT.md |
