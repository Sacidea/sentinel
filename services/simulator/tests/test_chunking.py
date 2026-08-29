from datetime import UTC, datetime
from typing import Literal

import pytest
from simulator.domain.chunking import create_chunks


@pytest.mark.unit
def test_create_chunks_with_valid_samples() -> None:
    # Arrange
    samples = [float(i) for i in range(20480)]
    source_timestamp = datetime.now(UTC)
    axis: Literal["x", "y"] = "x"

    # Act
    chunks = create_chunks("bearing_1", axis, samples, source_timestamp, total_chunks=8)

    # Assert
    assert len(chunks) == 8

    # Tüm chunk'lar aynı snapshot_id'ye sahip olmalı
    snapshot_id = chunks[0].snapshot_id
    assert all(c.snapshot_id == snapshot_id for c in chunks)
    assert all(c.dataset == "unknown" for c in chunks)

    # Sıra numaraları 0'dan 7'ye kadar ardışık olmalı
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.total_chunks == 8
        assert chunk.axis == axis
        assert chunk.source_timestamp == source_timestamp

    # İlk chunk 0-2559 arası verileri içermeli (20480 / 8 = 2560)
    assert len(chunks[0].samples) == 2560
    assert chunks[0].samples[0] == 0.0
    assert chunks[0].samples[-1] == 2559.0


@pytest.mark.unit
def test_create_chunks_with_empty_samples() -> None:
    # Arrange
    samples: list[float] = []

    # Act
    chunks = create_chunks("bearing_2", "x", samples, datetime.now(UTC))

    # Assert
    assert len(chunks) == 0


@pytest.mark.unit
def test_create_chunks_indivisible_total() -> None:
    # Arrange
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]

    # Act
    # 5 sample, 2 chunk'a bölünmek isteniyor. (5 // 2 = 2)
    # İlk chunk 2 eleman, son chunk geri kalanını (3 eleman) almalı
    chunks = create_chunks("bearing_3", "y", samples, datetime.now(UTC), total_chunks=2)

    # Assert
    assert len(chunks) == 2
    assert chunks[0].samples == [1.0, 2.0]
    assert chunks[1].samples == [3.0, 4.0, 5.0]


@pytest.mark.unit
def test_x_and_y_of_same_bearing_get_distinct_snapshot_ids() -> None:
    """Reassembly tamponu snapshot_id anahtarlı; aynı id x/y chunk'larını karıştırır."""
    stamp = datetime.now(UTC)
    x_chunks = create_chunks("bearing_3", "x", [1.0] * 8, stamp, total_chunks=2)
    y_chunks = create_chunks("bearing_3", "y", [2.0] * 8, stamp, total_chunks=2)

    assert x_chunks[0].snapshot_id == x_chunks[1].snapshot_id
    assert y_chunks[0].snapshot_id == y_chunks[1].snapshot_id
    assert x_chunks[0].snapshot_id != y_chunks[0].snapshot_id
    assert x_chunks[0].axis == "x"
    assert y_chunks[0].axis == "y"


@pytest.mark.unit
def test_create_chunks_copies_dataset() -> None:
    chunks = create_chunks(
        "bearing_1", "x", [1.0] * 4, datetime.now(UTC), total_chunks=2, dataset="set1"
    )
    assert all(chunk.dataset == "set1" for chunk in chunks)
    assert all(chunk.schema_version == 2 for chunk in chunks)


@pytest.mark.unit
def test_infer_dataset_name_from_path() -> None:
    from simulator.config import infer_dataset_name

    assert infer_dataset_name("/data/ims_set1/1st_test") == "set1"
    assert infer_dataset_name("/data/ims") == "set2"
    assert infer_dataset_name("/data/ims/2nd_test") == "set2"
    assert infer_dataset_name("/tmp/custom") is None
