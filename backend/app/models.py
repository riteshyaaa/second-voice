"""Normalized schema: users, preferences, sessions, audio, transcripts,
suggestions, approvals, corrections, vocabulary, memory, learning,
confirmations, TTS. Mirrored by alembic 0001_init.py."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    preferences: Mapped["UserPreference"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions: Mapped[list["CommSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en")
    output_language: Mapped[str] = mapped_column(String(16), default="en")
    script: Mapped[str] = mapped_column(String(16), default="native")  # native|roman|mixed
    tts_voice: Mapped[str] = mapped_column(String(120), default="")
    tts_speed: Mapped[float] = mapped_column(Float, default=1.0)
    learning_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    save_rejections: Mapped[bool] = mapped_column(Boolean, default=False)
    use_history: Mapped[bool] = mapped_column(Boolean, default=True)
    audio_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    font_scale: Mapped[float] = mapped_column(Float, default=1.0)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped[User] = relationship(back_populates="preferences")


class CommSession(Base):
    __tablename__ = "communication_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled session")
    language: Mapped[str] = mapped_column(String(16), default="en")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(back_populates="sessions")
    audios: Mapped[list["AudioAsset"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AudioAsset(Base):
    __tablename__ = "audio_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("communication_sessions.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(80), default="audio/wav")
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Phase 1 audio intelligence verdict
    consent_stored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session: Mapped[CommSession] = relationship(back_populates="audios")
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="audio", cascade="all, delete-orphan")
    derivatives: Mapped[list["AudioDerivative"]] = relationship(back_populates="parent", cascade="all, delete-orphan")


DERIVATIVE_KINDS = ("normalized", "enhanced", "restored", "generated")


class AudioDerivative(Base):
    """CLARIS P1: processing derivative of an immutable original.

    The original file is never modified; each derivative is a new file with
    full lineage (parent, operation, model, config). `enhanced`/`restored`/
    `generated` kinds are reserved for P4/P5/P9 — only `normalized` is
    produced in P1.
    """
    __tablename__ = "audio_derivatives"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_asset_id: Mapped[int] = mapped_column(ForeignKey("audio_assets.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="normalized")
    operation: Mapped[str] = mapped_column(String(80), default="")
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(80), default="audio/wav")
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # output QA of this derivative
    status: Mapped[str] = mapped_column(String(16), default="ready")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    parent: Mapped[AudioAsset] = relationship(back_populates="derivatives")


class Transcript(Base):
    __tablename__ = "transcripts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audio_id: Mapped[int] = mapped_column(ForeignKey("audio_assets.id", ondelete="CASCADE"), index=True)
    text_original: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="en")
    provider: Mapped[str] = mapped_column(String(40), default="dev-fallback")
    model_version: Mapped[str] = mapped_column(String(80), default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Phase 3: providers, comparison, uncertainty
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    audio: Mapped[AudioAsset] = relationship(back_populates="transcripts")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="transcript", cascade="all, delete-orphan")


class Suggestion(Base):
    __tablename__ = "reconstruction_suggestions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id", ondelete="CASCADE"), index=True)
    proposed_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    changed_words: Mapped[list] = mapped_column(JSON, default=list)
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    needs_clarification: Mapped[bool] = mapped_column(Boolean, default=False)
    clarification_question: Mapped[str] = mapped_column(Text, default="")
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_for: Mapped[list | None] = mapped_column(JSON, nullable=True)  # Phase 7 audit
    evidence_missing: Mapped[list | None] = mapped_column(JSON, nullable=True)
    clarification_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Phase 8: {qid: answer}
    provider: Mapped[str] = mapped_column(String(40), default="dev-fallback")
    model_version: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(24), default="pending")  # pending|accepted|edited|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    transcript: Mapped[Transcript] = relationship(back_populates="suggestions")


class ApprovedMessage(Base):
    __tablename__ = "approved_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("communication_sessions.id", ondelete="CASCADE"), index=True, nullable=True)  # Phase 9: card taps have no session
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("reconstruction_suggestions.id", ondelete="SET NULL"), nullable=True)
    transcript_id: Mapped[int | None] = mapped_column(ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True)
    final_text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="en")
    source: Mapped[str] = mapped_column(String(24), default="accepted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("reconstruction_suggestions.id", ondelete="SET NULL"), nullable=True)
    original_text: Mapped[str] = mapped_column(Text)
    suggested_text: Mapped[str] = mapped_column(Text, default="")
    corrected_text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24), default="edit")
    provenance: Mapped[str] = mapped_column(String(80), default="user-approved")  # Phase 5
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VocabularyEntry(Base):
    __tablename__ = "vocabulary_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(200))
    normalized: Mapped[str] = mapped_column(String(200), index=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    category: Mapped[str] = mapped_column(String(40), default="word")  # word|name|place|phrase
    source: Mapped[str] = mapped_column(String(40), default="user-approved")  # Phase 5 provenance
    status: Mapped[str] = mapped_column(String(16), default="approved")  # approved|provisional
    version: Mapped[int] = mapped_column(Integer, default=1)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    times_corrected: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "normalized", name="uq_vocab_user_term"),)


class CommMemory(Base):
    __tablename__ = "communication_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="phrase")  # phrase|context|preference
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="en")
    source: Mapped[str] = mapped_column(String(40), default="user-approved")  # Phase 5 provenance
    provenance: Mapped[str] = mapped_column(String(80), default="user-approved")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileRevision(Base):
    """Version journal for rollback (Phase 6): snapshot BEFORE each edit."""
    __tablename__ = "profile_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entity: Mapped[str] = mapped_column(String(16))  # vocab|memory
    entity_id: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommCard(Base):
    """Visual communication card (Phase 9): tap-to-speak message with an
    emoji anchor, category, optional native-language label, and an
    optional illustration (only from a verified provider — never
    generated imagery presented as evidence of anything said)."""
    __tablename__ = "communication_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    label_native: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    emoji: Mapped[str] = mapped_column(String(16), default="")
    category: Mapped[str] = mapped_column(String(24), default="personal")  # needs|requests|feelings|questions|emergency|personal
    phrase: Mapped[str] = mapped_column(Text)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearningEvent(Base):
    __tablename__ = "learning_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # vocab|language|correction|pattern|rejection
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[str] = mapped_column(String(80), default="user-approved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfirmationEvent(Base):
    __tablename__ = "confirmation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approved_message_id: Mapped[int] = mapped_column(ForeignKey("approved_messages.id", ondelete="CASCADE"), unique=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    language: Mapped[str] = mapped_column(String(16), default="en")
    tts_status: Mapped[str] = mapped_column(String(24), default="pending")


class TTSRequest(Base):
    __tablename__ = "tts_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approved_message_id: Mapped[int] = mapped_column(ForeignKey("approved_messages.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="webspeech-fallback")
    voice: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    status: Mapped[str] = mapped_column(String(24), default="ready")
    audio_path: Mapped[str] = mapped_column(String(512), default="")
    fallback: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
