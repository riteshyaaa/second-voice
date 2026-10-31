"""Second Voice API — assistive communication, evidence-first, confirm-before-speak."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, evaluation, feedback, languages, memory, reconstruction, sessions, settings, speech, transcription
from .core.config import settings as cfg
from .core.database import init_db
from .core.logging import log, new_trace

app = FastAPI(title="Second Voice API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cfg.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace(request, call_next):
    trace_id = new_trace()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled trace=%s %s %s", trace_id, request.method, request.url.path)
        raise
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.on_event("startup")
def startup():
    init_db()
    log.info("Second Voice API up (META live: %s)", bool(cfg.META_API_KEY))


@app.get("/healthz")
def healthz():
    from .services import meta_asr_service

    st = meta_asr_service.status()
    return {"ok": True, "asr_provider": st.name, "asr_live": st.live, "tts_provider": cfg.TTS_PROVIDER}


for r in (auth.router, sessions.router, transcription.router, reconstruction.router,
          languages.router, memory.router, feedback.router, speech.router, settings.router,
          evaluation.router):
    app.include_router(r)
