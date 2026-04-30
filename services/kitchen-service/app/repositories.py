from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KdsStationTask, KdsTaskStatus, Kitchen, Station, StationType
from app.schemas import KitchenCreate, KdsTaskDeliveryRequest, StationCreate


class KitchenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: KitchenCreate) -> Kitchen:
        kitchen = Kitchen(name=payload.name)
        self.session.add(kitchen)
        await self.session.flush()
        await self.session.refresh(kitchen)
        return kitchen

    async def list(self) -> list[Kitchen]:
        result = await self.session.scalars(select(Kitchen).order_by(Kitchen.id))
        return list(result)

    async def get(self, kitchen_id: int) -> Kitchen | None:
        return await self.session.get(Kitchen, kitchen_id)


class StationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, kitchen_id: int, payload: StationCreate) -> Station:
        station = Station(
            kitchen_id=kitchen_id,
            name=payload.name,
            station_type=payload.station_type,
            capacity=payload.capacity,
            visible_backlog_limit=payload.visible_backlog_limit,
            busy_slots=0,
        )
        self.session.add(station)
        await self.session.flush()
        await self.session.refresh(station)
        return station

    async def list_by_kitchen(
        self,
        kitchen_id: int,
        station_type: StationType | None = None,
    ) -> list[Station]:
        statement = select(Station).where(Station.kitchen_id == kitchen_id)
        if station_type is not None:
            statement = statement.where(Station.station_type == station_type)
        result = await self.session.scalars(statement.order_by(Station.id))
        return list(result)

    async def get(self, station_id: int) -> Station | None:
        return await self.session.get(Station, station_id)

    async def get_for_update(self, station_id: int) -> Station | None:
        statement = select(Station).where(Station.id == station_id).with_for_update()
        return await self.session.scalar(statement)


class KdsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def visible_backlog_size(self, station_id: int) -> int:
        statement = select(func.count(KdsStationTask.id)).where(
            KdsStationTask.station_id == station_id,
            KdsStationTask.status == KdsTaskStatus.displayed,
        )
        return int(await self.session.scalar(statement) or 0)

    async def dispatch_candidates(
        self,
        kitchen_id: int,
        station_type: StationType,
    ) -> list[tuple[Station, int]]:
        backlog = (
            select(
                KdsStationTask.station_id.label("station_id"),
                func.count(KdsStationTask.id).label("visible_backlog_size"),
            )
            .where(KdsStationTask.status == KdsTaskStatus.displayed)
            .group_by(KdsStationTask.station_id)
            .subquery()
        )
        statement = (
            select(Station, func.coalesce(backlog.c.visible_backlog_size, 0))
            .outerjoin(backlog, backlog.c.station_id == Station.id)
            .where(
                Station.kitchen_id == kitchen_id,
                Station.station_type == station_type,
                Station.status == "available",
                func.coalesce(backlog.c.visible_backlog_size, 0) < Station.visible_backlog_limit,
            )
            .order_by(Station.id)
        )
        rows = await self.session.execute(statement)
        return [(station, int(size)) for station, size in rows.all()]

    async def create_task(
        self,
        station_id: int,
        payload: KdsTaskDeliveryRequest,
    ) -> KdsStationTask:
        task = KdsStationTask(
            task_id=str(payload.task_id),
            order_id=str(payload.order_id),
            kitchen_id=payload.kitchen_id,
            station_id=station_id,
            station_type=payload.station_type,
            operation=payload.operation,
            menu_item_name=payload.menu_item_name,
            status=KdsTaskStatus.displayed,
            estimated_duration_seconds=payload.estimated_duration_seconds,
            pickup_deadline=payload.pickup_deadline,
            idempotency_key=payload.idempotency_key,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_by_idempotency_key(self, idempotency_key: str) -> KdsStationTask | None:
        return await self.session.scalar(
            select(KdsStationTask).where(KdsStationTask.idempotency_key == idempotency_key)
        )

    async def get_by_task_id(self, task_id: str) -> KdsStationTask | None:
        return await self.session.scalar(select(KdsStationTask).where(KdsStationTask.task_id == task_id))

    async def list_station_tasks(
        self,
        station_id: int,
        task_status: KdsTaskStatus,
        limit: int,
        offset: int,
    ) -> list[KdsStationTask]:
        result = await self.session.scalars(
            select(KdsStationTask)
            .where(KdsStationTask.station_id == station_id, KdsStationTask.status == task_status)
            .order_by(KdsStationTask.displayed_at, KdsStationTask.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list(result)
