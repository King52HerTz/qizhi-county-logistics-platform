"""add versioned logistics scenarios

Revision ID: 20260724_0003
Revises: 20260724_0002
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0003"
down_revision: str | None = "20260724_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenario_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_code", sa.String(length=64), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_key", sa.String(length=96), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("county_name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("vehicle_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "node_count > 0 and order_count > 0 and vehicle_count > 0",
            name="scenario_versions_counts_positive",
        ),
        sa.CheckConstraint(
            "source_type in ('demo','excel')",
            name="scenario_versions_source_type_check",
        ),
        sa.CheckConstraint(
            "status in ('draft','active','archived')",
            name="scenario_versions_status_check",
        ),
        sa.CheckConstraint("version_no > 0", name="scenario_versions_version_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_code", "version_no", name="scenario_versions_code_version_key"),
        sa.UniqueConstraint("version_key"),
    )
    op.create_index(
        "scenario_versions_active_idx",
        "scenario_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "scenario_versions_created_idx",
        "scenario_versions",
        ["created_at", "id"],
        unique=False,
    )
    op.create_index(
        "scenario_versions_creator_id_idx",
        "scenario_versions",
        ["created_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("scenario_versions_creator_id_idx", table_name="scenario_versions")
    op.drop_index("scenario_versions_created_idx", table_name="scenario_versions")
    op.drop_index("scenario_versions_active_idx", table_name="scenario_versions")
    op.drop_table("scenario_versions")
