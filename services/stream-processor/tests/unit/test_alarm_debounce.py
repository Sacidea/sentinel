"""Bildirim debounce — kayıt her tespitte durur, Telegram spam olmaz (bkz. 15)."""

from datetime import UTC, datetime, timedelta

import pytest
from stream_processor.application.alarm_debounce import AlarmDebounce

T0 = datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC)


@pytest.mark.unit
def test_first_alarm_is_notified() -> None:
    debounce = AlarmDebounce(cooldown_sec=60.0)

    assert debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="critical", at=T0
    )


@pytest.mark.unit
def test_same_key_inside_cooldown_is_suppressed() -> None:
    debounce = AlarmDebounce(cooldown_sec=60.0)
    debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="critical", at=T0
    )

    assert not debounce.should_notify(
        machine_id="bearing_1",
        axis="x",
        metric="rms",
        severity="critical",
        at=T0 + timedelta(seconds=59),
    )


@pytest.mark.unit
def test_same_key_after_cooldown_is_notified_again() -> None:
    debounce = AlarmDebounce(cooldown_sec=60.0)
    debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="critical", at=T0
    )

    assert debounce.should_notify(
        machine_id="bearing_1",
        axis="x",
        metric="rms",
        severity="critical",
        at=T0 + timedelta(seconds=60),
    )


@pytest.mark.unit
def test_different_severity_or_axis_is_independent() -> None:
    debounce = AlarmDebounce(cooldown_sec=60.0)
    debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="warning", at=T0
    )

    assert debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="critical", at=T0
    )
    assert debounce.should_notify(
        machine_id="bearing_1", axis="y", metric="rms", severity="warning", at=T0
    )


@pytest.mark.unit
def test_different_detector_is_independent() -> None:
    debounce = AlarmDebounce(cooldown_sec=60.0)
    debounce.should_notify(
        machine_id="bearing_1",
        axis="x",
        metric="rms",
        severity="critical",
        at=T0,
        detector="zscore",
    )

    assert debounce.should_notify(
        machine_id="bearing_1",
        axis="x",
        metric="rms",
        severity="critical",
        at=T0,
        detector="isolation_forest",
    )


@pytest.mark.unit
def test_zero_cooldown_never_suppresses() -> None:
    debounce = AlarmDebounce(cooldown_sec=0.0)

    assert debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="critical", at=T0
    )
    assert debounce.should_notify(
        machine_id="bearing_1", axis="x", metric="rms", severity="critical", at=T0
    )


@pytest.mark.unit
def test_negative_cooldown_is_rejected() -> None:
    with pytest.raises(ValueError, match="cooldown"):
        AlarmDebounce(cooldown_sec=-1.0)
