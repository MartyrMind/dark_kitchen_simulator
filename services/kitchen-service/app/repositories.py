from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Kitchen, Station, StationType
from app.schemas import KitchenCreate, StationCreate


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
