"""create menu service tables

Revision ID: 0001_create_menu_service_tables
Revises:
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_menu_service_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "menu_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_menu_items_lower_name", "menu_items", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "kitchen_menu_availability",
        sa.Column("kitchen_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kitchen_id", "menu_item_id"),
        sa.UniqueConstraint("kitchen_id", "menu_item_id", name="uq_kitchen_menu_availability"),
    )

    op.create_table(
        "recipe_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("station_type", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("duration_seconds > 0", name="ck_recipe_steps_duration_seconds_positive"),
        sa.CheckConstraint("step_order > 0", name="ck_recipe_steps_step_order_positive"),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("menu_item_id", "step_order", name="uq_recipe_steps_menu_item_id_step_order"),
    )
    op.create_index("ix_recipe_steps_menu_item_id_step_order", "recipe_steps", ["menu_item_id", "step_order"])


def downgrade() -> None:
    op.drop_index("ix_recipe_steps_menu_item_id_step_order", table_name="recipe_steps")
    op.drop_table("recipe_steps")
    op.drop_table("kitchen_menu_availability")
    op.drop_index("uq_menu_items_lower_name", table_name="menu_items")
    op.drop_table("menu_items")
