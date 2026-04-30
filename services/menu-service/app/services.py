from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItem, MenuItemStatus
from app.repositories import AvailabilityRepository, MenuItemRepository, RecipeStepRepository
from app.schemas import AvailabilityUpsert, MenuItemCreate, RecipeRead, RecipeStepCreate


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class MenuService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.menu_items = MenuItemRepository(session)
        self.recipe_steps = RecipeStepRepository(session)
        self.availability = AvailabilityRepository(session)

    async def create_menu_item(self, payload: MenuItemCreate) -> MenuItem:
        try:
            item = await self.menu_items.create(payload)
            await self.session.commit()
            return item
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("menu_item_already_exists") from exc

    async def list_menu_items(
        self,
        status: MenuItemStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MenuItem]:
        return await self.menu_items.list(status, limit, offset)

    async def get_menu_item(self, menu_item_id: UUID) -> MenuItem:
        item = await self.menu_items.get(menu_item_id)
        if item is None:
            raise NotFoundError("menu_item_not_found")
        return item

    async def create_recipe_step(self, menu_item_id: UUID, payload: RecipeStepCreate):
        await self.get_menu_item(menu_item_id)
        try:
            step = await self.recipe_steps.create(menu_item_id, payload)
            await self.session.commit()
            return step
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("recipe_step_order_already_exists") from exc

    async def get_recipe(self, menu_item_id: UUID) -> RecipeRead:
        await self.get_menu_item(menu_item_id)
        steps = await self.recipe_steps.list_by_menu_item(menu_item_id)
        return RecipeRead(menu_item_id=menu_item_id, steps=steps)

    async def upsert_availability(self, kitchen_id: UUID, menu_item_id: UUID, payload: AvailabilityUpsert):
        await self.get_menu_item(menu_item_id)
        availability = await self.availability.upsert(kitchen_id, menu_item_id, payload)
        await self.session.commit()
        await self.session.refresh(availability)
        return availability

    async def list_kitchen_menu(self, kitchen_id: UUID, include_unavailable: bool = False):
        return await self.availability.list_kitchen_menu(kitchen_id, include_unavailable)
