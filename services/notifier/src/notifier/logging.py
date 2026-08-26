import logging

import structlog


def setup_logging(log_level: str) -> None:
    logging.basicConfig(level=log_level, format="%(message)s")
    # httpx INFO URL'de bot token taşır; Telegram isteğini loglama.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
