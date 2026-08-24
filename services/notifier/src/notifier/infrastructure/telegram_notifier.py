import structlog
from contracts.events import AnomalyDetected

logger = structlog.get_logger(__name__)


class LoggingNotifier:
    """Walking Skeleton aşamasında Telegram yerine olayı yapılandırılmış loga yazar."""

    async def notify(self, event: AnomalyDetected) -> None:
        logger.warning(
            "Anomali bildirimi alındı.",
            event_id=str(event.event_id),
            machine_id=event.machine_id,
            metric=event.metric,
            severity=event.severity,
        )
