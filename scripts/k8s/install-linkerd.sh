#!/usr/bin/env bash
set -euo pipefail

if ! command -v linkerd >/dev/null 2>&1; then
  echo "linkerd CLI is required. Install it from https://linkerd.io/2/getting-started/ and rerun this script." >&2
  exit 1
fi

linkerd check --pre
kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.1/standard-install.yaml
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check

linkerd viz install | kubectl apply -f -
linkerd viz check
