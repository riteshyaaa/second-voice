"""Pydantic request/response schemas (strict validation at the API boundary)."""
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionIn(BaseModel):
    title: str = Field(default="Untitled session", max_length=200)
    language: str = Field(default="en", max_length=16)


class AudioMetaIn(BaseModel):
    mime: str = "audio/wav"
    duration_s: float = 0.0
    consent_stored: bool = False


class TranscribeIn(BaseModel):
    audio_id: int
    language_hint: str = Field(default="auto", max_length=16)
    keywords: list[str] = Field(default_factory=list, max_length=50)


class CompareIn(TranscribeIn):
    force_secondary: bool = False


class ReconstructIn(BaseModel):
    transcript_id: int
    user_request: str = Field(default="", max_length=2000)


class AlternativesIn(BaseModel):
    transcript_id: int
    count: int = Field(default=3, ge=1, le=5)


class ConfirmIn(BaseModel):
    transcript_id: int | None = None
    suggestion_id: int | None = None
    final_text: str = Field(min_length=1, max_length=5000)
    language: str = Field(default="en", max_length=16)
    source: str = Field(default="accepted", max_length=24)
    save_as_learning: bool = False
    force: bool = False  # Phase 8: explicit override of clarification blockers


class ClarifyAnswerIn(BaseModel):
    question_id: str = Field(max_length=16)
    kind: str = Field(max_length=16)  # select|type|saved_phrase|skip
    value: str | None = Field(default=None, max_length=200)


class FeedbackIn(BaseModel):
    suggestion_id: int | None = None
    transcript_id: int | None = None
    final_text: str = Field(min_length=1, max_length=5000)
    kind: str = Field(default="edit", max_length=24)
    save: bool = True


class VocabIn(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    language: str = Field(default="en", max_length=16)
    category: str = Field(default="word", max_length=40)


class MemoryIn(BaseModel):
    kind: str = Field(default="phrase", max_length=40)
    content: str = Field(min_length=1, max_length=5000)
    language: str = Field(default="en", max_length=16)


class VocabPatch(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=16)
    category: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, max_length=16)  # approved|provisional


class MemoryPatch(BaseModel):
    kind: str | None = Field(default=None, max_length=40)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    language: str | None = Field(default=None, max_length=16)


class CardIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    label_native: str | None = Field(default=None, max_length=200)
    language: str = Field(default="en", max_length=16)
    emoji: str = Field(default="", max_length=16)
    category: str = Field(default="personal", max_length=24)
    phrase: str = Field(min_length=1, max_length=500)


class CardPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    label_native: str | None = Field(default=None, max_length=200)
    language: str | None = Field(default=None, max_length=16)
    emoji: str | None = Field(default=None, max_length=16)
    category: str | None = Field(default=None, max_length=24)
    phrase: str | None = Field(default=None, min_length=1, max_length=500)
    favorite: bool | None = None


class SynthesizeIn(BaseModel):
    approved_message_id: int
    voice: str = Field(default="", max_length=120)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class PreviewIn(BaseModel):
    language: str = Field(default="en", max_length=16)
    voice: str = Field(default="", max_length=120)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    target: str = Field(max_length=16)


class PreferencesIn(BaseModel):
    preferred_language: str | None = None
    output_language: str | None = None
    script: str | None = None
    tts_voice: str | None = None
    tts_speed: float | None = None
    learning_enabled: bool | None = None
    save_rejections: bool | None = None
    use_history: bool | None = None
    audio_retention_days: int | None = None
    font_scale: float | None = None
    reduced_motion: bool | None = None
    high_contrast: bool | None = None


class SuggestionOut(BaseModel):
    original_text: str
    proposed_text: str
    explanation: str
    changed_words: list[dict] = []
    alternatives: list[str] = []
    needs_clarification: bool = False
    clarification_question: str = ""
    abstained: bool = False
    meaning_risk: str = "low"
    provider: str = "dev-fallback"
    model_version: str = ""


class RestorationJobIn(BaseModel):
    beam: int = Field(default=5, ge=1, le=20)
