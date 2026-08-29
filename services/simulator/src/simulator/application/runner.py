import asyncio

import structlog

from simulator.domain.chunking import create_chunks
from simulator.ports.dataset import DatasetProvider
from simulator.ports.publisher import MessagePublisher

logger = structlog.get_logger(__name__)


class SimulatorRunner:
    """
    Simülatör orkestrasyonu (Application Layer).
    Dataset üzerinden snapshot'ları okur, chunk'lara böler ve yayınlar.
    """

    def __init__(
        self,
        dataset: DatasetProvider,
        publisher: MessagePublisher,
        playback_interval_sec: float = 1.0,
        topic: str = "sensor.vibration.raw",
        dataset_name: str = "unknown",
    ):
        self.dataset = dataset
        self.publisher = publisher
        self.playback_interval_sec = playback_interval_sec
        self.topic = topic
        self.dataset_name = dataset_name

    async def run(self) -> None:
        logger.info("Simülatör başlatılıyor...")
        await self.publisher.start()

        try:
            async for snapshot in self.dataset.stream_snapshots():
                logger.info(f"Yeni snapshot alındı, {len(snapshot)} sensör verisi içeriyor.")

                # snapshot formatı: list of (machine_id, axis, samples, source_timestamp)
                for machine_id, axis, samples, timestamp in snapshot:
                    # Domain logic: Chunk'lara böl
                    chunks = create_chunks(
                        machine_id=machine_id,
                        axis=axis,
                        samples=samples,
                        source_timestamp=timestamp,
                        dataset=self.dataset_name,
                    )

                    # Publish
                    for chunk in chunks:
                        # Pydantic modelini JSON'a çevir
                        message_bytes = chunk.model_dump_json().encode("utf-8")
                        await self.publisher.publish(
                            topic=self.topic,
                            key=machine_id,  # Chunk anahtarlaması machine_id ile (AGENTS.md kuralı)
                            message=message_bytes,
                        )

                logger.debug(
                    "Snapshot tamamlandı, bekleniyor.",
                    bekleme_sn=self.playback_interval_sec,
                )
                await asyncio.sleep(self.playback_interval_sec)
        except asyncio.CancelledError:
            logger.info("Simülatör döngüsü iptal edildi.")
        except Exception as e:
            logger.exception("Simülatör çalışırken hata oluştu", exc_info=e)
        finally:
            await self.publisher.stop()
            logger.info("Simülatör durduruldu.")
