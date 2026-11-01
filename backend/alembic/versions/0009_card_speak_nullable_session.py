"""Alembic migration 0009 — card speaks are session-less (Phase 9).

Tapping a communication card creates an ApprovedMessage without a
session (cards live outside recording sessions). Everything that reads
session_id tolerates null (dashboard counts, joins, cascade wipe).
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_card_speak_nullable_session"
down_revision = "0008_comm_cards"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("approved_messages", "session_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("approved_messages", "session_id", existing_type=sa.Integer(), nullable=False)
