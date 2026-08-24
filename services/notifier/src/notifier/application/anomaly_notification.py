from contracts.events import AnomalyDetected

from notifier.ports.consumer import AnomalyConsumer
from notifier.ports.notifier import Notifier


class AnomalyNotification:
    def __init__(self, consumer: AnomalyConsumer, notifier: Notifier) -> None:
        self._consumer = consumer
        self._notifier = notifier

    async def run(self) -> None:
        await self._consumer.consume(self.handle)

    async def handle(self, event: AnomalyDetected) -> None:
        await self._notifier.notify(event)
