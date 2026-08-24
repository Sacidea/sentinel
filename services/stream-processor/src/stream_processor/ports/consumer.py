from collections.abc import Awaitable, Callable
from typing import Protocol

from contracts.events import RawVibrationWindow

RawWindowHandler = Callable[[RawVibrationWindow], Awaitable[None]]


class RawWindowConsumer(Protocol):
    """Ham Kafka pencerelerini uygulama katmanına iletir."""

    async def consume(self, handler: RawWindowHandler) -> None:
        """Mesajı yalnız handler başarıyla işledikten sonra onaylar."""
