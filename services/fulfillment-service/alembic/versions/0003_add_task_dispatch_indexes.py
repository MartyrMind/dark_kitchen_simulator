"""add task dispatch indexes

Revision ID: 0003_add_task_dispatch_indexes
Revises: 0002_add_task_queue_publish_fields
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_add_task_dispatch_indexes"
down_revision: str | None = "0002_add_task_queue_publish_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_kitchen_tasks_station_id", "kitchen_tasks", ["station_id"])
    op.create_index("ix_kitchen_tasks_kds_task_id", "kitchen_tasks", ["kds_task_id"])


def downgrade() -> None:
    op.drop_index("ix_kitchen_tasks_kds_task_id", table_name="kitchen_tasks")
    op.drop_index("ix_kitchen_tasks_station_id", table_name="kitchen_tasks")
