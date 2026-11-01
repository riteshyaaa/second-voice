"""Alembic migration 0003 — transcript evidence package (Phase 3)."""
from alembic import op
import sqlalchemy as sa

revision = "0003_transcript_evidence"
down_revision = "0002_audio_quality"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transcripts", sa.Column("evidence", sa.JSON, nullable=True))


def downgrade():
    op.drop_column("transcripts", "evidence")
