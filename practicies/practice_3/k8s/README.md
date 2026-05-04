# Практика 3: отчет по Kubernetes / Minikube

Инструкция рассчитана на запуск через WSL/Linux. Все команды ниже выполняются из WSL-терминала.

Основные Kubernetes-манифесты находятся в:

```text
deploy/k8s
```

Основной overlay для Minikube:

```text
deploy/k8s/overlays/minikube
```

Подробная инструкция по Minikube:

```text
docs/k8s/minikube.md
```

## Список микросервисов и образов

Прикладные микросервисы:

| Микросервис | Kubernetes workload | Service | Docker image |
| --- | --- | --- | --- |
| kitchen-service | Deployment/kitchen-service | svc/kitchen-service:8000 | dark-kitchen/kitchen-service:local |
| menu-service | Deployment/menu-service | svc/menu-service:8000 | dark-kitchen/menu-service:local |
| fulfillment-service | Deployment/fulfillment-service | svc/fulfillment-service:8000 | dark-kitchen/fulfillment-service:local |
| kitchen-scheduler-worker | Deployment/kitchen-scheduler-worker | svc/kitchen-scheduler-worker:9090 | dark-kitchen/kitchen-scheduler-worker:local |
| station-simulator-service | Deployment/station-simulator-service | svc/station-simulator-service:8000 | dark-kitchen/station-simulator-service:local |

Инфраструктурные компоненты:

| Компонент | Kubernetes workload | Service | Docker image |
| --- | --- | --- | --- |
| PostgreSQL | StatefulSet/postgres | svc/postgres:5432 | postgres:16 |
| Redis | StatefulSet/redis | svc/redis:6379 | redis:7 |
| MongoDB | StatefulSet/mongo | svc/mongo:27017 | mongo:7 |
| Prometheus | Deployment/prometheus | svc/prometheus:9090 | prom/prometheus:v2.55.1 |
| Grafana | Deployment/grafana | svc/grafana:3000 | grafana/grafana:11.3.0 |

Получить список образов из манифестов:

```bash
rg -n "image:" deploy/k8s/base
```

Получить список образов из запущенного кластера:

```bash
kubectl -n dark-kitchen get deploy,statefulset \
  -o custom-columns=KIND:.kind,NAME:.metadata.name,IMAGE:.spec.template.spec.containers[*].image
```

## Развертывание в Minikube

Перейти в корень репозитория. Если проект лежит на диске `F:` Windows, путь в WSL обычно будет таким:

```bash
cd /mnt/f/programming/projects/dark_kitchen_simulator
```

Запустить Minikube и включить Ingress:

```bash
minikube start
minikube addons enable ingress
```

Собрать локальные Docker-образы и загрузить их в Minikube:

```bash
chmod +x scripts/k8s/*.sh
./scripts/k8s/minikube-build-images.sh
```

Скрипт собирает и загружает следующие образы:

```text
dark-kitchen/kitchen-service:local
dark-kitchen/menu-service:local
dark-kitchen/fulfillment-service:local
dark-kitchen/kitchen-scheduler-worker:local
dark-kitchen/station-simulator-service:local
```

Применить Kubernetes-манифесты:

```bash
kubectl apply -k deploy/k8s/overlays/minikube
```

Дождаться готовности StatefulSet и Deployment:

```bash
kubectl -n dark-kitchen rollout status statefulset/postgres
kubectl -n dark-kitchen rollout status statefulset/redis
kubectl -n dark-kitchen rollout status statefulset/mongo

kubectl -n dark-kitchen rollout status deploy/kitchen-service
kubectl -n dark-kitchen rollout status deploy/menu-service
kubectl -n dark-kitchen rollout status deploy/fulfillment-service
kubectl -n dark-kitchen rollout status deploy/kitchen-scheduler-worker
kubectl -n dark-kitchen rollout status deploy/station-simulator-service
kubectl -n dark-kitchen rollout status deploy/prometheus
kubectl -n dark-kitchen rollout status deploy/grafana
```

Применить миграции БД:

```bash
./scripts/k8s/run-migrations.sh
```

Или вручную:

```bash
kubectl -n dark-kitchen exec deploy/kitchen-service -- alembic upgrade head
kubectl -n dark-kitchen exec deploy/menu-service -- alembic upgrade head
kubectl -n dark-kitchen exec deploy/fulfillment-service -- alembic upgrade head
```

Проверить созданные ресурсы:

```bash
kubectl -n dark-kitchen get pods
kubectl -n dark-kitchen get svc
kubectl -n dark-kitchen get ingress
```

## Проброс портов

Команды `port-forward` остаются активными, поэтому каждую из них удобно запускать в отдельном WSL-терминале.

Прикладные сервисы:

```bash
kubectl -n dark-kitchen port-forward svc/kitchen-service 8001:8000
kubectl -n dark-kitchen port-forward svc/menu-service 8002:8000
kubectl -n dark-kitchen port-forward svc/fulfillment-service 8003:8000
kubectl -n dark-kitchen port-forward svc/station-simulator-service 8004:8000
kubectl -n dark-kitchen port-forward svc/kitchen-scheduler-worker 9091:9090
```

Сервисы наблюдаемости:

```bash
kubectl -n dark-kitchen port-forward svc/prometheus 9090:9090
kubectl -n dark-kitchen port-forward svc/grafana 3000:3000
```

Проверка health endpoints:

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:9091/health
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
```

Grafana будет доступна по адресу:

```text
http://localhost:3000
```

Логин и пароль для локального стенда:

```text
admin / admin
```

## Проверка приложения через Ingress

Настроенные маршруты Ingress:

```text
http://dark-kitchen.local/orders -> fulfillment-service
http://dark-kitchen.local/kds -> kitchen-service
http://dark-kitchen.local/kitchens -> kitchen-service
http://dark-kitchen.local/menu-items -> menu-service
```

Получить IP Minikube:

```bash
minikube ip
```

Добавить запись в `/etc/hosts` внутри WSL:

```bash
echo "$(minikube ip) dark-kitchen.local" | sudo tee -a /etc/hosts
```

Проверить запросы через Ingress:

```bash
curl -i http://dark-kitchen.local:8080/kitchens
curl -i "http://dark-kitchen.local/menu-items?limit=5"
curl -i http://dark-kitchen.local/kds/stations/11111111-1111-1111-1111-111111111101/tasks
```

Можно не менять `/etc/hosts`, а использовать `--resolve`:

```bash
curl --resolve "dark-kitchen.local:80:$(minikube ip)" -i http://dark-kitchen.local/kitchens
curl --resolve "dark-kitchen.local:80:$(minikube ip)" -i http://dark-kitchen.local/kds/stations/11111111-1111-1111-1111-111111111101/tasks
```

Если Ingress не открывается напрямую, запустить в отдельном WSL-терминале:

```bash
minikube tunnel
```

После `minikube tunnel` иногда удобнее использовать IP `127.0.0.1`:

```bash
curl --resolve "dark-kitchen.local:80:127.0.0.1" -i http://dark-kitchen.local/kitchens
```

## Запуск демо-сценария

Перед запуском демо нужно открыть port-forward для сервисов. Каждую команду лучше держать в отдельном WSL-терминале:

```bash
kubectl -n dark-kitchen port-forward svc/kitchen-service 8001:8000
kubectl -n dark-kitchen port-forward svc/menu-service 8002:8000
kubectl -n dark-kitchen port-forward svc/fulfillment-service 8003:8000
kubectl -n dark-kitchen port-forward svc/prometheus 9090:9090
kubectl -n dark-kitchen port-forward svc/grafana 3000:3000
```

Загрузить тестовые данные:

```bash
python scripts/demo/seed_demo_data.py \
  --kitchen-url http://localhost:8001 \
  --menu-url http://localhost:8002 \
  --fulfillment-url http://localhost:8003
```

Запустить полный smoke demo. Скрипт создает заказ, ждет dispatch от scheduler worker, выполнение задач station simulator, переход заказа в `ready_for_pickup`, а также проверяет доступность Prometheus и Grafana:

```bash
python scripts/demo/smoke_demo.py \
  --fulfillment-url http://localhost:8003 \
  --kitchen-url http://localhost:8001 \
  --prometheus-url http://localhost:9090 \
  --grafana-url http://localhost:3000 \
  --timeout 180
```

Ожидаемый успешный результат:

```text
Demo succeeded.
order_status=ready_for_pickup
```

## Команды для скриншотов

Скриншот списка Pod, Service и Ingress:

```bash
kubectl -n dark-kitchen get pods,svc,ingress
```

Скриншот успешного curl-запроса через Ingress:

```bash
curl --resolve "dark-kitchen.local:80:$(minikube ip)" -i http://dark-kitchen.local/kds/stations/11111111-1111-1111-1111-111111111101/tasks
```

Скриншот логов одного из подов:

```bash
kubectl -n dark-kitchen logs deploy/fulfillment-service --tail=100
```

Альтернативные команды для логов:

```bash
kubectl -n dark-kitchen logs deploy/kitchen-scheduler-worker --tail=100
kubectl -n dark-kitchen logs deploy/station-simulator-service --tail=100
```

## Места для скриншотов

Скриншоты можно положить в папку:

```text
practicies/practice_3/k8s/screenshots
```

### kubectl get pods,svc,ingress

Файл скриншота:

```text
practicies/practice_3/k8s/screenshots/get-pods-svc-ingress.png
```

### curl через Ingress

Файл скриншота:

```text
practicies/practice_3/k8s/screenshots/curl-ingress.png
```

### Логи пода

Файл скриншота:

```text
practicies/practice_3/k8s/screenshots/pod-logs.png
```

## Дополнительные Kubernetes-возможности

В основном Minikube-деплое реализовано:

- StatefulSet для PostgreSQL: `deploy/k8s/base/postgres/statefulset.yaml`
- StatefulSet для Redis: `deploy/k8s/base/redis/statefulset.yaml`
- StatefulSet для MongoDB: `deploy/k8s/base/mongo/statefulset.yaml`
- PVC через `volumeClaimTemplates` для хранения данных stateful-компонентов
- Ingress для маршрутов `/orders` и `/kds`
- Deployment для Prometheus и Grafana

Дополнительные манифесты, которые есть в репозитории, но не применяются основным overlay `deploy/k8s/overlays/minikube`:

- HPA manifests: `deploy/k8s/base/hpa`
- Service Mesh / Linkerd injection patch note: `deploy/k8s/base/service-mesh`
- Prometheus Operator `ServiceMonitor` и дополнительные Grafana dashboard ConfigMaps: `deploy/k8s/base/observability`

Посмотреть сгенерированные HPA-манифесты:

```bash
kubectl kustomize deploy/k8s/base/hpa
```

Применить HPA после включения Metrics Server:

```bash
minikube addons enable metrics-server
kubectl apply -k deploy/k8s/base/hpa
kubectl -n dark-kitchen get hpa
```

Манифесты из `deploy/k8s/base/observability` не нужно применять в обычный Minikube-кластер, если в нем не установлены CRD от Prometheus Operator для ресурса `ServiceMonitor`.

## Очистка стенда

Удалить namespace со всеми ресурсами:

```bash
kubectl delete namespace dark-kitchen
```

Остановить Minikube:

```bash
minikube stop
```
