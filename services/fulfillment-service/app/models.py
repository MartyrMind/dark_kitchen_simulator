from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.statuses import OrderStatus, TaskStatus


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kitchen_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(String(32), nullable=False, default=OrderStatus.created)
    pickup_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    tasks: Mapped[list["KitchenTask"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_menu_item_id", "menu_item_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    menu_item_id: Mapped[UUID] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship(back_populates="items")
    tasks: Mapped[list["KitchenTask"]] = relationship(back_populates="order_item")


class KitchenTask(Base):
    __tablename__ = "kitchen_tasks"
    __table_args__ = (
        CheckConstraint("estimated_duration_seconds > 0", name="ck_kitchen_tasks_duration_positive"),
        CheckConstraint("attempts >= 0", name="ck_kitchen_tasks_attempts_non_negative"),
        CheckConstraint("recipe_step_order > 0", name="ck_kitchen_tasks_recipe_step_order_positive"),
        CheckConstraint("item_unit_index > 0", name="ck_kitchen_tasks_item_unit_index_positive"),
        Index("ix_kitchen_tasks_order_id", "order_id"),
        Index("ix_kitchen_tasks_menu_item_id", "menu_item_id"),
        Index("ix_kitchen_tasks_status", "status"),
        Index("ix_kitchen_tasks_station_type", "station_type"),
        Index("ix_kitchen_tasks_order_item_id", "order_item_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    order_item_id: Mapped[UUID] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    menu_item_id: Mapped[UUID] = mapped_column(nullable=False)
    station_type: Mapped[str] = mapped_column(String(32), nullable=False)
    station_id: Mapped[UUID | None] = mapped_column(nullable=True)
    kds_task_id: Mapped[UUID | None] = mapped_column(nullable=True)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(String(32), nullable=False, default=TaskStatus.created)
    estimated_duration_seconds: Mapped[int] = mapped_column(nullable=False)
    displayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    delay_seconds: Mapped[int | None] = mapped_column(nullable=True)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    recipe_step_order: Mapped[int] = mapped_column(nullable=False)
    item_unit_index: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship(back_populates="tasks")
    order_item: Mapped[OrderItem] = relationship(back_populates="tasks")
    dependencies: Mapped[list["TaskDependency"]] = relationship(
        foreign_keys="TaskDependency.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependencies_task_id_depends_on_task_id"),
        CheckConstraint("task_id != depends_on_task_id", name="ck_task_dependencies_not_self"),
    )

    task_id: Mapped[UUID] = mapped_column(ForeignKey("kitchen_tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_task_id: Mapped[UUID] = mapped_column(ForeignKey("kitchen_tasks.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    task: Mapped[KitchenTask] = relationship(foreign_keys=[task_id], back_populates="dependencies")
