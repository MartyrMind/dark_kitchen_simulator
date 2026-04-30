#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${TARGET_URL:-http://fulfillment-service:8000/health}"
QPS="${QPS:-50}"
DURATION="${DURATION:-120s}"

kubectl run dark-kitchen-load-test \
  --rm -i --restart=Never \
  --image=fortio/fortio \
  -n dark-kitchen \
  -- load -qps "${QPS}" -t "${DURATION}" "${TARGET_URL}"

kubectl get hpa -n dark-kitchen
kubectl get pods -n dark-kitchen
