"""Muse Image — optional visual communication cards (never evidence).

Generates simple illustrative cards from USER-APPROVED concepts only.
Primary workflow works without it.
"""
import httpx

from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available


async def generate_card(concept: str, style: str = "simple pictogram") -> tuple[dict, ProviderStatus]:
    if not meta_available(settings.META_API_KEY):
        return (
            {"image_url": None, "provider": "dev-fallback", "note": "META_API_KEY not set — card not generated."},
            ProviderStatus("dev-fallback", "dev-fallback-1", False, "no key"),
        )
    url = settings.META_BASE_URL.rstrip("/") + "/images/generations"
    headers = {"Authorization": f"Bearer {settings.META_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json={"model": settings.META_IMAGE_MODEL, "prompt": f"{style}: {concept}", "n": 1})
    if resp.status_code >= 400:
        raise RuntimeError(f"Muse Image error {resp.status_code}: {resp.text[:300]}")
    body = resp.json()
    data = (body.get("data") or [{}])[0]
    return (
        {"image_url": data.get("url"), "provider": "meta-image", "note": "illustration of approved concept, not evidence"},
        ProviderStatus("meta-image", settings.META_IMAGE_MODEL, True, "live"),
    )
