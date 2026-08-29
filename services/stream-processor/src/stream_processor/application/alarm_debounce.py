"""Alarm debounce: kayıt her tespitte durur, bildirim spam olmaz (bkz. planning/15)."""

from datetime import datetime


class AlarmDebounce:
    """Aynı seri+severity için cooldown dolmadan ikinci bildirimi keser."""

    def __init__(self, *, cooldown_sec: float) -> None:
        if cooldown_sec < 0.0:
            raise ValueError("cooldown negatif olamaz.")
        self._cooldown_sec = cooldown_sec
        # (dataset, machine_id, axis, metric, severity, detector) → son bildirim anı
        self._last_notified: dict[tuple[str, str, str, str, str, str], datetime] = {}

    def should_notify(
        self,
        *,
        machine_id: str,
        axis: str,
        metric: str,
        severity: str,
        at: datetime,
        detector: str = "zscore",
        dataset: str = "unknown",
    ) -> bool:
        """İlk alarm ve cooldown sonrası True; aradaki tekrarlar False."""
        if self._cooldown_sec == 0.0:
            return True
        key = (dataset, machine_id, axis, metric, severity, detector)
        last = self._last_notified.get(key)
        if last is not None and (at - last).total_seconds() < self._cooldown_sec:
            return False
        self._last_notified[key] = at
        return True
