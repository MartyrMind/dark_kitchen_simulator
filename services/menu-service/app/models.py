from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MenuItemStatus(StrEnum):
    active = "active"
    disabled = "disabled"


class StationType(StrEnum):
    grill = "grill"
    fryer = "fryer"
    drinks = "drinks"
    packaging = "packaging"


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (Index("uq_menu_items_lower_name", text("lower(name)"), unique=True),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[MenuItemStatus] = mapped_column(String(24), nullable=False, default=MenuItemStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    recipe_steps: Mapped[list["RecipeStep"]] = relationship(back_populates="menu_item", cascade="all, delete-orphan")
    availability: Mapped[list["KitchenMenuAvailability"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
    )


class KitchenMenuAvailability(Base):
    __tablename__ = "kitchen_menu_availability"
    __table_args__ = (UniqueConstraint("kitchen_id", "menu_item_id", name="uq_kitchen_menu_availability"),)

    kitchen_id: Mapped[UUID] = mapped_column(primary_key=True)
    menu_item_id: Mapped[UUID] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"), primary_key=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    menu_item: Mapped[MenuItem] = relationship(back_populates="availability")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "step_order", name="uq_recipe_steps_menu_item_id_step_order"),
        CheckConstraint("duration_seconds > 0", name="ck_recipe_steps_duration_seconds_positive"),
        CheckConstraint("step_order > 0", name="ck_recipe_steps_step_order_positive"),
        Index("ix_recipe_steps_menu_item_id_step_order", "menu_item_id", "step_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    menu_item_id: Mapped[UUID] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    station_type: Mapped[StationType] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(nullable=False)
    step_order: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    menu_item: Mapped[MenuItem] = relationship(back_populates="recipe_steps")
