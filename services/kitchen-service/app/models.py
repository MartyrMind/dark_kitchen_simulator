from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class KitchenStatus(StrEnum):
    active = "active"
    inactive = "inactive"


class StationType(StrEnum):
    grill = "grill"
    fryer = "fryer"
    packaging = "packaging"
    cold = "cold"
    drinks = "drinks"
    assembly = "assembly"


class StationStatus(StrEnum):
    available = "available"
    unavailable = "unavailable"
    maintenance = "maintenance"


class KdsTaskStatus(StrEnum):
    displayed = "displayed"
    claimed = "claimed"
    completed = "completed"
    failed = "failed"
    removed = "removed"


class Kitchen(Base):
    __tablename__ = "kitchens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    status: Mapped[KitchenStatus] = mapped_column(String(24), nullable=False, default=KitchenStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    stations: Mapped[list["Station"]] = relationship(
        back_populates="kitchen",
        cascade="all, delete-orphan",
    )


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (UniqueConstraint("kitchen_id", "name", name="uq_stations_kitchen_id_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kitchen_id: Mapped[UUID] = mapped_column(ForeignKey("kitchens.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    station_type: Mapped[StationType] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[StationStatus] = mapped_column(String(24), nullable=False, default=StationStatus.available)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    busy_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visible_backlog_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    kitchen: Mapped[Kitchen] = relationship(back_populates="stations")
    kds_tasks: Mapped[list["KdsStationTask"]] = relationship(back_populates="station")


class KdsStationTask(Base):
    __tablename__ = "kds_station_tasks"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_kds_station_tasks_task_id"),
        UniqueConstraint("idempotency_key", name="uq_kds_station_tasks_idempotency_key"),
        CheckConstraint("estimated_duration_seconds > 0", name="ck_kds_station_tasks_duration_positive"),
        Index("ix_kds_station_tasks_station_id_status", "station_id", "status"),
        Index("ix_kds_station_tasks_kitchen_id_station_type", "kitchen_id", "station_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kitchen_id: Mapped[UUID] = mapped_column(nullable=False)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    station_type: Mapped[StationType] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    menu_item_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[KdsTaskStatus] = mapped_column(String(24), nullable=False, default=KdsTaskStatus.displayed)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    pickup_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    displayed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    station: Mapped[Station] = relationship(back_populates="kds_tasks")
