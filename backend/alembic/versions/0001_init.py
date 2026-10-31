"""Alembic migration 0001 — mirrors app/models.py (see ERD in docs/architecture.md)."""
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("email", sa.String(320), unique=True, index=True),
                    sa.Column("password_hash", sa.String(256)), sa.Column("display_name", sa.String(120), server_default=""),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("user_preferences", sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("preferred_language", sa.String(16), server_default="en"),
                    sa.Column("output_language", sa.String(16), server_default="en"),
                    sa.Column("script", sa.String(16), server_default="native"),
                    sa.Column("tts_voice", sa.String(120), server_default=""),
                    sa.Column("tts_speed", sa.Float, server_default="1.0"),
                    sa.Column("learning_enabled", sa.Boolean, server_default="1"),
                    sa.Column("save_rejections", sa.Boolean, server_default="0"),
                    sa.Column("use_history", sa.Boolean, server_default="1"),
                    sa.Column("audio_retention_days", sa.Integer, server_default="30"),
                    sa.Column("font_scale", sa.Float, server_default="1.0"),
                    sa.Column("reduced_motion", sa.Boolean, server_default="0"),
                    sa.Column("high_contrast", sa.Boolean, server_default="0"))
    op.create_table("communication_sessions", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
                    sa.Column("title", sa.String(200), server_default="Untitled session"),
                    sa.Column("language", sa.String(16), server_default="en"),
                    sa.Column("status", sa.String(24), server_default="active"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("audio_assets", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("session_id", sa.Integer, sa.ForeignKey("communication_sessions.id", ondelete="CASCADE"), index=True),
                    sa.Column("file_path", sa.String(512)), sa.Column("mime", sa.String(80), server_default="audio/wav"),
                    sa.Column("duration_s", sa.Float, server_default="0"),
                    sa.Column("consent_stored", sa.Boolean, server_default="0"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("transcripts", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("audio_id", sa.Integer, sa.ForeignKey("audio_assets.id", ondelete="CASCADE"), index=True),
                    sa.Column("text_original", sa.Text), sa.Column("language", sa.String(16), server_default="en"),
                    sa.Column("provider", sa.String(40), server_default="dev-fallback"),
                    sa.Column("model_version", sa.String(80), server_default=""),
                    sa.Column("confidence", sa.Float, nullable=True), sa.Column("timestamps", sa.JSON, nullable=True),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("reconstruction_suggestions", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("transcript_id", sa.Integer, sa.ForeignKey("transcripts.id", ondelete="CASCADE"), index=True),
                    sa.Column("proposed_text", sa.Text), sa.Column("explanation", sa.Text, server_default=""),
                    sa.Column("changed_words", sa.JSON, server_default="[]"), sa.Column("alternatives", sa.JSON, server_default="[]"),
                    sa.Column("needs_clarification", sa.Boolean, server_default="0"),
                    sa.Column("clarification_question", sa.Text, server_default=""),
                    sa.Column("abstained", sa.Boolean, server_default="0"),
                    sa.Column("provider", sa.String(40), server_default="dev-fallback"),
                    sa.Column("model_version", sa.String(80), server_default=""),
                    sa.Column("status", sa.String(24), server_default="pending"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    for name, extra in [
        ("approved_messages", [sa.Column("session_id", sa.Integer, sa.ForeignKey("communication_sessions.id", ondelete="CASCADE"), index=True),
                               sa.Column("suggestion_id", sa.Integer, sa.ForeignKey("reconstruction_suggestions.id", ondelete="SET NULL"), nullable=True),
                               sa.Column("transcript_id", sa.Integer, sa.ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True),
                               sa.Column("final_text", sa.Text), sa.Column("language", sa.String(16), server_default="en"),
                               sa.Column("source", sa.String(24), server_default="accepted")]),
        ("corrections", [sa.Column("suggestion_id", sa.Integer, sa.ForeignKey("reconstruction_suggestions.id", ondelete="SET NULL"), nullable=True),
                         sa.Column("original_text", sa.Text), sa.Column("suggested_text", sa.Text, server_default=""),
                         sa.Column("corrected_text", sa.Text), sa.Column("kind", sa.String(24), server_default="edit")]),
    ]:
        op.create_table(name, sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
                        *extra, sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("vocabulary_entries", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
                    sa.Column("term", sa.String(200)), sa.Column("normalized", sa.String(200), index=True),
                    sa.Column("language", sa.String(16), server_default="en"), sa.Column("category", sa.String(40), server_default="word"),
                    sa.Column("times_used", sa.Integer, server_default="0"), sa.Column("times_corrected", sa.Integer, server_default="0"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
                    sa.UniqueConstraint("user_id", "normalized", name="uq_vocab_user_term"))
    op.create_table("communication_memory", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
                    sa.Column("kind", sa.String(40), server_default="phrase"), sa.Column("content", sa.Text),
                    sa.Column("language", sa.String(16), server_default="en"), sa.Column("version", sa.Integer, server_default="1"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("learning_events", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
                    sa.Column("kind", sa.String(24)), sa.Column("detail", sa.JSON, server_default="{}"),
                    sa.Column("provenance", sa.String(80), server_default="user-approved"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("confirmation_events", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("approved_message_id", sa.Integer, sa.ForeignKey("approved_messages.id", ondelete="CASCADE"), unique=True),
                    sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
                    sa.Column("language", sa.String(16), server_default="en"),
                    sa.Column("tts_status", sa.String(24), server_default="pending"))
    op.create_table("tts_requests", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("approved_message_id", sa.Integer, sa.ForeignKey("approved_messages.id", ondelete="CASCADE"), index=True),
                    sa.Column("provider", sa.String(40), server_default="webspeech-fallback"),
                    sa.Column("voice", sa.String(120), server_default=""), sa.Column("language", sa.String(16), server_default="en"),
                    sa.Column("status", sa.String(24), server_default="ready"),
                    sa.Column("audio_path", sa.String(512), server_default=""), sa.Column("fallback", sa.Boolean, server_default="1"),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade():
    for t in ["tts_requests", "confirmation_events", "learning_events", "communication_memory",
              "vocabulary_entries", "corrections", "approved_messages", "reconstruction_suggestions",
              "transcripts", "audio_assets", "communication_sessions", "user_preferences", "users"]:
        op.drop_table(t)
