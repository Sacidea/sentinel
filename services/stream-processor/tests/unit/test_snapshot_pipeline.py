"""Kapanan snapshot → özellik + Z-Score; I/O yok (bkz. planning/03, 15)."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest
from contracts.events import RawVibrationWindow
from stream_processor.application.snapshot_buffer import ClosedReason, ClosedSnapshot
from stream_processor.application.snapshot_pipeline import process_closed_snapshot
from stream_processor.domain.detectors import ZScoreDetector
from stream_processor.domain.features import extract_features
from stream_processor.domain.reassembly import SnapshotAssembly

MOMENT = datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC)


def _chunk(
    index: int,
    *,
    snapshot_id: UUID,
    samples: list[float],
    total_chunks: int = 4,
    machine_id: str = "bearing_1",
    axis: Literal["x", "y"] = "x",
) -> RawVibrationWindow:
    return RawVibrationWindow(
        snapshot_id=snapshot_id,
        chunk_index=index,
        total_chunks=total_chunks,
        machine_id=machine_id,
        axis=axis,
        samples=samples,
        occurred_at=MOMENT,
        source_timestamp=MOMENT,
    )


def _closed(
    sample_groups: list[list[float]],
    *,
    reason: ClosedReason = ClosedReason.COMPLETE,
    total_chunks: int | None = None,
    machine_id: str = "bearing_1",
) -> ClosedSnapshot:
    snapshot_id = uuid4()
    chunk_total = total_chunks if total_chunks is not None else len(sample_groups)
    assembly = SnapshotAssembly(
        _chunk(
            0,
            snapshot_id=snapshot_id,
            samples=sample_groups[0],
            total_chunks=chunk_total,
            machine_id=machine_id,
        )
    )
    for index, samples in enumerate(sample_groups[1:], start=1):
        assembly.add(
            _chunk(
                index,
                snapshot_id=snapshot_id,
                samples=samples,
                total_chunks=chunk_total,
                machine_id=machine_id,
            )
        )
    return ClosedSnapshot(assembly=assembly, reason=reason)


def _detector() -> ZScoreDetector:
    return ZScoreDetector(
        baseline_window=2,
        ma_window=1,
        warning_threshold=3.0,
        critical_threshold=5.0,
    )


@pytest.mark.unit
def test_discarded_snapshot_is_not_processed() -> None:
    closed = _closed([[0.0], [1.0]], reason=ClosedReason.DISCARDED)
    outcome = process_closed_snapshot(closed, _detector())

    assert outcome.features is None
    assert outcome.anomaly is None
    assert outcome.discard_reason == "reassembly_insufficient_chunks"


@pytest.mark.unit
def test_complete_snapshot_extracts_features() -> None:
    closed = _closed([[1.0, -1.0], [1.0, -1.0]])
    outcome = process_closed_snapshot(closed, _detector())

    assert outcome.features is not None
    assert outcome.discard_reason is None
    expected = extract_features([1.0, -1.0, 1.0, -1.0])
    assert outcome.features.rms == expected.rms
    assert outcome.features.kurtosis == expected.kurtosis
    assert outcome.features.fft_band_energy == expected.fft_band_energy
    assert outcome.features.is_complete is True
    assert outcome.features.chunks_received == 2


@pytest.mark.unit
def test_partial_snapshot_marks_incomplete() -> None:
    closed = _closed([[0.1], [0.2]], reason=ClosedReason.PARTIAL, total_chunks=4)
    outcome = process_closed_snapshot(closed, _detector())

    assert outcome.features is not None
    assert outcome.features.is_complete is False
    assert outcome.features.chunks_received == 2


@pytest.mark.unit
def test_warmup_persists_features_without_anomaly() -> None:
    detector = _detector()
    first = process_closed_snapshot(_closed([[0.0, 0.0]]), detector)
    second = process_closed_snapshot(_closed([[2.0, 2.0]]), detector)

    assert first.features is not None and first.anomaly is None
    assert second.features is not None and second.anomaly is None


@pytest.mark.unit
def test_spike_after_baseline_emits_anomaly() -> None:
    detector = _detector()
    process_closed_snapshot(_closed([[0.0, 0.0]]), detector)
    process_closed_snapshot(_closed([[2.0, 2.0]]), detector)
    spiked = process_closed_snapshot(_closed([[6.0, 6.0]]), detector)

    assert spiked.anomaly is not None
    assert spiked.anomaly.severity == "critical"
    assert spiked.anomaly.metric == "rms"
    assert spiked.anomaly.detector == "zscore"
    assert spiked.anomaly.is_complete is True
    assert spiked.anomaly.score_kind == "zscore"
    assert spiked.anomaly.z_score is not None
    assert spiked.anomaly.anomaly_score is None
    assert spiked.anomaly.schema_version == 3
    assert spiked.anomaly.dataset == "unknown"


@pytest.mark.unit
def test_extra_detector_emits_parallel_anomaly() -> None:
    from stream_processor.domain.detectors import DetectionResult, DetectionStatus

    class _AlwaysWarn:
        def observe(
            self, machine_id: str, axis: str, features: object, *, dataset: str = "unknown"
        ) -> DetectionResult:
            return DetectionResult(
                status=DetectionStatus.WARNING,
                scores=(),
                triggered_metric="feature_vector",
                triggered_value=1.0,
                triggered_z=1.0,
                detector="isolation_forest",
                score_kind="if_score",
            )

    detector = _detector()
    process_closed_snapshot(_closed([[0.0, 0.0]]), detector)
    process_closed_snapshot(_closed([[2.0, 2.0]]), detector)
    spiked = process_closed_snapshot(
        _closed([[6.0, 6.0]]), detector, extra_detectors=(_AlwaysWarn(),)
    )

    assert spiked.anomaly is not None
    names = {event.detector for event in spiked.anomalies}
    assert names == {"zscore", "isolation_forest"}
    forest = next(event for event in spiked.anomalies if event.detector == "isolation_forest")
    assert forest.z_score is None
    assert forest.anomaly_score == pytest.approx(1.0)
    assert forest.score_kind == "if_score"


@pytest.mark.unit
def test_invalid_samples_are_discarded() -> None:
    closed = _closed([[float("nan")], [0.1]])
    outcome = process_closed_snapshot(closed, _detector())

    assert outcome.features is None
    assert outcome.discard_reason == "invalid_samples"
