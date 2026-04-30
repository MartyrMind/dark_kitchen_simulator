#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

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
