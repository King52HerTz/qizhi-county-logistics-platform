"""add reproducible algorithm comparison experiments

Revision ID: 20260724_0005
Revises: 20260724_0004
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0005"
down_revision: str | None = "20260724_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "algorithm_experiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("experiment_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scenario_version_id", sa.Integer(), nullable=True),
        sa.Column("scenario_key", sa.String(length=96), nullable=False),
        sa.Column("scenario_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("solver", sa.String(length=40), nullable=False),
        sa.Column("baseline", sa.String(length=48), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('running','completed','failed')",
            name="algorithm_experiments_status_check",
        ),
        sa.CheckConstraint(
            "time_limit_seconds >= 1 and time_limit_seconds <= 10",
            name="algorithm_experiments_time_limit_check",
        ),
        sa.CheckConstraint("case_count > 0", name="algorithm_experiments_case_count_check"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["scenario_version_id"],
            ["scenario_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_code"),
    )
    op.create_index(
        "algorithm_experiments_scenario_version_id_idx",
        "algorithm_experiments",
        ["scenario_version_id"],
    )
    op.create_index(
        "algorithm_experiments_created_by_idx",
        "algorithm_experiments",
        ["created_by"],
    )
    op.create_index(
        "algorithm_experiments_status_created_idx",
        "algorithm_experiments",
        ["status", "created_at"],
    )
    op.create_index(
        "algorithm_experiments_scenario_created_idx",
        "algorithm_experiments",
        ["scenario_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("algorithm_experiments")
