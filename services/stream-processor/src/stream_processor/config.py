from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Stream processor çalışma ayarlarını ortam değişkenlerinden okur."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_RAW: str = "sensor.vibration.raw"
    KAFKA_TOPIC_DLQ: str = "anomaly.dlq"
    KAFKA_CONSUMER_GROUP: str = "stream-processor-features"
    TIMESCALE_DSN: str = ""
    LOG_LEVEL: str = "INFO"


settings = Settings()
