# Stage 14 - Bonus Kubernetes Observability, Autoscaling, and Service Mesh

This stage adds Kubernetes infrastructure metrics, CPU-based autoscaling, kube-prometheus-stack dashboards, Linkerd service mesh visibility, and a report evidence workflow for the Minikube deployment.

The changes are educational and local-only. They do not replace the Compose observability stack and do not change the order/task business flow.

## Start Minikube

```bash
minikube start --driver=docker --cpus=4 --memory=8192
minikube addons enable ingress
```

## Deploy The App

```bash
scripts/k8s/minikube-build-images.sh
scripts/k8s/deploy-minikube.sh
scripts/k8s/run-migrations.sh
```

Verify the base deployment:

```bash
kubectl get pods -n dark-kitchen
kubectl get deploy -n dark-kitchen
kubectl get statefulset -n dark-kitchen
kubectl get svc -n dark-kitchen
kubectl get ingress -n dark-kitchen
kubectl get pvc -n dark-kitchen
```

Stateful evidence expected for the report:

- PostgreSQL runs as a StatefulSet with PVC.
- Redis runs as a StatefulSet in this Minikube setup.
- MongoDB runs as a StatefulSet in this Minikube setup.

## Install Metrics Server

```bash
scripts/k8s/install-metrics-server.sh
kubectl top nodes
kubectl top pods -n dark-kitchen
```

Metrics Server is used by CPU-based HPA. It is not a Prometheus replacement.

## Install kube-prometheus-stack

```bash
scripts/k8s/install-kube-prometheus-stack.sh
kubectl apply -k deploy/k8s/base/observability
```

The Helm release installs Prometheus, Grafana, kube-state-metrics, node-exporter, and kubelet scraping. Local Grafana credentials are `admin` / `admin` and are for Minikube only.

Open Prometheus:

```bash
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
```

Open <http://localhost:9090/targets> and verify application targets plus kube-state-metrics, node-exporter, and kubelet are UP.

Open Grafana:

```bash
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
```

Open <http://localhost:3000> and verify dashboards:

- Dark Kitchen Application Overview
- Dark Kitchen Business Flow
- Dark Kitchen Scheduler Worker
- Dark Kitchen KDS and Kitchen
- Dark Kitchen Station Simulator
- Dark Kitchen Kubernetes Workloads
- Dark Kitchen HPA
- Dark Kitchen Service Mesh

## Apply HPA

All autoscaled workloads have CPU requests. Only stateless application workloads are autoscaled:

- kitchen-service
- menu-service
- fulfillment-service
- kitchen-scheduler-worker

Infrastructure components are not autoscaled.

```bash
kubectl apply -k deploy/k8s/base/hpa
scripts/k8s/verify-hpa.sh
```

Run a safe health-check load test:

```bash
scripts/k8s/load-test-hpa.sh
```

Optional overrides:

```bash
QPS=80 DURATION=180s TARGET_URL=http://fulfillment-service:8000/health scripts/k8s/load-test-hpa.sh
```

Capture `kubectl get hpa -n dark-kitchen`, `kubectl top pods -n dark-kitchen`, and deployment replica changes during the test. If Minikube resources are too small to scale, include the HPA output and document the resource limit.

## Install Linkerd

Install the Linkerd CLI first if needed:

```bash
# See the current official install command:
# https://linkerd.io/2/getting-started/
linkerd version
```

Install Linkerd and the viz extension:

```bash
scripts/k8s/install-linkerd.sh
```

Inject only application workloads:

```bash
kubectl apply -k deploy/k8s/overlays/minikube-linkerd
kubectl rollout status deploy/kitchen-service -n dark-kitchen
kubectl rollout status deploy/menu-service -n dark-kitchen
kubectl rollout status deploy/fulfillment-service -n dark-kitchen
kubectl rollout status deploy/kitchen-scheduler-worker -n dark-kitchen
kubectl rollout status deploy/station-simulator-service -n dark-kitchen
```

Verify the mesh:

```bash
scripts/k8s/verify-service-mesh.sh
linkerd viz dashboard
```

The pod container list should include `linkerd-proxy` for application pods only. PostgreSQL, Redis, MongoDB, Prometheus, and Grafana are intentionally not injected by these manifests.

Generate traffic for the mesh with the normal demo flow, or with safe health calls:

```bash
curl http://dark-kitchen.local/orders
curl http://dark-kitchen.local/kds/stations/11111111-1111-1111-1111-111111111101/tasks
```

## MongoDB Event Evidence

After a successful demo run:

```bash
kubectl port-forward svc/mongo 27017:27017 -n dark-kitchen
mongosh mongodb://localhost:27017/dark_kitchen_events
```

Queries for screenshots:

```javascript
db.order_events.find().sort({created_at: -1}).limit(5)
db.task_events.find().sort({created_at: -1}).limit(5)
db.kds_events.find().sort({created_at: -1}).limit(5)
db.station_events.find().sort({created_at: -1}).limit(5)
db.app_audit_events.find().sort({created_at: -1}).limit(5)
```

If `app_audit_events` is empty after a successful run, document that it is reserved for technical failures. Do not corrupt business data just to create an event.

## Collect Report Evidence

```bash
scripts/k8s/collect-practice-evidence.sh
```

Text evidence is written to `docs/practice4/evidence/`. Screenshots are collected manually; use `docs/practice4/report-evidence-checklist.md` as the checklist.

## Verification Shortlist

```bash
scripts/k8s/verify-observability.sh
scripts/k8s/verify-hpa.sh
scripts/k8s/verify-service-mesh.sh
```

## Known Limitations

- Secrets and Grafana `admin` / `admin` credentials are local-only and not production-grade.
- Minikube resource limits can restrict HPA scale-up.
- HPA is CPU-based; custom business-metric autoscaling is not implemented.
- Linkerd is installed for educational demonstration, not production hardening.
- MongoDB event log is an audit/history store, not the source of truth.
- PostgreSQL remains the source of truth for business state.

## Cleanup

```bash
kubectl delete -k deploy/k8s/base/hpa || true
kubectl delete -k deploy/k8s/base/observability || true
helm uninstall kube-prometheus-stack -n monitoring || true
linkerd viz uninstall | kubectl delete -f - || true
linkerd uninstall | kubectl delete -f - || true
minikube delete
```
