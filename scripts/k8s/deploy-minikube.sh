#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

minikube status >/dev/null
minikube addons enable ingress

./scripts/k8s/minikube-build-images.sh

kubectl apply -k deploy/k8s/overlays/minikube
./scripts/k8s/wait-for-k8s.sh

kubectl -n dark-kitchen get pods
kubectl -n dark-kitchen get svc
kubectl -n dark-kitchen get ingress

cat <<'EOF'

Next useful commands:
  ./scripts/k8s/run-migrations.sh
  kubectl -n dark-kitchen port-forward svc/prometheus 9090:9090
  kubectl -n dark-kitchen port-forward svc/grafana 3000:3000

Ingress host:
  Add "<minikube-ip> dark-kitchen.local" to your hosts file.
  Get the IP with: minikube ip
EOF
