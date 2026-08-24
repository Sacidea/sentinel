from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_ANOMALY: str = "anomaly.detected"
    KAFKA_CONSUMER_GROUP: str = "notifier-alerts"
    LOG_LEVEL: str = "INFO"


settings = Settings()
