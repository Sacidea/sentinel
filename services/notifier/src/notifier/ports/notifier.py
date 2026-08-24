from typing import Protocol

from contracts.events import AnomalyDetected


class Notifier(Protocol):
    async def notify(self, event: AnomalyDetected) -> None:
        """Bir anomali olayını seçili bildirim kanalına iletir."""
