"""Alembic migration 0007 — clarification answers (Phase 8)."""
from alembic import op
import sqlalchemy as sa

revision = "0007_clarification_answers"
down_revision = "0006_suggestion_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reconstruction_suggestions", sa.Column("clarification_answers", sa.JSON, nullable=True))


def downgrade():
    op.drop_column("reconstruction_suggestions", "clarification_answers")
