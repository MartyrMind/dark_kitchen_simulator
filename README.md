# Dark Kitchen Simulator

Training monorepo for a dark kitchen fulfillment backend.

## Observability

All Python services expose Prometheus metrics on `/metrics` through `dk_common.metrics.setup_metrics()`. The Go kitchen scheduler worker exposes `/metrics` on its Prometheus port, default `9090`.

Manual checks:

```bash
curl http://localhost:8000/metrics
curl http://localhost:9090/api/v1/targets
```

Prometheus config is stored in `deploy/compose/prometheus.yml`. Container scrape targets use service DNS names, for example `kitchen-service:8000` and `kitchen-scheduler-worker:9090`.

Grafana provisioning is stored in `deploy/compose/grafana/provisioning`. Dashboards are stored in `deploy/compose/grafana/dashboards`. Local default credentials, when using the recommended Compose service, are `admin` / `admin`.

MongoDB stores business and audit events in database `dark_kitchen_events`:

```bash
mongosh mongodb://localhost:27017/dark_kitchen_events
db.order_events.find().sort({created_at: -1}).limit(5)
db.task_events.find().sort({created_at: -1}).limit(5)
db.kds_events.find().sort({created_at: -1}).limit(5)
db.station_events.find().sort({created_at: -1}).limit(5)
db.app_audit_events.find().sort({created_at: -1}).limit(5)
```

MongoDB is used for business/audit history, not as a sink for every application log.

## Docker Compose Demo

The full MVP can be started locally from the repository root.

Prerequisites:

- Docker with the Docker Compose plugin.
- Python 3.11 available as `python` on the host, or a working Poetry env for `services/kitchen-service`, for the demo helper scripts.
- Bash for `scripts/demo/run-demo.sh`.

Clean demo run:

```bash
chmod +x scripts/demo/run-demo.sh
./scripts/demo/run-demo.sh --clean
```

Normal run without deleting volumes:

```bash
./scripts/demo/run-demo.sh
```

The script starts Postgres, Redis, MongoDB, all MVP services, Prometheus, and Grafana. It then runs Alembic migrations, seeds deterministic demo data through HTTP APIs, starts the station simulator with the seeded station UUIDs, creates a Burger order, and waits until the order reaches `ready_for_pickup`.

Useful URLs:

```text
Kitchen Service:      http://localhost:8001/docs
Menu Service:         http://localhost:8002/docs
Fulfillment Service:  http://localhost:8003/docs
Station Simulator:    http://localhost:8004/health
Worker Health:        http://localhost:9091/health
Prometheus:           http://localhost:9090
Grafana:              http://localhost:3000
```

Grafana credentials are `admin` / `admin`.

Manual Compose commands:

```bash
docker compose -f deploy/compose/docker-compose.yml up --build
docker compose -f deploy/compose/docker-compose.yml --profile demo up --build
docker compose -f deploy/compose/docker-compose.yml --profile demo down
docker compose -f deploy/compose/docker-compose.yml --profile demo down -v
```

Inspect logs:

```bash
docker compose -f deploy/compose/docker-compose.yml --profile demo logs -f fulfillment-service
docker compose -f deploy/compose/docker-compose.yml --profile demo logs -f kitchen-scheduler-worker
docker compose -f deploy/compose/docker-compose.yml --profile demo logs -f station-simulator-service
```

Rerun only the seed step:

```bash
python scripts/demo/seed_demo_data.py \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003
```

If ports are already in use, either stop the local process using the port or override the host port variables from `.env.example`. For a fully fresh state, use `./scripts/demo/run-demo.sh --clean` or `docker compose -f deploy/compose/docker-compose.yml --profile demo down -v`.
