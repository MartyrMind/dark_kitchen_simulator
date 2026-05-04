# Финальный отчет по проекту Dark Kitchen Simulator

## Ссылка на репозиторий

Репозиторий проекта: <https://github.com/MartyrMind/dark_kitchen_simulator>

## Краткое описание выбранной темы

Тема проекта: **микросервисная backend-система управления выполнением заказов для dark kitchen**.

Система моделирует путь заказа от создания до готовности к выдаче:

```text
POST /orders
  -> Fulfillment Service создает order и kitchen_tasks
  -> задачи публикуются в Redis Streams
  -> Go Kitchen Scheduler Worker выбирает подходящую станцию
  -> задача доставляется в KDS внутри Kitchen Service
  -> Station Simulator имитирует claim и complete
  -> Fulfillment Service переводит задачи в done
  -> заказ переходит в ready_for_pickup
```

Архитектура разделена на несколько сервисов:

- **Fulfillment Service**: владеет заказами, kitchen tasks и глобальными бизнес-статусами.
- **Kitchen Service**: владеет кухнями, станциями, capacity, busy slots и KDS.
- **Menu Service**: владеет меню, доступностью блюд и recipe steps.
- **Kitchen Scheduler Worker**: Go-сервис, который выполняет только dispatch из Redis Streams в KDS.
- **Station Simulator Service**: demo-сервис, имитирующий работу сотрудников станции через KDS API.

Для хранения текущего состояния используется PostgreSQL, для асинхронной очереди задач - Redis Streams, для audit/business events - MongoDB, для наблюдаемости - Prometheus и Grafana.

## Объединение отчетов практик

### Практика 1. Архитектура и C4

Отчет: [practicies/practice_1/README.md](practicies/practice_1/README.md)

В первой практике была сформулирована предметная область и архитектурная модель системы. Были подготовлены C4-диаграммы:

- C1 Context: система dark kitchen во внешнем окружении.
- C2 Containers: микросервисы, базы данных, Redis Streams, MongoDB, Prometheus/Grafana.
- C3 Components для Kitchen Service / KDS: внутренние компоненты KDS, capacity guard, repositories, API и взаимодействие с Fulfillment.

Главный результат практики - были зафиксированы границы владения данными. Fulfillment отвечает за глобальные статусы заказов и задач, Kitchen Service - за состояние KDS и станций, Menu Service - за рецепты и меню, worker - только за dispatch.

### Практика 2. Реализация и Docker Compose

Отчет: [practicies/practice_2/PRACTICE2.md](practicies/practice_2/PRACTICE2.md)

Во второй практике была реализована основная микросервисная система:

- Python-сервисы с отдельными `pyproject.toml`: `kitchen-service`, `menu-service`, `fulfillment-service`, `station-simulator-service`.
- Go-сервис `kitchen-scheduler-worker` с собственным `go.mod`.
- Общая техническая библиотека `dk-common` для logging, healthcheck, correlation id и HTTP metrics.
- Dockerfile для сервисов и `docker-compose.yml` для локального запуска.
- PostgreSQL, Redis, MongoDB, Prometheus и Grafana в docker-compose окружении.
- Unit/component tests для сервисов и тесты worker logic.

Ключевой результат - полный demo-flow локально через Docker Compose: создание заказа, генерация kitchen tasks, публикация в Redis Streams, dispatch в KDS, claim/complete через simulator и переход заказа в `ready_for_pickup`.

### Практика 3. Kubernetes / Minikube

Отчет: [practicies/practice_3/k8s/README.md](practicies/practice_3/k8s/README.md)

В третьей практике система была перенесена в Kubernetes:

- Stateless-сервисы развернуты как `Deployment`.
- PostgreSQL, Redis и MongoDB развернуты как `StatefulSet` с постоянным хранилищем.
- Для сервисов созданы `Service`, `ConfigMap`, `Secret`, `Ingress`.
- Добавлены Minikube overlay и scripts для сборки локальных образов, деплоя и миграций.
- Проверены `kubectl get pods`, `svc`, `ingress`, health endpoints и demo сценарий.

Дополнительно были реализованы:

- **HPA** для stateless-сервисов.
- **Linkerd Service Mesh** с sidecar injection для приложений.
- Проверка traffic statistics через Linkerd Viz.

Практика показала, что локальная микросервисная система может быть перенесена в Kubernetes без нарушения границ сервисов.

### Практика 4. Мониторинг

Отчет: [practicies/practice_4/README.md](practicies/practice_4/README.md)

В четвертой практике была оформлена наблюдаемость системы:

- Выбрана связка `Prometheus + Grafana` через `kube-prometheus-stack`.
- Приложения экспортируют `/metrics`.
- Prometheus собирает метрики через `ServiceMonitor`.
- Grafana получает dashboards через sidecar и ConfigMap с label `grafana_dashboard: "1"`.
- Подготовлены dashboards: application overview, business flow, Kubernetes API server и список dashboard'ов.

Основные группы метрик:

- HTTP RPS, 5xx rate и p95 latency по сервисам.
- Бизнес-метрики заказов и kitchen tasks.
- KDS backlog, claim conflicts, station capacity и utilization.
- Worker dispatch attempts/success/failures/retries, Redis pending и DLQ.
- Simulator worker metrics.

Нагрузочный тест через `fortio` показал рост RPS примерно до 50 RPS, рост p95 latency в миллисекундном диапазоне и отсутствие 5xx/dispatch failures/DLQ на наблюдаемом интервале.

## Дополнительные усложнения

В проекте реализованы дополнительные элементы, которые повышают качество системы:

| Усложнение | Почему повышает качество |
|---|---|
| Redis Streams между Fulfillment и worker | Делает dispatch асинхронным и ближе к реальной event-driven архитектуре. Сервис создания заказов не обязан синхронно ждать KDS. |
| Go Kitchen Scheduler Worker | Отделяет orchestration/dispatch от Python backend-сервисов и демонстрирует polyglot microservices. |
| Четкие границы владения данными | Снижает связанность: Fulfillment не пишет в KDS, Kitchen Service не меняет глобальные статусы напрямую, Menu Service не создает заказы. |
| MongoDB audit/business events | Позволяет хранить историю бизнес-событий отдельно от текущего состояния в PostgreSQL. |
| Station Simulator Service | Позволяет проверять полный flow без ручной работы через KDS API. |
| Prometheus metrics и Grafana dashboards | Делают систему наблюдаемой: видны RPS, latency, backlog, utilization, DLQ и ошибки dispatch. |
| Kubernetes StatefulSet для БД/Redis/Mongo | Корректнее моделирует stateful-инфраструктуру, чем обычный Deployment. |
| HPA | Показывает готовность stateless-сервисов к горизонтальному масштабированию под нагрузкой. |
| Linkerd Service Mesh | Добавляет mTLS и traffic visibility между сервисами без изменения бизнес-кода. |
| Unit/component/integration-style проверки | Повышают доверие к переходам статусов, KDS operations, worker dispatch и metrics endpoints. |

Эти усложнения делают проект не просто набором CRUD-сервисов, а более реалистичной микросервисной системой с очередями, worker'ом, наблюдаемостью, инфраструктурой и эксплуатационными сценариями.

## Заключение и рефлексия

Использование ИИ на всех этапах разработки заметно изменило понимание процесса создания ПО. Раньше разработка воспринималась как последовательная работа: сначала требования, потом архитектура, потом код, тесты и документация. С ИИ этот процесс стал более итеративным: можно быстро получить черновик архитектуры, проверить слабые места, попросить альтернативы, сгенерировать тесты, найти несоответствия и затем вручную принять инженерные решения.

Самое полезное применение ИИ в этом проекте:

- **Архитектурное моделирование**: ИИ хорошо помогает разложить систему на bounded contexts, сформулировать C4-диаграммы и заметить лишние связи.
- **Создание boilerplate-кода**: сервисные шаблоны, Dockerfile, Kubernetes manifests, тестовые заготовки и README ускоряются в разы.
- **Проверка consistency**: ИИ полезен как reviewer, который напоминает про границы сервисов, миграции, метрики, тесты и audit events.
- **Документация**: отчеты, инструкции запуска и пояснения dashboards быстрее приводятся к единому стилю.
- **Тестирование**: ИИ помогает придумать edge cases: повторный dispatch, конфликт claim, недоступность внешнего сервиса, retry, DLQ.

Где ИИ менее применим или требует особенно строгого контроля:

- **Финальные архитектурные решения**: ИИ может предложить слишком сложную или слишком связанную схему. Ответственность за границы сервисов остается на разработчике.
- **Безопасность и данные**: нельзя слепо принимать решения по секретам, доступам, auth, персональным данным и production-конфигурации.
- **Доменные инварианты**: ИИ может не почувствовать тонкости предметной области. Например, worker не должен переводить задачу в `done`, даже если это кажется удобным.
- **Отладка реального окружения**: Kubernetes, сеть, DNS, volume, port-forward и локальные особенности часто требуют ручной проверки.
- **Оценка готовности к production**: ИИ может создать убедительный текст, но только реальные тесты, метрики и эксплуатационный опыт показывают зрелость системы.

С учетом роста популярности ИИ рынок ИТ, скорее всего, изменится в сторону увеличения производительности отдельных инженеров. Простая генерация CRUD, конфигураций, тестов и документации станет дешевле. Поэтому ценность будет смещаться от умения просто писать код к умению:

- формулировать задачу;
- проектировать границы системы;
- проверять корректность и безопасность;
- читать чужой и сгенерированный код;
- строить надежную эксплуатацию;
- принимать инженерные решения в условиях неопределенности.

ИИ не заменяет разработчика полностью, но меняет роль разработчика. Разработчик становится не только автором кода, но и постановщиком задачи, архитектором, reviewer'ом, интегратором и ответственным за качество результата. В этом проекте это проявилось особенно хорошо: ИИ ускорял движение, но ключевые решения приходилось проверять через архитектурные правила, тесты, запуск системы и наблюдаемость.

Итоговый вывод: ИИ наиболее полезен как сильный ускоритель и партнер по анализу, но не как автономный источник истины. Лучший результат получается там, где ИИ генерирует варианты, а человек задает границы, проверяет факты и принимает финальные решения.
