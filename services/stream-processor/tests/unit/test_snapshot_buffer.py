"""Reassembly tamponu ve timeout davranışı — senaryolar 05-testing-observability.md (T7, T10-T15).

Saat enjekte edildiği için testler gerçek zaman beklemez.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest
from contracts.events import RawVibrationWindow
from stream_processor.application.snapshot_buffer import (
    ChunkDisposition,
    ClosedReason,
    SnapshotBuffer,
    reassembly_timeout_sec,
)

MOMENT = datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _chunk(
    index: int,
    *,
    snapshot_id: UUID,
    total_chunks: int = 8,
    machine_id: str = "bearing_1",
    axis: Literal["x", "y"] = "x",
) -> RawVibrationWindow:
    return RawVibrationWindow(
        snapshot_id=snapshot_id,
        chunk_index=index,
        total_chunks=total_chunks,
        machine_id=machine_id,
        axis=axis,
        samples=[float(index)],
        occurred_at=MOMENT,
        source_timestamp=MOMENT,
    )


def _buffer(
    clock: FakeClock,
    *,
    timeout_sec: float = 10.0,
    max_pending: int = 100,
) -> SnapshotBuffer:
    return SnapshotBuffer(
        timeout_sec=timeout_sec,
        min_chunks_ratio=0.5,
        max_pending=max_pending,
        clock=clock,
    )


# --- Timeout hesabı (T14, T15) ---


@pytest.mark.unit
def test_t14_tiny_interval_falls_back_to_floor() -> None:
    # Çok hızlı playback'te timeout sıfıra inmez, tabana oturur.
    assert reassembly_timeout_sec(playback_interval_sec=0.1, floor=0.5, factor=1.5) == 0.5


@pytest.mark.unit
def test_t15_large_interval_grows_with_formula() -> None:
    assert reassembly_timeout_sec(playback_interval_sec=600.0, floor=0.5, factor=1.5) == 900.0


@pytest.mark.unit
def test_timeout_is_never_zero_or_negative() -> None:
    assert reassembly_timeout_sec(playback_interval_sec=0.0, floor=0.5, factor=1.5) > 0


# --- Tampon davranışı ---


@pytest.mark.unit
def test_t7_empty_buffer_closes_nothing() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)

    clock.advance(1000)

    assert buffer.sweep() == []
    assert buffer.flush() == []
    assert buffer.pending_count == 0


@pytest.mark.unit
def test_complete_snapshot_closes_immediately() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)
    snapshot_id = uuid4()

    closed: list[ClosedReason] = []
    for index in range(8):
        result = buffer.add(_chunk(index, snapshot_id=snapshot_id))
        closed.extend(item.reason for item in result.closed)

    assert closed == [ClosedReason.COMPLETE]
    assert buffer.pending_count == 0


@pytest.mark.unit
def test_expired_snapshot_above_threshold_is_partial() -> None:
    clock = FakeClock()
    buffer = _buffer(clock, timeout_sec=10.0)
    snapshot_id = uuid4()
    for index in range(6):
        buffer.add(_chunk(index, snapshot_id=snapshot_id))

    clock.advance(10.0)
    closed = buffer.sweep()

    assert [item.reason for item in closed] == [ClosedReason.PARTIAL]
    assert closed[0].assembly.chunks_received == 6
    assert closed[0].assembly.is_complete is False


@pytest.mark.unit
def test_expired_snapshot_below_threshold_is_discarded() -> None:
    clock = FakeClock()
    buffer = _buffer(clock, timeout_sec=10.0)
    snapshot_id = uuid4()
    for index in range(3):
        buffer.add(_chunk(index, snapshot_id=snapshot_id))

    clock.advance(11.0)
    closed = buffer.sweep()

    assert [item.reason for item in closed] == [ClosedReason.DISCARDED]
    assert closed[0].assembly.chunks_received == 3


@pytest.mark.unit
def test_snapshot_does_not_expire_before_deadline() -> None:
    clock = FakeClock()
    buffer = _buffer(clock, timeout_sec=10.0)
    buffer.add(_chunk(0, snapshot_id=uuid4()))

    clock.advance(9.9)

    assert buffer.sweep() == []
    assert buffer.pending_count == 1


@pytest.mark.unit
def test_t10_late_chunk_does_not_reopen_closed_snapshot() -> None:
    clock = FakeClock()
    buffer = _buffer(clock, timeout_sec=10.0)
    snapshot_id = uuid4()
    for index in range(8):
        buffer.add(_chunk(index, snapshot_id=snapshot_id))

    result = buffer.add(_chunk(3, snapshot_id=snapshot_id))

    assert result.disposition is ChunkDisposition.LATE
    assert result.closed == []
    assert buffer.pending_count == 0


@pytest.mark.unit
def test_t11_multiple_snapshots_are_buffered_independently() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)
    first, second = uuid4(), uuid4()

    buffer.add(_chunk(0, snapshot_id=first))
    buffer.add(_chunk(1, snapshot_id=second, machine_id="bearing_2"))

    assert buffer.pending_count == 2
    closed = buffer.flush()
    assert {item.assembly.snapshot_id for item in closed} == {first, second}


@pytest.mark.unit
def test_t12_max_pending_forces_oldest_snapshot_closed() -> None:
    clock = FakeClock()
    buffer = _buffer(clock, max_pending=2)
    oldest, middle, newest = uuid4(), uuid4(), uuid4()

    buffer.add(_chunk(0, snapshot_id=oldest))
    buffer.add(_chunk(0, snapshot_id=middle))
    result = buffer.add(_chunk(0, snapshot_id=newest))

    # En eski yarım snapshot zorla kapatıldı, yeni gelen kabul edildi.
    assert [item.assembly.snapshot_id for item in result.closed] == [oldest]
    assert result.disposition is ChunkDisposition.BUFFERED
    assert buffer.pending_count == 2


@pytest.mark.unit
def test_t13_flush_closes_pending_snapshots_on_shutdown() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)
    complete_enough, too_few = uuid4(), uuid4()
    for index in range(4):
        buffer.add(_chunk(index, snapshot_id=complete_enough))
    buffer.add(_chunk(0, snapshot_id=too_few, machine_id="bearing_2"))

    closed = buffer.flush()

    reasons = {item.assembly.snapshot_id: item.reason for item in closed}
    assert reasons[complete_enough] is ClosedReason.PARTIAL
    assert reasons[too_few] is ClosedReason.DISCARDED
    assert buffer.pending_count == 0


@pytest.mark.unit
def test_duplicate_chunk_is_reported_without_closing() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)
    snapshot_id = uuid4()
    buffer.add(_chunk(0, snapshot_id=snapshot_id))

    result = buffer.add(_chunk(0, snapshot_id=snapshot_id))

    assert result.disposition is ChunkDisposition.DUPLICATE
    assert buffer.pending_count == 1


@pytest.mark.unit
def test_inconsistent_chunk_is_reported_for_dlq() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)
    snapshot_id = uuid4()
    buffer.add(_chunk(0, snapshot_id=snapshot_id, total_chunks=8))

    result = buffer.add(_chunk(1, snapshot_id=snapshot_id, total_chunks=4))

    assert result.disposition is ChunkDisposition.INCONSISTENT
    assert buffer.pending_count == 1


@pytest.mark.unit
def test_same_bearing_x_and_y_complete_when_snapshot_ids_differ() -> None:
    clock = FakeClock()
    buffer = _buffer(clock)
    id_x = uuid4()
    id_y = uuid4()

    closed_x: list[str] = []
    closed_y: list[str] = []
    for index in range(8):
        result_x = buffer.add(_chunk(index, snapshot_id=id_x, machine_id="bearing_3", axis="x"))
        result_y = buffer.add(_chunk(index, snapshot_id=id_y, machine_id="bearing_3", axis="y"))
        closed_x.extend(item.assembly.axis for item in result_x.closed)
        closed_y.extend(item.assembly.axis for item in result_y.closed)

    assert closed_x == ["x"]
    assert closed_y == ["y"]
    assert buffer.pending_count == 0
