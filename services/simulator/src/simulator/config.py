from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    12-Factor App prensiplerine uygun olarak tüm ayarları env üzerinden okur.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    DATASET_PATH: str = "/data/ims"
    PLAYBACK_INTERVAL_SEC: float = 1.0  # Varsayılan 1 saniyede 1 dosya/snapshot
    KAFKA_TOPIC: str = "sensor.vibration.raw"
    LOG_LEVEL: str = "INFO"

settings = Settings()
