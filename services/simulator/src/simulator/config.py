from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def infer_dataset_name(dataset_path: str) -> str | None:
    """Yol yaprağından set1/set2; belirsizse None (sentetik/özel klasör)."""
    normalized = dataset_path.replace("\\", "/").rstrip("/").lower()
    if "1st_test" in normalized or "ims_set1" in normalized:
        return "set1"
    if "2nd_test" in normalized or normalized.endswith("/ims"):
        return "set2"
    return None


class Settings(BaseSettings):
    """
    12-Factor App prensiplerine uygun olarak tüm ayarları env üzerinden okur.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    DATASET_PATH: str = "/data/ims"
    DATASET_NAME: str = ""  # boşsa DATASET_PATH'ten türetilir (set1/set2)
    PLAYBACK_INTERVAL_SEC: float = 1.0  # Varsayılan 1 saniyede 1 dosya/snapshot
    KAFKA_TOPIC: str = "sensor.vibration.raw"
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def _dataset_matches_path(self) -> "Settings":
        inferred = infer_dataset_name(self.DATASET_PATH)
        if not self.DATASET_NAME:
            self.DATASET_NAME = inferred or "set2"
            return self
        if inferred is not None and inferred != self.DATASET_NAME:
            raise ValueError(
                f"DATASET_NAME={self.DATASET_NAME!r} ile DATASET_PATH={self.DATASET_PATH!r} "
                f"uyumsuz (beklenen {inferred})."
            )
        return self


settings = Settings()
