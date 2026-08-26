import asyncio

from notifier.application.anomaly_notification import AnomalyNotification
from notifier.config import settings
from notifier.domain.idempotency import SeenEventIds
from notifier.infrastructure.celery_enqueue import CeleryEnqueue
from notifier.infrastructure.kafka_consumer import KafkaAnomalyConsumer
from notifier.infrastructure.kafka_dlq import KafkaDlqPublisher
from notifier.logging import setup_logging


async def main() -> None:
    setup_logging(settings.LOG_LEVEL)
    dlq = KafkaDlqPublisher(settings.KAFKA_BOOTSTRAP_SERVERS, settings.KAFKA_TOPIC_DLQ)
    consumer = KafkaAnomalyConsumer(
        settings.KAFKA_BOOTSTRAP_SERVERS,
        settings.KAFKA_TOPIC_ANOMALY,
        settings.KAFKA_CONSUMER_GROUP,
        dead_letters=dlq,
    )
    await dlq.start()
    try:
        await AnomalyNotification(
            consumer,
            CeleryEnqueue(),
            SeenEventIds(),
        ).run()
    finally:
        await dlq.stop()


if __name__ == "__main__":
    asyncio.run(main())
