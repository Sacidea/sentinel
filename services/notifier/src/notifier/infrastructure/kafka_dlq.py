import json

from aiokafka import AIOKafkaProducer


class KafkaDlqPublisher:
    """Parse edilemeyen anomali mesajını anomaly.dlq'ya yazar (07)."""

    def __init__(self, bootstrap_servers: str, dlq_topic: str) -> None:
        self._dlq_topic = dlq_topic
        self._producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def reject_raw(self, payload: bytes, *, reason: str) -> None:
        body = json.dumps(
            {"reason": reason, "raw": payload.decode("utf-8", errors="replace")}
        ).encode("utf-8")
        await self._producer.send_and_wait(self._dlq_topic, body)
