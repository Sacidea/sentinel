from datetime import UTC, datetime
from uuid import uuid4

import pytest
from contracts.events import AnomalyDetected
from notifier.application.anomaly_notification import AnomalyNotification
from notifier.domain.idempotency import SeenEventIds
from notifier.infrastructure.telegram_notifier import (
    LoggingNotifier,
    TelegramNotifier,
    format_alert_text,
)


class _CaptureEnqueue:
    def __init__(self) -> None:
        self.events: list[AnomalyDetected] = []

    def enqueue(self, event: AnomalyDetected) -> None:
        self.events.append(event)


class _FakeConsumer:
    def __init__(self) -> None:
        self.handler = None

    async def consume(self, handler: object) -> None:
        self.handler = handler


def _event() -> AnomalyDetected:
    return AnomalyDetected(
        event_id=uuid4(),
        occurred_at=datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC),
        machine_id="bearing_1",
        axis="x",
        metric="rms",
        value=0.3,
        z_score=6.0,
        score_kind="zscore",
        severity="warning",
        is_complete=True,
        detector="zscore",
    )


@pytest.mark.unit
def test_duplicate_event_is_not_enqueued() -> None:
    import asyncio

    enqueue = _CaptureEnqueue()
    seen = SeenEventIds()
    app = AnomalyNotification(_FakeConsumer(), enqueue, seen)  # type: ignore[arg-type]
    event = _event()

    asyncio.run(app.handle(event))
    asyncio.run(app.handle(event))

    assert len(enqueue.events) == 1


@pytest.mark.unit
def test_unconfigured_telegram_is_not_configured() -> None:
    notifier = TelegramNotifier("CHANGE_ME", "CHANGE_ME", fallback=LoggingNotifier())
    notifier.notify_sync(_event())
    assert notifier.configured() is False


@pytest.mark.unit
def test_non_numeric_chat_id_is_not_configured() -> None:
    notifier = TelegramNotifier("123:token", "not-a-chat-id", fallback=LoggingNotifier())
    assert notifier.configured() is False


@pytest.mark.unit
def test_alert_text_uses_z_score_for_layer1() -> None:
    text = format_alert_text(_event())
    assert "z_score=6.00" in text
    assert "if_score" not in text
    assert "unknown/bearing_1" in text


@pytest.mark.unit
def test_alert_text_uses_anomaly_score_for_isolation_forest() -> None:
    event = AnomalyDetected(
        event_id=uuid4(),
        occurred_at=datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC),
        machine_id="bearing_3",
        axis="x",
        metric="feature_vector",
        value=0.014,
        z_score=None,
        anomaly_score=0.014,
        score_kind="if_score",
        severity="warning",
        is_complete=True,
        detector="isolation_forest",
    )
    text = format_alert_text(event)
    assert "if_score=0.014" in text
    assert "z_score=" not in text


@pytest.mark.unit
def test_alert_text_v1_isolation_forest_reads_z_score() -> None:
    event = AnomalyDetected.model_validate(
        {
            "event_id": uuid4(),
            "occurred_at": datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC),
            "machine_id": "bearing_3",
            "axis": "x",
            "metric": "feature_vector",
            "value": 0.014,
            "z_score": 0.014,
            "severity": "warning",
            "is_complete": True,
            "detector": "isolation_forest",
            "schema_version": 1,
        }
    )
    text = format_alert_text(event)
    assert "if_score=0.014" in text


@pytest.mark.unit
def test_alert_text_uses_extent_kind() -> None:
    event = AnomalyDetected(
        event_id=uuid4(),
        occurred_at=datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC),
        machine_id="bearing_1",
        axis="x",
        metric="feature_vector",
        value=8.65,
        z_score=None,
        anomaly_score=8.65,
        score_kind="extent",
        severity="critical",
        is_complete=True,
        detector="isolation_forest",
    )
    text = format_alert_text(event)
    assert "extent=8.65" in text
    assert "z_score=" not in text
