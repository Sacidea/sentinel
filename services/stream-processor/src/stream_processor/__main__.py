import asyncio
import signal

import structlog

from stream_processor.application.raw_window_ingestion import RawWindowIngestion
from stream_processor.config import settings
from stream_processor.infrastructure.kafka_consumer import KafkaRawWindowConsumer
from stream_processor.infrastructure.timescale_repo import TimescaleRawWindowRepository
from stream_processor.logging import setup_logging

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Adapter'ları oluşturur ve Walking Skeleton tüketim akışını başlatır."""
    setup_logging(settings.LOG_LEVEL)
    consumer = KafkaRawWindowConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.KAFKA_TOPIC_RAW,
        dlq_topic=settings.KAFKA_TOPIC_DLQ,
        consumer_group=settings.KAFKA_CONSUMER_GROUP,
    )
    repository = TimescaleRawWindowRepository(settings.TIMESCALE_DSN)
    ingestion = RawWindowIngestion(consumer, repository)
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


if __name__ == "__main__":
    asyncio.run(main())
