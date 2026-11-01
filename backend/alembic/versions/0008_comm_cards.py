"""Alembic migration 0008 — communication cards (Phase 9)."""
from alembic import op
import sqlalchemy as sa

revision = "0008_comm_cards"
down_revision = "0007_clarification_answers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "communication_cards",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("label", sa.String(200)),
        sa.Column("label_native", sa.String(200), nullable=True),
        sa.Column("language", sa.String(16), server_default="en"),
        sa.Column("emoji", sa.String(16), server_default=""),
        sa.Column("category", sa.String(24), server_default="personal"),
        sa.Column("phrase", sa.Text),
        sa.Column("favorite", sa.Boolean, server_default="false"),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("communication_cards")
