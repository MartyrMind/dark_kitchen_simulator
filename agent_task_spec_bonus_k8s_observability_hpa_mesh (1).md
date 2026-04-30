# Agent Task Spec: Bonus Kubernetes Observability, HPA, Service Mesh, and Evidence Pack

Encoding note: this file is English-only and ASCII-friendly where possible.

---

## 0. Context

The project is a polyglot monorepo for a dark kitchen order fulfillment system.

The existing task specifications already cover:

```text
Stage 11: Metrics, Mongo events, Prometheus, Grafana
Stage 13: Kubernetes / Minikube deployment
```

This document adds the missing advanced work needed to maximize the practical assignment score:

```text
1. Kubernetes infrastructure metrics.
2. Horizontal Pod Autoscaler.
3. Service Mesh.
4. Grafana dashboards for Kubernetes and business metrics.
5. Evidence pack for the final report and defense.
```

This stage is an add-on stage. It must not replace Stage 11 or Stage 13.

Recommended stage name:

```text
Stage 14 - Bonus Kubernetes Observability, Autoscaling, and Service Mesh
```

---

## 1. Goal

Implement the additional Kubernetes and observability features required for a high / maximum score in the practical cycle.

At the end of this stage:

```text
1. Application metrics still work in Kubernetes.
2. Prometheus scrapes all application services in Kubernetes.
3. Kubernetes cluster metrics are collected.
4. Grafana contains dashboards for application metrics, business metrics, and Kubernetes metrics.
5. HPA is configured for stateless application services.
6. HPA can be demonstrated with a simple load test.
7. Service Mesh is installed and application services are meshed.
8. Service Mesh traffic visibility can be demonstrated.
9. README files document how to reproduce everything in Minikube.
10. Report screenshots are prepared for final defense.
```

This stage is specifically intended to cover advanced assignment items:

```text
- Stateful components with persistence: already covered by Stage 13, verify and document it.
- HPA: implement now.
- Service Mesh: implement now.
- Kubernetes metrics: implement now.
- Distributed traffic observability: implement through Service Mesh and Grafana.
- Business metrics: verify and expose in Kubernetes dashboards.
```

---

## 2. Strict boundaries

Do not rewrite business logic.

Do not change the order/task state machine.

Do not change API contracts except when strictly needed for metrics or Kubernetes readiness.

Do not replace the existing local Docker Compose observability from Stage 11.

Do not remove existing Prometheus/Grafana files.

Do not add high-cardinality labels to metrics.

Do not use these values as Prometheus labels:

```text
order_id
task_id
request_id
correlation_id
redis_message_id
station_worker_id
```

Do not autoscale stateful infrastructure components:

```text
postgres
redis
mongo
prometheus
grafana
```

Do not inject Service Mesh sidecars into infrastructure components unless explicitly required and tested.

---

## 3. Preferred implementation choices

### 3.1. Kubernetes metrics stack

Preferred option:

```text
kube-prometheus-stack installed through Helm
```

Reason:

```text
It provides Prometheus, Grafana, kube-state-metrics, node-exporter, and Kubernetes dashboards with minimal custom code.
```

Acceptable alternative:

```text
Raw manifests for Prometheus + kube-state-metrics + node-exporter + custom Grafana dashboards
```

If using Helm, this bonus stage is allowed to introduce Helm only for observability tooling.
Do not convert the whole application deployment to Helm.

### 3.2. Service Mesh

Preferred option:

```text
Linkerd
```

Reason:

```text
It is simpler for Minikube, provides automatic mTLS, traffic metrics, and a built-in dashboard through linkerd-viz.
```

Acceptable alternative:

```text
Istio
```

If Istio is used, document the reason and provide equivalent evidence.

### 3.3. HPA metrics source

Use CPU-based HPA through Kubernetes Metrics Server.

Optional advanced extension:

```text
Prometheus Adapter for custom metrics
```

Do not implement Prometheus Adapter unless the basic CPU-based HPA is already working.

---

## 4. Expected repository changes

Create or update:

```text
deploy/
  k8s/
    base/
      hpa/
        kitchen-service-hpa.yaml
        menu-service-hpa.yaml
        fulfillment-service-hpa.yaml
        kitchen-scheduler-worker-hpa.yaml
        kustomization.yaml

      observability/
        servicemonitor-kitchen-service.yaml
        servicemonitor-menu-service.yaml
        servicemonitor-fulfillment-service.yaml
        servicemonitor-station-simulator-service.yaml
        servicemonitor-kitchen-scheduler-worker.yaml
        grafana-dashboard-application-overview.yaml
        grafana-dashboard-business-flow.yaml
        grafana-dashboard-kubernetes-workloads.yaml
        grafana-dashboard-hpa.yaml
        kustomization.yaml

      service-mesh/
        linkerd-injection-patch.yaml
        kustomization.yaml

    overlays/
      minikube/
        kustomization.yaml
        hpa-patch.yaml optional
        service-monitor-patch.yaml optional

scripts/
  k8s/
    install-metrics-server.sh
    install-kube-prometheus-stack.sh
    install-linkerd.sh
    verify-observability.sh
    verify-hpa.sh
    verify-service-mesh.sh
    load-test-hpa.sh
    collect-practice-evidence.sh

docs/
  k8s/
    bonus-observability-hpa-service-mesh.md

  practice4/
    screenshots/
      README.md
    report-evidence-checklist.md
```

If the repository already has a different layout, keep it consistent but provide equivalent files.

If the educational assignment expects files under `practice3/` or `practice4/`, add README files there pointing to the canonical files under `deploy/k8s/` and `docs/`.

---

## 5. Prerequisites to verify first

Before implementing this stage, verify that the following already works:

```bash
kubectl get pods -n dark-kitchen
kubectl get deploy -n dark-kitchen
kubectl get statefulset -n dark-kitchen
kubectl get svc -n dark-kitchen
kubectl get ingress -n dark-kitchen
```

Expected existing workload types:

```text
Deployments:
  kitchen-service
  menu-service
  fulfillment-service
  kitchen-scheduler-worker
  station-simulator-service

StatefulSets:
  postgres
  redis recommended
  mongo recommended

Services:
  one Service for each networked component

Ingress:
  dark-kitchen.local routes /orders and /kds
```

Verify application metrics in Kubernetes before adding ServiceMonitor objects:

```bash
kubectl port-forward svc/kitchen-service 8001:8000 -n dark-kitchen
curl http://localhost:8001/metrics
```

Repeat for:

```text
menu-service
fulfillment-service
station-simulator-service
kitchen-scheduler-worker, port 9090 if that is the metrics port
```

---

## 6. Kubernetes Metrics Server

### 6.1. Goal

Install Kubernetes Metrics Server so HPA can use CPU and memory metrics.

### 6.2. Script

Create:

```text
scripts/k8s/install-metrics-server.sh
```

Required behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail

minikube addons enable metrics-server

kubectl wait --for=condition=available deployment/metrics-server \
  -n kube-system \
  --timeout=180s

kubectl top nodes || true
kubectl top pods -A || true
```

If Minikube requires insecure TLS flags for metrics-server, patch it in the script and document why it is local-only.

### 6.3. Acceptance checks

```bash
kubectl top nodes
kubectl top pods -n dark-kitchen
```

Both commands should return metrics.

---

## 7. Resource requests and limits

HPA requires CPU requests.

Add resource requests and limits to all stateless application Deployments.

Recommended defaults:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

For the Go worker:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

For station-simulator-service:

```yaml
resources:
  requests:
    cpu: 50m
    memory: 128Mi
  limits:
    cpu: 300m
    memory: 256Mi
```

Do not set unrealistic requests that make Minikube unable to schedule pods.

---

## 8. HPA

### 8.1. Goal

Configure HPA for stateless workloads.

Required HPA objects:

```text
kitchen-service-hpa
menu-service-hpa
fulfillment-service-hpa
kitchen-scheduler-worker-hpa
```

Optional:

```text
station-simulator-service-hpa
```

Do not autoscale:

```text
postgres
redis
mongo
prometheus
grafana
```

### 8.2. Important worker requirement

The kitchen-scheduler-worker can have multiple replicas only if each replica has a unique consumer identity.

Update the worker Deployment to pass a unique worker ID through the Downward API:

```yaml
env:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
  - name: WORKER_ID
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
```

The Go worker must use `WORKER_ID` as its Redis Streams consumer name.

If the current code hardcodes the worker ID, make the smallest safe change needed to read it from the environment.

### 8.3. Example HPA manifest

Create one file per workload, for example:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fulfillment-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fulfillment-service
  minReplicas: 1
  maxReplicas: 4
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 180
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
```

Use similar manifests for other services.

### 8.4. HPA verification script

Create:

```text
scripts/k8s/verify-hpa.sh
```

Required checks:

```bash
kubectl get hpa -n dark-kitchen
kubectl describe hpa fulfillment-service-hpa -n dark-kitchen
kubectl top pods -n dark-kitchen
```

### 8.5. Load test script

Create:

```text
scripts/k8s/load-test-hpa.sh
```

The script should generate load against an endpoint that is safe to call repeatedly.

Preferred target:

```text
GET /health
```

Alternative:

```text
GET /orders/{existing_order_id}
```

Example using an ephemeral container:

```bash
#!/usr/bin/env bash
set -euo pipefail

kubectl run dark-kitchen-load-test \
  --rm -i --restart=Never \
  --image=fortio/fortio \
  -n dark-kitchen \
  -- load -qps 50 -t 120s http://fulfillment-service:8000/health

kubectl get hpa -n dark-kitchen
kubectl get pods -n dark-kitchen
```

If `fortio/fortio` is not available, use another documented simple load generator.

### 8.6. HPA screenshots for report

Prepare screenshots showing:

```text
1. kubectl get hpa -n dark-kitchen
2. kubectl top pods -n dark-kitchen
3. HPA desired replicas increasing during load
4. Deployment replicas after scale-up
5. Deployment replicas after scale-down if time allows
```

---

## 9. Kubernetes observability stack

### 9.1. Goal

Collect metrics not only from the application, but also from Kubernetes itself.

Required Kubernetes metrics sources:

```text
kube-state-metrics
node-exporter
kubelet / cAdvisor metrics
Metrics Server for HPA
```

### 9.2. Install kube-prometheus-stack

Create:

```text
scripts/k8s/install-kube-prometheus-stack.sh
```

Recommended behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values deploy/k8s/observability/kube-prometheus-stack-values.yaml \
  --wait \
  --timeout 10m

kubectl get pods -n monitoring
```

Create:

```text
deploy/k8s/observability/kube-prometheus-stack-values.yaml
```

Minimum values:

```yaml
grafana:
  enabled: true
  adminPassword: admin
  sidecar:
    dashboards:
      enabled: true
      searchNamespace: ALL
    datasources:
      enabled: true

prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
    retention: 3d

kube-state-metrics:
  enabled: true

prometheus-node-exporter:
  enabled: true
```

Local credentials are acceptable only for Minikube and must be documented as local-only.

### 9.3. Application ServiceMonitor objects

Create ServiceMonitor objects for all application services.

Required files:

```text
deploy/k8s/base/observability/servicemonitor-kitchen-service.yaml
deploy/k8s/base/observability/servicemonitor-menu-service.yaml
deploy/k8s/base/observability/servicemonitor-fulfillment-service.yaml
deploy/k8s/base/observability/servicemonitor-station-simulator-service.yaml
deploy/k8s/base/observability/servicemonitor-kitchen-scheduler-worker.yaml
```

Example:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: fulfillment-service
  labels:
    release: kube-prometheus-stack
spec:
  namespaceSelector:
    matchNames:
      - dark-kitchen
  selector:
    matchLabels:
      app: fulfillment-service
  endpoints:
    - port: http
      path: /metrics
      interval: 5s
```

Make sure the corresponding Kubernetes Service has a named port:

```yaml
ports:
  - name: http
    port: 8000
    targetPort: 8000
```

For the Go worker, use the actual metrics port name:

```yaml
ports:
  - name: metrics
    port: 9090
    targetPort: 9090
```

And ServiceMonitor:

```yaml
endpoints:
  - port: metrics
    path: /metrics
    interval: 5s
```

### 9.4. Prometheus target verification

Create:

```text
scripts/k8s/verify-observability.sh
```

Required checks:

```bash
kubectl get servicemonitor -A
kubectl get pods -n monitoring
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
```

Manual checks to document:

```text
Prometheus UI -> Status -> Targets:
  kitchen-service is UP
  menu-service is UP
  fulfillment-service is UP
  station-simulator-service is UP
  kitchen-scheduler-worker is UP
  kube-state-metrics is UP
  node-exporter is UP
  kubelet is UP
```

---

## 10. Grafana dashboards

### 10.1. Goal

Create or provision dashboards that clearly show:

```text
1. System health.
2. Business flow.
3. Scheduler worker health.
4. KDS / kitchen station health.
5. Simulator activity.
6. Kubernetes workload metrics.
7. HPA behavior.
8. Optional Service Mesh traffic metrics.
```

Stage 11 already requires application dashboards. This stage must make them available in Kubernetes Grafana too.

### 10.2. Required dashboards

Create these dashboards as ConfigMaps or JSON files consumed by Grafana sidecar:

```text
grafana-dashboard-application-overview.yaml
grafana-dashboard-business-flow.yaml
grafana-dashboard-scheduler-worker.yaml
grafana-dashboard-kds-kitchen.yaml
grafana-dashboard-simulator.yaml
grafana-dashboard-kubernetes-workloads.yaml
grafana-dashboard-hpa.yaml
grafana-dashboard-service-mesh.yaml optional if Linkerd dashboard is used separately
```

### 10.3. Kubernetes Workloads dashboard panels

Required panels:

```text
Pod CPU usage by pod
Pod memory usage by pod
Pod restarts by pod/container
Pod phase/status
Deployment desired replicas vs available replicas
StatefulSet ready replicas
PVC usage if available
Network receive/transmit if available
```

Suggested PromQL:

```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="dark-kitchen", container!="", image!=""}[5m]))
```

```promql
sum by (pod) (container_memory_working_set_bytes{namespace="dark-kitchen", container!="", image!=""})
```

```promql
sum by (pod, container) (increase(kube_pod_container_status_restarts_total{namespace="dark-kitchen"}[1h]))
```

```promql
sum by (phase) (kube_pod_status_phase{namespace="dark-kitchen"})
```

```promql
kube_deployment_spec_replicas{namespace="dark-kitchen"}
```

```promql
kube_deployment_status_replicas_available{namespace="dark-kitchen"}
```

```promql
kube_statefulset_status_replicas_ready{namespace="dark-kitchen"}
```

### 10.4. HPA dashboard panels

Required panels:

```text
HPA current replicas
HPA desired replicas
HPA max replicas
CPU usage by autoscaled workload
CPU request vs usage
HPA scale events if available
```

Suggested PromQL:

```promql
kube_horizontalpodautoscaler_status_current_replicas{namespace="dark-kitchen"}
```

```promql
kube_horizontalpodautoscaler_status_desired_replicas{namespace="dark-kitchen"}
```

```promql
kube_horizontalpodautoscaler_spec_max_replicas{namespace="dark-kitchen"}
```

```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="dark-kitchen", container!="", image!=""}[5m]))
```

### 10.5. Business Flow dashboard panels

Required business panels:

```text
Orders created rate
Orders ready for pickup rate
Orders cancelled / delayed rate if implemented
Tasks queued/displayed/started/completed rate
Task completion p95 duration
Task delay p95
Failed tasks rate
Station utilization ratio
KDS visible backlog
DLQ messages
Dispatch failures by reason
```

Suggested PromQL:

```promql
sum(rate(orders_created_total[5m]))
```

```promql
sum(rate(orders_ready_total[5m]))
```

```promql
sum by (station_type) (rate(tasks_completed_total[5m]))
```

```promql
histogram_quantile(0.95, sum by (station_type, le) (rate(task_actual_duration_seconds_bucket[5m])))
```

```promql
histogram_quantile(0.95, sum by (station_type, le) (rate(task_delay_seconds_bucket[5m])))
```

```promql
station_utilization_ratio
```

```promql
kds_visible_backlog_size
```

```promql
sum by (station_type) (rate(redis_dlq_messages_total[5m]))
```

### 10.6. Application Overview dashboard panels

Required panels:

```text
HTTP RPS by service
HTTP error rate by service
p95 HTTP latency by service
Prometheus up status by job
```

Suggested PromQL:

```promql
sum by (service) (rate(http_requests_total[1m]))
```

```promql
sum by (service) (rate(http_requests_total{status=~"5.."}[1m]))
```

```promql
histogram_quantile(0.95, sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))
```

```promql
up
```

---

## 11. Service Mesh with Linkerd

### 11.1. Goal

Install Linkerd and mesh the application services to demonstrate Service Mesh usage.

Required Service Mesh capabilities to demonstrate:

```text
1. Injected sidecar proxies for application services.
2. Automatic service-to-service mTLS.
3. Traffic metrics between services.
4. Linkerd dashboard or CLI output showing meshed workloads.
5. No broken application behavior after injection.
```

### 11.2. Install script

Create:

```text
scripts/k8s/install-linkerd.sh
```

Recommended behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail

linkerd check --pre
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check

linkerd viz install | kubectl apply -f -
linkerd viz check
```

Document how to install the `linkerd` CLI if it is not installed.

### 11.3. Sidecar injection

Prefer annotating only application Deployments, not databases or observability components.

Add this annotation to application Deployment pod templates:

```yaml
metadata:
  annotations:
    linkerd.io/inject: enabled
```

Apply to:

```text
kitchen-service
menu-service
fulfillment-service
kitchen-scheduler-worker
station-simulator-service
```

Do not apply by default to:

```text
postgres
redis
mongo
prometheus
grafana
```

### 11.4. Linkerd verification script

Create:

```text
scripts/k8s/verify-service-mesh.sh
```

Required checks:

```bash
linkerd check
linkerd -n dark-kitchen check --proxy
linkerd -n dark-kitchen stat deploy
linkerd -n dark-kitchen viz stat deploy
kubectl get pods -n dark-kitchen -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].name}{"\n"}{end}'
```

The container list should show an additional `linkerd-proxy` container in meshed application pods.

### 11.5. Service Mesh dashboard

Document how to open Linkerd dashboard:

```bash
linkerd viz dashboard
```

Required screenshots:

```text
1. Linkerd dashboard with dark-kitchen namespace.
2. Meshed Deployments list.
3. Traffic between services.
4. Success rate / RPS / latency for at least one service.
5. CLI output of linkerd stat deploy -n dark-kitchen.
```

### 11.6. Traffic generation for Service Mesh demo

Use existing demo flow if available.

Minimum fallback:

```bash
curl http://dark-kitchen.local/orders
curl http://dark-kitchen.local/kds/stations/<station_id>/tasks
```

Better:

```text
Run the full demo order flow so traffic crosses:
  fulfillment-service -> menu-service
  fulfillment-service -> kitchen-service
  fulfillment-service -> redis
  kitchen-scheduler-worker -> kitchen-service
  kitchen-service -> fulfillment-service
  station-simulator-service -> kitchen-service
```

Document the exact commands used.

---

## 12. MongoDB event evidence

Stage 11 already requires MongoDB event collections.

For maximum score, prepare evidence that events exist after a demo run.

Required collections:

```text
order_events
task_events
kds_events
station_events
app_audit_events
```

Create or update documentation with these commands:

```bash
kubectl port-forward svc/mongo 27017:27017 -n dark-kitchen
mongosh mongodb://localhost:27017/dark_kitchen_events
```

Then run:

```javascript
db.order_events.find().sort({created_at: -1}).limit(5)
db.task_events.find().sort({created_at: -1}).limit(5)
db.kds_events.find().sort({created_at: -1}).limit(5)
db.station_events.find().sort({created_at: -1}).limit(5)
db.app_audit_events.find().sort({created_at: -1}).limit(5)
```

Required screenshots:

```text
1. order_events query result.
2. task_events query result.
3. kds_events query result.
4. station_events query result.
5. app_audit_events query result if available.
```

If `app_audit_events` is empty after a successful run, document that it is reserved for technical failures and produce a controlled safe failure only if already supported.

Do not intentionally corrupt business data just to create an audit event.

---

## 13. Report evidence pack

Create:

```text
docs/practice4/report-evidence-checklist.md
```

It must contain a checklist of screenshots and commands.

Required evidence:

```text
Architecture / deployment:
  [ ] kubectl get pods -n dark-kitchen
  [ ] kubectl get deploy -n dark-kitchen
  [ ] kubectl get statefulset -n dark-kitchen
  [ ] kubectl get svc -n dark-kitchen
  [ ] kubectl get ingress -n dark-kitchen
  [ ] kubectl get pvc -n dark-kitchen

StatefulSet / persistence:
  [ ] postgres StatefulSet exists
  [ ] postgres PVC exists
  [ ] redis StatefulSet or documented Deployment exists
  [ ] mongo StatefulSet or documented Deployment exists

Application metrics:
  [ ] /metrics works for kitchen-service
  [ ] /metrics works for menu-service
  [ ] /metrics works for fulfillment-service
  [ ] /metrics works for station-simulator-service
  [ ] /metrics works for kitchen-scheduler-worker

Prometheus:
  [ ] all application targets are UP
  [ ] kube-state-metrics target is UP
  [ ] node-exporter target is UP
  [ ] kubelet target is UP

Grafana:
  [ ] Application Overview dashboard
  [ ] Business Flow dashboard
  [ ] Scheduler Worker dashboard
  [ ] KDS / Kitchen dashboard
  [ ] Simulator dashboard
  [ ] Kubernetes Workloads dashboard
  [ ] HPA dashboard

HPA:
  [ ] kubectl get hpa -n dark-kitchen
  [ ] HPA desired replicas change during load test
  [ ] kubectl top pods -n dark-kitchen

Service Mesh:
  [ ] linkerd check passes
  [ ] app pods have linkerd-proxy sidecar
  [ ] linkerd stat deploy -n dark-kitchen
  [ ] Linkerd dashboard screenshot

Business evidence:
  [ ] successful order creation
  [ ] task queued/displayed/started/completed
  [ ] order ready_for_pickup
  [ ] MongoDB order_events
  [ ] MongoDB task_events
  [ ] MongoDB kds_events
  [ ] MongoDB station_events
```

---

## 14. Documentation

Create:

```text
docs/k8s/bonus-observability-hpa-service-mesh.md
```

The document must include:

```text
1. What was added and why.
2. How to start Minikube.
3. How to deploy the app.
4. How to install Metrics Server.
5. How to install kube-prometheus-stack.
6. How to apply ServiceMonitor objects.
7. How to open Prometheus.
8. How to open Grafana.
9. How to install Linkerd.
10. How to verify Service Mesh.
11. How to run HPA load test.
12. How to collect report screenshots.
13. Known limitations.
14. Cleanup commands.
```

Required example commands:

```bash
minikube start --driver=docker --cpus=4 --memory=8192
minikube addons enable ingress
scripts/k8s/minikube-build-images.sh
scripts/k8s/deploy-minikube.sh
scripts/k8s/install-metrics-server.sh
scripts/k8s/install-kube-prometheus-stack.sh
kubectl apply -k deploy/k8s/base/observability
kubectl apply -k deploy/k8s/base/hpa
scripts/k8s/install-linkerd.sh
scripts/k8s/verify-observability.sh
scripts/k8s/verify-hpa.sh
scripts/k8s/verify-service-mesh.sh
```

Port-forward commands:

```bash
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
linkerd viz dashboard
```

Cleanup commands:

```bash
kubectl delete -k deploy/k8s/base/hpa || true
kubectl delete -k deploy/k8s/base/observability || true
helm uninstall kube-prometheus-stack -n monitoring || true
linkerd viz uninstall | kubectl delete -f - || true
linkerd uninstall | kubectl delete -f - || true
minikube delete
```

---

## 15. README summary for final defense

Update the root README with a concise section:

```markdown
## Advanced Kubernetes Observability and Autoscaling

The project includes an extended Minikube setup for the final practical assignment:

- PostgreSQL runs as StatefulSet with PVC.
- Redis and MongoDB run as StatefulSet or documented persistent workloads.
- Application services expose Prometheus metrics through `/metrics`.
- kube-prometheus-stack collects application and Kubernetes metrics.
- Grafana dashboards show HTTP metrics, business KPIs, Kubernetes workloads, and HPA behavior.
- HorizontalPodAutoscaler is configured for stateless services.
- Linkerd Service Mesh provides mTLS and service-to-service traffic visibility.

See `docs/k8s/bonus-observability-hpa-service-mesh.md` for commands.
```

---

## 16. Smoke test expectations

Create:

```text
scripts/k8s/collect-practice-evidence.sh
```

The script should print useful commands and collect text output into:

```text
docs/practice4/evidence/
```

Suggested files:

```text
docs/practice4/evidence/kubectl-pods.txt
docs/practice4/evidence/kubectl-deployments.txt
docs/practice4/evidence/kubectl-statefulsets.txt
docs/practice4/evidence/kubectl-services.txt
docs/practice4/evidence/kubectl-ingress.txt
docs/practice4/evidence/kubectl-pvc.txt
docs/practice4/evidence/kubectl-hpa.txt
docs/practice4/evidence/kubectl-top-pods.txt
docs/practice4/evidence/linkerd-stat-deploy.txt
docs/practice4/evidence/prometheus-targets-note.md
docs/practice4/evidence/grafana-dashboards-note.md
```

Do not commit screenshots automatically unless the user adds them manually.

---

## 17. Acceptance checklist

This bonus stage is complete when all required items are true:

```text
1. Metrics Server is installed and `kubectl top pods -n dark-kitchen` works.
2. All stateless app Deployments have CPU requests.
3. HPA manifests exist for kitchen-service, menu-service, fulfillment-service, and kitchen-scheduler-worker.
4. HPA objects are applied successfully.
5. A load test can show at least one HPA reacting or the report documents why Minikube resources were insufficient.
6. kube-prometheus-stack or equivalent Kubernetes monitoring stack is installed.
7. Prometheus scrapes application services in Kubernetes.
8. Prometheus scrapes Kubernetes metrics through kube-state-metrics and node-exporter.
9. Grafana has application dashboards.
10. Grafana has business dashboards.
11. Grafana has Kubernetes workload dashboards.
12. Grafana has HPA dashboard panels.
13. Linkerd or Istio is installed.
14. Application pods are injected with Service Mesh sidecars.
15. Service Mesh status checks pass.
16. Service Mesh dashboard or CLI shows traffic for dark-kitchen services.
17. PostgreSQL StatefulSet and PVC are documented as evidence.
18. Redis and MongoDB persistence choice is documented.
19. MongoDB event collections are documented and query commands exist.
20. Report screenshot checklist exists.
21. Root README links to the bonus documentation.
22. No business logic was rewritten.
23. No high-cardinality metric labels were introduced.
24. Infrastructure components are not autoscaled.
25. The system still supports the original demo order flow after all changes.
```

---

## 18. Suggested implementation order

Follow this order to minimize risk:

```text
1. Verify existing Kubernetes deployment.
2. Add resource requests and limits.
3. Install Metrics Server.
4. Add HPA manifests.
5. Verify HPA without load.
6. Add kube-prometheus-stack.
7. Add ServiceMonitor objects.
8. Add / port-name fixes if targets are not discovered.
9. Add Grafana dashboards.
10. Install Linkerd.
11. Inject only application workloads.
12. Run demo traffic.
13. Verify Prometheus, Grafana, HPA, and Linkerd.
14. Prepare evidence docs and screenshot checklist.
```

---

## 19. Known limitations to document

Add a `Known limitations` section to the docs:

```text
1. Secrets are local-only and not production-grade.
2. Minikube resource limits can restrict HPA scale-up.
3. HPA is CPU-based; custom business-metric autoscaling is not implemented.
4. Service Mesh is installed for educational demonstration, not production hardening.
5. Grafana admin/admin credentials are local-only.
6. MongoDB event log is an audit/history store, not the source of truth.
7. PostgreSQL remains the source of truth for business state.
```

---

## 20. Short instruction for the agent

Implement the bonus Kubernetes stage for maximum practical assignment score.

Add:

```text
- Kubernetes Metrics Server
- CPU-based HPA for stateless services
- kube-prometheus-stack or equivalent Kubernetes metrics stack
- ServiceMonitor objects for all app services
- Grafana dashboards for app, business, Kubernetes, and HPA metrics
- Linkerd Service Mesh for app workloads
- verification scripts
- report evidence checklist
- documentation with exact commands and screenshots to capture
```

Do not rewrite business logic.
Do not autoscale databases.
Do not add high-cardinality Prometheus labels.
Keep the original Minikube deployment working.
