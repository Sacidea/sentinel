"""Anomali detektör portu — yeni algoritma orkestrasyona dokunmadan eklenir (03)."""

from typing import Protocol

from stream_processor.domain.detectors import DetectionResult
from stream_processor.domain.features import SignalFeatures


class AnomalyDetector(Protocol):
    """Katman 1 ve 2 ortak sözleşmesi: `score` değil, soğuk başlangıçlı `observe`."""

    def observe(
        self,
        machine_id: str,
        axis: str,
        features: SignalFeatures,
        *,
        dataset: str = "unknown",
    ) -> DetectionResult:
        """Özellik vektörünü baseline'a ekler veya skorlar."""
        ...
