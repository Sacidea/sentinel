"""Reassembly tamponu: state ve timeout (bkz. planning/03, 07; ADR-0004, ADR-0005).

Saf kurallar `domain/reassembly.py`'de. Burada snapshot'ların tamponlanması, zaman aşımı,
bellek koruması ve kapanış nedeninin belirlenmesi var. Saat enjekte edilir; bu modül de
I/O yapmaz — kapanan snapshot'ları döndürür, onlarla ne yapılacağına çağıran karar verir.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from contracts.events import RawVibrationWindow

from stream_processor.domain.reassembly import ChunkOutcome, SnapshotAssembly


def reassembly_timeout_sec(*, playback_interval_sec: float, floor: float, factor: float) -> float:
    """ADR-0005: `max(FLOOR, PLAYBACK_INTERVAL_SEC * FACTOR)`; sıfır/negatif olamaz."""
    return max(floor, playback_interval_sec * factor)


class ClosedReason(Enum):
    """Bir snapshot'ın tampondan çıkış nedeni."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    DISCARDED = "discarded"


class ChunkDisposition(Enum):
    """Gelen chunk'a ne olduğu."""

    BUFFERED = "buffered"
    DUPLICATE = "duplicate"
    INCONSISTENT = "inconsistent"
    LATE = "late"


@dataclass(frozen=True)
class ClosedSnapshot:
    assembly: SnapshotAssembly
    reason: ClosedReason


@dataclass(frozen=True)
class AddResult:
    disposition: ChunkDisposition
    closed: list[ClosedSnapshot] = field(default_factory=list)


@dataclass
class _Pending:
    assembly: SnapshotAssembly
    deadline: float


class SnapshotBuffer:
    """`snapshot_id` → yarım snapshot tamponu; zaman aşımını ve bellek sınırını uygular."""

    def __init__(
        self,
        *,
        timeout_sec: float,
        min_chunks_ratio: float,
        max_pending: int,
        clock: Callable[[], float] = time.monotonic,
        closed_memory: int = 512,
    ) -> None:
        self._timeout_sec = timeout_sec
        self._min_chunks_ratio = min_chunks_ratio
        self._max_pending = max_pending
        self._clock = clock
        self._closed_memory = closed_memory
        # Ekleme sırası korunur; "en eski" bu sıradan bulunur.
        self._pending: OrderedDict[UUID, _Pending] = OrderedDict()
        # Kapanmış snapshot'lar geç gelen chunk'ı tanımak için sınırlı sayıda hatırlanır.
        self._recently_closed: OrderedDict[UUID, None] = OrderedDict()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def add(self, chunk: RawVibrationWindow) -> AddResult:
        """Chunk'ı tamponlar; bu sırada süresi geçmiş snapshot'ları da kapatır."""
        closed = self._close_expired()

        if chunk.snapshot_id in self._recently_closed:
            return AddResult(ChunkDisposition.LATE, closed)

        pending = self._pending.get(chunk.snapshot_id)
        if pending is None:
            if len(self._pending) >= self._max_pending:
                closed.extend(self._close_oldest())
            self._pending[chunk.snapshot_id] = _Pending(
                assembly=SnapshotAssembly(chunk),
                deadline=self._clock() + self._timeout_sec,
            )
            disposition = ChunkDisposition.BUFFERED
        else:
            disposition = _DISPOSITION_BY_OUTCOME[pending.assembly.add(chunk)]

        completed = self._pending.get(chunk.snapshot_id)
        if completed is not None and completed.assembly.is_complete:
            closed.append(self._close(chunk.snapshot_id, ClosedReason.COMPLETE))

        return AddResult(disposition, closed)

    def sweep(self) -> list[ClosedSnapshot]:
        """Mesaj akmadığında da zaman aşımının işlemesi için periyodik çağrılır."""
        return self._close_expired()

    def flush(self) -> list[ClosedSnapshot]:
        """Graceful shutdown: tamponda kalan yarım snapshot'lar sessizce kaybolmaz."""
        return [
            self._close(snapshot_id, self._reason_for(snapshot_id))
            for snapshot_id in list(self._pending)
        ]

    def _close_expired(self) -> list[ClosedSnapshot]:
        now = self._clock()
        expired = [
            snapshot_id for snapshot_id, pending in self._pending.items() if pending.deadline <= now
        ]
        return [self._close(snapshot_id, self._reason_for(snapshot_id)) for snapshot_id in expired]

    def _close_oldest(self) -> list[ClosedSnapshot]:
        oldest_id = next(iter(self._pending))
        return [self._close(oldest_id, self._reason_for(oldest_id))]

    def _reason_for(self, snapshot_id: UUID) -> ClosedReason:
        assembly = self._pending[snapshot_id].assembly
        if assembly.is_complete:
            return ClosedReason.COMPLETE
        if assembly.is_processable(self._min_chunks_ratio):
            return ClosedReason.PARTIAL
        return ClosedReason.DISCARDED

    def _close(self, snapshot_id: UUID, reason: ClosedReason) -> ClosedSnapshot:
        pending = self._pending.pop(snapshot_id)
        self._remember_closed(snapshot_id)
        return ClosedSnapshot(assembly=pending.assembly, reason=reason)

    def _remember_closed(self, snapshot_id: UUID) -> None:
        self._recently_closed[snapshot_id] = None
        while len(self._recently_closed) > self._closed_memory:
            self._recently_closed.popitem(last=False)


_DISPOSITION_BY_OUTCOME = {
    ChunkOutcome.ACCEPTED: ChunkDisposition.BUFFERED,
    ChunkOutcome.DUPLICATE: ChunkDisposition.DUPLICATE,
    ChunkOutcome.INCONSISTENT: ChunkDisposition.INCONSISTENT,
}
