"""Ham chunk tüketimi: reassembly → özellik → Katman 1+2 → kalıcı kayıt / bildirim."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import structlog
from contracts.events import RawVibrationWindow

from stream_processor.application.alarm_debounce import AlarmDebounce
from stream_processor.application.snapshot_buffer import (
    ChunkDisposition,
    ClosedSnapshot,
    SnapshotBuffer,
)
from stream_processor.application.snapshot_pipeline import process_closed_snapshot
from stream_processor.domain.detectors import ZScoreDetector
from stream_processor.ports.consumer import RawWindowConsumer
from stream_processor.ports.detector import AnomalyDetector
from stream_processor.ports.publisher import AnomalyPublisher, DeadLetterPublisher
from stream_processor.ports.repository import (
    AnomalyRepository,
    BaselineRepository,
    FeatureRepository,
)

logger = structlog.get_logger(__name__)

# Kafka → notifier → Telegram. PCA/River kayda yazar, bildirim yok (ADR-0008).
NOTIFY_DETECTORS = frozenset({"zscore", "isolation_forest"})


class RawWindowIngestion:
    """Chunk'ları birleştirir; kapanan snapshot'ları özellik ve anomaliye çevirir."""

    def __init__(
        self,
        consumer: RawWindowConsumer,
        buffer: SnapshotBuffer,
        detector: ZScoreDetector,
        features: FeatureRepository,
        anomalies: AnomalyRepository,
        anomaly_publisher: AnomalyPublisher,
        dead_letters: DeadLetterPublisher,
        baselines: BaselineRepository | None = None,
        debounce: AlarmDebounce | None = None,
        extra_detectors: Sequence[AnomalyDetector] = (),
        notify_detectors: frozenset[str] | None = None,
        *,
        sweep_interval_sec: float = 0.0,
    ) -> None:
        self._consumer = consumer
        self._buffer = buffer
        self._detector = detector
        self._extra_detectors = extra_detectors
        self._features = features
        self._anomalies = anomalies
        self._anomaly_publisher = anomaly_publisher
        self._dead_letters = dead_letters
        self._baselines = baselines
        self._debounce = debounce or AlarmDebounce(cooldown_sec=0.0)
        self._notify_detectors = notify_detectors or NOTIFY_DETECTORS
        self._sweep_interval_sec = sweep_interval_sec

    async def run(self) -> None:
        sweeper = (
            asyncio.create_task(self._sweep_loop()) if self._sweep_interval_sec > 0.0 else None
        )
        try:
            await self._consumer.consume(self.handle)
        finally:
            if sweeper is not None:
                sweeper.cancel()
            await self._dispatch(self._buffer.flush())

    async def handle(self, window: RawVibrationWindow) -> None:
        result = self._buffer.add(window)
        if result.disposition is ChunkDisposition.INCONSISTENT:
            await self._dead_letters.reject_chunk(window, reason="inconsistent_chunk")
            logger.warning(
                "Tutarsiz chunk DLQ'ya gitti.",
                snapshot_id=str(window.snapshot_id),
                chunk_index=window.chunk_index,
            )
        await self._dispatch(result.closed)

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(self._sweep_interval_sec)
            await self._dispatch(self._buffer.sweep())

    async def _dispatch(self, closed: list[ClosedSnapshot]) -> None:
        for snapshot in closed:
            outcome = process_closed_snapshot(
                snapshot, self._detector, extra_detectors=self._extra_detectors
            )
            if outcome.discard_reason is not None:
                await self._dead_letters.reject_snapshot(snapshot, reason=outcome.discard_reason)
                logger.warning(
                    "Snapshot DLQ'ya gitti.",
                    snapshot_id=str(snapshot.assembly.snapshot_id),
                    reason=outcome.discard_reason,
                    chunks_received=snapshot.assembly.chunks_received,
                )
                continue
            if outcome.features is not None:
                await self._features.save_features(outcome.features)
            if self._baselines is not None:
                for frozen in self._detector.drain_frozen():
                    await self._baselines.save_baseline(frozen)
            if outcome.anomalies:
                for event in outcome.anomalies:
                    await self._anomalies.save_anomaly(event)
                    if event.detector not in self._notify_detectors:
                        continue
                    axis = event.axis or ""
                    if self._debounce.should_notify(
                        machine_id=event.machine_id,
                        axis=axis,
                        metric=event.metric,
                        severity=event.severity,
                        at=event.occurred_at,
                        detector=event.detector,
                        dataset=event.dataset,
                    ):
                        await self._anomaly_publisher.publish_anomaly(event)
                        logger.warning(
                            "Anomali tespit edildi.",
                            dataset=event.dataset,
                            machine_id=event.machine_id,
                            metric=event.metric,
                            severity=event.severity,
                            detector=event.detector,
                            score_kind=event.score_kind,
                            z_score=event.z_score,
                            anomaly_score=event.anomaly_score,
                        )
