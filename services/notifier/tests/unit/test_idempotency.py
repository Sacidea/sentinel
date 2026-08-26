"""Görülen event_id — çift Telegram yok (planning/07)."""

from uuid import uuid4

import pytest
from notifier.domain.idempotency import SeenEventIds


@pytest.mark.unit
def test_first_event_is_new() -> None:
    seen = SeenEventIds(max_size=4)
    event_id = uuid4()
    assert seen.already_seen(event_id) is False
    assert seen.already_seen(event_id) is True


@pytest.mark.unit
def test_evicts_oldest_when_full() -> None:
    seen = SeenEventIds(max_size=2)
    first = uuid4()
    second = uuid4()
    third = uuid4()
    seen.already_seen(first)
    seen.already_seen(second)
    seen.already_seen(third)
    assert first not in seen
    assert second in seen
    assert third in seen


@pytest.mark.unit
def test_invalid_max_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_size"):
        SeenEventIds(max_size=0)
