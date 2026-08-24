from collections.abc import Awaitable, Callable
from typing import Protocol

from contracts.events import AnomalyDetected

AnomalyHandler = Callable[[AnomalyDetected], Awaitable[None]]


class AnomalyConsumer(Protocol):
    async def consume(self, handler: AnomalyHandler) -> None:
        """Anomali olaylarını başarıyla işlendikten sonra onaylar."""
