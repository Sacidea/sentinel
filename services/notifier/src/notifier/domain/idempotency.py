"""Görülen event_id kümesi — Kafka at-least-once çift bildirimi önler (07)."""

from __future__ import annotations

from collections import OrderedDict
from uuid import UUID


class SeenEventIds:
    """Tek instance notifier için kısa süreli idempotency bellegi."""

    def __init__(self, max_size: int = 10_000) -> None:
        if max_size < 1:
            raise ValueError("max_size en az 1 olmali.")
        self._max_size = max_size
        self._ids: OrderedDict[UUID, None] = OrderedDict()

    def __contains__(self, event_id: object) -> bool:
        return isinstance(event_id, UUID) and event_id in self._ids

    def already_seen(self, event_id: UUID) -> bool:
        """True ise ikinci kez; False ise ilk kez (kaydeder)."""
        if event_id in self._ids:
            return True
        self._ids[event_id] = None
        if len(self._ids) > self._max_size:
            self._ids.popitem(last=False)
        return False
