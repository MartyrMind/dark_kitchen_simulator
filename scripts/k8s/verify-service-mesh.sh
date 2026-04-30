#!/usr/bin/env bash
set -euo pipefail

linkerd check
linkerd -n dark-kitchen check --proxy
linkerd -n dark-kitchen stat deploy
linkerd viz stat deploy -n dark-kitchen
kubectl get pods -n dark-kitchen -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].name}{"\n"}{end}'
