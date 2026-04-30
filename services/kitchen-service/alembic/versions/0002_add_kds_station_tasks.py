"""add kds station tasks

Revision ID: 0002_add_kds_station_tasks
Revises: 0001_create_kitchens_and_stations
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_kds_station_tasks"
down_revision: str | None = "0001_create_kitchens_and_stations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kds_station_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("kitchen_id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("station_type", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("menu_item_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("pickup_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("displayed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_by", sa.String(length=120), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estimated_duration_seconds > 0", name="ck_kds_station_tasks_duration_positive"),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_kds_station_tasks_idempotency_key"),
        sa.UniqueConstraint("task_id", name="uq_kds_station_tasks_task_id"),
    )
    op.create_index("ix_kds_station_tasks_idempotency_key", "kds_station_tasks", ["idempotency_key"])
    op.create_index("ix_kds_station_tasks_kitchen_id_station_type", "kds_station_tasks", ["kitchen_id", "station_type"])
    op.create_index("ix_kds_station_tasks_station_id_status", "kds_station_tasks", ["station_id", "status"])
    op.create_index("ix_kds_station_tasks_task_id", "kds_station_tasks", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_kds_station_tasks_task_id", table_name="kds_station_tasks")
    op.drop_index("ix_kds_station_tasks_station_id_status", table_name="kds_station_tasks")
    op.drop_index("ix_kds_station_tasks_kitchen_id_station_type", table_name="kds_station_tasks")
    op.drop_index("ix_kds_station_tasks_idempotency_key", table_name="kds_station_tasks")
    op.drop_table("kds_station_tasks")
