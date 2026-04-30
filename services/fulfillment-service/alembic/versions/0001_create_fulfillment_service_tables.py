"""create fulfillment service tables

Revision ID: fulf_0001
Revises:
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "fulf_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kitchen_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pickup_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_kitchen_id", "orders", ["kitchen_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_menu_item_id", "order_items", ["menu_item_id"])

    op.create_table(
        "kitchen_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("station_type", sa.String(length=32), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=True),
        sa.Column("kds_task_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("displayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("delay_seconds", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("recipe_step_order", sa.Integer(), nullable=False),
        sa.Column("item_unit_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estimated_duration_seconds > 0", name="ck_kitchen_tasks_duration_positive"),
        sa.CheckConstraint("attempts >= 0", name="ck_kitchen_tasks_attempts_non_negative"),
        sa.CheckConstraint("recipe_step_order > 0", name="ck_kitchen_tasks_recipe_step_order_positive"),
        sa.CheckConstraint("item_unit_index > 0", name="ck_kitchen_tasks_item_unit_index_positive"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_tasks_order_id", "kitchen_tasks", ["order_id"])
    op.create_index("ix_kitchen_tasks_menu_item_id", "kitchen_tasks", ["menu_item_id"])
    op.create_index("ix_kitchen_tasks_status", "kitchen_tasks", ["status"])
    op.create_index("ix_kitchen_tasks_station_type", "kitchen_tasks", ["station_type"])
    op.create_index("ix_kitchen_tasks_order_item_id", "kitchen_tasks", ["order_item_id"])

    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_task_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("task_id != depends_on_task_id", name="ck_task_dependencies_not_self"),
        sa.ForeignKeyConstraint(["task_id"], ["kitchen_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["kitchen_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id"),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependencies_task_id_depends_on_task_id"),
    )


def downgrade() -> None:
    op.drop_table("task_dependencies")
    op.drop_index("ix_kitchen_tasks_order_item_id", table_name="kitchen_tasks")
    op.drop_index("ix_kitchen_tasks_station_type", table_name="kitchen_tasks")
    op.drop_index("ix_kitchen_tasks_status", table_name="kitchen_tasks")
    op.drop_index("ix_kitchen_tasks_menu_item_id", table_name="kitchen_tasks")
    op.drop_index("ix_kitchen_tasks_order_id", table_name="kitchen_tasks")
    op.drop_table("kitchen_tasks")
    op.drop_index("ix_order_items_menu_item_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_kitchen_id", table_name="orders")
    op.drop_table("orders")
