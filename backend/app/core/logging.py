"""Structured logging with request tracing."""
import logging
import sys
import uuid

from .config import settings

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("secondvoice")


def new_trace() -> str:
    return uuid.uuid4().hex[:12]
