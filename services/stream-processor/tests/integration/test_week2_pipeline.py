"""Hafta 2 uçtan uca: chunk → reassembly → Z-Score + Katman 2 (I/O yok, fake port)."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from contracts.events import AnomalyDetected, RawVibrationWindow, VibrationFeatures
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
        self.snapshots: list[tuple[ClosedSnapshot, str]] = []

    async def reject_chunk(self, window: RawVibrationWindow, *, reason: str) -> None:
        return None

    async def reject_snapshot(self, closed: ClosedSnapshot, *, reason: str) -> None:
        self.snapshots.append((closed, reason))


class FakeBaselines:
    def __init__(self) -> None:
        self.saved: list[BaselineSnapshot] = []

    async def save_baseline(self, snapshot: BaselineSnapshot) -> None:
        self.saved.append(snapshot)


class WarnForest:
    def __init__(self) -> None:
        self._seen = 0

    def observe(self, machine_id: str, axis: str, features: object) -> DetectionResult:
        self._seen += 1
        if self._seen <= 2:
            return DetectionResult(
                status=DetectionStatus.WARMING_UP, scores=(), detector="isolation_forest"
            )
        return DetectionResult(
            status=DetectionStatus.WARNING,
            scores=(),
            triggered_metric="feature_vector",
            triggered_value=1.5,
            triggered_z=1.5,
            detector="isolation_forest",
        )


def _chunk(snapshot_id: UUID, samples: list[float]) -> RawVibrationWindow:
    return RawVibrationWindow(
        snapshot_id=snapshot_id,
        chunk_index=0,
        total_chunks=1,
        machine_id="bearing_1",
        axis="x",
        samples=samples,
        occurred_at=MOMENT,
        source_timestamp=MOMENT,
    )


@pytest.mark.integration
def test_processor_persists_zscore_and_layer2_in_parallel() -> None:
    windows = [
        _chunk(uuid4(), [0.0, 0.0]),
        _chunk(uuid4(), [2.0, 2.0]),
        _chunk(uuid4(), [6.0, 6.0]),
    ]
    features = FakeFeatures()
    anomalies = FakeAnomalies()
    publisher = FakeAnomalyPublisher()
    dead = FakeDeadLetters()
    ingestion = RawWindowIngestion(
        FakeConsumer(windows),
        SnapshotBuffer(timeout_sec=10.0, min_chunks_ratio=0.5, max_pending=100),
        ZScoreDetector(
            baseline_window=2, ma_window=1, warning_threshold=3.0, critical_threshold=5.0
        ),
        features,
        anomalies,
        publisher,
        dead,
        baselines=FakeBaselines(),
        extra_detectors=(WarnForest(),),
    )

    asyncio.run(ingestion.run())

    detectors = {event.detector for event in anomalies.saved}
    assert detectors == {"zscore", "isolation_forest"}
    assert len(publisher.published) == 2
    assert dead.snapshots == []
    assert len(features.saved) == 3
