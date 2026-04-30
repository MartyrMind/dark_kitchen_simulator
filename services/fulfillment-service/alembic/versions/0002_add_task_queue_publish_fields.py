"""add task queue publish fields

Revision ID: fulf_0002
Revises: fulf_0001
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "fulf_0002"
down_revision: str | None = "fulf_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kitchen_tasks", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kitchen_tasks", sa.Column("redis_stream", sa.String(length=255), nullable=True))
    op.add_column("kitchen_tasks", sa.Column("redis_message_id", sa.String(length=128), nullable=True))
    op.create_index("ix_kitchen_tasks_redis_stream", "kitchen_tasks", ["redis_stream"])


def downgrade() -> None:
    op.drop_index("ix_kitchen_tasks_redis_stream", table_name="kitchen_tasks")
    op.drop_column("kitchen_tasks", "redis_message_id")
    op.drop_column("kitchen_tasks", "redis_stream")
    op.drop_column("kitchen_tasks", "queued_at")
