"""scenario version governance

Revision ID: 20260728_0011
Revises: 20260726_0010
"""

from alembic import op
import sqlalchemy as sa


revision = "20260728_0011"
down_revision = "20260726_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scenario_versions") as batch:
        batch.drop_constraint("scenario_versions_status_check", type_="check")
        batch.create_check_constraint(
            "scenario_versions_status_check",
            "status in ('draft','pending_review','rejected','active','archived')",
        )
        batch.add_column(sa.Column("fingerprint", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("release_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("submitted_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reviewed_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "scenario_versions_submitted_by_fkey",
            "users",
            ["submitted_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "scenario_versions_reviewed_by_fkey",
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("scenario_versions_submitted_by_idx", ["submitted_by"])
        batch.create_index("scenario_versions_reviewed_by_idx", ["reviewed_by"])
        batch.create_index(
            "scenario_versions_status_created_idx",
            ["status", "created_at"],
        )

    op.create_table(
        "scenario_version_transitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_version_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status is null or from_status in "
            "('draft','pending_review','rejected','active','archived')",
            name="scenario_transition_from_status_check",
        ),
        sa.CheckConstraint(
            "to_status in ('draft','pending_review','rejected','active','archived')",
            name="scenario_transition_to_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_version_id"],
            ["scenario_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "scenario_transition_version_created_idx",
        "scenario_version_transitions",
        ["scenario_version_id", "created_at"],
    )
    op.create_index(
        "scenario_transition_actor_id_idx",
        "scenario_version_transitions",
        ["actor_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "scenario_transition_actor_id_idx",
        table_name="scenario_version_transitions",
    )
    op.drop_index(
        "scenario_transition_version_created_idx",
        table_name="scenario_version_transitions",
    )
    op.drop_table("scenario_version_transitions")

    with op.batch_alter_table("scenario_versions") as batch:
        batch.drop_index("scenario_versions_status_created_idx")
        batch.drop_index("scenario_versions_reviewed_by_idx")
        batch.drop_index("scenario_versions_submitted_by_idx")
        batch.drop_constraint("scenario_versions_reviewed_by_fkey", type_="foreignkey")
        batch.drop_constraint("scenario_versions_submitted_by_fkey", type_="foreignkey")
        batch.drop_column("review_note")
        batch.drop_column("reviewed_at")
        batch.drop_column("reviewed_by")
        batch.drop_column("submitted_at")
        batch.drop_column("submitted_by")
        batch.drop_column("release_note")
        batch.drop_column("fingerprint")
        batch.drop_constraint("scenario_versions_status_check", type_="check")
        batch.create_check_constraint(
            "scenario_versions_status_check",
            "status in ('draft','active','archived')",
        )
