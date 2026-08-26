import structlog
from contracts.events import AnomalyDetected
from pybreaker import CircuitBreaker, CircuitBreakerError

logger = structlog.get_logger(__name__)


class LoggingNotifier:
    """Telegram yokken veya token ayarlanmamışken yapılandırılmış loga yazar."""

    async def notify(self, event: AnomalyDetected) -> None:
        self.notify_sync(event)

    def notify_sync(self, event: AnomalyDetected) -> None:
        logger.warning(
            "Anomali bildirimi alındı.",
            event_id=str(event.event_id),
            machine_id=event.machine_id,
            metric=event.metric,
            severity=event.severity,
            detector=event.detector,
        )


class TelegramNotifier:
    """Telegram Bot API; pybreaker ile kaskad çökme önlenir (07)."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        breaker: CircuitBreaker | None = None,
        fallback: LoggingNotifier | None = None,
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._breaker = breaker or CircuitBreaker(fail_max=5, reset_timeout=30)
        self._fallback = fallback or LoggingNotifier()

    def configured(self) -> bool:
        if self._token in ("", "CHANGE_ME") or self._chat_id in ("", "CHANGE_ME"):
            return False
        # Bot API chat_id sayısal (kişi/grup); kullanıcı adı veya invite kodu 400 verir.
        return self._chat_id.lstrip("-").isdigit()

    async def notify(self, event: AnomalyDetected) -> None:
        self.notify_sync(event)

    def notify_sync(self, event: AnomalyDetected) -> None:
        if not self.configured():
            self._fallback.notify_sync(event)
            return
        try:
            self._breaker.call(self._send, event)
        except CircuitBreakerError:
            logger.error("Telegram circuit acik; bildirim loga dustu.")
            self._fallback.notify_sync(event)

    def _send(self, event: AnomalyDetected) -> None:
        import httpx

        text = (
            f"Sentinel {event.severity.upper()} {event.detector}\n"
            f"{event.machine_id} {event.metric}={event.value:.4f} "
            f"score={event.z_score:.2f}"
        )
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        response = httpx.post(
            url,
            json={"chat_id": self._chat_id, "text": text},
            timeout=10.0,
        )
        if response.status_code >= 500:
            response.raise_for_status()
        if response.status_code >= 400:
            logger.error(
                "Telegram kalici hata; retry yok.",
                status_code=response.status_code,
            )
            return
        response.raise_for_status()
