"""Central configuration. All secrets come from the environment — never code."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./secondvoice.db"
    JWT_SECRET: str = "dev-only-secret-change-me-32-chars-minimum"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 30

    META_API_KEY: str = ""
    META_BASE_URL: str = "https://api.meta.ai/v1"
    META_ASR_MODEL: str = "muse-voice-transcribe-1.0"
    META_SPARK_MODEL: str = "muse-spark-1.3"
    META_WONDER_MODEL: str = "muse-wonder-1.0"
    META_IMAGE_MODEL: str = "muse-image-1.0"
    META_RETRIES: int = 1  # extra attempts for transport errors / 429 / 5xx
    META_RETRY_BACKOFF_S: float = 1.0

    RATE_LIMIT_PER_MINUTE: int = 120  # auth endpoints, per IP (single-process)

    SECOND_ASR_ENABLED: bool = False
    SECOND_ASR_PROVIDER: str = ""

    TTS_PROVIDER: str = "webspeech-fallback"
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = ""
    ELEVENLABS_API_KEY: str = ""

    STORAGE_DIR: str = "/data/audio"
    AUDIO_RETENTION_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
SUPPORTED_LANGUAGES = ["en", "hi", "hinglish", "mr", "bn", "ta", "te", "kn", "ml", "gu", "pa"]
