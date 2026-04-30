from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.events import MongoKdsEventWriter
from app.models import KdsStationTask, KdsTaskStatus, Kitchen, Station, StationStatus, StationType
from app.repositories import KdsRepository, KitchenRepository, StationRepository
from app.schemas import DispatchCandidateResponse, KdsTaskDeliveryRequest, KitchenCreate, StationCreate


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
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kitchens = KitchenRepository(session)
        self.stations = StationRepository(session)

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

    async def get_kitchen(self, kitchen_id: int) -> Kitchen:
        kitchen = await self.kitchens.get(kitchen_id)
        if kitchen is None:
            raise NotFoundError("kitchen_not_found")
        return kitchen

    async def create_station(self, kitchen_id: int, payload: StationCreate) -> Station:
        await self.get_kitchen(kitchen_id)
        try:
            station = await self.stations.create(kitchen_id, payload)
            await self.session.commit()
            return station
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("station_already_exists") from exc

    async def list_stations(
        self,
        kitchen_id: int,
        station_type: StationType | None = None,
    ) -> list[Station]:
        await self.get_kitchen(kitchen_id)
        return await self.stations.list_by_kitchen(kitchen_id, station_type)

    async def update_station_capacity(self, station_id: int, capacity: int) -> Station:
        station = await self._get_station(station_id)
        station.capacity = capacity
        await self.session.commit()
        await self.session.refresh(station)
        return station

    async def update_station_status(self, station_id: int, status: StationStatus) -> Station:
        station = await self._get_station(station_id)
        station.status = status
        await self.session.commit()
        await self.session.refresh(station)
        return station

    async def _get_station(self, station_id: int) -> Station:
        station = await self.stations.get(station_id)
        if station is None:
            raise NotFoundError("station_not_found")
        return station


class KdsService:
    def __init__(self, session: AsyncSession, event_writer: MongoKdsEventWriter) -> None:
        self.session = session
        self.stations = StationRepository(session)
        self.kds = KdsRepository(session)
        self.event_writer = event_writer

    async def dispatch_candidates(
        self,
        kitchen_id: int,
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
        station_id: int,
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
        return task, True

    async def list_station_tasks(
        self,
        station_id: int,
        task_status: KdsTaskStatus,
        limit: int,
        offset: int,
    ) -> list[KdsStationTask]:
        station = await self.stations.get(station_id)
        if station is None:
            raise KdsDomainError("station_not_found", "Station not found", status_code=404)
        return await self.kds.list_station_tasks(station_id, task_status, limit, offset)

    def _validate_delivery_station(self, station: Station, payload: KdsTaskDeliveryRequest) -> None:
        if station.status != StationStatus.available:
            raise KdsDomainError("station_not_available", "Station is not available")
        if station.kitchen_id != payload.kitchen_id:
            raise KdsDomainError("station_kitchen_mismatch", "Station belongs to another kitchen")
        if station.station_type != payload.station_type:
            raise KdsDomainError("station_type_mismatch", "Station type does not match task station type")
