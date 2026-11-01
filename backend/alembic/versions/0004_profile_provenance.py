"""Alembic migration 0004 — speaker-profile provenance (Phase 5).

Every learned entry carries source, approval status/provenance, and a
version. Existing rows backfill to user-approved/approved/v1, which is
what they were: all were created through explicit user save actions.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_profile_provenance"
down_revision = "0003_transcript_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vocabulary_entries", sa.Column("source", sa.String(40), server_default="user-approved"))
    op.add_column("vocabulary_entries", sa.Column("status", sa.String(16), server_default="approved"))
    op.add_column("vocabulary_entries", sa.Column("version", sa.Integer, server_default="1"))
    op.add_column("communication_memory", sa.Column("source", sa.String(40), server_default="user-approved"))
    op.add_column("communication_memory", sa.Column("provenance", sa.String(80), server_default="user-approved"))
    op.add_column("corrections", sa.Column("provenance", sa.String(80), server_default="user-approved"))


def downgrade():
    op.drop_column("corrections", "provenance")
    op.drop_column("communication_memory", "provenance")
    op.drop_column("communication_memory", "source")
    op.drop_column("vocabulary_entries", "version")
    op.drop_column("vocabulary_entries", "status")
    op.drop_column("vocabulary_entries", "source")
