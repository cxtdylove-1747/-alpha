import hashlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def mask_text(text: str) -> str:
    if not text:
        return ""
    if len(text) <= 6:
        return "***"
    return f"{text[:3]}***{text[-3:]}"


def digest_text(text: str) -> str:
    payload = f"{settings.SECRET_KEY}:{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def log_event(event: str, payload: dict):
    logger.info("event=%s payload=%s", event, payload)

