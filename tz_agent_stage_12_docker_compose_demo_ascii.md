# Agent Task Spec: Stage 12 - Docker Compose demo

Encoding note:
This file is ASCII-only on purpose.
It contains no Cyrillic text and no typographic Unicode characters.
Use this version if the agent console shows broken Russian text.

---

## 0. Context

The project is a polyglot monorepo for a dark kitchen order fulfillment system.

Previous stages should already exist:

```text
Stage 1:
  libs/python/dk-common
  common settings, logging, correlation middleware, health helper, errors

Stage 2:
  services/kitchen-service
  kitchens and stations management without KDS

Stage 3:
  services/menu-service
  menu items, recipe steps, kitchen menu availability

Stage 4:
  services/fulfillment-service
  orders, order_items, kitchen_tasks, task_dependencies

Stage 5:
  fulfillment-service publishes kitchen_tasks to Redis Streams
  kitchen_tasks move from created to queued

Stage 6:
  kitchen-service has KDS local state and KDS delivery

Stage 7:
  fulfillment-service has internal task transition APIs

Stage 8:
  kitchen-scheduler-worker in Go dispatches Redis tasks to KDS

Stage 9:
  kitchen-service has KDS claim and complete

Stage 10:
  station-simulator-service claims and completes KDS tasks

Stage 11:
  metrics, Mongo events, Prometheus, and Grafana
```

This stage is about local demo orchestration.

The goal is to run the whole MVP locally with one command or a short documented command sequence.

---

## 1. Goal

Create a Docker Compose demo for the full MVP.

At the end of this stage:

```text
1. docker-compose.yml starts all required infrastructure.
2. docker-compose.yml starts all MVP services.
3. station-simulator-service is controlled by compose profile demo.
4. seed_demo_data.py creates demo kitchens, stations, menu items, recipes, and availability.
5. run-demo.sh starts the system, waits for health checks, runs migrations, seeds data, creates an order, and verifies the full flow.
6. The demo proves:
   - create kitchen
   - create stations
   - create menu
   - create recipe
   - create order
   - Redis publish
   - worker dispatch
   - KDS display
   - simulator claim
   - simulator complete
   - order ready_for_pickup
7. README documents how to run the demo.
```

Stage boundary:

```text
This stage is Docker Compose demo only.
This stage must not implement Kubernetes.
This stage must not implement new business logic.
This stage must not rewrite service internals unless needed for container startup or env config.
```

---

## 2. Scope

Implement:

```text
1. deploy/compose/docker-compose.yml for full MVP.
2. .env.example for compose demo.
3. Dockerfiles for services if missing:
   - kitchen-service
   - menu-service
   - fulfillment-service
   - kitchen-scheduler-worker
   - station-simulator-service
4. Healthcheck configuration for containers.
5. Migration runner strategy.
6. seed_demo_data.py.
7. run-demo.sh.
8. Optional demo API helper client.
9. README section for demo run.
10. Smoke checks for full local flow.
```

---

## 3. Out of scope

Do not implement in this stage:

```text
- Kubernetes manifests
- Minikube deployment
- service mesh
- Helm charts
- production-ready secrets
- external managed databases
- new service endpoints
- new task status transitions
- new Redis worker behavior
- new KDS claim/complete behavior
- frontend UI
```

Do not add complex CI/CD unless it already exists and only needs a small update.

---

## 4. Expected repository changes

Add or update:

```text
deploy/
  compose/
    docker-compose.yml
    docker-compose.demo.yml optional
    prometheus.yml
    grafana/
      provisioning/
      dashboards/

scripts/
  demo/
    seed_demo_data.py
    run-demo.sh
    wait_for_http.py optional
    demo_client.py optional

.env.example

README.md
```

Service Dockerfiles should exist:

```text
services/kitchen-service/Dockerfile
services/menu-service/Dockerfile
services/fulfillment-service/Dockerfile
services/kitchen-scheduler-worker/Dockerfile
services/station-simulator-service/Dockerfile
```

If Dockerfiles already exist, update them instead of creating duplicates.

---

## 5. Docker Compose services

The compose demo must include:

```text
kitchen-service
menu-service
fulfillment-service
kitchen-scheduler-worker
station-simulator-service
postgres
mongo
redis
prometheus
grafana
```

Recommended additional service:

```text
migrate
```

The migrate service can run Alembic migrations for all Python database services.

Alternative acceptable approach:

```text
run-demo.sh executes docker compose run --rm for migration commands.
```

---

## 6. Compose file location

Primary compose file:

```text
deploy/compose/docker-compose.yml
```

The user should be able to run from repository root:

```bash
docker compose -f deploy/compose/docker-compose.yml up --build
```

For demo profile:

```bash
docker compose -f deploy/compose/docker-compose.yml --profile demo up --build
```

If the repo already uses another compose path, keep consistency but document it.

---

## 7. Docker build context

Use repository root as build context for Python services because they need dk-common.

Example:

```yaml
kitchen-service:
  build:
    context: ../..
    dockerfile: services/kitchen-service/Dockerfile
```

Why:

```text
Docker build must see:
  libs/python/dk-common
  services/{service-name}
```

Python Dockerfile pattern:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /repo

RUN pip install --no-cache-dir uv

COPY libs/python/dk-common /repo/libs/python/dk-common
COPY services/kitchen-service /repo/services/kitchen-service

RUN uv pip install --system /repo/libs/python/dk-common
RUN uv pip install --system /repo/services/kitchen-service

WORKDIR /repo/services/kitchen-service

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Repeat with correct service path for each Python service.

Go worker Dockerfile should build the binary and run it.

---

## 8. Network and ports

All services should use the default compose network.

Recommended internal ports:

```text
kitchen-service: 8000
menu-service: 8000
fulfillment-service: 8000
station-simulator-service: 8000
kitchen-scheduler-worker: 9090
prometheus: 9090
grafana: 3000
postgres: 5432
redis: 6379
mongo: 27017
```

Host port mappings should avoid conflicts.

Recommended host mappings:

```yaml
kitchen-service:
  ports:
    - "8001:8000"

menu-service:
  ports:
    - "8002:8000"

fulfillment-service:
  ports:
    - "8003:8000"

station-simulator-service:
  ports:
    - "8004:8000"

kitchen-scheduler-worker:
  ports:
    - "9091:9090"

prometheus:
  ports:
    - "9090:9090"

grafana:
  ports:
    - "3000:3000"

postgres:
  ports:
    - "5432:5432"

redis:
  ports:
    - "6379:6379"

mongo:
  ports:
    - "27017:27017"
```

Internal service URLs must use compose DNS names, not localhost.

Examples:

```env
KITCHEN_SERVICE_URL=http://kitchen-service:8000
MENU_SERVICE_URL=http://menu-service:8000
FULFILLMENT_SERVICE_URL=http://fulfillment-service:8000
REDIS_URL=redis://redis:6379/0
MONGO_URL=mongodb://mongo:27017
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/kitchen_service
```

---

## 9. PostgreSQL database strategy

For MVP demo, use one physical PostgreSQL container.

Each service must still own its own logical database or schema.

Recommended approach:

```text
Use separate databases:
  kitchen_service
  menu_service
  fulfillment_service
```

Create them during Postgres init.

Add init script:

```text
deploy/compose/postgres/initdb/01-create-databases.sql
```

Example:

```sql
CREATE DATABASE kitchen_service;
CREATE DATABASE menu_service;
CREATE DATABASE fulfillment_service;
```

Compose:

```yaml
postgres:
  image: postgres:16
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: postgres
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./postgres/initdb:/docker-entrypoint-initdb.d:ro
```

Alternative acceptable approach:

```text
Use one database with separate schemas.
```

If using schemas, document it clearly.

Preferred MVP:

```text
separate databases
```

---

## 10. Volumes

Use named volumes:

```yaml
volumes:
  postgres_data:
  redis_data:
  mongo_data:
  grafana_data:
```

During demo reset, run:

```bash
docker compose -f deploy/compose/docker-compose.yml down -v
```

---

## 11. Healthchecks

Add healthchecks for infrastructure:

```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 5s
    timeout: 5s
    retries: 20

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 5s
    retries: 20

mongo:
  healthcheck:
    test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
    interval: 5s
    timeout: 5s
    retries: 20
```

Add healthchecks for HTTP services:

```yaml
kitchen-service:
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 5s
    timeout: 5s
    retries: 30
```

If curl is available in image, curl is fine.
If not, use Python urllib for Python services.

For Go worker:

```yaml
kitchen-scheduler-worker:
  healthcheck:
    test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:9090/health"]
```

If wget is not available, either add it or use a small Go-native healthcheck strategy.
Healthchecks are helpful but not worth breaking the image.
At minimum, run-demo.sh must wait for /health endpoints.

---

## 12. Migration strategy

Alembic migrations must run before seeding data.

Services with migrations:

```text
kitchen-service
menu-service
fulfillment-service
```

Recommended run-demo.sh strategy:

```bash
docker compose -f deploy/compose/docker-compose.yml run --rm kitchen-service alembic upgrade head
docker compose -f deploy/compose/docker-compose.yml run --rm menu-service alembic upgrade head
docker compose -f deploy/compose/docker-compose.yml run --rm fulfillment-service alembic upgrade head
```

This requires service images to include alembic and have correct WORKDIR.

Alternative:

```text
Create one-shot migration services:
  migrate-kitchen
  migrate-menu
  migrate-fulfillment
```

Example:

```yaml
migrate-kitchen:
  build:
    context: ../..
    dockerfile: services/kitchen-service/Dockerfile
  command: ["alembic", "upgrade", "head"]
  environment:
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/kitchen_service
  depends_on:
    postgres:
      condition: service_healthy
```

Either approach is acceptable.

Definition of Done requires:

```text
run-demo.sh applies all migrations automatically or clearly fails with instructions.
```

---

## 13. Compose profiles

station-simulator-service must be controlled by profile:

```yaml
station-simulator-service:
  profiles:
    - demo
```

Reason:

```text
The core services can run without simulator.
The full demo uses simulator to auto-complete tasks.
```

Recommended:

```bash
docker compose -f deploy/compose/docker-compose.yml up --build
```

Starts core services without simulator.

```bash
docker compose -f deploy/compose/docker-compose.yml --profile demo up --build
```

Starts simulator too.

For run-demo.sh, use profile demo.

---

## 14. Environment variables

Create or update:

```text
.env.example
```

Include:

```env
# Common
ENVIRONMENT=local
LOG_LEVEL=INFO
LOG_FORMAT=json

# Postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres

# Service DB URLs
KITCHEN_DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/kitchen_service
MENU_DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/menu_service
FULFILLMENT_DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/fulfillment_service

# Service URLs
KITCHEN_SERVICE_URL=http://kitchen-service:8000
MENU_SERVICE_URL=http://menu-service:8000
FULFILLMENT_SERVICE_URL=http://fulfillment-service:8000

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_STREAM_PATTERNS=stream:kitchen:*:station:*
REDIS_CONSUMER_GROUP=group:kitchen-scheduler-workers

# Mongo
MONGO_URL=mongodb://mongo:27017
MONGO_DATABASE=dark_kitchen_events
MONGO_EVENTS_ENABLED=true

# Worker
WORKER_ID=scheduler-worker-1
STREAM_SCAN_INTERVAL_MS=500
XREAD_BLOCK_MS=5000
XREAD_COUNT=10
MAX_DISPATCH_ATTEMPTS=5
DISPATCH_BACKOFF_BASE_MS=1000
DISPATCH_BACKOFF_MAX_MS=30000
HTTP_TIMEOUT_MS=3000
PROMETHEUS_PORT=9090

# Simulator
SIMULATOR_ENABLED=true
SIMULATOR_SPEED_FACTOR=60
SIMULATOR_POLL_INTERVAL_MS=1000
SIMULATOR_WORKERS_CONFIG=
```

Important:

```text
SIMULATOR_WORKERS_CONFIG may need real station IDs.
run-demo.sh or seed_demo_data.py should generate and inject the final worker config if station IDs are random UUIDs.
```

Recommended solution:

```text
Use deterministic UUIDs for seeded stations.
Then SIMULATOR_WORKERS_CONFIG can be static.
```

Example deterministic station IDs:

```text
11111111-1111-1111-1111-111111111101 = grill station
11111111-1111-1111-1111-111111111102 = fryer station
11111111-1111-1111-1111-111111111103 = packaging station
```

---

## 15. Seed demo data

Create:

```text
scripts/demo/seed_demo_data.py
```

Purpose:

```text
Create deterministic demo data through public APIs.
```

It must use HTTP APIs, not direct DB inserts.

Required services:

```text
Kitchen Service
Menu Service
Fulfillment Service optional for order creation
```

### 15.1. Seed data

Seed these objects:

```text
Kitchen:
  id optional deterministic if API supports it
  name = Demo Kitchen
  city = London
  status = active

Stations:
  grill
  fryer optional
  packaging

Station config:
  grill:
    capacity = 1 or 2
    visible_backlog_limit = 4
    status = available

  packaging:
    capacity = 1
    visible_backlog_limit = 4
    status = available

Menu item:
  Burger
  status = active

Recipe steps:
  step 1:
    station_type = grill
    operation = cook_patty
    duration_seconds = 480
    step_order = 1

  step 2:
    station_type = packaging
    operation = pack_burger
    duration_seconds = 60
    step_order = 2

Availability:
  Burger available for Demo Kitchen
```

Optional second item:

```text
Fries:
  fryer -> packaging
```

For MVP, Burger only is enough.

### 15.2. Deterministic IDs

If service APIs allow client-provided IDs, seed deterministic IDs.

If APIs do not allow client-provided IDs, seed script must capture response IDs and write them to a demo state file:

```text
scripts/demo/.demo_state.json
```

State file example:

```json
{
  "kitchen_id": "d53b7d88-b23c-4bb8-a403-6238c810092a",
  "stations": {
    "grill": "7a7fef8e-560f-4d77-95ab-758d9a4ae4b8",
    "packaging": "be1ba4c7-7f26-45b9-9bb4-c728ff99735f"
  },
  "menu_items": {
    "burger": "3b675b7e-d4e1-4fc5-80dc-5f3ef89d55ce"
  }
}
```

### 15.3. Idempotency

seed_demo_data.py must be safe to run multiple times.

Recommended behavior:

```text
1. Try to find existing resources by name.
2. If found, reuse them.
3. If not found, create them.
4. For availability, upsert.
5. For recipe steps, avoid duplicate step_order.
```

If APIs do not support find-by-name, use state file.

MVP acceptable:

```text
If seed already exists, print a clear message and continue.
```

### 15.4. CLI arguments

Recommended args:

```bash
python scripts/demo/seed_demo_data.py \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003 \
  --state-file scripts/demo/.demo_state.json
```

Use env defaults:

```text
KITCHEN_SERVICE_URL
MENU_SERVICE_URL
FULFILLMENT_SERVICE_URL
```

### 15.5. Output

Script should print:

```text
kitchen_id
grill_station_id
packaging_station_id
burger_menu_item_id
recommended SIMULATOR_WORKERS_CONFIG
```

Example:

```text
SIMULATOR_WORKERS_CONFIG=7a7fef8e-560f-4d77-95ab-758d9a4ae4b8:1,be1ba4c7-7f26-45b9-9bb4-c728ff99735f:1
```

---

## 16. Demo order creation

run-demo.sh should create an order after seeding.

Order request:

```json
{
  "kitchen_id": "{kitchen_id}",
  "pickup_deadline": "2026-04-30T18:45:00Z",
  "items": [
    {
      "menu_item_id": "{burger_menu_item_id}",
      "quantity": 1
    }
  ]
}
```

The script must capture:

```text
order_id
```

Then poll:

```http
GET /orders/{order_id}
GET /orders/{order_id}/tasks
```

Until:

```text
order.status = ready_for_pickup
```

Timeout:

```text
120 seconds recommended
```

Poll interval:

```text
2 seconds recommended
```

On timeout, script should print diagnostics:

```text
order response
order tasks response
KDS tasks for seeded stations
Redis streams
Redis pending info
Mongo recent events
```

---

## 17. run-demo.sh

Create:

```text
scripts/demo/run-demo.sh
```

Make it executable.

Required behavior:

```text
1. Set strict shell flags.
2. Start compose with profile demo.
3. Wait for infrastructure health.
4. Wait for service /health endpoints.
5. Run migrations.
6. Seed demo data.
7. Restart or configure simulator with seeded station IDs if needed.
8. Create demo order.
9. Wait until order becomes ready_for_pickup.
10. Print success summary.
```

Shell flags:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

Suggested options:

```text
--clean
  docker compose down -v before starting

--no-build
  skip build

--timeout SECONDS
  override wait timeout

--keep-running
  do not stop containers after script
```

MVP can implement only:

```text
--clean
```

### 17.1. Compose command

Use variables:

```bash
COMPOSE_FILE="${COMPOSE_FILE:-deploy/compose/docker-compose.yml}"
COMPOSE="docker compose -f ${COMPOSE_FILE}"
```

Start:

```bash
$COMPOSE --profile demo up --build -d
```

Clean:

```bash
$COMPOSE --profile demo down -v
```

### 17.2. Waiting for health

Implement helper:

```bash
wait_for_url "http://localhost:8001/health"
wait_for_url "http://localhost:8002/health"
wait_for_url "http://localhost:8003/health"
wait_for_url "http://localhost:8004/health"
wait_for_url "http://localhost:9091/health"
wait_for_url "http://localhost:9090/-/ready"
```

If worker /health is on host port 9091.

If service host ports differ, keep script aligned with compose.

### 17.3. Running migrations

Example:

```bash
$COMPOSE run --rm kitchen-service alembic upgrade head
$COMPOSE run --rm menu-service alembic upgrade head
$COMPOSE run --rm fulfillment-service alembic upgrade head
```

If services are already running, using run is still acceptable.

Alternative:

```bash
$COMPOSE exec kitchen-service alembic upgrade head
```

Use whichever works with your Dockerfiles.

### 17.4. Seeding data

Run from host:

```bash
python scripts/demo/seed_demo_data.py \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003
```

Or run in a helper container if host Python is not guaranteed.

MVP acceptable:

```text
Host Python script with clear README requirement.
```

Better:

```text
Use a demo-tools container.
```

Do not overcomplicate unless needed.

### 17.5. Simulator worker config issue

If station IDs are generated dynamically, the simulator container needs them in SIMULATOR_WORKERS_CONFIG.

Recommended solutions in order:

1. Use deterministic station IDs in seed data if API supports client-provided IDs.
2. If not, seed script writes .demo_state.env:

```env
SIMULATOR_WORKERS_CONFIG=station1:1,station2:1
```

Then run-demo.sh restarts simulator with env file:

```bash
$COMPOSE --profile demo up -d --force-recreate station-simulator-service
```

However Docker Compose does not automatically reload env files generated after up unless configured.

Simpler MVP approach:

```text
Start simulator after seeding data.
```

Compose can keep simulator in profile demo, but run-demo.sh can start core first, seed, then start simulator with env var:

```bash
$COMPOSE up --build -d postgres redis mongo kitchen-service menu-service fulfillment-service kitchen-scheduler-worker prometheus grafana

python scripts/demo/seed_demo_data.py ...

export SIMULATOR_WORKERS_CONFIG="$(cat scripts/demo/.simulator_workers_config)"
$COMPOSE --profile demo up -d station-simulator-service
```

Document the chosen approach.

---

## 18. Demo flow assertions

run-demo.sh must verify the full flow.

Required checks:

```text
1. Kitchen exists.
2. Stations exist.
3. Menu item exists.
4. Recipe exists.
5. Availability is set.
6. POST /orders returns 201.
7. GET /orders/{order_id}/tasks returns tasks.
8. At least one task reaches displayed.
9. At least one task reaches in_progress or done.
10. All tasks eventually reach done.
11. Order eventually reaches ready_for_pickup.
12. Prometheus is reachable.
13. Grafana is reachable.
```

Optional checks:

```text
Redis stream has messages.
Redis pending messages eventually drop.
MongoDB has expected events.
```

Recommended final success output:

```text
Demo succeeded.

Order:
  order_id = ...
  status = ready_for_pickup

Stations:
  grill_station_id = ...
  packaging_station_id = ...

URLs:
  Kitchen Service: http://localhost:8001/docs
  Menu Service: http://localhost:8002/docs
  Fulfillment Service: http://localhost:8003/docs
  Simulator: http://localhost:8004/health
  Prometheus: http://localhost:9090
  Grafana: http://localhost:3000
```

---

## 19. Diagnostics on failure

If demo fails, print useful diagnostics.

### 19.1. Docker status

```bash
$COMPOSE ps
```

### 19.2. Service logs

Print last logs:

```bash
$COMPOSE logs --tail=100 kitchen-service
$COMPOSE logs --tail=100 menu-service
$COMPOSE logs --tail=100 fulfillment-service
$COMPOSE logs --tail=100 kitchen-scheduler-worker
$COMPOSE logs --tail=100 station-simulator-service
```

### 19.3. Order diagnostics

```bash
curl http://localhost:8003/orders/{order_id}
curl http://localhost:8003/orders/{order_id}/tasks
```

### 19.4. KDS diagnostics

```bash
curl http://localhost:8001/kds/stations/{grill_station_id}/tasks
curl http://localhost:8001/kds/stations/{packaging_station_id}/tasks
```

### 19.5. Redis diagnostics

```bash
docker compose -f deploy/compose/docker-compose.yml exec redis redis-cli KEYS 'stream:kitchen:*'
docker compose -f deploy/compose/docker-compose.yml exec redis redis-cli XRANGE {stream} - +
docker compose -f deploy/compose/docker-compose.yml exec redis redis-cli XPENDING {stream} group:kitchen-scheduler-workers
```

### 19.6. Mongo diagnostics

```bash
docker compose -f deploy/compose/docker-compose.yml exec mongo mongosh dark_kitchen_events --eval 'db.task_events.find().sort({created_at:-1}).limit(10).toArray()'
docker compose -f deploy/compose/docker-compose.yml exec mongo mongosh dark_kitchen_events --eval 'db.kds_events.find().sort({created_at:-1}).limit(10).toArray()'
```

Do not fail silently.

---

## 20. Prometheus and Grafana in demo

The demo compose must include Prometheus and Grafana from Stage 11.

Prometheus URL:

```text
http://localhost:9090
```

Grafana URL:

```text
http://localhost:3000
```

Default credentials if configured:

```text
admin / admin
```

run-demo.sh should check:

```text
Prometheus ready endpoint responds.
Grafana HTTP endpoint responds.
```

It does not need to validate dashboards in detail.

README must mention:

```text
Open Grafana and inspect Dark Kitchen dashboards after running the demo.
```

---

## 21. README updates

Update root README.md.

Add section:

```text
Docker Compose demo
```

Include:

```text
1. Prerequisites:
   - Docker
   - Docker Compose plugin
   - Python 3.11 if seed script runs on host
2. Clean run command.
3. Normal run command.
4. How to stop demo.
5. Service URLs.
6. Grafana credentials.
7. How to inspect logs.
8. How to rerun seed.
9. Troubleshooting.
```

Example:

```bash
chmod +x scripts/demo/run-demo.sh
./scripts/demo/run-demo.sh --clean
```

Stop:

```bash
docker compose -f deploy/compose/docker-compose.yml --profile demo down
```

Clean stop:

```bash
docker compose -f deploy/compose/docker-compose.yml --profile demo down -v
```

---

## 22. Test or smoke script

Optional but recommended:

```text
scripts/demo/smoke_demo.py
```

It can be used by run-demo.sh.

Responsibilities:

```text
1. Create order.
2. Poll order status.
3. Print diagnostics on failure.
```

If implemented, keep run-demo.sh simple.

If not implemented, run-demo.sh can use curl and jq.

If using jq, document it as a prerequisite.

To avoid jq dependency, use Python script.

Recommended:

```text
Use Python for JSON parsing.
```

---

## 23. Idempotency of demo

The demo should be repeatable.

Recommended behavior:

```text
./scripts/demo/run-demo.sh --clean
```

should always start from an empty state.

Without --clean:

```text
seed_demo_data.py should reuse existing kitchen/menu/stations where possible.
order creation creates a new order each run.
```

The script should not require manually deleting volumes.

---

## 24. Common pitfalls to handle

### 24.1. Services start before migrations

Solution:

```text
run migrations before seed and order creation.
Services can start before migrations, but seed should wait until migrations complete.
```

### 24.2. Simulator starts before station IDs are known

Solution:

```text
Use deterministic station IDs or start simulator after seed.
```

### 24.3. Worker scans streams before they exist

This is okay.

Worker should periodically scan stream patterns.

### 24.4. Packaging task waits for grill task

This is expected.

Worker should retry not-ready tasks.
run-demo.sh timeout must allow enough time.

### 24.5. Simulated duration too long

Use:

```env
SIMULATOR_SPEED_FACTOR=60
```

or higher for faster demo.

Recommended demo value:

```env
SIMULATOR_SPEED_FACTOR=120
```

### 24.6. Ports are already in use

README should mention changing port mappings or stopping local services.

---

## 25. Acceptance checklist

Stage is complete when:

```text
1. deploy/compose/docker-compose.yml exists.
2. Compose includes postgres.
3. Compose includes redis.
4. Compose includes mongo.
5. Compose includes kitchen-service.
6. Compose includes menu-service.
7. Compose includes fulfillment-service.
8. Compose includes kitchen-scheduler-worker.
9. Compose includes station-simulator-service behind profile demo.
10. Compose includes prometheus.
11. Compose includes grafana.
12. Compose uses repository root build context for Python services.
13. Python services can install dk-common in Docker.
14. Go worker builds in Docker.
15. PostgreSQL init creates needed service databases or schemas.
16. Migrations can be run from demo script.
17. seed_demo_data.py exists.
18. seed_demo_data.py creates kitchen.
19. seed_demo_data.py creates stations.
20. seed_demo_data.py creates menu item.
21. seed_demo_data.py creates recipe steps.
22. seed_demo_data.py sets availability.
23. seed_demo_data.py outputs created IDs or state file.
24. run-demo.sh exists and is executable.
25. run-demo.sh can start compose.
26. run-demo.sh waits for health checks.
27. run-demo.sh runs migrations.
28. run-demo.sh seeds data.
29. run-demo.sh creates an order.
30. run-demo.sh waits for ready_for_pickup.
31. Full flow reaches ready_for_pickup locally.
32. Prometheus is reachable.
33. Grafana is reachable.
34. README documents demo usage.
35. Failure diagnostics are printed on timeout.
```

---

## 26. Short instruction for the agent

Implement Stage 12: Docker Compose demo.

Add or update:

```text
deploy/compose/docker-compose.yml
.env.example
scripts/demo/seed_demo_data.py
scripts/demo/run-demo.sh
README.md
```

Compose must run:

```text
postgres
mongo
redis
kitchen-service
menu-service
fulfillment-service
kitchen-scheduler-worker
station-simulator-service with profile demo
prometheus
grafana
```

seed_demo_data.py must create through HTTP APIs:

```text
Demo Kitchen
grill station
packaging station
Burger menu item
grill recipe step
packaging recipe step
availability
```

run-demo.sh must:

```text
start compose
wait for services
run migrations
seed data
create order
wait until order.status = ready_for_pickup
print useful URLs and diagnostics
```

Do not implement:

```text
Kubernetes
new business logic
new service endpoints
frontend
service mesh
```
