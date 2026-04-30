from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.clients import FulfillmentClient, FulfillmentClientError
from app.events import MongoKdsEventWriter
from app.metrics import business_metrics
from app.models import KdsStationTask, KdsTaskStatus, Kitchen, Station, StationStatus, StationType
from app.repositories import KdsRepository, KitchenRepository, StationRepository
from app.schemas import (
    DispatchCandidateResponse,
    KdsTaskClaimRequest,
    KdsTaskCompleteRequest,
    KdsTaskDeliveryRequest,
    KitchenCreate,
    StationCreate,
)


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class KdsDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code


class KitchenService:
    def __init__(self, session: AsyncSession, event_writer: MongoKdsEventWriter | None = None) -> None:
        self.session = session
        self.kitchens = KitchenRepository(session)
        self.stations = StationRepository(session)
        self.event_writer = event_writer

    async def create_kitchen(self, payload: KitchenCreate) -> Kitchen:
        try:
            kitchen = await self.kitchens.create(payload)
            await self.session.commit()
            return kitchen
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("kitchen_already_exists") from exc

    async def list_kitchens(self) -> list[Kitchen]:
        return await self.kitchens.list()

    async def get_kitchen(self, kitchen_id: UUID) -> Kitchen:
        kitchen = await self.kitchens.get(kitchen_id)
        if kitchen is None:
            raise NotFoundError("kitchen_not_found")
        return kitchen

    async def create_station(self, kitchen_id: UUID, payload: StationCreate) -> Station:
        await self.get_kitchen(kitchen_id)
        try:
            station = await self.stations.create(kitchen_id, payload)
            await self.session.commit()
            business_metrics.update_station_gauges(station, visible_backlog_size=0)
            await self._write_station_event(
                "StationCreated",
                station,
                None,
                {"status": station.status, "capacity": station.capacity, "visible_backlog_limit": station.visible_backlog_limit},
            )
            return station
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("station_already_exists") from exc

    async def list_stations(
        self,
        kitchen_id: UUID,
        station_type: StationType | None = None,
    ) -> list[Station]:
        await self.get_kitchen(kitchen_id)
        return await self.stations.list_by_kitchen(kitchen_id, station_type)

    async def update_station_capacity(self, station_id: UUID, capacity: int) -> Station:
        station = await self._get_station(station_id)
        station.capacity = capacity
        await self.session.commit()
        await self.session.refresh(station)
        business_metrics.update_station_gauges(station)
        await self._write_station_event("StationCapacityChanged", station, None, {"capacity": station.capacity})
        return station

    async def update_station_status(self, station_id: UUID, status: StationStatus) -> Station:
        station = await self._get_station(station_id)
        station.status = status
        await self.session.commit()
        await self.session.refresh(station)
        business_metrics.update_station_gauges(station)
        await self._write_station_event("StationStatusChanged", station, None, {"status": station.status})
        return station

    async def _get_station(self, station_id: UUID) -> Station:
        station = await self.stations.get(station_id)
        if station is None:
            raise NotFoundError("station_not_found")
        return station

    async def _write_station_event(
        self,
        event_type: str,
        station: Station,
        correlation_id: str | None,
        payload: dict,
    ) -> None:
        if self.event_writer is None:
            return
        try:
            await self.event_writer.write_station_event(
                event_type,
                kitchen_id=station.kitchen_id,
                station_id=station.id,
                station_type=station.station_type,
                correlation_id=correlation_id,
                payload=payload,
            )
        except Exception as exc:
            logger.bind(event="station_event_failed", station_id=station.id).error(
                "failed to write {} event: {}",
                event_type,
                exc,
            )


class KdsService:
    def __init__(
        self,
        session: AsyncSession,
        event_writer: MongoKdsEventWriter,
        fulfillment_client: FulfillmentClient,
    ) -> None:
        self.session = session
        self.stations = StationRepository(session)
        self.kds = KdsRepository(session)
        self.event_writer = event_writer
        self.fulfillment_client = fulfillment_client

    async def dispatch_candidates(
        self,
        kitchen_id: UUID,
        station_type: StationType,
    ) -> list[DispatchCandidateResponse]:
        rows = await self.kds.dispatch_candidates(kitchen_id, station_type)
        return [
            DispatchCandidateResponse(
                station_id=station.id,
                station_type=station.station_type,
                status=station.status,
                capacity=station.capacity,
                busy_slots=station.busy_slots,
                visible_backlog_size=visible_backlog_size,
                visible_backlog_limit=station.visible_backlog_limit,
                health="ok",
            )
            for station, visible_backlog_size in rows
        ]

    async def deliver_task(
        self,
        station_id: UUID,
        payload: KdsTaskDeliveryRequest,
        correlation_id: str | None,
    ) -> tuple[KdsStationTask, bool]:
        existing = await self.kds.get_by_idempotency_key(payload.idempotency_key)
        if existing is not None:
            return existing, False

        station = await self.stations.get_for_update(station_id)
        if station is None:
            raise KdsDomainError("station_not_found", "Station not found", status_code=404)
        self._validate_delivery_station(station, payload)

        visible_backlog_size = await self.kds.visible_backlog_size(station_id)
        if visible_backlog_size >= station.visible_backlog_limit:
            raise KdsDomainError(
                "visible_backlog_limit_exceeded",
                "Station visible backlog limit exceeded",
            )

        try:
            task = await self.kds.create_task(station_id, payload)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            replay = await self.kds.get_by_idempotency_key(payload.idempotency_key)
            if replay is not None:
                return replay, False
            duplicate_task = await self.kds.get_by_task_id(str(payload.task_id))
            if duplicate_task is not None:
                raise KdsDomainError("kds_task_already_exists", "KDS task already exists") from exc
            raise

        try:
            await self.event_writer.write_task_displayed(task, correlation_id)
        except Exception as exc:
            logger.bind(event="kds_task_displayed_event_failed", task_id=task.task_id).error(
                "failed to write KdsTaskDisplayed event: {}",
                exc,
            )
        backlog_after = await self.kds.visible_backlog_size(station_id)
        business_metrics.update_station_gauges(station, visible_backlog_size=backlog_after)
        return task, True

    async def list_station_tasks(
        self,
        station_id: UUID,
        task_status: KdsTaskStatus,
        limit: int,
        offset: int,
    ) -> list[KdsStationTask]:
        station = await self.stations.get(station_id)
        if station is None:
            raise KdsDomainError("station_not_found", "Station not found", status_code=404)
        return await self.kds.list_station_tasks(station_id, task_status, limit, offset)

    async def claim_task(
        self,
        station_id: UUID,
        task_id: str,
        payload: KdsTaskClaimRequest,
        correlation_id: str | None,
    ) -> KdsStationTask:
        claimed_at = payload.claimed_at or datetime.now(UTC)
        station = await self.stations.get_for_update(station_id)
        if station is None:
            raise KdsDomainError("station_not_found", "Station not found", status_code=404)

        task = await self.kds.get_by_task_id_for_update(task_id)
        if task is None:
            raise KdsDomainError("kds_task_not_found", "KDS task not found", status_code=404)
        business_metrics.kds_claim_attempts_total.labels(
            str(station.kitchen_id),
            str(station.id),
            str(station.station_type),
        ).inc()
        try:
            self._validate_claim(station, task)
        except KdsDomainError as exc:
            business_metrics.kds_claim_conflicts_total.labels(
                str(station.kitchen_id),
                str(station.id),
                str(station.station_type),
                exc.code,
            ).inc()
            await self._write_kds_event(
                "KdsTaskClaimRejected",
                task,
                payload.station_worker_id,
                correlation_id,
                {"reason": exc.code},
            )
            raise

        task.status = KdsTaskStatus.claimed
        task.claimed_by = payload.station_worker_id
        task.claimed_at = claimed_at
        station.busy_slots += 1
        await self.session.commit()
        await self.session.refresh(task)
        await self.session.refresh(station)

        try:
            await self.fulfillment_client.start_task(
                task.task_id,
                station_id=str(station.id),
                kds_task_id=str(task.id),
                station_worker_id=payload.station_worker_id,
                started_at=claimed_at,
            )
        except FulfillmentClientError as exc:
            await self.event_writer.write_audit_event(
                "ExternalServiceUnavailable" if exc.code == "fulfillment_service_unavailable" else "FulfillmentCallbackFailed",
                correlation_id=correlation_id,
                task_id=task.task_id,
                order_id=task.order_id,
                station_id=station.id,
                station_type=station.station_type,
                kds_task_id=task.id,
                payload={
                    "external_service": "fulfillment-service",
                    "operation": "POST /internal/tasks/{task_id}/start",
                    "error": str(exc.code),
                },
            )
            await self._compensate_claim(task.task_id, payload.station_worker_id, correlation_id, str(exc.code))
            status_code = 503 if exc.code == "fulfillment_service_unavailable" else 409
            message = (
                "Fulfillment Service is unavailable"
                if exc.code == "fulfillment_service_unavailable"
                else "Fulfillment rejected task start"
            )
            raise KdsDomainError(exc.code, message, status_code=status_code) from exc

        business_metrics.kds_claim_success_total.labels(
            str(station.kitchen_id),
            str(station.id),
            str(station.station_type),
        ).inc()
        backlog_after = await self.kds.visible_backlog_size(station_id)
        business_metrics.update_station_gauges(station, visible_backlog_size=backlog_after)
        await self._write_kds_event(
            "KdsTaskClaimed",
            task,
            payload.station_worker_id,
            correlation_id,
            {"claimed_at": claimed_at.isoformat()},
        )
        await self._write_station_event(
            "StationBusySlotOccupied",
            station,
            correlation_id,
            {"busy_slots": station.busy_slots, "capacity": station.capacity},
        )
        return task

    async def complete_task(
        self,
        station_id: UUID,
        task_id: str,
        payload: KdsTaskCompleteRequest,
        correlation_id: str | None,
    ) -> KdsStationTask:
        completed_at = payload.completed_at or datetime.now(UTC)
        station = await self.stations.get_for_update(station_id)
        if station is None:
            raise KdsDomainError("station_not_found", "Station not found", status_code=404)

        task = await self.kds.get_by_task_id_for_update(task_id)
        if task is None:
            raise KdsDomainError("kds_task_not_found", "KDS task not found", status_code=404)
        self._validate_complete(station, task, payload.station_worker_id)
        await self.session.commit()

        try:
            await self.fulfillment_client.complete_task(
                task.task_id,
                station_id=str(station.id),
                kds_task_id=str(task.id),
                station_worker_id=payload.station_worker_id,
                completed_at=completed_at,
            )
        except FulfillmentClientError as exc:
            await self.event_writer.write_audit_event(
                "ExternalServiceUnavailable" if exc.code == "fulfillment_service_unavailable" else "FulfillmentCallbackFailed",
                correlation_id=correlation_id,
                task_id=task.task_id,
                order_id=task.order_id,
                station_id=station.id,
                station_type=station.station_type,
                kds_task_id=task.id,
                payload={
                    "external_service": "fulfillment-service",
                    "operation": "POST /internal/tasks/{task_id}/complete",
                    "error": str(exc.code),
                },
            )
            status_code = 503 if exc.code == "fulfillment_service_unavailable" else 409
            message = (
                "Fulfillment Service is unavailable"
                if exc.code == "fulfillment_service_unavailable"
                else "Fulfillment rejected task complete"
            )
            raise KdsDomainError(exc.code, message, status_code=status_code) from exc

        station = await self.stations.get_for_update(station_id)
        task = await self.kds.get_by_task_id_for_update(task_id)
        if station is None or task is None:
            raise KdsDomainError("kds_task_not_found", "KDS task not found", status_code=404)
        self._validate_complete(station, task, payload.station_worker_id)

        task.status = KdsTaskStatus.completed
        task.completed_at = completed_at
        station.busy_slots = max(0, station.busy_slots - 1)
        await self.session.commit()
        await self.session.refresh(task)
        await self.session.refresh(station)
        backlog_after = await self.kds.visible_backlog_size(station_id)
        business_metrics.update_station_gauges(station, visible_backlog_size=backlog_after)

        await self._write_kds_event(
            "KdsTaskCompleted",
            task,
            payload.station_worker_id,
            correlation_id,
            {"completed_at": completed_at.isoformat()},
        )
        await self._write_station_event(
            "StationBusySlotReleased",
            station,
            correlation_id,
            {"busy_slots": station.busy_slots, "capacity": station.capacity, "reason": "task_completed"},
        )
        return task

    def _validate_delivery_station(self, station: Station, payload: KdsTaskDeliveryRequest) -> None:
        if station.status != StationStatus.available:
            raise KdsDomainError("station_not_available", "Station is not available")
        if station.kitchen_id != payload.kitchen_id:
            raise KdsDomainError("station_kitchen_mismatch", "Station belongs to another kitchen")
        if station.station_type != payload.station_type:
            raise KdsDomainError("station_type_mismatch", "Station type does not match task station type")

    def _validate_claim(self, station: Station, task: KdsStationTask) -> None:
        if task.station_id != station.id:
            raise KdsDomainError("kds_task_station_mismatch", "KDS task belongs to another station")
        if station.status != StationStatus.available:
            raise KdsDomainError("station_not_available", "Station is not available")
        if task.status == KdsTaskStatus.claimed:
            raise KdsDomainError("task_already_claimed", "Task is already claimed")
        if task.status != KdsTaskStatus.displayed:
            raise KdsDomainError("task_not_displayed", "Task is not displayed")
        if station.busy_slots >= station.capacity:
            raise KdsDomainError("station_capacity_exceeded", "Station capacity is exceeded")

    def _validate_complete(self, station: Station, task: KdsStationTask, station_worker_id: str) -> None:
        if task.station_id != station.id:
            raise KdsDomainError("kds_task_station_mismatch", "KDS task belongs to another station")
        if task.status == KdsTaskStatus.completed:
            raise KdsDomainError("task_already_completed", "Task is already completed")
        if task.status != KdsTaskStatus.claimed:
            raise KdsDomainError("task_not_claimed", "Task is not claimed")
        if task.claimed_by != station_worker_id:
            raise KdsDomainError("task_claimed_by_another_worker", "Task is claimed by another worker")

    async def _compensate_claim(
        self,
        task_id: str,
        station_worker_id: str,
        correlation_id: str | None,
        reason: str,
    ) -> None:
        task = await self.kds.get_by_task_id_for_update(task_id)
        if task is None:
            await self.session.rollback()
            return
        station = await self.stations.get_for_update(task.station_id)
        if station is None:
            await self.session.rollback()
            return

        if task.status == KdsTaskStatus.claimed and task.claimed_by == station_worker_id:
            task.status = KdsTaskStatus.displayed
            task.claimed_by = None
            task.claimed_at = None
            station.busy_slots = max(0, station.busy_slots - 1)
            await self.session.commit()
            await self.session.refresh(task)
            await self.session.refresh(station)

            await self._write_kds_event(
                "KdsTaskClaimRejected",
                task,
                station_worker_id,
                correlation_id,
                {"reason": reason},
            )
            await self._write_station_event(
                "StationBusySlotReleased",
                station,
                correlation_id,
                {"busy_slots": station.busy_slots, "capacity": station.capacity, "reason": "claim_compensation"},
            )
        else:
            await self.session.rollback()

    async def _write_kds_event(
        self,
        event_type: str,
        task: KdsStationTask,
        station_worker_id: str,
        correlation_id: str | None,
        payload: dict,
    ) -> None:
        try:
            await self.event_writer.write_kds_event(event_type, task, station_worker_id, correlation_id, payload)
        except Exception as exc:
            logger.bind(event="kds_event_failed", task_id=task.task_id).error(
                "failed to write {} event: {}",
                event_type,
                exc,
            )

    async def _write_station_event(
        self,
        event_type: str,
        station: Station,
        correlation_id: str | None,
        payload: dict,
    ) -> None:
        try:
            await self.event_writer.write_station_event(
                event_type,
                kitchen_id=station.kitchen_id,
                station_id=station.id,
                station_type=station.station_type,
                correlation_id=correlation_id,
                payload=payload,
            )
        except Exception as exc:
            logger.bind(event="station_event_failed", station_id=station.id).error(
                "failed to write {} event: {}",
                event_type,
                exc,
            )
