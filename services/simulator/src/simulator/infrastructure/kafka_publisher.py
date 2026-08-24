from aiokafka import AIOKafkaProducer
from simulator.ports.publisher import MessagePublisher


class KafkaPublisherAdapter(MessagePublisher):
    """
    Kafka'ya mesaj gönderme görevini üstlenen adaptör.
    """

    def __init__(self, bootstrap_servers: str):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda m: m  # Zaten bytes alacağız
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish(self, topic: str, key: str, message: bytes) -> None:
        await self._producer.send_and_wait(
            topic=topic,
            key=key.encode("utf-8"),
            value=message
        )
