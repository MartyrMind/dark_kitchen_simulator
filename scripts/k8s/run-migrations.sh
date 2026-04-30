#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-dark-kitchen}"

kubectl -n "$NAMESPACE" exec deploy/kitchen-service -- alembic upgrade head
kubectl -n "$NAMESPACE" exec deploy/menu-service -- alembic upgrade head
kubectl -n "$NAMESPACE" exec deploy/fulfillment-service -- alembic upgrade head
