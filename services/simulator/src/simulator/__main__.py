import asyncio
import signal

import structlog

from simulator.application.runner import SimulatorRunner
from simulator.config import settings
from simulator.infrastructure.kafka_publisher import KafkaPublisherAdapter
from simulator.infrastructure.local_dataset import LocalDatasetAdapter
from simulator.logger import setup_logging

logger = structlog.get_logger(__name__)


async def main() -> None:
    setup_logging(settings.LOG_LEVEL)
    logger.info("Simulator servisi başlıyor...", config=settings.model_dump())

    # Adapter'lar (Infrastructure)
    publisher = KafkaPublisherAdapter(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    dataset = LocalDatasetAdapter(dataset_path=settings.DATASET_PATH)

    # Orkestrasyon (Application)
    runner = SimulatorRunner(
        dataset=dataset,
        publisher=publisher,
        playback_interval_sec=settings.PLAYBACK_INTERVAL_SEC,
        topic=settings.KAFKA_TOPIC,
    )

    # Graceful shutdown için sinyal yakalama
    loop = asyncio.get_running_loop()
    main_task = asyncio.create_task(runner.run())

    def handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Sinyal alındı: {sig.name}. Kapatılıyor...")
        main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await main_task
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Uygulama başarıyla sonlandı.")


if __name__ == "__main__":
    asyncio.run(main())
