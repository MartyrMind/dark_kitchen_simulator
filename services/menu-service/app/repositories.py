from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.models import KitchenMenuAvailability, MenuItem, MenuItemStatus, RecipeStep
from app.schemas import AvailabilityUpsert, MenuItemCreate, RecipeStepCreate


class MenuItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: MenuItemCreate) -> MenuItem:
        item = MenuItem(name=payload.name, description=payload.description, status=payload.status)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def list(self, status: MenuItemStatus | None, limit: int, offset: int) -> list[MenuItem]:
        statement = select(MenuItem)
        if status is not None:
            statement = statement.where(MenuItem.status == status)
        result = await self.session.scalars(statement.order_by(MenuItem.name).limit(limit).offset(offset))
        return list(result)

    async def get(self, menu_item_id: UUID) -> MenuItem | None:
        return await self.session.get(MenuItem, menu_item_id)


class RecipeStepRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, menu_item_id: UUID, payload: RecipeStepCreate) -> RecipeStep:
        step = RecipeStep(
            menu_item_id=menu_item_id,
            station_type=payload.station_type,
            operation=payload.operation,
            duration_seconds=payload.duration_seconds,
            step_order=payload.step_order,
        )
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def list_by_menu_item(self, menu_item_id: UUID) -> list[RecipeStep]:
        result = await self.session.scalars(
            select(RecipeStep).where(RecipeStep.menu_item_id == menu_item_id).order_by(RecipeStep.step_order)
        )
        return list(result)


class AvailabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        kitchen_id: UUID,
        menu_item_id: UUID,
        payload: AvailabilityUpsert,
    ) -> KitchenMenuAvailability:
        availability = await self.session.get(
            KitchenMenuAvailability,
            {"kitchen_id": kitchen_id, "menu_item_id": menu_item_id},
        )
        if availability is None:
            availability = KitchenMenuAvailability(
                kitchen_id=kitchen_id,
                menu_item_id=menu_item_id,
                is_available=payload.is_available,
            )
            self.session.add(availability)
        else:
            availability.is_available = payload.is_available
        await self.session.flush()
        await self.session.refresh(availability)
        return availability

    async def list_kitchen_menu(self, kitchen_id: UUID, include_unavailable: bool) -> list[MenuItem]:
        statement = (
            select(MenuItem)
            .join(KitchenMenuAvailability)
            .options(contains_eager(MenuItem.availability))
            .where(
                KitchenMenuAvailability.kitchen_id == kitchen_id,
                MenuItem.status == MenuItemStatus.active,
            )
            .order_by(MenuItem.name)
        )
        if not include_unavailable:
            statement = statement.where(KitchenMenuAvailability.is_available.is_(True))
        result = await self.session.scalars(statement)
        return list(result.unique())
