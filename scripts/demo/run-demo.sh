#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

COMPOSE_FILE="${COMPOSE_FILE:-deploy/compose/docker-compose.yml}"
COMPOSE=(docker compose -f "${COMPOSE_FILE}")
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
CLEAN=false
BUILD_FLAG="--build"
PYTHON_RUNNER=()

for arg in "$@"; do
  case "${arg}" in
    --clean) CLEAN=true ;;
    --no-build) BUILD_FLAG="" ;;
    --timeout=*) TIMEOUT_SECONDS="${arg#*=}" ;;
    *) echo "Unknown argument: ${arg}" >&2; exit 2 ;;
  esac
done

if python -c "print('ok')" >/dev/null 2>&1; then
  PYTHON_RUNNER=(python)
elif command -v py >/dev/null 2>&1 && py -3.11 -c "print('ok')" >/dev/null 2>&1; then
  PYTHON_RUNNER=(py -3.11)
elif command -v poetry >/dev/null 2>&1 && poetry -C services/kitchen-service run python -c "print('ok')" >/dev/null 2>&1; then
  PYTHON_RUNNER=(poetry -C services/kitchen-service run python)
else
  echo "Could not find a usable Python runner. Install Python 3.11 or Poetry env for services/kitchen-service." >&2
  exit 1
fi

wait_for_url() {
  local url="$1"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  until "${PYTHON_RUNNER[@]}" -c "import urllib.request; urllib.request.urlopen('${url}', timeout=3)" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for ${url}" >&2
      return 1
    fi
    sleep 2
  done
}

diagnostics() {
  local order_id="${1:-}"
  echo
  echo "Docker status:"
  "${COMPOSE[@]}" --profile demo ps || true
  echo
  for service in kitchen-service menu-service fulfillment-service kitchen-scheduler-worker station-simulator-service; do
    echo "Logs: ${service}"
    "${COMPOSE[@]}" --profile demo logs --tail=100 "${service}" || true
  done
  if [[ -n "${order_id}" ]]; then
    "${PYTHON_RUNNER[@]}" "${REPO_ROOT}/scripts/demo/smoke_demo.py" --fulfillment-url http://localhost:8003 --kitchen-url http://localhost:8001 --timeout 1 || true
  fi
  echo
  echo "Redis streams:"
  "${COMPOSE[@]}" exec -T redis redis-cli KEYS 'stream:kitchen:*' || true
  echo
  echo "Recent Mongo events:"
  "${COMPOSE[@]}" exec -T mongo mongosh dark_kitchen_events --quiet --eval 'db.task_events.find().sort({created_at:-1}).limit(10).toArray()' || true
}

trap 'diagnostics ""' ERR

if [[ "${CLEAN}" == "true" ]]; then
  "${COMPOSE[@]}" --profile demo down -v
fi

if [[ -n "${BUILD_FLAG}" ]]; then
  "${COMPOSE[@]}" up ${BUILD_FLAG} -d postgres redis mongo kitchen-service menu-service fulfillment-service kitchen-scheduler-worker prometheus grafana
else
  "${COMPOSE[@]}" up -d postgres redis mongo kitchen-service menu-service fulfillment-service kitchen-scheduler-worker prometheus grafana
fi

wait_for_url "http://localhost:8001/health"
wait_for_url "http://localhost:8002/health"
wait_for_url "http://localhost:8003/health"
wait_for_url "http://localhost:9091/health"
wait_for_url "http://localhost:9090/-/ready"
wait_for_url "http://localhost:3000/api/health"

"${COMPOSE[@]}" run --rm kitchen-service alembic upgrade head
"${COMPOSE[@]}" run --rm menu-service alembic upgrade head
"${COMPOSE[@]}" run --rm fulfillment-service alembic upgrade head

"${PYTHON_RUNNER[@]}" "${REPO_ROOT}/scripts/demo/seed_demo_data.py" \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003

set -a
source scripts/demo/.demo_state.env
set +a

if [[ -n "${BUILD_FLAG}" ]]; then
  "${COMPOSE[@]}" --profile demo up ${BUILD_FLAG} -d station-simulator-service
else
  "${COMPOSE[@]}" --profile demo up -d station-simulator-service
fi
wait_for_url "http://localhost:8004/health"

"${PYTHON_RUNNER[@]}" "${REPO_ROOT}/scripts/demo/smoke_demo.py" \
  --fulfillment-url http://localhost:8003 \
  --kitchen-url http://localhost:8001 \
  --prometheus-url http://localhost:9090 \
  --grafana-url http://localhost:3000 \
  --timeout "${TIMEOUT_SECONDS}"

trap - ERR

cat <<EOF

Demo URLs:
  Kitchen Service:      http://localhost:8001/docs
  Menu Service:         http://localhost:8002/docs
  Fulfillment Service:  http://localhost:8003/docs
  Simulator:            http://localhost:8004/health
  Worker:               http://localhost:9091/health
  Prometheus:           http://localhost:9090
  Grafana:              http://localhost:3000

Grafana credentials:
  admin / admin
EOF
