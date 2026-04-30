from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class KitchenStatus(StrEnum):
    active = "active"
    inactive = "inactive"


class StationType(StrEnum):
    grill = "grill"
    fryer = "fryer"
    cold = "cold"
    drinks = "drinks"
    assembly = "assembly"


class StationStatus(StrEnum):
    active = "active"
    inactive = "inactive"
    maintenance = "maintenance"


class Kitchen(Base):
    __tablename__ = "kitchens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kitchen_id: Mapped[int] = mapped_column(ForeignKey("kitchens.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    station_type: Mapped[StationType] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[StationStatus] = mapped_column(String(24), nullable=False, default=StationStatus.active)
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
