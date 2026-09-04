from typing import Protocol

from contracts.events import AnomalyDetected, VibrationFeatures

from stream_processor.domain.detectors import BaselineSnapshot


class FeatureRepository(Protocol):
    """Çıkarılmış özellikleri kalıcı hâle getirir; ham örnek yazılmaz (bkz. 14)."""

    async def save_features(self, features: VibrationFeatures) -> None:
        """Bir snapshot'ın özellik satırını yazar."""


class AnomalyRepository(Protocol):
    """Tespit edilen anomali olayını kaydeder."""

    async def save_anomaly(self, event: AnomalyDetected) -> None:
        """Aynı event_id ikinci kez gelirse yok sayılır (idempotency)."""


class BaselineRepository(Protocol):
    """Donmuş Z-Score baseline'ını saklar; restart'ta tekrar öğrenilmez."""

    async def save_baseline(self, snapshot: BaselineSnapshot) -> None:
        """İlk donma kalır; sonraki yazımlar yok sayılır (ON CONFLICT DO NOTHING)."""

    async def load_baselines(self) -> list[BaselineSnapshot]:
        """Kayıtlı tüm baseline satırlarını döner."""
