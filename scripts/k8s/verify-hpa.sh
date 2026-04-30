#!/usr/bin/env bash
set -euo pipefail

kubectl get hpa -n dark-kitchen
kubectl describe hpa fulfillment-service-hpa -n dark-kitchen
kubectl top pods -n dark-kitchen || true
