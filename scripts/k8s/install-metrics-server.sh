#!/usr/bin/env bash
set -euo pipefail

minikube addons enable metrics-server

kubectl wait --for=condition=available deployment/metrics-server \
  -n kube-system \
  --timeout=180s

kubectl top nodes || true
kubectl top pods -A || true
