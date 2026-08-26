from typing import Any

from celery import Celery
from contracts.events import AnomalyDetected
from pybreaker import CircuitBreakerError

from notifier.config import settings
from notifier.infrastructure.telegram_notifier import TelegramNotifier

app = Celery("notifier", broker=settings.REDIS_URL)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@app.task(bind=True, max_retries=3, retry_backoff=True)
def deliver_anomaly(self: Any, payload: dict[str, object]) -> None:
    """Telegram'a iletir; 5xx retry, 4xx/circuit log (07)."""
    event = AnomalyDetected.model_validate(payload)
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    try:
        notifier.notify_sync(event)
    except CircuitBreakerError as exc:
        raise self.retry(exc=exc) from exc
    except Exception as exc:
        raise self.retry(exc=exc) from exc


class CeleryEnqueue:
    def enqueue(self, event: AnomalyDetected) -> None:
        deliver_anomaly.delay(event.model_dump(mode="json"))
