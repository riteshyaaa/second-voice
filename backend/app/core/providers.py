"""Provider abstraction: Meta live vs labelled dev fallback. No mock pretends."""
from dataclasses import dataclass


@dataclass
class ProviderStatus:
    name: str  # e.g. "meta-asr", "meta-spark", "dev-fallback"
    model_version: str
    live: bool
    detail: str = ""


def meta_available(api_key: str) -> bool:
    return bool(api_key and api_key.strip())
