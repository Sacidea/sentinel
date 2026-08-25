from pydantic_settings import BaseSettings, SettingsConfigDict

from stream_processor.domain.detectors import (
    DEFAULT_ZSCORE_CRITICAL,
    DEFAULT_ZSCORE_WARNING,
)


class Settings(BaseSettings):
    """Stream processor çalışma ayarlarını ortam değişkenlerinden okur."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_RAW: str = "sensor.vibration.raw"
    KAFKA_TOPIC_ANOMALY: str = "anomaly.detected"
    KAFKA_TOPIC_DLQ: str = "anomaly.dlq"
    KAFKA_CONSUMER_GROUP: str = "stream-processor-features"
    TIMESCALE_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    PLAYBACK_INTERVAL_SEC: float = 1.0
    REASSEMBLY_MIN_CHUNKS_RATIO: float = 0.5
    REASSEMBLY_TIMEOUT_FLOOR: float = 0.5
    REASSEMBLY_TIMEOUT_FACTOR: float = 1.5
    MAX_PENDING_SNAPSHOTS: int = 100

    BASELINE_WINDOW: int = 200
    MA_WINDOW: int = 5
    ANOMALY_ZSCORE_WARNING: float = DEFAULT_ZSCORE_WARNING
    ANOMALY_ZSCORE_CRITICAL: float = DEFAULT_ZSCORE_CRITICAL
    ALARM_COOLDOWN: float = 60.0


settings = Settings()
