import structlog
from contracts.events import AnomalyDetected

from notifier.domain.idempotency import SeenEventIds
from notifier.ports.consumer import AnomalyConsumer
from notifier.ports.enqueue import AnomalyEnqueue

logger = structlog.get_logger(__name__)


class AnomalyNotification:
    def __init__(
        self,
        consumer: AnomalyConsumer,
        enqueue: AnomalyEnqueue,
        seen: SeenEventIds | None = None,
    ) -> None:
        self._consumer = consumer
        self._enqueue = enqueue
        self._seen = seen or SeenEventIds()

    async def run(self) -> None:
        await self._consumer.consume(self.handle)

    async def handle(self, event: AnomalyDetected) -> None:
        if self._seen.already_seen(event.event_id):
            logger.info("Tekrarlayan anomali bildirimi atlandi.", event_id=str(event.event_id))
            return
        self._enqueue.enqueue(event)
