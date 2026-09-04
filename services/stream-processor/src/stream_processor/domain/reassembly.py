"""Chunk'lı snapshot yeniden birleştirmenin saf mantığı (ADR-0004).

Yalnız kurallar burada: chunk seti tamam mı, duplicate var mı, kısmi birleştirme nasıl yapılır.
Tampon ve timeout application katmanında yaşar (bkz. planning/03, 07).
"""

from __future__ import annotations

from enum import Enum

from contracts.events import RawVibrationWindow


class ChunkOutcome(Enum):
    """Bir chunk'ın tampona eklenme sonucu."""

    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    INCONSISTENT = "inconsistent"


class SnapshotAssembly:
    """Tek bir snapshot'ın chunk'larını biriktirir; zamanı ve I/O'yu bilmez."""

    def __init__(self, first_chunk: RawVibrationWindow) -> None:
        self.snapshot_id = first_chunk.snapshot_id
        self.machine_id = first_chunk.machine_id
        self.axis = first_chunk.axis
        self.dataset = first_chunk.dataset
        self.total_chunks = first_chunk.total_chunks
        self.occurred_at = first_chunk.occurred_at
        self.source_timestamp = first_chunk.source_timestamp
        self._samples_by_index: dict[int, list[float]] = {}
        self.add(first_chunk)

    def add(self, chunk: RawVibrationWindow) -> ChunkOutcome:
        """Chunk'ı ekler. Tutarsız chunk tamponu kirletmez, duplicate sessizce yok sayılır."""
        if not self._belongs_here(chunk):
            return ChunkOutcome.INCONSISTENT
        if chunk.chunk_index in self._samples_by_index:
            return ChunkOutcome.DUPLICATE
        self._samples_by_index[chunk.chunk_index] = list(chunk.samples)
        return ChunkOutcome.ACCEPTED

    @property
    def chunks_received(self) -> int:
        return len(self._samples_by_index)

    @property
    def is_complete(self) -> bool:
        return self.chunks_received == self.total_chunks

    def is_processable(self, min_chunks_ratio: float) -> bool:
        """Eşiğe eşit olan da işlenir (4/8 = %50 dahil); altı DLQ'ya gider."""
        return self.chunks_received >= self.total_chunks * min_chunks_ratio

    def merged_samples(self) -> list[float]:
        """Geliş sırası değil, chunk_index sırası belirleyici; eksik chunk'lar atlanır."""
        merged: list[float] = []
        for index in sorted(self._samples_by_index):
            merged.extend(self._samples_by_index[index])
        return merged

    def _belongs_here(self, chunk: RawVibrationWindow) -> bool:
        return (
            chunk.snapshot_id == self.snapshot_id
            and chunk.machine_id == self.machine_id
            and chunk.axis == self.axis
            and chunk.dataset == self.dataset
            and chunk.total_chunks == self.total_chunks
            and chunk.chunk_index < self.total_chunks
        )
