import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from contracts.events import RawVibrationWindow
from stream_processor.application.raw_window_ingestion import RawWindowIngestion
from stream_processor.ports.consumer import RawWindowHandler


class FakeConsumer:
    def __init__(self, window: RawVibrationWindow) -> None:
        self._window = window

    async def consume(self, handler: RawWindowHandler) -> None:
        await handler(self._window)


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[RawVibrationWindow] = []

    async def save(self, window: RawVibrationWindow) -> None:
        self.saved.append(window)


@pytest.mark.unit
def test_ingestion_persists_valid_window() -> None:
    window = RawVibrationWindow(
        snapshot_id=uuid4(),
        chunk_index=0,
        total_chunks=8,
        machine_id="bearing_1",
        axis="x",
        samples=[0.1, 0.2],
        occurred_at=datetime.now(UTC),
        source_timestamp=datetime.now(UTC),
    )
    repository = FakeRepository()

    asyncio.run(RawWindowIngestion(FakeConsumer(window), repository).run())

    assert repository.saved == [window]
