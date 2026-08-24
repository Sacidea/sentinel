from datetime import UTC, datetime
from typing import Literal

from simulator.domain.chunking import create_chunks


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


def test_create_chunks_with_empty_samples() -> None:
    # Arrange
    samples: list[float] = []

    # Act
    chunks = create_chunks("bearing_2", "x", samples, datetime.now(UTC))

    # Assert
    assert len(chunks) == 0


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
