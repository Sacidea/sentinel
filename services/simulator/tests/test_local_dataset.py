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
    assert all(row[1] == "x" for row in snapshot)


@pytest.mark.unit
def test_four_column_file_stays_single_axis(tmp_path: Path) -> None:
    (tmp_path / "2004.02.12.10.32.39").write_text("0.1 0.2 0.3 0.4\n")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert [(row[0], row[1]) for row in snapshot] == [
        ("bearing_1", "x"),
        ("bearing_2", "x"),
        ("bearing_3", "x"),
        ("bearing_4", "x"),
    ]


@pytest.mark.unit
def test_eight_column_file_emits_xy_per_bearing(tmp_path: Path) -> None:
    (tmp_path / "2003.10.22.12.06.24").write_text(
        "0.11 0.12 0.21 0.22 0.31 0.32 0.41 0.42\n1.11 1.12 1.21 1.22 1.31 1.32 1.41 1.42\n"
    )

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert [(row[0], row[1]) for row in snapshot] == [
        ("bearing_1", "x"),
        ("bearing_1", "y"),
        ("bearing_2", "x"),
        ("bearing_2", "y"),
        ("bearing_3", "x"),
        ("bearing_3", "y"),
        ("bearing_4", "x"),
        ("bearing_4", "y"),
    ]
    by_key = {(row[0], row[1]): row[2] for row in snapshot}
    assert by_key[("bearing_1", "x")] == [0.11, 1.11]
    assert by_key[("bearing_1", "y")] == [0.12, 1.12]
    assert by_key[("bearing_3", "x")] == [0.31, 1.31]
    assert by_key[("bearing_3", "y")] == [0.32, 1.32]
    assert by_key[("bearing_4", "y")] == [0.42, 1.42]


@pytest.mark.unit
def test_eight_column_file_is_not_read_as_four(tmp_path: Path) -> None:
    """Eski >=4 parser y eksenini atardı; 8 sütun tam eşlenmeli."""
    (tmp_path / "2003.10.22.12.06.24").write_text("1 2 3 4 5 6 7 8\n")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert len(snapshot) == 8
    assert snapshot[1][2] == [2.0]


@pytest.mark.unit
def test_bad_line_is_skipped_in_eight_column_file(tmp_path: Path) -> None:
    (tmp_path / "2003.10.22.12.06.24").write_text(
        "0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8\n"
        "not-a-float 0 0 0 0 0 0 0\n"
        "1.1 1.2 1.3 1.4\n"
        "9.1 9.2 9.3 9.4 9.5 9.6 9.7 9.8\n"
    )

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert snapshot[0][2] == [0.1, 9.1]
    assert snapshot[7][2] == [0.8, 9.8]


@pytest.mark.unit
def test_layout_is_detected_after_short_garbage_line(tmp_path: Path) -> None:
    (tmp_path / "2004.02.12.10.32.39").write_text("1 2 3\n0.1 0.2 0.3 0.4\n")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))

    assert snapshot is not None
    assert len(snapshot) == 4
    assert snapshot[0][2] == [0.1]


@pytest.mark.unit
def test_each_channel_gets_its_own_snapshot_id(tmp_path: Path) -> None:
    from simulator.domain.chunking import create_chunks

    (tmp_path / "2003.10.22.12.06.24").write_text("1 2 3 4 5 6 7 8\n")
    snapshot = _first_snapshot(LocalDatasetAdapter(str(tmp_path)))
    assert snapshot is not None

    snapshot_ids = []
    for machine_id, axis, samples, stamp in snapshot:
        chunks = create_chunks(machine_id, axis, samples, stamp, total_chunks=2)
        snapshot_ids.append(chunks[0].snapshot_id)
        assert all(chunk.snapshot_id == chunks[0].snapshot_id for chunk in chunks)
        assert all(chunk.axis == axis for chunk in chunks)

    assert len(snapshot) == 8
    assert len(set(snapshot_ids)) == 8
    b3 = [(row[0], row[1]) for row in snapshot if row[0] == "bearing_3"]
    assert b3 == [("bearing_3", "x"), ("bearing_3", "y")]
    b3_ids = [
        sid
        for (machine_id, axis, _, _), sid in zip(snapshot, snapshot_ids, strict=True)
        if machine_id == "bearing_3"
    ]
    assert b3_ids[0] != b3_ids[1]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _first_data_dir(*candidates: Path) -> Path | None:
    for folder in candidates:
        if folder.is_dir() and any(path.is_file() for path in folder.iterdir()):
            return folder
    return None


@pytest.mark.unit
def test_real_set2_file_is_four_x_streams() -> None:
    data_dir = _first_data_dir(
        _repo_root() / "data" / "ims" / "2nd_test",
        _repo_root() / "data" / "ims",
    )
    if data_dir is None:
        pytest.skip("IMS Set 2 dosyası yok")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(data_dir)))
    assert snapshot is not None
    assert len(snapshot) == 4
    assert [(row[0], row[1]) for row in snapshot] == [
        ("bearing_1", "x"),
        ("bearing_2", "x"),
        ("bearing_3", "x"),
        ("bearing_4", "x"),
    ]
    assert all(len(row[2]) > 0 for row in snapshot)


@pytest.mark.unit
def test_real_set1_file_is_eight_xy_streams() -> None:
    data_dir = _first_data_dir(_repo_root() / "data" / "ims_set1" / "1st_test")
    if data_dir is None:
        pytest.skip("IMS Set 1 dosyası yok")

    snapshot = _first_snapshot(LocalDatasetAdapter(str(data_dir)))
    assert snapshot is not None
    assert len(snapshot) == 8
    assert [(row[0], row[1]) for row in snapshot] == [
        ("bearing_1", "x"),
        ("bearing_1", "y"),
        ("bearing_2", "x"),
        ("bearing_2", "y"),
        ("bearing_3", "x"),
        ("bearing_3", "y"),
        ("bearing_4", "x"),
        ("bearing_4", "y"),
    ]
    b3x = next(row[2] for row in snapshot if row[0] == "bearing_3" and row[1] == "x")
    b3y = next(row[2] for row in snapshot if row[0] == "bearing_3" and row[1] == "y")
    assert b3x != b3y
    assert len(b3x) == 20480
    assert len(b3y) == 20480
