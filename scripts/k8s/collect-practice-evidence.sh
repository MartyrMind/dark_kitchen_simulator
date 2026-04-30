#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="docs/practice4/evidence"
mkdir -p "${OUT_DIR}"

kubectl get pods -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-pods.txt"
kubectl get deploy -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-deployments.txt"
kubectl get statefulset -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-statefulsets.txt"
kubectl get svc -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-services.txt"
kubectl get ingress -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-ingress.txt" || true
kubectl get pvc -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-pvc.txt" || true
kubectl get hpa -n dark-kitchen -o wide > "${OUT_DIR}/kubectl-hpa.txt" || true
kubectl top pods -n dark-kitchen > "${OUT_DIR}/kubectl-top-pods.txt" || true

if command -v linkerd >/dev/null 2>&1; then
  linkerd -n dark-kitchen stat deploy > "${OUT_DIR}/linkerd-stat-deploy.txt" || true
else
  echo "linkerd CLI is not installed on this machine." > "${OUT_DIR}/linkerd-stat-deploy.txt"
fi

cat > "${OUT_DIR}/prometheus-targets-note.md" <<'EOF'
# Prometheus Targets Screenshot

Run:

```bash
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
```

Open <http://localhost:9090/targets> and capture all dark-kitchen application targets plus kube-state-metrics, node-exporter, and kubelet as UP.
EOF

cat > "${OUT_DIR}/grafana-dashboards-note.md" <<'EOF'
# Grafana Dashboards Screenshot

Run:

```bash
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
```

Open <http://localhost:3000> with local-only admin/admin credentials and capture the application, business, Kubernetes workloads, HPA, and service mesh dashboards.
EOF

echo "Evidence text files written to ${OUT_DIR}"
