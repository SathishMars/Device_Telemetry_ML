# Kubernetes Deployment with Helm Charts

**Device Telemetry MLOps — London Metro Reader Monitoring System**

---

## Overview

This guide covers deploying the full MLOps stack (FastAPI, MLflow, Prometheus, Grafana) on Kubernetes using Helm charts. It replaces the Docker Compose approach in `monitoring/docker-compose.yml` and adds production-grade features: auto-scaling, self-healing, rolling updates, and namespace isolation.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| kubectl | ≥ 1.28 | Kubernetes CLI |
| helm | ≥ 3.13 | Package manager |
| Docker | ≥ 24 | Build images |
| A K8s cluster | — | Minikube (local) / AKS / GKE / EKS |

```bash
# Verify tools
kubectl version --client
helm version
docker --version

# For local development (Minikube)
minikube start --cpus=4 --memory=8192 --driver=docker
minikube addons enable ingress
minikube addons enable metrics-server
```

---

## Helm Chart Structure

The entire stack is packaged as a single Helm chart with sub-components:

```
helm/
└── telemetry-mlops/
    ├── Chart.yaml              # Chart metadata + dependencies
    ├── values.yaml             # Default values (all environments)
    ├── values-dev.yaml         # Dev overrides (low resources, 1 replica)
    ├── values-staging.yaml     # Staging overrides (medium resources)
    ├── values-prod.yaml        # Prod overrides (HPA, PDB, full replicas)
    └── templates/
        ├── _helpers.tpl        # Shared label/name helpers
        ├── namespace.yaml      # Dedicated namespace
        ├── serviceaccount.yaml # RBAC service account
        ├── secret.yaml         # Sensitive config (mlflow URI, etc.)
        ├── ingress.yaml        # Nginx ingress (routes all services)
        ├── api/
        │   ├── deployment.yaml # FastAPI pods (PS-1 to PS-5)
        │   ├── service.yaml    # ClusterIP service
        │   ├── hpa.yaml        # Horizontal Pod Autoscaler
        │   ├── pdb.yaml        # Pod Disruption Budget
        │   └── configmap.yaml  # Non-sensitive env config
        └── mlflow/
            ├── deployment.yaml # MLflow tracking server
            ├── service.yaml    # ClusterIP service
            └── pvc.yaml        # Persistent volume for mlruns/
```

---

## Chart Files

### `helm/telemetry-mlops/Chart.yaml`

```yaml
apiVersion: v2
name: telemetry-mlops
description: ML Device Telemetry MLOps — London Metro Reader Monitoring
type: application
version: 1.0.0
appVersion: "1.0.0"

dependencies:
  - name: kube-prometheus-stack
    version: "65.1.1"
    repository: https://prometheus-community.github.io/helm-charts
    condition: prometheus.enabled
```

> **Note:** Prometheus + Grafana come from the official `kube-prometheus-stack` dependency — no need to write those templates from scratch.

---

### `helm/telemetry-mlops/values.yaml`

```yaml
# ──────────────────────────────────────────────
# Global settings
# ──────────────────────────────────────────────
global:
  namespace: telemetry-mlops
  imageRegistry: ""          # Set to your ACR/ECR/GCR e.g. myacr.azurecr.io
  imagePullPolicy: IfNotPresent

# ──────────────────────────────────────────────
# FastAPI Telemetry API
# ──────────────────────────────────────────────
api:
  enabled: true
  image:
    repository: telemetry-api
    tag: "latest"
  replicaCount: 2
  port: 8000

  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
    limits:
      cpu: "1000m"
      memory: "2Gi"

  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80

  podDisruptionBudget:
    enabled: true
    minAvailable: 1

  env:
    LOG_LEVEL: "info"
    WORKERS: "2"
    DATA_ARTIFACTS_PATH: "/app/data/artifacts"
    FEATURE_STORE_PATH: "/app/data/feature_store"
    MLFLOW_TRACKING_URI: "http://mlflow:5000"

  # Data volume — model artifacts (ReadOnlyMany or use initContainer)
  persistence:
    enabled: false            # Set true if using PVC for artifacts
    storageClass: "standard"
    size: 5Gi

  service:
    type: ClusterIP
    port: 80
    targetPort: 8000

  ingress:
    path: /api
    pathType: Prefix

  livenessProbe:
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 30
    periodSeconds: 15
    failureThreshold: 3

  readinessProbe:
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 10
    periodSeconds: 10
    failureThreshold: 3

# ──────────────────────────────────────────────
# MLflow Tracking Server
# ──────────────────────────────────────────────
mlflow:
  enabled: true
  image:
    repository: ghcr.io/mlflow/mlflow
    tag: "v2.17.0"
  replicaCount: 1
  port: 5000

  resources:
    requests:
      cpu: "100m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "1Gi"

  persistence:
    enabled: true
    storageClass: "standard"
    size: 10Gi
    mountPath: /mlruns

  service:
    type: ClusterIP
    port: 5000

  ingress:
    path: /mlflow
    pathType: Prefix

# ──────────────────────────────────────────────
# kube-prometheus-stack (Prometheus + Grafana)
# ──────────────────────────────────────────────
kube-prometheus-stack:
  enabled: true

  prometheus:
    prometheusSpec:
      retention: 30d
      resources:
        requests:
          cpu: "200m"
          memory: "512Mi"
        limits:
          cpu: "1000m"
          memory: "2Gi"
      additionalScrapeConfigs:
        - job_name: 'telemetry-api'
          static_configs:
            - targets: ['telemetry-api:80']
          metrics_path: /metrics
          scrape_interval: 15s

  grafana:
    adminUser: admin
    adminPassword: admin            # Override in prod via Secret
    persistence:
      enabled: true
      size: 5Gi
    dashboardProviders:
      dashboardproviders.yaml:
        apiVersion: 1
        providers:
          - name: 'telemetry'
            folder: 'Telemetry MLOps'
            type: file
            options:
              path: /var/lib/grafana/dashboards/telemetry
    dashboardsConfigMaps:
      telemetry: "grafana-dashboards-cm"
    service:
      type: ClusterIP

# ──────────────────────────────────────────────
# Ingress (Nginx)
# ──────────────────────────────────────────────
ingress:
  enabled: true
  className: nginx
  host: telemetry.local             # Change to your domain in prod
  tls:
    enabled: false                  # Set true for HTTPS in prod
    secretName: telemetry-tls

# ──────────────────────────────────────────────
# RBAC
# ──────────────────────────────────────────────
serviceAccount:
  create: true
  name: telemetry-sa
  annotations: {}                   # Add Azure workload-identity annotations here
```

---

### `helm/telemetry-mlops/values-dev.yaml`

```yaml
api:
  replicaCount: 1
  autoscaling:
    enabled: false
  resources:
    requests:
      cpu: "100m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "1Gi"

mlflow:
  persistence:
    storageClass: "standard"
    size: 2Gi

kube-prometheus-stack:
  grafana:
    persistence:
      enabled: false

ingress:
  host: telemetry.dev.local
```

---

### `helm/telemetry-mlops/values-prod.yaml`

```yaml
global:
  imageRegistry: myacr.azurecr.io   # Replace with your ACR name
  imagePullPolicy: Always

api:
  replicaCount: 3
  image:
    tag: "1.2.0"                     # Pin to a specific version in prod
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "2000m"
      memory: "4Gi"

kube-prometheus-stack:
  grafana:
    adminPassword: ""                # Injected from K8s secret in prod
    persistence:
      storageClass: "managed-premium"
      size: 20Gi
  prometheus:
    prometheusSpec:
      retention: 90d
      storageSpec:
        volumeClaimTemplate:
          spec:
            storageClassName: managed-premium
            resources:
              requests:
                storage: 50Gi

ingress:
  host: telemetry.yourdomain.com
  tls:
    enabled: true
    secretName: telemetry-tls-prod
```

---

### `helm/telemetry-mlops/templates/_helpers.tpl`

```go
{{/*
Expand the name of the chart.
*/}}
{{- define "telemetry-mlops.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "telemetry-mlops.labels" -}}
helm.sh/chart: {{ include "telemetry-mlops.name" . }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API selector labels
*/}}
{{- define "telemetry-mlops.api.selectorLabels" -}}
app.kubernetes.io/name: telemetry-api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
MLflow selector labels
*/}}
{{- define "telemetry-mlops.mlflow.selectorLabels" -}}
app.kubernetes.io/name: mlflow
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
```

---

### `helm/telemetry-mlops/templates/serviceaccount.yaml`

```yaml
{{- if .Values.serviceAccount.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.serviceAccount.name }}
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
  {{- with .Values.serviceAccount.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: telemetry-secrets
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
type: Opaque
stringData:
  MLFLOW_TRACKING_URI: "http://mlflow:{{ .Values.mlflow.port }}"
  # Add more secrets here (DB passwords, API keys, etc.)
  # In prod: use External Secrets Operator or Azure Key Vault CSI
```

---

### `helm/telemetry-mlops/templates/api/configmap.yaml`

```yaml
{{- if .Values.api.enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: telemetry-api-config
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
data:
  LOG_LEVEL: {{ .Values.api.env.LOG_LEVEL | quote }}
  WORKERS: {{ .Values.api.env.WORKERS | quote }}
  DATA_ARTIFACTS_PATH: {{ .Values.api.env.DATA_ARTIFACTS_PATH | quote }}
  FEATURE_STORE_PATH: {{ .Values.api.env.FEATURE_STORE_PATH | quote }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/api/deployment.yaml`

```yaml
{{- if .Values.api.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telemetry-api
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
    {{- include "telemetry-mlops.api.selectorLabels" . | nindent 4 }}
spec:
  {{- if not .Values.api.autoscaling.enabled }}
  replicas: {{ .Values.api.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "telemetry-mlops.api.selectorLabels" . | nindent 6 }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0          # Zero-downtime rolling updates
  template:
    metadata:
      labels:
        {{- include "telemetry-mlops.api.selectorLabels" . | nindent 8 }}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "{{ .Values.api.port }}"
        prometheus.io/path: "/metrics"
        checksum/config: {{ include (print $.Template.BasePath "/api/configmap.yaml") . | sha256sum }}
    spec:
      serviceAccountName: {{ .Values.serviceAccount.name }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: telemetry-api
          image: "{{ .Values.global.imageRegistry }}/{{ .Values.api.image.repository }}:{{ .Values.api.image.tag }}"
          imagePullPolicy: {{ .Values.global.imagePullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.api.port }}
              protocol: TCP
          envFrom:
            - configMapRef:
                name: telemetry-api-config
            - secretRef:
                name: telemetry-secrets
          livenessProbe:
            {{- toYaml .Values.api.livenessProbe | nindent 12 }}
          readinessProbe:
            {{- toYaml .Values.api.readinessProbe | nindent 12 }}
          resources:
            {{- toYaml .Values.api.resources | nindent 12 }}
          volumeMounts:
            - name: artifacts
              mountPath: /app/data/artifacts
              readOnly: true
            - name: feature-store
              mountPath: /app/data/feature_store
              readOnly: true
      volumes:
        - name: artifacts
          {{- if .Values.api.persistence.enabled }}
          persistentVolumeClaim:
            claimName: telemetry-artifacts-pvc
          {{- else }}
          emptyDir: {}
          {{- end }}
        - name: feature-store
          emptyDir: {}
      terminationGracePeriodSeconds: 30
{{- end }}
```

---

### `helm/telemetry-mlops/templates/api/service.yaml`

```yaml
{{- if .Values.api.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: telemetry-api
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
    {{- include "telemetry-mlops.api.selectorLabels" . | nindent 4 }}
spec:
  type: {{ .Values.api.service.type }}
  ports:
    - port: {{ .Values.api.service.port }}
      targetPort: {{ .Values.api.service.targetPort }}
      protocol: TCP
      name: http
  selector:
    {{- include "telemetry-mlops.api.selectorLabels" . | nindent 4 }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/api/hpa.yaml`

```yaml
{{- if and .Values.api.enabled .Values.api.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: telemetry-api-hpa
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: telemetry-api
  minReplicas: {{ .Values.api.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.api.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.api.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.api.autoscaling.targetMemoryUtilizationPercentage }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/api/pdb.yaml`

```yaml
{{- if and .Values.api.enabled .Values.api.podDisruptionBudget.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: telemetry-api-pdb
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
spec:
  minAvailable: {{ .Values.api.podDisruptionBudget.minAvailable }}
  selector:
    matchLabels:
      {{- include "telemetry-mlops.api.selectorLabels" . | nindent 6 }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/mlflow/pvc.yaml`

```yaml
{{- if and .Values.mlflow.enabled .Values.mlflow.persistence.enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mlflow-data-pvc
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: {{ .Values.mlflow.persistence.storageClass }}
  resources:
    requests:
      storage: {{ .Values.mlflow.persistence.size }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/mlflow/deployment.yaml`

```yaml
{{- if .Values.mlflow.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
    {{- include "telemetry-mlops.mlflow.selectorLabels" . | nindent 4 }}
spec:
  replicas: {{ .Values.mlflow.replicaCount }}
  selector:
    matchLabels:
      {{- include "telemetry-mlops.mlflow.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "telemetry-mlops.mlflow.selectorLabels" . | nindent 8 }}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: mlflow
          image: "{{ .Values.mlflow.image.repository }}:{{ .Values.mlflow.image.tag }}"
          imagePullPolicy: {{ .Values.global.imagePullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.mlflow.port }}
          args:
            - mlflow
            - server
            - --host=0.0.0.0
            - --port={{ .Values.mlflow.port }}
            - --backend-store-uri=sqlite:///{{ .Values.mlflow.persistence.mountPath }}/mlflow.db
            - --default-artifact-root={{ .Values.mlflow.persistence.mountPath }}/artifacts
          resources:
            {{- toYaml .Values.mlflow.resources | nindent 12 }}
          volumeMounts:
            - name: mlflow-data
              mountPath: {{ .Values.mlflow.persistence.mountPath }}
      volumes:
        - name: mlflow-data
          {{- if .Values.mlflow.persistence.enabled }}
          persistentVolumeClaim:
            claimName: mlflow-data-pvc
          {{- else }}
          emptyDir: {}
          {{- end }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/mlflow/service.yaml`

```yaml
{{- if .Values.mlflow.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: mlflow
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
    {{- include "telemetry-mlops.mlflow.selectorLabels" . | nindent 4 }}
spec:
  type: {{ .Values.mlflow.service.type }}
  ports:
    - port: {{ .Values.mlflow.service.port }}
      targetPort: {{ .Values.mlflow.port }}
      protocol: TCP
      name: http
  selector:
    {{- include "telemetry-mlops.mlflow.selectorLabels" . | nindent 4 }}
{{- end }}
```

---

### `helm/telemetry-mlops/templates/ingress.yaml`

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: telemetry-ingress
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "telemetry-mlops.labels" . | nindent 4 }}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
spec:
  ingressClassName: {{ .Values.ingress.className }}
  {{- if .Values.ingress.tls.enabled }}
  tls:
    - hosts:
        - {{ .Values.ingress.host }}
      secretName: {{ .Values.ingress.tls.secretName }}
  {{- end }}
  rules:
    - host: {{ .Values.ingress.host }}
      http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: telemetry-api
                port:
                  number: {{ .Values.api.service.port }}
          - path: /mlflow(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: mlflow
                port:
                  number: {{ .Values.mlflow.service.port }}
          - path: /grafana(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: telemetry-mlops-grafana
                port:
                  number: 80
{{- end }}
```

---

## Deployment Steps

### Step 1: Add Helm Repositories

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

### Step 2: Update Helm Dependencies

```bash
cd helm/telemetry-mlops
helm dependency update
```

This downloads `kube-prometheus-stack` into `charts/`.

### Step 3: Build and Push the API Image

```bash
# Build the API image (same Dockerfile as before)
docker build -t telemetry-api:latest -f api/Dockerfile .

# Tag for your registry (e.g., Minikube local registry)
minikube image load telemetry-api:latest

# Or for ACR (Azure):
# az acr build --registry myacr --image telemetry-api:latest --file api/Dockerfile .
```

### Step 4: Install the Chart (Development)

```bash
helm install telemetry-dev helm/telemetry-mlops \
  --namespace telemetry-mlops \
  --create-namespace \
  --values helm/telemetry-mlops/values-dev.yaml
```

### Step 5: Verify Deployment

```bash
# Check all pods are Running
kubectl get pods -n telemetry-mlops

# Expected output:
# NAME                              READY   STATUS    RESTARTS
# telemetry-api-7d9b8f6-xxxx       1/1     Running   0
# mlflow-6c5b7d8-xxxx              1/1     Running   0
# telemetry-dev-grafana-xxxx       1/1     Running   0
# prometheus-xxxx                  1/1     Running   0

# Check services
kubectl get svc -n telemetry-mlops

# Check ingress
kubectl get ingress -n telemetry-mlops
```

### Step 6: Access Services (Minikube)

```bash
# Add to /etc/hosts
echo "$(minikube ip) telemetry.local" | sudo tee -a /etc/hosts

# Services are now available at:
# API:      http://telemetry.local/api/
# MLflow:   http://telemetry.local/mlflow/
# Grafana:  http://telemetry.local/grafana/  (admin / admin)
# Prometheus: port-forward only
kubectl port-forward -n telemetry-mlops svc/prometheus-operated 9090:9090
```

### Step 7: Install for Production

```bash
helm upgrade --install telemetry-prod helm/telemetry-mlops \
  --namespace telemetry-mlops-prod \
  --create-namespace \
  --values helm/telemetry-mlops/values-prod.yaml \
  --set global.imageRegistry=myacr.azurecr.io \
  --set api.image.tag=1.2.0 \
  --atomic \
  --timeout 5m
```

---

## Rolling Updates (Zero-Downtime)

```bash
# Update to a new image version
helm upgrade telemetry-prod helm/telemetry-mlops \
  --namespace telemetry-mlops-prod \
  --values helm/telemetry-mlops/values-prod.yaml \
  --set api.image.tag=1.3.0

# Watch the rollout
kubectl rollout status deployment/telemetry-api -n telemetry-mlops-prod

# Rollback if needed
helm rollback telemetry-prod 1 -n telemetry-mlops-prod
```

---

## Blue-Green Deployment with Kubernetes

Kubernetes replaces the Nginx `docker-compose.blue-green.yml` with labels and Services:

```bash
# Deploy blue version
helm upgrade telemetry-prod helm/telemetry-mlops \
  --set api.image.tag=1.2.0 \
  --set api.deploymentSuffix=blue

# Deploy green version alongside (does NOT replace blue yet)
helm install telemetry-green helm/telemetry-mlops \
  --namespace telemetry-mlops-prod \
  --values helm/telemetry-mlops/values-prod.yaml \
  --set api.image.tag=1.3.0 \
  --set api.deploymentSuffix=green

# Switch traffic: patch the service selector to point to green
kubectl patch svc telemetry-api -n telemetry-mlops-prod \
  -p '{"spec":{"selector":{"version":"green"}}}'

# After validation: remove blue
helm uninstall telemetry-green -n telemetry-mlops-prod
```

---

## Monitoring Integration

The `kube-prometheus-stack` dependency automatically:
- Scrapes all pods with `prometheus.io/scrape: "true"` annotation
- Discovers the 28 custom metrics from `/metrics` on port 8000
- Provides Grafana at `/grafana/` with your existing dashboard JSON

To import the existing Grafana dashboards:

```bash
# Create ConfigMap from existing dashboard JSON files
kubectl create configmap grafana-dashboards-cm \
  --from-file=monitoring/grafana/dashboards/ \
  --namespace telemetry-mlops

# Grafana auto-loads them via dashboardsConfigMaps in values.yaml
```

---

## Uninstall

```bash
# Remove the release
helm uninstall telemetry-dev -n telemetry-mlops

# Remove the namespace (deletes all resources)
kubectl delete namespace telemetry-mlops
```
