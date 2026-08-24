from contracts.events import RawVibrationWindow

from stream_processor.ports.consumer import RawWindowConsumer
from stream_processor.ports.repository import RawWindowRepository


class RawWindowIngestion:
    """Walking Skeleton için doğrulanmış chunk'ları kalıcı depoya aktarır."""

    def __init__(self, consumer: RawWindowConsumer, repository: RawWindowRepository) -> None:
        self._consumer = consumer
        self._repository = repository

    async def run(self) -> None:
        await self._consumer.consume(self.handle)

    async def handle(self, window: RawVibrationWindow) -> None:
        await self._repository.save(window)
