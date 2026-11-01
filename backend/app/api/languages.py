from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.config import SUPPORTED_LANGUAGES
from ..core.database import get_db
from ..core.deps import current_user
from ..services import language_service, muse_spark_service
from ..core.config import settings
from ..core.providers import meta_available

router = APIRouter(prefix="/api/v1/languages", tags=["languages"])


@router.get("")
def supported():
    return {"languages": SUPPORTED_LANGUAGES, "scripts": ["native", "roman", "mixed"]}


@router.post("/detect")
def detect(text: str, user: models.User = Depends(current_user)):
    return language_service.detect_language(text)


@router.post("/translate")
async def translate(body: schemas.TranslateIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Explicit translation. Original is preserved; caller confirms which to speak."""
    if body.target not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"Unsupported target: {body.target}")
    if meta_available(settings.META_API_KEY):
        try:
            text, status = await muse_spark_service.translate(body.text, body.target)
            return {"original": body.text, "translated": text, "provider": status.name, "target": body.target,
                    "guard_warnings": language_service.translation_guards(body.text, text)}
        except Exception:
            pass
    local = language_service.translate_explicit(body.text, body.target)
    return {"original": body.text, "translated": local["text"], "provider": local["provider"],
            "target": body.target, "note": local["note"],
            "guard_warnings": language_service.translation_guards(body.text, local["text"])}
