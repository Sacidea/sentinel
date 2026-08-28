import asyncio
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest
from contracts.events import AnomalyDetected, RawVibrationWindow, VibrationFeatures
from stream_processor.application.alarm_debounce import AlarmDebounce
from stream_processor.application.raw_window_ingestion import RawWindowIngestion
from stream_processor.application.snapshot_buffer import ClosedSnapshot, SnapshotBuffer
from stream_processor.domain.detectors import (
    BaselineSnapshot,
    DetectionResult,
    DetectionStatus,
    ZScoreDetector,
)
from stream_processor.ports.consumer import RawWindowHandler

MOMENT = datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC)


class FakeConsumer:
    def __init__(self, windows: list[RawVibrationWindow]) -> None:
        self._windows = windows

    async def consume(self, handler: RawWindowHandler) -> None:
        for window in self._windows:
            await handler(window)


class FakeFeatures:
    def __init__(self) -> None:
        self.saved: list[VibrationFeatures] = []

    async def save_features(self, features: VibrationFeatures) -> None:
        self.saved.append(features)


class FakeAnomalies:
    def __init__(self) -> None:
        self.saved: list[AnomalyDetected] = []

    async def save_anomaly(self, event: AnomalyDetected) -> None:
        self.saved.append(event)


class FakeAnomalyPublisher:
    def __init__(self) -> None:
        self.published: list[AnomalyDetected] = []

    async def publish_anomaly(self, event: AnomalyDetected) -> None:
        self.published.append(event)


class FakeDeadLetters:
    def __init__(self) -> None:
        self.chunks: list[tuple[RawVibrationWindow, str]] = []
        self.snapshots: list[tuple[ClosedSnapshot, str]] = []

    async def reject_chunk(self, window: RawVibrationWindow, *, reason: str) -> None:
        self.chunks.append((window, reason))

    async def reject_snapshot(self, closed: ClosedSnapshot, *, reason: str) -> None:
        self.snapshots.append((closed, reason))


class FakeBaselines:
    def __init__(self) -> None:
        self.saved: list[BaselineSnapshot] = []

    async def save_baseline(self, snapshot: BaselineSnapshot) -> None:
        self.saved.append(snapshot)

    async def load_baselines(self) -> list[BaselineSnapshot]:
        return list(self.saved)


def _chunk(
    index: int,
    *,
    snapshot_id: UUID,
    samples: list[float],
    total_chunks: int = 2,
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


def _ingestion(
    windows: list[RawVibrationWindow],
    *,
    buffer: SnapshotBuffer | None = None,
    detector: ZScoreDetector | None = None,
    debounce: AlarmDebounce | None = None,
    extra_detectors: tuple[object, ...] = (),
) -> tuple[
    RawWindowIngestion,
    FakeFeatures,
    FakeAnomalies,
    FakeAnomalyPublisher,
    FakeDeadLetters,
    FakeBaselines,
]:
    features = FakeFeatures()
    anomalies = FakeAnomalies()
    publisher = FakeAnomalyPublisher()
    dead_letters = FakeDeadLetters()
    baselines = FakeBaselines()
    ingestion = RawWindowIngestion(
        FakeConsumer(windows),
        buffer or SnapshotBuffer(timeout_sec=10.0, min_chunks_ratio=0.5, max_pending=100),
        detector
        or ZScoreDetector(
            baseline_window=2,
            ma_window=1,
            warning_threshold=3.0,
            critical_threshold=5.0,
        ),
        features,
        anomalies,
        publisher,
        dead_letters,
        baselines=baselines,
        debounce=debounce,
        extra_detectors=extra_detectors,
    )
    return ingestion, features, anomalies, publisher, dead_letters, baselines


@pytest.mark.unit
def test_complete_snapshot_persists_extracted_features() -> None:
    snapshot_id = uuid4()
    windows = [
        _chunk(0, snapshot_id=snapshot_id, samples=[1.0, -1.0]),
        _chunk(1, snapshot_id=snapshot_id, samples=[1.0, -1.0]),
    ]
    ingestion, features, anomalies, publisher, dead_letters, _ = _ingestion(windows)

    asyncio.run(ingestion.run())

    assert len(features.saved) == 1
    assert features.saved[0].rms == 1.0
    assert features.saved[0].is_complete is True
    assert anomalies.saved == []
    assert publisher.published == []
    assert dead_letters.snapshots == []


@pytest.mark.unit
def test_incomplete_snapshot_goes_to_dlq_on_flush() -> None:
    snapshot_id = uuid4()
    ingestion, features, _, _, dead_letters, _ = _ingestion(
        [_chunk(0, snapshot_id=snapshot_id, samples=[0.1], total_chunks=8)]
    )

    asyncio.run(ingestion.run())

    assert features.saved == []
    assert len(dead_letters.snapshots) == 1
    assert dead_letters.snapshots[0][1] == "reassembly_insufficient_chunks"


@pytest.mark.unit
def test_inconsistent_chunk_goes_to_dlq() -> None:
    snapshot_id = uuid4()
    windows = [
        _chunk(0, snapshot_id=snapshot_id, samples=[0.1], total_chunks=2),
        _chunk(1, snapshot_id=snapshot_id, samples=[0.2], total_chunks=4),
    ]
    ingestion, _, _, _, dead_letters, _ = _ingestion(windows)

    asyncio.run(ingestion.run())

    assert any(reason == "inconsistent_chunk" for _, reason in dead_letters.chunks)
    assert all(item[0].total_chunks == 4 for item in dead_letters.chunks)


@pytest.mark.unit
def test_spike_after_baseline_publishes_anomaly() -> None:
    first = uuid4()
    second = uuid4()
    spike = uuid4()
    windows = [
        _chunk(0, snapshot_id=first, samples=[0.0, 0.0], total_chunks=1),
        _chunk(0, snapshot_id=second, samples=[2.0, 2.0], total_chunks=1),
        _chunk(0, snapshot_id=spike, samples=[6.0, 6.0], total_chunks=1),
    ]
    ingestion, features, anomalies, publisher, dead_letters, _ = _ingestion(windows)

    asyncio.run(ingestion.run())

    assert len(features.saved) == 3
    assert len(anomalies.saved) == 1
    assert publisher.published == anomalies.saved
    assert anomalies.saved[0].severity == "critical"
    assert dead_letters.snapshots == []


@pytest.mark.unit
def test_frozen_baseline_is_persisted() -> None:
    first = uuid4()
    second = uuid4()
    windows = [
        _chunk(0, snapshot_id=first, samples=[0.0, 0.0], total_chunks=1),
        _chunk(0, snapshot_id=second, samples=[2.0, 2.0], total_chunks=1),
    ]
    ingestion, _, _, _, _, baselines = _ingestion(windows)

    asyncio.run(ingestion.run())

    metrics = {row.metric for row in baselines.saved}
    assert metrics == {"rms", "kurtosis"}
    rms = next(row for row in baselines.saved if row.metric == "rms")
    assert rms.mean == pytest.approx(1.0)
    assert rms.std == pytest.approx(1.0)


@pytest.mark.unit
def test_debounce_records_anomaly_but_skips_second_publish() -> None:
    first = uuid4()
    second = uuid4()
    spike = uuid4()
    again = uuid4()
    windows = [
        _chunk(0, snapshot_id=first, samples=[0.0, 0.0], total_chunks=1),
        _chunk(0, snapshot_id=second, samples=[2.0, 2.0], total_chunks=1),
        _chunk(0, snapshot_id=spike, samples=[6.0, 6.0], total_chunks=1),
        _chunk(0, snapshot_id=again, samples=[6.0, 6.0], total_chunks=1),
    ]
    ingestion, _, anomalies, publisher, _, _ = _ingestion(
        windows, debounce=AlarmDebounce(cooldown_sec=60.0)
    )

    asyncio.run(ingestion.run())

    assert len(anomalies.saved) == 2
    assert len(publisher.published) == 1
    assert publisher.published[0].event_id == anomalies.saved[0].event_id


class _WarnPca:
    def __init__(self) -> None:
        self._seen = 0

    def observe(self, machine_id: str, axis: str, features: object) -> DetectionResult:
        self._seen += 1
        if self._seen <= 2:
            return DetectionResult(status=DetectionStatus.WARMING_UP, scores=(), detector="pca")
        return DetectionResult(
            status=DetectionStatus.WARNING,
            scores=(),
            triggered_metric="hotelling_t2",
            triggered_value=4.0,
            triggered_z=4.0,
            detector="pca",
        )


@pytest.mark.unit
def test_pca_alarm_is_persisted_but_not_published() -> None:
    windows = [
        _chunk(0, snapshot_id=uuid4(), samples=[0.0, 0.0], total_chunks=1),
        _chunk(0, snapshot_id=uuid4(), samples=[2.0, 2.0], total_chunks=1),
        _chunk(0, snapshot_id=uuid4(), samples=[6.0, 6.0], total_chunks=1),
    ]
    ingestion, _, anomalies, publisher, _, _ = _ingestion(windows, extra_detectors=(_WarnPca(),))

    asyncio.run(ingestion.run())

    detectors = [event.detector for event in anomalies.saved]
    assert "pca" in detectors
    assert "zscore" in detectors
    assert all(event.detector != "pca" for event in publisher.published)
    assert any(event.detector == "zscore" for event in publisher.published)
