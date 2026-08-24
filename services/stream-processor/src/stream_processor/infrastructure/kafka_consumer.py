import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from contracts.events import RawVibrationWindow
from pydantic import ValidationError

from stream_processor.ports.consumer import RawWindowHandler

logger = structlog.get_logger(__name__)


class KafkaRawWindowConsumer:
    """Kafka'dan doğrulanmış ham pencereleri tüketir; bozukları DLQ'ya yollar."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        dlq_topic: str,
        consumer_group: str,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._dlq_topic = dlq_topic
        self._consumer_group = consumer_group

    async def consume(self, handler: RawWindowHandler) -> None:
        consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._consumer_group,
            enable_auto_commit=False,
        )
        producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
        await consumer.start()
        await producer.start()
        try:
            async for message in consumer:
                try:
                    window = RawVibrationWindow.model_validate_json(message.value)
                except ValidationError as error:
                    await producer.send_and_wait(
                        self._dlq_topic,
                        message.value,
                        headers=[("error", str(error).encode("utf-8"))],
                    )
                    await consumer.commit()
                    logger.warning("Geçersiz ham pencere DLQ'ya gönderildi.")
                    continue

                await handler(window)
                await consumer.commit()
                logger.debug(
                    "Ham pencere kaydedildi.",
                    machine_id=window.machine_id,
                    snapshot_id=str(window.snapshot_id),
                    chunk_index=window.chunk_index,
                )
        finally:
            await producer.stop()
            await consumer.stop()
