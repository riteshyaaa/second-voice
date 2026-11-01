"""Alembic migration 0006 — suggestion evidence audit (Phase 7)."""
from alembic import op
import sqlalchemy as sa

revision = "0006_suggestion_evidence"
down_revision = "0005_profile_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reconstruction_suggestions", sa.Column("evidence_for", sa.JSON, nullable=True))
    op.add_column("reconstruction_suggestions", sa.Column("evidence_missing", sa.JSON, nullable=True))


def downgrade():
    op.drop_column("reconstruction_suggestions", "evidence_missing")
    op.drop_column("reconstruction_suggestions", "evidence_for")
