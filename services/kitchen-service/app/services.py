from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Kitchen, Station, StationStatus, StationType
from app.repositories import KitchenRepository, StationRepository
from app.schemas import KitchenCreate, StationCreate


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


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
