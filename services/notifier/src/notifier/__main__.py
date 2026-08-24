import asyncio

from notifier.application.anomaly_notification import AnomalyNotification
from notifier.config import settings
from notifier.infrastructure.kafka_consumer import KafkaAnomalyConsumer
from notifier.infrastructure.telegram_notifier import LoggingNotifier
from notifier.logging import setup_logging


async def main() -> None:
    setup_logging(settings.LOG_LEVEL)
    consumer = KafkaAnomalyConsumer(
        settings.KAFKA_BOOTSTRAP_SERVERS,
        settings.KAFKA_TOPIC_ANOMALY,
        settings.KAFKA_CONSUMER_GROUP,
    )
    await AnomalyNotification(consumer, LoggingNotifier()).run()


if __name__ == "__main__":
    asyncio.run(main())
