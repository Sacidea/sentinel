import structlog
from aiokafka import AIOKafkaConsumer
from contracts.events import AnomalyDetected
from pydantic import ValidationError

from notifier.ports.consumer import AnomalyHandler

logger = structlog.get_logger(__name__)


class KafkaAnomalyConsumer:
    def __init__(self, bootstrap_servers: str, topic: str, consumer_group: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._consumer_group = consumer_group

    async def consume(self, handler: AnomalyHandler) -> None:
        consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._consumer_group,
            enable_auto_commit=False,
        )
        await consumer.start()
        try:
            async for message in consumer:
                try:
                    event = AnomalyDetected.model_validate_json(message.value)
                except ValidationError:
                    logger.warning("Geçersiz anomali olayı atlandı.")
                    await consumer.commit()
                    continue
                await handler(event)
                await consumer.commit()
        finally:
            await consumer.stop()
