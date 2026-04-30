# Practice 4 Report Evidence Checklist

## Architecture / Deployment

- [ ] `kubectl get pods -n dark-kitchen`
- [ ] `kubectl get deploy -n dark-kitchen`
- [ ] `kubectl get statefulset -n dark-kitchen`
- [ ] `kubectl get svc -n dark-kitchen`
- [ ] `kubectl get ingress -n dark-kitchen`
- [ ] `kubectl get pvc -n dark-kitchen`

## StatefulSet / Persistence

- [ ] PostgreSQL StatefulSet exists
- [ ] PostgreSQL PVC exists
- [ ] Redis StatefulSet or documented persistent workload exists
- [ ] MongoDB StatefulSet or documented persistent workload exists

## Application Metrics

- [ ] `/metrics` works for kitchen-service
- [ ] `/metrics` works for menu-service
- [ ] `/metrics` works for fulfillment-service
- [ ] `/metrics` works for station-simulator-service
- [ ] `/metrics` works for kitchen-scheduler-worker

## Prometheus

- [ ] All application targets are UP
- [ ] kube-state-metrics target is UP
- [ ] node-exporter target is UP
- [ ] kubelet target is UP

## Grafana

- [ ] Application Overview dashboard
- [ ] Business Flow dashboard
- [ ] Scheduler Worker dashboard
- [ ] KDS / Kitchen dashboard
- [ ] Simulator dashboard
- [ ] Kubernetes Workloads dashboard
- [ ] HPA dashboard
- [ ] Service Mesh dashboard or Linkerd dashboard

## HPA

- [ ] `kubectl get hpa -n dark-kitchen`
- [ ] HPA desired replicas change during load test
- [ ] `kubectl top pods -n dark-kitchen`
- [ ] Deployment replicas after scale-up
- [ ] Deployment replicas after scale-down, if time allows

## Service Mesh

- [ ] `linkerd check` passes
- [ ] App pods have `linkerd-proxy` sidecar
- [ ] `linkerd stat deploy -n dark-kitchen`
- [ ] Linkerd dashboard screenshot
- [ ] Traffic between dark-kitchen services is visible

## Business Evidence

- [ ] Successful order creation
- [ ] Task queued
- [ ] Task displayed
- [ ] Task started
- [ ] Task completed
- [ ] Order reaches `ready_for_pickup`
- [ ] MongoDB `order_events`
- [ ] MongoDB `task_events`
- [ ] MongoDB `kds_events`
- [ ] MongoDB `station_events`
- [ ] MongoDB `app_audit_events` or documented reason why empty

## Evidence Collection Helper

```bash
scripts/k8s/collect-practice-evidence.sh
```

The script writes text evidence into `docs/practice4/evidence/`. Add screenshots manually under `docs/practice4/screenshots/`.
