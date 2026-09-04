from typing import Protocol

from contracts.events import AnomalyDetected


class AnomalyEnqueue(Protocol):
    """Bildirim işini kuyruğa bırakır (Celery); application broker'a bağlanmaz."""

    def enqueue(self, event: AnomalyDetected) -> None:
        """At-least-once teslim; idempotency çağıranda."""
        ...
