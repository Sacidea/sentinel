"""Kapanan snapshot'ı özellik ve tespit sonucuna çevirir; I/O yok.

Tampon `snapshot_buffer.py`'de. Burada COMPLETE/PARTIAL işlenir, DISCARDED ve bozuk
örnekler çağıranın DLQ'ya göndermesi için işaretlenir (bkz. planning/03, 07, 15).
Katman 1 (Z-Score) ve Katman 2 (AnomalyDetector) aynı anda çalışabilir.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from contracts.events import ANOMALY_SCHEMA_VERSION, AnomalyDetected, ScoreKind, VibrationFeatures

from stream_processor.application.snapshot_buffer import ClosedReason, ClosedSnapshot
from stream_processor.domain.detectors import DetectionResult, DetectionStatus, ZScoreDetector
from stream_processor.domain.features import SignalFeatures, extract_features
from stream_processor.ports.detector import AnomalyDetector


@dataclass(frozen=True)
class PipelineOutcome:
    """İşlenmiş snapshot; None alanlar o adımın atlandığını gösterir."""

    features: VibrationFeatures | None
    anomalies: tuple[AnomalyDetected, ...]
    discard_reason: str | None

    @property
    def anomaly(self) -> AnomalyDetected | None:
        """İlk anomali; eski testler tek event bekler."""
        return self.anomalies[0] if self.anomalies else None


def process_closed_snapshot(
    closed: ClosedSnapshot,
    detector: ZScoreDetector,
    extra_detectors: Sequence[AnomalyDetector] = (),
    *,
    event_id_factory: Callable[[], UUID] = uuid4,
) -> PipelineOutcome:
    """Kapanış nedenine göre özellik çıkarır; Katman 1+2 skorlar."""
    if closed.reason is ClosedReason.DISCARDED:
        return PipelineOutcome(None, (), "reassembly_insufficient_chunks")

    assembly = closed.assembly
    try:
        extracted = extract_features(assembly.merged_samples())
    except ValueError:
        return PipelineOutcome(None, (), "invalid_samples")

    features = VibrationFeatures(
        snapshot_id=assembly.snapshot_id,
        machine_id=assembly.machine_id,
        axis=assembly.axis,
        dataset=assembly.dataset,
        occurred_at=assembly.occurred_at,
        rms=extracted.rms,
        kurtosis=extracted.kurtosis,
        crest_factor=extracted.crest_factor,
        peak=extracted.peak,
        is_complete=closed.reason is ClosedReason.COMPLETE,
        chunks_received=assembly.chunks_received,
        fft_band_energy=dict(extracted.fft_band_energy),
    )
    detections = [
        detector.observe(assembly.machine_id, assembly.axis, extracted, dataset=assembly.dataset)
    ]
    for extra in extra_detectors:
        detections.append(
            extra.observe(assembly.machine_id, assembly.axis, extracted, dataset=assembly.dataset)
        )
    anomalies = tuple(
        _to_anomaly(
            detection,
            extracted=extracted,
            features=features,
            event_id=event_id_factory(),
        )
        for detection in detections
        if _is_alarm(detection)
    )
    return PipelineOutcome(features, anomalies, None)


def _is_alarm(detection: DetectionResult) -> bool:
    return (
        detection.status in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
        and detection.triggered_metric is not None
        and detection.triggered_value is not None
        and detection.triggered_z is not None
    )


def _to_anomaly(
    detection: DetectionResult,
    *,
    extracted: SignalFeatures,
    features: VibrationFeatures,
    event_id: UUID,
) -> AnomalyDetected:
    severity: Literal["warning", "critical"] = (
        "warning" if detection.status is DetectionStatus.WARNING else "critical"
    )
    metric = detection.triggered_metric or "unknown"
    value = detection.triggered_value
    score = detection.triggered_z
    if value is None:
        value = extracted.rms
    if score is None:
        score = 0.0
    kind = _score_kind(detection)
    z_score = score if kind == "zscore" else None
    anomaly_score = None if kind == "zscore" else score
    return AnomalyDetected(
        event_id=event_id,
        occurred_at=features.occurred_at,
        machine_id=features.machine_id,
        axis=features.axis,
        dataset=features.dataset,
        metric=metric,
        value=value,
        z_score=z_score,
        anomaly_score=anomaly_score,
        score_kind=kind,
        severity=severity,
        is_complete=features.is_complete,
        detector=detection.detector,
        schema_version=ANOMALY_SCHEMA_VERSION,
    )


_SCORE_KINDS: dict[str, ScoreKind] = {
    "zscore": "zscore",
    "if_score": "if_score",
    "extent": "extent",
    "pca_t2": "pca_t2",
    "pca_spe": "pca_spe",
    "river": "river",
}


def _score_kind(detection: DetectionResult) -> ScoreKind:
    """Detector'ın kazanan skor türü; test sahtekarları için detector/metric'ten türet."""
    named = _SCORE_KINDS.get(detection.score_kind or "")
    if named is not None:
        return named
    if detection.detector == "zscore":
        return "zscore"
    if detection.detector == "pca":
        return "pca_spe" if detection.triggered_metric == "spe" else "pca_t2"
    if detection.detector == "river":
        return "river"
    return "if_score"
