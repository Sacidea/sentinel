import json

from aiokafka import AIOKafkaProducer
from contracts.events import AnomalyDetected, RawVibrationWindow

from stream_processor.application.snapshot_buffer import ClosedSnapshot


class KafkaDownstreamPublisher:
    """Anomali event'lerini ve DLQ kayıtlarını Kafka'ya yazar."""

    def __init__(self, bootstrap_servers: str, anomaly_topic: str, dlq_topic: str) -> None:
        self._anomaly_topic = anomaly_topic
        self._dlq_topic = dlq_topic
        self._producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish_anomaly(self, event: AnomalyDetected) -> None:
        await self._producer.send_and_wait(
            self._anomaly_topic,
            event.model_dump_json().encode("utf-8"),
            key=event.machine_id.encode("utf-8"),
        )

    async def reject_chunk(self, window: RawVibrationWindow, *, reason: str) -> None:
        payload = {"reason": reason, "chunk": json.loads(window.model_dump_json())}
        await self._send_dlq(payload, key=window.machine_id)

    async def reject_snapshot(self, closed: ClosedSnapshot, *, reason: str) -> None:
        assembly = closed.assembly
        payload = {
            "reason": reason,
            "snapshot_id": str(assembly.snapshot_id),
            "machine_id": assembly.machine_id,
            "axis": assembly.axis,
            "chunks_received": assembly.chunks_received,
            "total_chunks": assembly.total_chunks,
        }
        await self._send_dlq(payload, key=assembly.machine_id)

    async def _send_dlq(self, payload: dict[str, object], *, key: str) -> None:
        await self._producer.send_and_wait(
            self._dlq_topic,
            json.dumps(payload).encode("utf-8"),
            key=key.encode("utf-8"),
        )
