#!/usr/bin/env bash
set -euo pipefail

kubectl get servicemonitor -A
kubectl get pods -n monitoring
kubectl get svc -n monitoring

cat <<'EOF'

Manual checks:
  kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
  Open http://localhost:9090/targets

Expected UP targets:
  kitchen-service
  menu-service
  fulfillment-service
  station-simulator-service
  kitchen-scheduler-worker
  kube-state-metrics
  node-exporter
  kubelet
EOF
