"""Celery worker giriş noktası: `celery -A notifier.worker worker`."""

import logging

from notifier.infrastructure.celery_enqueue import app

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

__all__ = ["app"]
