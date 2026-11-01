"""Alembic migration 0005 — profile revision journal (Phase 6 rollback)."""
from alembic import op
import sqlalchemy as sa

revision = "0005_profile_revisions"
down_revision = "0004_profile_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "profile_revisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("entity", sa.String(16)),  # vocab|memory
        sa.Column("entity_id", sa.Integer),
        sa.Column("snapshot", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("profile_revisions")
