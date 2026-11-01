"""Alembic migration 0002 — audio intelligence quality column (Phase 1)."""
from alembic import op
import sqlalchemy as sa

revision = "0002_audio_quality"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audio_assets", sa.Column("quality", sa.JSON, nullable=True))


def downgrade():
    op.drop_column("audio_assets", "quality")
