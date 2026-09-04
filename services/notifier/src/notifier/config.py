from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_ANOMALY: str = "anomaly.detected"
    KAFKA_TOPIC_DLQ: str = "anomaly.dlq"
    KAFKA_CONSUMER_GROUP: str = "notifier-alerts"
    REDIS_URL: str = "redis://localhost:6379/0"
    TELEGRAM_BOT_TOKEN: str = "CHANGE_ME"
    TELEGRAM_CHAT_ID: str = "CHANGE_ME"
    LOG_LEVEL: str = "INFO"


settings = Settings()
