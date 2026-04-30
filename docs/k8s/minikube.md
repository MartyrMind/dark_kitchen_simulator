# Minikube Deployment

This runbook deploys the local MVP stack to Minikube with plain Kubernetes manifests and kustomize. It is for local education only: secrets are simple, MongoDB auth is disabled, and ingress has no TLS.

## Prerequisites

- Docker
- kubectl with kustomize support
- minikube
- Bash
- Python 3.11 for the optional seed helper

## Start Minikube

```bash
minikube start
minikube addons enable ingress
```

## Build and Load Images

The manifests use local images and `imagePullPolicy: IfNotPresent`.

```bash
chmod +x scripts/k8s/*.sh
./scripts/k8s/minikube-build-images.sh
```

The script builds these images from the repository root and loads them into Minikube:

```text
dark-kitchen/kitchen-service:local
dark-kitchen/menu-service:local
dark-kitchen/fulfillment-service:local
dark-kitchen/kitchen-scheduler-worker:local
dark-kitchen/station-simulator-service:local
```

## Apply Manifests

```bash
kubectl apply -k deploy/k8s/overlays/minikube
./scripts/k8s/wait-for-k8s.sh
```

Or run the full local deployment helper:

```bash
./scripts/k8s/deploy-minikube.sh
```

## Run Migrations

PostgreSQL starts with three databases from `deploy/k8s/base/postgres/init-configmap.yaml`:

```text
kitchen_service
menu_service
fulfillment_service
```

After the pods are ready, run Alembic migrations inside the service deployments:

```bash
./scripts/k8s/run-migrations.sh
```

The init SQL only runs when the Postgres data directory is empty. If you redeploy with an existing PVC, the databases are not recreated.

## Seed Demo Data

Use port-forwarding and the existing host seed script:

```bash
kubectl -n dark-kitchen port-forward svc/kitchen-service 8001:8000 &
kubectl -n dark-kitchen port-forward svc/menu-service 8002:8000 &
kubectl -n dark-kitchen port-forward svc/fulfillment-service 8003:8000 &

python scripts/demo/seed_demo_data.py \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003
```

The Minikube config already contains the deterministic simulator station IDs used by the seed script.

## Verify Pods and Services

```bash
kubectl -n dark-kitchen get pods
kubectl -n dark-kitchen get svc
kubectl -n dark-kitchen get ingress
```

Expected services:

```text
kitchen-service
menu-service
fulfillment-service
station-simulator-service
kitchen-scheduler-worker
postgres
redis
mongo
prometheus
grafana
```

## Health Checks

Port-forward each service in a separate terminal when needed:

```bash
kubectl -n dark-kitchen port-forward svc/kitchen-service 8001:8000
curl http://localhost:8001/health

kubectl -n dark-kitchen port-forward svc/menu-service 8002:8000
curl http://localhost:8002/health

kubectl -n dark-kitchen port-forward svc/fulfillment-service 8003:8000
curl http://localhost:8003/health

kubectl -n dark-kitchen port-forward svc/station-simulator-service 8004:8000
curl http://localhost:8004/health

kubectl -n dark-kitchen port-forward svc/kitchen-scheduler-worker 9091:9090
curl http://localhost:9091/health
```

## Ingress

The ingress host is `dark-kitchen.local` and exposes direct prefix routes:

```text
/orders -> fulfillment-service:8000
/kds -> kitchen-service:8000
```

Add a hosts entry using the Minikube IP:

```bash
echo "$(minikube ip) dark-kitchen.local" | sudo tee -a /etc/hosts
```

On some drivers you may need:

```bash
minikube tunnel
```

Smoke checks:

```bash
curl -i http://dark-kitchen.local/orders
curl -i http://dark-kitchen.local/kds/stations/11111111-1111-1111-1111-111111111101/tasks
```

`GET /orders` may return `404` or `405` depending on API behavior. The ingress check is successful when the request reaches the expected service.

## Prometheus

```bash
kubectl -n dark-kitchen port-forward svc/prometheus 9090:9090
curl http://localhost:9090/-/ready
```

Open `http://localhost:9090` and check the targets page.

## Grafana

```bash
kubectl -n dark-kitchen port-forward svc/grafana 3000:3000
```

Open `http://localhost:3000`.

Local credentials:

```text
admin / admin
```

Prometheus is provisioned as the default datasource at `http://prometheus:9090`.

## Troubleshooting

### ImagePullBackOff

Cause: the local image was not loaded into Minikube or the pull policy does not match the local-image workflow.

Fix:

```bash
./scripts/k8s/minikube-build-images.sh
kubectl -n dark-kitchen rollout restart deploy/kitchen-service
```

Repeat the restart for the affected deployment.

### CrashLoopBackOff

Inspect logs and pod events:

```bash
kubectl -n dark-kitchen logs deploy/kitchen-service
kubectl -n dark-kitchen describe pod <pod-name>
```

Common causes are an incorrect `DATABASE_URL`, missing database initialization, missing ConfigMap or Secret keys, or migrations not being run.

### Services Cannot Connect

Check cluster DNS:

```bash
kubectl -n dark-kitchen exec deploy/fulfillment-service -- python -c "import socket; print(socket.gethostbyname('kitchen-service'))"
```

Check service URL environment variables:

```bash
kubectl -n dark-kitchen exec deploy/fulfillment-service -- env | grep SERVICE_URL
```

### Ingress Not Working

```bash
minikube addons list | grep ingress
kubectl -n ingress-nginx get pods
kubectl -n dark-kitchen describe ingress dark-kitchen-ingress
cat /etc/hosts | grep dark-kitchen.local
```

If the Minikube driver does not expose the ingress IP directly, run `minikube tunnel`.

### Postgres Database Missing

If the init script did not run because a PVC already existed, delete and recreate the namespace for a fresh local state:

```bash
kubectl delete namespace dark-kitchen
kubectl apply -k deploy/k8s/overlays/minikube
```

Or create a database manually:

```bash
kubectl -n dark-kitchen exec statefulset/postgres -- psql -U postgres -c "CREATE DATABASE kitchen_service;"
```

## Cleanup

```bash
kubectl delete namespace dark-kitchen
kubectl get pvc -A
```

If Minikube itself is no longer needed:

```bash
minikube stop
```
