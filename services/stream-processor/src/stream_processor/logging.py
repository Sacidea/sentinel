import logging

import structlog


def setup_logging(log_level: str) -> None:
    """Servis loglarını JSON biçiminde ve yapılandırılmış olarak üretir."""
    logging.basicConfig(level=log_level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
