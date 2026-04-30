# Agent Task Spec: Stage 13 - Kubernetes and Minikube

Encoding note:
This file is ASCII-only on purpose.
It contains no Cyrillic text and no typographic Unicode characters.
Use this version if the agent console shows broken Russian text.

---

## 0. Context

The project is a polyglot monorepo for a dark kitchen order fulfillment system.

Previous stages should already exist:

```text
Stage 1:
  libs/python/dk-common

Stage 2:
  kitchen-service

Stage 3:
  menu-service

Stage 4:
  fulfillment-service

Stage 5:
  Redis Streams and queued tasks

Stage 6:
  KDS inside Kitchen Service

Stage 7:
  Fulfillment internal task transitions

Stage 8:
  Kitchen Scheduler Worker in Go

Stage 9:
  KDS claim and complete

Stage 10:
  Station Simulator Service

Stage 11:
  Metrics, Mongo events, Prometheus, Grafana

Stage 12:
  Docker Compose demo
```

This stage is about Kubernetes deployment for local Minikube.

The system must be deployable to Minikube with Kubernetes manifests or kustomize.

---

## 1. Goal

Prepare Kubernetes / Minikube deployment.

At the end of this stage:

```text
1. Kubernetes manifests exist.
2. Minikube can deploy all MVP services.
3. API services run as Deployments.
4. Go worker runs as Deployment.
5. PostgreSQL runs as StatefulSet with PVC.
6. Redis runs as StatefulSet or Deployment.
7. MongoDB runs as StatefulSet or Deployment.
8. Services expose internal DNS names.
9. ConfigMap and Secret provide configuration.
10. Ingress exposes:
   - /orders
   - /kds/stations/{station_id}/tasks
11. Prometheus and Grafana can run in Minikube.
12. README documents the Minikube deployment flow.
```

Stage boundary:

```text
This stage creates Kubernetes deployment artifacts.
This stage must not implement new business logic.
This stage must not rewrite service code except for Kubernetes readiness needs.
This stage must not require a managed cloud Kubernetes cluster.
```

---

## 2. Scope

Implement:

```text
1. deploy/k8s/base manifests.
2. deploy/k8s/overlays/minikube kustomize overlay.
3. Deployments for application services:
   - kitchen-service
   - menu-service
   - fulfillment-service
   - kitchen-scheduler-worker
   - station-simulator-service
4. StatefulSet or Deployment for infrastructure:
   - postgres
   - redis
   - mongo
5. Services for all networked components.
6. PVCs for stateful components.
7. ConfigMap for non-secret env vars.
8. Secret for passwords and sensitive env vars.
9. Ingress for external access.
10. Optional jobs for Alembic migrations.
11. Optional job for demo seed data.
12. Minikube README.
13. Smoke test commands.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- Helm charts
- production cloud deployment
- managed PostgreSQL
- managed Redis
- managed MongoDB
- cert-manager
- TLS certificates
- service mesh
- Linkerd
- Istio
- autoscaling unless trivial
- production-grade secrets management
- new integration tests
- new business endpoints
```

Optional but not required:

```text
- HorizontalPodAutoscaler
- NetworkPolicy
- ServiceMonitor CRDs
```

Do not add CRDs that require external operators unless explicitly documented.

---

## 4. Expected directory layout

Create or update:

```text
deploy/
  k8s/
    base/
      namespace.yaml

      kitchen-service/
        deployment.yaml
        service.yaml

      menu-service/
        deployment.yaml
        service.yaml

      fulfillment-service/
        deployment.yaml
        service.yaml

      kitchen-scheduler-worker/
        deployment.yaml
        service.yaml optional

      station-simulator-service/
        deployment.yaml
        service.yaml

      postgres/
        statefulset.yaml
        service.yaml
        pvc.yaml optional
        init-configmap.yaml optional

      redis/
        statefulset.yaml
        service.yaml
        pvc.yaml optional

      mongo/
        statefulset.yaml
        service.yaml
        pvc.yaml optional

      prometheus/
        deployment.yaml
        service.yaml
        configmap.yaml

      grafana/
        deployment.yaml
        service.yaml
        configmap-dashboards.yaml optional
        configmap-provisioning.yaml optional

      configmap.yaml
      secret.yaml
      ingress.yaml
      kustomization.yaml

    overlays/
      minikube/
        kustomization.yaml
        ingress-patch.yaml optional
        configmap-patch.yaml optional

      demo/
        kustomization.yaml optional
        station-simulator-patch.yaml optional

scripts/
  k8s/
    minikube-build-images.sh
    deploy-minikube.sh
    run-migrations.sh
    seed-demo-k8s.sh optional
    wait-for-k8s.sh optional

docs/
  k8s/
    minikube.md
```

If the educational task requires the path:

```text
practice3/k8s/
```

then either:

```text
1. duplicate manifests there
```

or:

```text
2. add a README there pointing to deploy/k8s
```

Preferred canonical path:

```text
deploy/k8s
```

---

## 5. Namespace

Create namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dark-kitchen
```

All resources should be in:

```text
dark-kitchen
```

kustomization.yaml should include namespace:

```yaml
namespace: dark-kitchen
```

---

## 6. Images

### 6.1. Image names

Use local image names for Minikube:

```text
dark-kitchen/kitchen-service:local
dark-kitchen/menu-service:local
dark-kitchen/fulfillment-service:local
dark-kitchen/kitchen-scheduler-worker:local
dark-kitchen/station-simulator-service:local
```

### 6.2. Image pull policy

For Minikube local images:

```yaml
imagePullPolicy: IfNotPresent
```

or:

```yaml
imagePullPolicy: Never
```

Recommended:

```text
If using minikube image load, use IfNotPresent.
If using eval $(minikube docker-env), use Never or IfNotPresent.
```

Document the chosen approach.

### 6.3. Build script

Create:

```text
scripts/k8s/minikube-build-images.sh
```

Recommended approach:

```bash
#!/usr/bin/env bash
set -euo pipefail

docker build -f services/kitchen-service/Dockerfile -t dark-kitchen/kitchen-service:local .
docker build -f services/menu-service/Dockerfile -t dark-kitchen/menu-service:local .
docker build -f services/fulfillment-service/Dockerfile -t dark-kitchen/fulfillment-service:local .
docker build -f services/kitchen-scheduler-worker/Dockerfile -t dark-kitchen/kitchen-scheduler-worker:local .
docker build -f services/station-simulator-service/Dockerfile -t dark-kitchen/station-simulator-service:local .

minikube image load dark-kitchen/kitchen-service:local
minikube image load dark-kitchen/menu-service:local
minikube image load dark-kitchen/fulfillment-service:local
minikube image load dark-kitchen/kitchen-scheduler-worker:local
minikube image load dark-kitchen/station-simulator-service:local
```

Alternative:

```bash
eval $(minikube docker-env)
docker build ...
```

Either is acceptable.
README must document one clear path.

---

## 7. ConfigMap

Create:

```text
deploy/k8s/base/configmap.yaml
```

ConfigMap name:

```text
dark-kitchen-config
```

Include non-secret configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dark-kitchen-config
data:
  ENVIRONMENT: "k8s"
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"

  KITCHEN_SERVICE_URL: "http://kitchen-service:8000"
  MENU_SERVICE_URL: "http://menu-service:8000"
  FULFILLMENT_SERVICE_URL: "http://fulfillment-service:8000"

  REDIS_URL: "redis://redis:6379/0"
  REDIS_STREAM_PATTERNS: "stream:kitchen:*:station:*"
  REDIS_CONSUMER_GROUP: "group:kitchen-scheduler-workers"

  MONGO_URL: "mongodb://mongo:27017"
  MONGO_DATABASE: "dark_kitchen_events"
  MONGO_EVENTS_ENABLED: "true"

  HTTP_TIMEOUT_SECONDS: "3"
  HTTP_TIMEOUT_MS: "3000"

  WORKER_ID: "scheduler-worker-1"
  STREAM_SCAN_INTERVAL_MS: "500"
  XREAD_BLOCK_MS: "5000"
  XREAD_COUNT: "10"
  MAX_DISPATCH_ATTEMPTS: "5"
  DISPATCH_BACKOFF_BASE_MS: "1000"
  DISPATCH_BACKOFF_MAX_MS: "30000"
  PROMETHEUS_PORT: "9090"

  SIMULATOR_ENABLED: "true"
  SIMULATOR_SPEED_FACTOR: "60"
  SIMULATOR_POLL_INTERVAL_MS: "1000"
  SIMULATOR_WORKERS_CONFIG: ""
```

Note:

```text
SIMULATOR_WORKERS_CONFIG may require station IDs from seeded data.
For Stage 13, it can be set manually after seed or patched in overlay.
```

---

## 8. Secret

Create:

```text
deploy/k8s/base/secret.yaml
```

Secret name:

```text
dark-kitchen-secret
```

Example with stringData:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dark-kitchen-secret
type: Opaque
stringData:
  POSTGRES_USER: "postgres"
  POSTGRES_PASSWORD: "postgres"

  KITCHEN_DATABASE_URL: "postgresql+asyncpg://postgres:postgres@postgres:5432/kitchen_service"
  MENU_DATABASE_URL: "postgresql+asyncpg://postgres:postgres@postgres:5432/menu_service"
  FULFILLMENT_DATABASE_URL: "postgresql+asyncpg://postgres:postgres@postgres:5432/fulfillment_service"
```

This is acceptable for local Minikube only.

Do not claim it is production secure.

---

## 9. PostgreSQL

### 9.1. StatefulSet

Create:

```text
deploy/k8s/base/postgres/statefulset.yaml
```

Requirements:

```text
image: postgres:16
serviceName: postgres
containerPort: 5432
PVC mounted to /var/lib/postgresql/data
env from dark-kitchen-secret
readinessProbe with pg_isready
livenessProbe with pg_isready
```

Example env:

```yaml
env:
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: dark-kitchen-secret
        key: POSTGRES_USER
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: dark-kitchen-secret
        key: POSTGRES_PASSWORD
  - name: POSTGRES_DB
    value: postgres
```

### 9.2. Database init

Need databases:

```text
kitchen_service
menu_service
fulfillment_service
```

Recommended for Minikube:

```text
Use initdb ConfigMap mounted to /docker-entrypoint-initdb.d.
```

Create:

```text
deploy/k8s/base/postgres/init-configmap.yaml
```

SQL:

```sql
CREATE DATABASE kitchen_service;
CREATE DATABASE menu_service;
CREATE DATABASE fulfillment_service;
```

Important:

```text
This runs only when the Postgres data directory is empty.
If PVC already exists, delete PVC to re-run init.
```

### 9.3. Service

Create:

```text
deploy/k8s/base/postgres/service.yaml
```

Service name:

```text
postgres
```

Port:

```text
5432
```

### 9.4. PVC

Use volumeClaimTemplates in StatefulSet or separate PVC.

For StatefulSet, volumeClaimTemplates is recommended.

Storage:

```text
1Gi
```

---

## 10. Redis

Create:

```text
deploy/k8s/base/redis/statefulset.yaml
deploy/k8s/base/redis/service.yaml
```

Requirements:

```text
image: redis:7
containerPort: 6379
service name: redis
readinessProbe: redis-cli ping
livenessProbe: redis-cli ping
```

Persistence:

```text
PVC optional for MVP.
```

Recommended:

```text
Use StatefulSet with PVC for consistency.
```

Storage:

```text
1Gi
```

---

## 11. MongoDB

Create:

```text
deploy/k8s/base/mongo/statefulset.yaml
deploy/k8s/base/mongo/service.yaml
```

Requirements:

```text
image: mongo:7
containerPort: 27017
service name: mongo
readinessProbe: mongosh --eval db.adminCommand('ping')
livenessProbe: mongosh --eval db.adminCommand('ping')
```

Persistence:

```text
PVC recommended.
```

Storage:

```text
1Gi
```

No authentication is acceptable for local Minikube MVP if documented.

---

## 12. Python API service Deployments

Services:

```text
kitchen-service
menu-service
fulfillment-service
station-simulator-service
```

Each should have:

```text
Deployment
Service
containerPort 8000
readinessProbe /health
livenessProbe /health
env from ConfigMap and Secret
resources requests/limits
```

### 12.1. Common Python deployment pattern

Example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kitchen-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kitchen-service
  template:
    metadata:
      labels:
        app: kitchen-service
    spec:
      containers:
        - name: kitchen-service
          image: dark-kitchen/kitchen-service:local
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: dark-kitchen-config
          env:
            - name: SERVICE_NAME
              value: kitchen-service
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: dark-kitchen-secret
                  key: KITCHEN_DATABASE_URL
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 10
```

Use correct DATABASE_URL key per service:

```text
kitchen-service -> KITCHEN_DATABASE_URL
menu-service -> MENU_DATABASE_URL
fulfillment-service -> FULFILLMENT_DATABASE_URL
station-simulator-service -> no DATABASE_URL
```

### 12.2. Service object

Example:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kitchen-service
spec:
  selector:
    app: kitchen-service
  ports:
    - name: http
      port: 8000
      targetPort: 8000
```

Use service names exactly as internal URLs expect:

```text
kitchen-service
menu-service
fulfillment-service
station-simulator-service
```

---

## 13. Go worker Deployment

Create:

```text
deploy/k8s/base/kitchen-scheduler-worker/deployment.yaml
```

Requirements:

```text
Deployment
replicas: 1 initially
containerPort 9090 for metrics/health
env from ConfigMap
readinessProbe /health on 9090
livenessProbe /health on 9090
```

Example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kitchen-scheduler-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kitchen-scheduler-worker
  template:
    metadata:
      labels:
        app: kitchen-scheduler-worker
    spec:
      containers:
        - name: kitchen-scheduler-worker
          image: dark-kitchen/kitchen-scheduler-worker:local
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 9090
          envFrom:
            - configMapRef:
                name: dark-kitchen-config
          env:
            - name: SERVICE_NAME
              value: kitchen-scheduler-worker
          readinessProbe:
            httpGet:
              path: /health
              port: 9090
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 9090
            initialDelaySeconds: 15
            periodSeconds: 10
```

Service for worker is optional but useful for Prometheus:

```text
kitchen-scheduler-worker service on port 9090
```

---

## 14. Prometheus

Create:

```text
deploy/k8s/base/prometheus/configmap.yaml
deploy/k8s/base/prometheus/deployment.yaml
deploy/k8s/base/prometheus/service.yaml
```

Prometheus config must scrape:

```text
kitchen-service:8000
menu-service:8000
fulfillment-service:8000
station-simulator-service:8000
kitchen-scheduler-worker:9090
```

Example scrape config:

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: kitchen-service
    static_configs:
      - targets: ["kitchen-service:8000"]

  - job_name: menu-service
    static_configs:
      - targets: ["menu-service:8000"]

  - job_name: fulfillment-service
    static_configs:
      - targets: ["fulfillment-service:8000"]

  - job_name: station-simulator-service
    static_configs:
      - targets: ["station-simulator-service:8000"]

  - job_name: kitchen-scheduler-worker
    static_configs:
      - targets: ["kitchen-scheduler-worker:9090"]
```

For MVP, static scrape config is fine.

No Prometheus Operator required.

---

## 15. Grafana

Create:

```text
deploy/k8s/base/grafana/deployment.yaml
deploy/k8s/base/grafana/service.yaml
```

Optional but recommended:

```text
ConfigMap for datasource provisioning.
ConfigMap for dashboards.
```

Minimum:

```text
Grafana Deployment and Service.
```

Admin credentials for local Minikube can be plain env values:

```yaml
env:
  - name: GF_SECURITY_ADMIN_USER
    value: admin
  - name: GF_SECURITY_ADMIN_PASSWORD
    value: admin
```

Document that this is local only.

Service:

```text
grafana:3000
```

Access via:

```bash
kubectl port-forward svc/grafana 3000:3000 -n dark-kitchen
```

---

## 16. Ingress

Create:

```text
deploy/k8s/base/ingress.yaml
```

Host:

```text
dark-kitchen.local
```

Required external routes:

```text
http://dark-kitchen.local/orders
http://dark-kitchen.local/kds/stations/{station_id}/tasks
```

Ingress should route:

```text
/orders -> fulfillment-service:8000
/orders/* -> fulfillment-service:8000
/kds -> kitchen-service:8000
/kds/* -> kitchen-service:8000
```

Optional:

```text
/menu-items -> menu-service
/kitchens -> kitchen-service
/docs routes for services
```

Example for nginx ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dark-kitchen-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
    - host: dark-kitchen.local
      http:
        paths:
          - path: /fulfillment(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: fulfillment-service
                port:
                  number: 8000
          - path: /kitchen(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: kitchen-service
                port:
                  number: 8000
```

However, the required public paths are direct:

```text
/orders
/kds/stations/{station_id}/tasks
```

For direct paths, prefer no rewrite:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dark-kitchen-ingress
spec:
  ingressClassName: nginx
  rules:
    - host: dark-kitchen.local
      http:
        paths:
          - path: /orders
            pathType: Prefix
            backend:
              service:
                name: fulfillment-service
                port:
                  number: 8000
          - path: /kds
            pathType: Prefix
            backend:
              service:
                name: kitchen-service
                port:
                  number: 8000
          - path: /kitchens
            pathType: Prefix
            backend:
              service:
                name: kitchen-service
                port:
                  number: 8000
          - path: /menu-items
            pathType: Prefix
            backend:
              service:
                name: menu-service
                port:
                  number: 8000
```

Recommended for MVP:

```text
Use direct prefix paths without rewrite.
```

Minikube setup:

```bash
minikube addons enable ingress
```

Add host entry:

```text
127.0.0.1 dark-kitchen.local
```

or use minikube IP:

```bash
echo "$(minikube ip) dark-kitchen.local" | sudo tee -a /etc/hosts
```

On some systems, minikube tunnel may be needed:

```bash
minikube tunnel
```

Document the exact approach.

---

## 17. Kustomize

Base kustomization:

```text
deploy/k8s/base/kustomization.yaml
```

Example:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: dark-kitchen

resources:
  - namespace.yaml
  - configmap.yaml
  - secret.yaml
  - postgres/init-configmap.yaml
  - postgres/statefulset.yaml
  - postgres/service.yaml
  - redis/statefulset.yaml
  - redis/service.yaml
  - mongo/statefulset.yaml
  - mongo/service.yaml
  - kitchen-service/deployment.yaml
  - kitchen-service/service.yaml
  - menu-service/deployment.yaml
  - menu-service/service.yaml
  - fulfillment-service/deployment.yaml
  - fulfillment-service/service.yaml
  - kitchen-scheduler-worker/deployment.yaml
  - kitchen-scheduler-worker/service.yaml
  - station-simulator-service/deployment.yaml
  - station-simulator-service/service.yaml
  - prometheus/configmap.yaml
  - prometheus/deployment.yaml
  - prometheus/service.yaml
  - grafana/deployment.yaml
  - grafana/service.yaml
  - ingress.yaml
```

Minikube overlay:

```text
deploy/k8s/overlays/minikube/kustomization.yaml
```

Example:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: dark-kitchen/kitchen-service
    newTag: local
  - name: dark-kitchen/menu-service
    newTag: local
  - name: dark-kitchen/fulfillment-service
    newTag: local
  - name: dark-kitchen/kitchen-scheduler-worker
    newTag: local
  - name: dark-kitchen/station-simulator-service
    newTag: local
```

If base already uses :local, image patching can be minimal.

---

## 18. Migration jobs

Migrations must run in Kubernetes before demo flow.

Create optional Jobs:

```text
deploy/k8s/base/migrations/
  kitchen-migration-job.yaml
  menu-migration-job.yaml
  fulfillment-migration-job.yaml
```

Or scripts:

```text
scripts/k8s/run-migrations.sh
```

Recommended for Stage 13:

```text
Use kubectl run or kubectl create job from service image via script.
```

Simpler script approach:

```bash
kubectl -n dark-kitchen exec deploy/kitchen-service -- alembic upgrade head
kubectl -n dark-kitchen exec deploy/menu-service -- alembic upgrade head
kubectl -n dark-kitchen exec deploy/fulfillment-service -- alembic upgrade head
```

This works if containers include alembic and can run it.

Better Kubernetes-native approach:

```text
Jobs are more correct.
```

MVP acceptable:

```text
scripts/k8s/run-migrations.sh using kubectl exec.
```

Definition of Done requires a documented migration path.

---

## 19. Demo seed in Kubernetes

Stage 13 does not need full automated Kubernetes demo, but should document how to seed.

Options:

```text
1. Reuse scripts/demo/seed_demo_data.py with port-forwarded services.
2. Create Kubernetes Job for seed data.
```

Recommended MVP:

```text
Use port-forward or Ingress and run seed_demo_data.py from host.
```

Example:

```bash
kubectl -n dark-kitchen port-forward svc/kitchen-service 8001:8000 &
kubectl -n dark-kitchen port-forward svc/menu-service 8002:8000 &
kubectl -n dark-kitchen port-forward svc/fulfillment-service 8003:8000 &

python scripts/demo/seed_demo_data.py \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003
```

If using Ingress:

```bash
python scripts/demo/seed_demo_data.py \
  --kitchen-url http://dark-kitchen.local \
  --menu-url http://dark-kitchen.local \
  --fulfillment-url http://dark-kitchen.local
```

Only works if routes are configured accordingly.

---

## 20. Scripts

### 20.1. deploy-minikube.sh

Create:

```text
scripts/k8s/deploy-minikube.sh
```

Required behavior:

```text
1. Check minikube is running.
2. Enable ingress addon.
3. Build/load images.
4. Apply kustomize overlay.
5. Wait for pods.
6. Print useful commands.
```

Example:

```bash
#!/usr/bin/env bash
set -euo pipefail

minikube status >/dev/null
minikube addons enable ingress

./scripts/k8s/minikube-build-images.sh

kubectl apply -k deploy/k8s/overlays/minikube

kubectl -n dark-kitchen rollout status deploy/kitchen-service
kubectl -n dark-kitchen rollout status deploy/menu-service
kubectl -n dark-kitchen rollout status deploy/fulfillment-service
kubectl -n dark-kitchen rollout status deploy/kitchen-scheduler-worker
kubectl -n dark-kitchen rollout status deploy/station-simulator-service

kubectl -n dark-kitchen get pods
kubectl -n dark-kitchen get svc
kubectl -n dark-kitchen get ingress
```

### 20.2. wait-for-k8s.sh optional

Create if useful:

```text
scripts/k8s/wait-for-k8s.sh
```

Should wait for:

```text
postgres ready
redis ready
mongo ready
all deployments available
```

### 20.3. run-migrations.sh

Create:

```text
scripts/k8s/run-migrations.sh
```

Required:

```text
Run Alembic migrations for kitchen-service, menu-service, fulfillment-service.
```

Example:

```bash
kubectl -n dark-kitchen exec deploy/kitchen-service -- alembic upgrade head
kubectl -n dark-kitchen exec deploy/menu-service -- alembic upgrade head
kubectl -n dark-kitchen exec deploy/fulfillment-service -- alembic upgrade head
```

If exec does not work because pods have multiple containers, specify container.

---

## 21. Minikube smoke checks

Add documented commands.

### 21.1. Pods

```bash
kubectl -n dark-kitchen get pods
```

Expected:

```text
all pods Running or Completed for jobs
```

### 21.2. Services

```bash
kubectl -n dark-kitchen get svc
```

Expected services:

```text
kitchen-service
menu-service
fulfillment-service
station-simulator-service
kitchen-scheduler-worker
postgres
redis
mongo
prometheus
grafana
```

### 21.3. Health checks via port-forward

```bash
kubectl -n dark-kitchen port-forward svc/kitchen-service 8001:8000
curl http://localhost:8001/health
```

Repeat for:

```text
menu-service -> 8002
fulfillment-service -> 8003
station-simulator-service -> 8004
kitchen-scheduler-worker -> 9091
```

### 21.4. Ingress checks

After configuring hosts:

```bash
curl http://dark-kitchen.local/orders
curl http://dark-kitchen.local/kds/stations/{station_id}/tasks
```

Note:

```text
GET /orders without order_id may be 404 or 405 depending on API.
Ingress is considered working if request reaches fulfillment-service.
```

Better check:

```bash
curl -i http://dark-kitchen.local/health
```

only if a health route is configured in ingress.

Required checks:

```text
/orders path routes to fulfillment-service.
/kds path routes to kitchen-service.
```

### 21.5. Prometheus

```bash
kubectl -n dark-kitchen port-forward svc/prometheus 9090:9090
curl http://localhost:9090/-/ready
```

### 21.6. Grafana

```bash
kubectl -n dark-kitchen port-forward svc/grafana 3000:3000
```

Open:

```text
http://localhost:3000
```

---

## 22. Resource requests and limits

Add reasonable resource requests/limits.

Example for Python API service:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

For databases:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"
```

For worker:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

Do not over-allocate for Minikube.

---

## 23. Readiness and liveness probes

All API services:

```text
readinessProbe: GET /health
livenessProbe: GET /health
```

Worker:

```text
readinessProbe: GET /health on 9090
livenessProbe: GET /health on 9090
```

Prometheus:

```text
readinessProbe: GET /-/ready
livenessProbe: GET /-/healthy
```

Grafana:

```text
readinessProbe: GET /api/health
livenessProbe: GET /api/health
```

Postgres/Redis/Mongo use command probes as described above.

---

## 24. Security notes for local MVP

Document:

```text
Secrets are local-only.
Postgres password is not production-grade.
MongoDB auth may be disabled for Minikube MVP.
Ingress has no TLS.
Do not use this config as production deployment.
```

Do not spend time on production hardening in this stage.

---

## 25. README documentation

Create:

```text
docs/k8s/minikube.md
```

Update root README with a link.

The Minikube README must include:

```text
1. Prerequisites:
   - Docker
   - kubectl
   - minikube
   - kustomize support via kubectl
2. Start Minikube.
3. Enable ingress addon.
4. Build and load images.
5. Apply manifests.
6. Run migrations.
7. Seed demo data.
8. Verify pods.
9. Verify Ingress.
10. Port-forward Prometheus.
11. Port-forward Grafana.
12. Troubleshooting.
13. Cleanup.
```

Example commands:

```bash
minikube start
minikube addons enable ingress

./scripts/k8s/minikube-build-images.sh
kubectl apply -k deploy/k8s/overlays/minikube

./scripts/k8s/run-migrations.sh

kubectl -n dark-kitchen get pods
kubectl -n dark-kitchen get svc
kubectl -n dark-kitchen get ingress
```

Cleanup:

```bash
kubectl delete namespace dark-kitchen
```

If PVCs remain:

```bash
kubectl get pvc -A
```

---

## 26. Troubleshooting

Add troubleshooting to docs/k8s/minikube.md.

### 26.1. ImagePullBackOff

Cause:

```text
Image not loaded into Minikube.
imagePullPolicy incompatible with local image.
```

Fix:

```bash
./scripts/k8s/minikube-build-images.sh
kubectl -n dark-kitchen rollout restart deploy/kitchen-service
```

### 26.2. CrashLoopBackOff

Check:

```bash
kubectl -n dark-kitchen logs deploy/kitchen-service
kubectl -n dark-kitchen describe pod <pod-name>
```

Common causes:

```text
wrong DATABASE_URL
database not initialized
missing ConfigMap key
missing Secret key
migration not run
```

### 26.3. Services cannot connect

Check DNS:

```bash
kubectl -n dark-kitchen exec deploy/fulfillment-service -- python -c "import socket; print(socket.gethostbyname('kitchen-service'))"
```

Check env:

```bash
kubectl -n dark-kitchen exec deploy/fulfillment-service -- env | grep SERVICE_URL
```

### 26.4. Ingress not working

Check:

```bash
minikube addons list | grep ingress
kubectl -n ingress-nginx get pods
kubectl -n dark-kitchen describe ingress dark-kitchen-ingress
```

Check hosts file:

```bash
cat /etc/hosts | grep dark-kitchen.local
```

### 26.5. Postgres database missing

If initdb script did not run because PVC already existed:

```bash
kubectl delete namespace dark-kitchen
```

Then redeploy.

Or manually create DB:

```bash
kubectl -n dark-kitchen exec statefulset/postgres -- psql -U postgres -c "CREATE DATABASE kitchen_service;"
```

---

## 27. Acceptance checklist

Stage is complete when:

```text
1. deploy/k8s/base exists.
2. deploy/k8s/overlays/minikube exists.
3. Namespace manifest exists.
4. ConfigMap exists.
5. Secret exists.
6. kitchen-service Deployment exists.
7. kitchen-service Service exists.
8. menu-service Deployment exists.
9. menu-service Service exists.
10. fulfillment-service Deployment exists.
11. fulfillment-service Service exists.
12. kitchen-scheduler-worker Deployment exists.
13. kitchen-scheduler-worker Service exists or metrics access is documented.
14. station-simulator-service Deployment exists.
15. station-simulator-service Service exists.
16. postgres StatefulSet exists.
17. postgres Service exists.
18. postgres persistence is configured.
19. postgres init creates required databases or setup is documented.
20. redis StatefulSet or Deployment exists.
21. redis Service exists.
22. mongo StatefulSet or Deployment exists.
23. mongo Service exists.
24. prometheus Deployment exists.
25. prometheus Service exists.
26. grafana Deployment exists.
27. grafana Service exists.
28. Ingress exists.
29. Ingress exposes /orders to fulfillment-service.
30. Ingress exposes /kds to kitchen-service.
31. Minikube overlay applies successfully.
32. Local images can be built and loaded.
33. Pods reach Running state.
34. Migrations can be run.
35. Service health endpoints are reachable.
36. Prometheus is reachable.
37. Grafana is reachable.
38. docs/k8s/minikube.md exists.
39. Troubleshooting section exists.
40. No new business logic is introduced in this stage.
```

---

## 28. Short instruction for the agent

Implement Stage 13: Kubernetes / Minikube deployment.

Add:

```text
deploy/k8s/base
deploy/k8s/overlays/minikube
scripts/k8s/minikube-build-images.sh
scripts/k8s/deploy-minikube.sh
scripts/k8s/run-migrations.sh
docs/k8s/minikube.md
```

Create Kubernetes manifests for:

```text
kitchen-service
menu-service
fulfillment-service
kitchen-scheduler-worker
station-simulator-service
postgres
redis
mongo
prometheus
grafana
ConfigMap
Secret
Ingress
```

Ingress must expose at minimum:

```text
/orders -> fulfillment-service
/kds -> kitchen-service
```

Use Minikube local images:

```text
dark-kitchen/kitchen-service:local
dark-kitchen/menu-service:local
dark-kitchen/fulfillment-service:local
dark-kitchen/kitchen-scheduler-worker:local
dark-kitchen/station-simulator-service:local
```

Do not implement:

```text
Helm
production cloud deployment
service mesh
TLS
new business logic
new API endpoints
```
