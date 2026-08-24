import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest
from simulator.infrastructure.local_dataset import LocalDatasetAdapter

Snapshot = list[tuple[str, Literal["x", "y"], list[float], datetime]]


def _first_snapshot(adapter: LocalDatasetAdapter) -> Snapshot | None:
    async def read_one() -> Snapshot | None:
        async for snapshot in adapter.stream_snapshots():
            return snapshot
        return None

    return asyncio.run(read_one())


@pytest.mark.unit
def test_missing_directory_falls_back_to_synthetic(tmp_path: Path) -> None:
    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path / "yok")))

    assert snapshot is not None
    assert len(snapshot) == 4


@pytest.mark.unit
def test_empty_directory_falls_back_to_synthetic(tmp_path: Path) -> None:
    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert len(snapshot) == 4
    assert len(snapshot[0][2]) == 20480


@pytest.mark.unit
def test_directory_with_files_is_read_from_disk(tmp_path: Path) -> None:
    (tmp_path / "2003.10.22.12.06.24").write_text("0.1 0.2 0.3 0.4\n0.5 0.6 0.7 0.8\n")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert [row[0] for row in snapshot] == [
        "bearing_1",
        "bearing_2",
        "bearing_3",
        "bearing_4",
    ]
    assert snapshot[0][2] == [0.1, 0.5]
    assert snapshot[0][3] == datetime(2003, 10, 22, 12, 6, 24, tzinfo=UTC)


@pytest.mark.unit
def test_source_timestamp_is_timezone_aware(tmp_path: Path) -> None:
    (tmp_path / "2004.02.12.10.32.39").write_text("0.1 0.2 0.3 0.4\n")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert snapshot[0][3].tzinfo is not None
