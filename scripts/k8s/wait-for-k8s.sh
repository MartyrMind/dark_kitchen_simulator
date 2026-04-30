#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-dark-kitchen}"

kubectl -n "$NAMESPACE" rollout status statefulset/postgres --timeout=180s
kubectl -n "$NAMESPACE" rollout status statefulset/redis --timeout=180s
kubectl -n "$NAMESPACE" rollout status statefulset/mongo --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/kitchen-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/menu-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/fulfillment-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/kitchen-scheduler-worker --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/station-simulator-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/prometheus --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/grafana --timeout=180s
