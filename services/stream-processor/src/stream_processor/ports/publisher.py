from typing import Protocol

from contracts.events import AnomalyDetected, RawVibrationWindow

from stream_processor.application.snapshot_buffer import ClosedSnapshot


class AnomalyPublisher(Protocol):
    """`anomaly.detected` event'ini notifier'a iletir."""

    async def publish_anomaly(self, event: AnomalyDetected) -> None:
        """Bildirim zincirine bir anomali olayı bırakır."""


class DeadLetterPublisher(Protocol):
    """İşlenemeyen chunk/snapshot'ı DLQ'ya yazar (bkz. 07)."""

    async def reject_chunk(self, window: RawVibrationWindow, *, reason: str) -> None:
        """Tutarsız gelen chunk tamponu kirletmez; DLQ'ya gider."""

    async def reject_snapshot(self, closed: ClosedSnapshot, *, reason: str) -> None:
        """Yetersiz veya bozuk snapshot sessizce kaybolmaz."""
