"""Kapanan snapshot'ı özellik ve Z-Score sonucuna çevirir; I/O yok.

Tampon `snapshot_buffer.py`'de. Burada COMPLETE/PARTIAL işlenir, DISCARDED ve bozuk
örnekler çağıranın DLQ'ya göndermesi için işaretlenir (bkz. planning/03, 07, 15).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from contracts.events import AnomalyDetected, VibrationFeatures

from stream_processor.application.snapshot_buffer import ClosedReason, ClosedSnapshot
from stream_processor.domain.detectors import DetectionStatus, ZScoreDetector
from stream_processor.domain.features import extract_features


@dataclass(frozen=True)
class PipelineOutcome:
    """İşlenmiş snapshot; None alanlar o adımın atlandığını gösterir."""

    features: VibrationFeatures | None
    anomaly: AnomalyDetected | None
    discard_reason: str | None


def process_closed_snapshot(
    closed: ClosedSnapshot,
    detector: ZScoreDetector,
    *,
    event_id_factory: Callable[[], UUID] = uuid4,
) -> PipelineOutcome:
    """Kapanış nedenine göre özellik çıkarır ve Z-Score uygular."""
    if closed.reason is ClosedReason.DISCARDED:
        return PipelineOutcome(None, None, "reassembly_insufficient_chunks")

    assembly = closed.assembly
    try:
        extracted = extract_features(assembly.merged_samples())
    except ValueError:
        return PipelineOutcome(None, None, "invalid_samples")

    detection = detector.observe(assembly.machine_id, assembly.axis, extracted)
    features = VibrationFeatures(
        snapshot_id=assembly.snapshot_id,
        machine_id=assembly.machine_id,
        axis=assembly.axis,
        occurred_at=assembly.occurred_at,
        rms=extracted.rms,
        kurtosis=extracted.kurtosis,
        crest_factor=extracted.crest_factor,
        peak=extracted.peak,
        is_complete=closed.reason is ClosedReason.COMPLETE,
        chunks_received=assembly.chunks_received,
    )
    if detection.status not in (DetectionStatus.WARNING, DetectionStatus.CRITICAL):
        return PipelineOutcome(features, None, None)
    if (
        detection.triggered_metric is None
        or detection.triggered_value is None
        or detection.triggered_z is None
    ):
        return PipelineOutcome(features, None, None)

    severity: Literal["warning", "critical"] = (
        "warning" if detection.status is DetectionStatus.WARNING else "critical"
    )
    anomaly = AnomalyDetected(
        event_id=event_id_factory(),
        occurred_at=assembly.occurred_at,
        machine_id=assembly.machine_id,
        axis=assembly.axis,
        metric=detection.triggered_metric,
        value=detection.triggered_value,
        z_score=detection.triggered_z,
        severity=severity,
        is_complete=closed.reason is ClosedReason.COMPLETE,
        detector=detection.detector,
    )
    return PipelineOutcome(features, anomaly, None)
