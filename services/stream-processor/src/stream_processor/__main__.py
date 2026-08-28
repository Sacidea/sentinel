import asyncio
import signal

import structlog

from stream_processor.application.alarm_debounce import AlarmDebounce
from stream_processor.application.raw_window_ingestion import RawWindowIngestion
from stream_processor.application.snapshot_buffer import SnapshotBuffer, reassembly_timeout_sec
from stream_processor.config import settings
from stream_processor.domain.detectors import ZScoreDetector
from stream_processor.domain.ml_detectors import (
    IsolationForestDetector,
    PcaDetector,
    RiverHalfSpaceTreesDetector,
)
from stream_processor.infrastructure.kafka_consumer import KafkaRawWindowConsumer
from stream_processor.infrastructure.kafka_publisher import KafkaDownstreamPublisher
from stream_processor.infrastructure.timescale_repo import TimescaleRepository
from stream_processor.logging import setup_logging
from stream_processor.ports.detector import AnomalyDetector

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Adapter'ları oluşturur ve reassembly + özellik + Z-Score akışını başlatır."""
    setup_logging(settings.LOG_LEVEL)
    timeout_sec = reassembly_timeout_sec(
        playback_interval_sec=settings.PLAYBACK_INTERVAL_SEC,
        floor=settings.REASSEMBLY_TIMEOUT_FLOOR,
        factor=settings.REASSEMBLY_TIMEOUT_FACTOR,
    )
    consumer = KafkaRawWindowConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.KAFKA_TOPIC_RAW,
        dlq_topic=settings.KAFKA_TOPIC_DLQ,
        consumer_group=settings.KAFKA_CONSUMER_GROUP,
    )
    publisher = KafkaDownstreamPublisher(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        anomaly_topic=settings.KAFKA_TOPIC_ANOMALY,
        dlq_topic=settings.KAFKA_TOPIC_DLQ,
    )
    repository = TimescaleRepository(settings.TIMESCALE_DSN)
    buffer = SnapshotBuffer(
        timeout_sec=timeout_sec,
        min_chunks_ratio=settings.REASSEMBLY_MIN_CHUNKS_RATIO,
        max_pending=settings.MAX_PENDING_SNAPSHOTS,
    )
    detector = ZScoreDetector(
        baseline_window=settings.BASELINE_WINDOW,
        ma_window=settings.MA_WINDOW,
        warning_threshold=settings.ANOMALY_ZSCORE_WARNING,
        critical_threshold=settings.ANOMALY_ZSCORE_CRITICAL,
    )
    extra_detectors: list[AnomalyDetector] = []
    if settings.ML_LAYER_ENABLED:
        extra_detectors = [
            IsolationForestDetector(
                baseline_window=settings.BASELINE_WINDOW,
                warning_quantile=settings.ML_WARNING_QUANTILE,
                critical_quantile=settings.ML_CRITICAL_QUANTILE,
                use_extent=True,
            ),
            PcaDetector(
                baseline_window=settings.BASELINE_WINDOW,
                warning_quantile=settings.ML_WARNING_QUANTILE,
                critical_quantile=settings.ML_CRITICAL_QUANTILE,
            ),
            RiverHalfSpaceTreesDetector(
                baseline_window=settings.BASELINE_WINDOW,
                warning_quantile=settings.ML_WARNING_QUANTILE,
                critical_quantile=settings.ML_CRITICAL_QUANTILE,
            ),
        ]
    for snapshot in await repository.load_baselines():
        detector.seed_baseline(snapshot)
    ingestion = RawWindowIngestion(
        consumer,
        buffer,
        detector,
        repository,
        repository,
        publisher,
        publisher,
        baselines=repository,
        debounce=AlarmDebounce(cooldown_sec=settings.ALARM_COOLDOWN),
        extra_detectors=extra_detectors,
        sweep_interval_sec=min(1.0, timeout_sec),
    )
    await publisher.start()
    task = asyncio.create_task(ingestion.run())
    loop = asyncio.get_running_loop()

    def stop_service(signal_name: str) -> None:
        logger.info("Kapatma sinyali alındı.", signal=signal_name)
        task.cancel()

    for current_signal in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(current_signal, stop_service, current_signal.name)

    try:
        await task
    except asyncio.CancelledError:
        logger.info("Stream processor durduruldu.")
    finally:
        await publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())
