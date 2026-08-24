"""Reassembly saf mantığı — senaryolar docs/planning/05-testing-observability.md (T1-T9).

Zaman/timeout davranışı application katmanına ait; burada yalnız saf kurallar test edilir.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest
from contracts.events import RawVibrationWindow
from stream_processor.domain.reassembly import ChunkOutcome, SnapshotAssembly

MOMENT = datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC)


def _chunk(
    index: int,
    *,
    snapshot_id: UUID,
    total_chunks: int = 8,
    machine_id: str = "bearing_1",
    axis: Literal["x", "y"] = "x",
    samples: list[float] | None = None,
) -> RawVibrationWindow:
    return RawVibrationWindow(
        snapshot_id=snapshot_id,
        chunk_index=index,
        total_chunks=total_chunks,
        machine_id=machine_id,
        axis=axis,
        samples=[float(index)] if samples is None else samples,
        occurred_at=MOMENT,
        source_timestamp=MOMENT,
    )


@pytest.mark.unit
def test_t1_all_chunks_in_order_completes_snapshot() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id))

    for index in range(1, 8):
        assert assembly.add(_chunk(index, snapshot_id=snapshot_id)) is ChunkOutcome.ACCEPTED

    assert assembly.is_complete is True
    assert assembly.chunks_received == 8


@pytest.mark.unit
def test_t2_shuffled_chunks_complete_and_merge_in_index_order() -> None:
    snapshot_id = uuid4()
    arrival_order = [3, 0, 7, 1, 5, 2, 6, 4]
    assembly = SnapshotAssembly(_chunk(arrival_order[0], snapshot_id=snapshot_id))

    for index in arrival_order[1:]:
        assert assembly.add(_chunk(index, snapshot_id=snapshot_id)) is ChunkOutcome.ACCEPTED

    assert assembly.is_complete is True
    # Geliş sırası değil, chunk_index sırası belirleyici.
    assert assembly.merged_samples() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


@pytest.mark.unit
def test_t3_six_of_eight_is_partial_but_processable() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id))
    for index in range(1, 6):
        assembly.add(_chunk(index, snapshot_id=snapshot_id))

    assert assembly.is_complete is False
    assert assembly.chunks_received == 6
    assert assembly.is_processable(0.5) is True


@pytest.mark.unit
def test_t4_exactly_half_is_processable() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id))
    for index in range(1, 4):
        assembly.add(_chunk(index, snapshot_id=snapshot_id))

    assert assembly.chunks_received == 4
    # Eşiğe eşit olan dahil edilir (4/8 = %50).
    assert assembly.is_processable(0.5) is True


@pytest.mark.unit
def test_t5_below_threshold_is_not_processable() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id))
    for index in (1, 2):
        assembly.add(_chunk(index, snapshot_id=snapshot_id))

    assert assembly.chunks_received == 3
    assert assembly.is_processable(0.5) is False


@pytest.mark.unit
def test_t6_single_chunk_is_not_processable() -> None:
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=uuid4()))

    assert assembly.chunks_received == 1
    assert assembly.is_complete is False
    assert assembly.is_processable(0.5) is False


@pytest.mark.unit
def test_t8_duplicate_chunk_is_ignored_idempotently() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id, samples=[1.0, 2.0]))

    outcome = assembly.add(_chunk(0, snapshot_id=snapshot_id, samples=[9.0, 9.0]))

    assert outcome is ChunkOutcome.DUPLICATE
    assert assembly.chunks_received == 1
    # İkinci kopya veriyi de değiştirmez.
    assert assembly.merged_samples() == [1.0, 2.0]


@pytest.mark.unit
def test_t9_inconsistent_total_chunks_is_rejected() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id, total_chunks=8))

    outcome = assembly.add(_chunk(1, snapshot_id=snapshot_id, total_chunks=4))

    assert outcome is ChunkOutcome.INCONSISTENT
    assert assembly.chunks_received == 1


@pytest.mark.unit
def test_chunk_from_another_snapshot_is_rejected() -> None:
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=uuid4()))

    outcome = assembly.add(_chunk(1, snapshot_id=uuid4()))

    assert outcome is ChunkOutcome.INCONSISTENT
    assert assembly.chunks_received == 1


@pytest.mark.unit
def test_chunk_from_another_machine_is_rejected() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id, machine_id="bearing_1"))

    outcome = assembly.add(_chunk(1, snapshot_id=snapshot_id, machine_id="bearing_2"))

    assert outcome is ChunkOutcome.INCONSISTENT
    assert assembly.chunks_received == 1


@pytest.mark.unit
def test_chunk_index_beyond_total_is_rejected() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id, total_chunks=8))

    outcome = assembly.add(_chunk(8, snapshot_id=snapshot_id, total_chunks=8))

    assert outcome is ChunkOutcome.INCONSISTENT
    assert assembly.chunks_received == 1


@pytest.mark.unit
def test_partial_merge_skips_missing_chunks() -> None:
    snapshot_id = uuid4()
    assembly = SnapshotAssembly(_chunk(0, snapshot_id=snapshot_id, samples=[0.0]))
    assembly.add(_chunk(3, snapshot_id=snapshot_id, samples=[3.0]))
    assembly.add(_chunk(1, snapshot_id=snapshot_id, samples=[1.0]))

    assert assembly.merged_samples() == [0.0, 1.0, 3.0]
