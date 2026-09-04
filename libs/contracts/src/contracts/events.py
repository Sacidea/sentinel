"""Sentinel servisleri arasinda paylasilan event semalari.

Bu semalar tek kaynak; tum servisler buradan import eder (AGENTS.md kurali).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ScoreKind = Literal["zscore", "if_score", "extent", "pca_t2", "pca_spe", "river"]
UNKNOWN_DATASET = "unknown"
RAW_WINDOW_SCHEMA_VERSION = 2
FEATURES_SCHEMA_VERSION = 2
ANOMALY_SCHEMA_VERSION = 3


class RawVibrationWindow(BaseModel):
    """Ham titresim snapshot'inin bir chunk'i (ADR-0004: chunk'li snapshot)."""

    snapshot_id: UUID
    chunk_index: int = Field(ge=0)
    total_chunks: int = Field(gt=0)
    machine_id: str  # PARTITION ANAHTARI (snapshot_id degil)
    axis: Literal["x", "y"]
    samples: list[float]
    occurred_at: datetime  # yayin ani (canli zaman ekseni)
    source_timestamp: datetime  # orijinal dosya zaman damgasi
    dataset: str = UNKNOWN_DATASET
    schema_version: int = RAW_WINDOW_SCHEMA_VERSION


class VibrationFeatures(BaseModel):
    """Bir snapshot'tan cikarilan sinyal ozellikleri."""

    snapshot_id: UUID
    machine_id: str
    axis: Literal["x", "y"]
    occurred_at: datetime
    rms: float
    kurtosis: float
    crest_factor: float
    peak: float
    is_complete: bool
    chunks_received: int
    fft_band_energy: dict[str, float] = Field(default_factory=dict)
    dataset: str = UNKNOWN_DATASET
    schema_version: int = FEATURES_SCHEMA_VERSION


class AnomalyDetected(BaseModel):
    """Tespit edilen bir anomali olayi.

    ADR-0009: `z_score` yalniz Katman 1. Katman 2 `anomaly_score` + `score_kind`.
    ADR-0014: `dataset` Set 1/Set 2 serilerini ayirir.
    """

    event_id: UUID
    occurred_at: datetime
    machine_id: str
    axis: str | None = None
    dataset: str = UNKNOWN_DATASET
    metric: str  # ornek: "kurtosis", "rms", "feature_vector"
    value: float
    z_score: float | None = None
    anomaly_score: float | None = None
    score_kind: ScoreKind | None = None
    severity: Literal["warning", "critical"]
    is_complete: bool
    detector: str  # "zscore" / "isolation_forest" / "pca" / "river"
    schema_version: int = ANOMALY_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def _v1_fills_optional_score_fields(cls, data: object) -> object:
        """v1 Kafka: `anomaly_score`/`score_kind` yok; skor `z_score` icindeydi."""
        if not isinstance(data, dict):
            return data
        if data.get("score_kind") is not None:
            return data
        kind = _score_kind_from_v1(data)
        if kind is None:
            return data
        patched = dict(data)
        patched["score_kind"] = kind
        return patched

    def reported_score(self) -> float | None:
        """Bildirim/pano: v2 `anomaly_score`, v1 ve Katman 1 `z_score`."""
        if self.score_kind == "zscore" or self.score_kind is None:
            if self.anomaly_score is not None:
                return self.anomaly_score
            return self.z_score
        if self.anomaly_score is not None:
            return self.anomaly_score
        return self.z_score


def _score_kind_from_v1(data: dict[str, object]) -> ScoreKind | None:
    detector = data.get("detector")
    metric = data.get("metric")
    if detector == "zscore":
        return "zscore"
    if detector == "isolation_forest":
        return "if_score"
    if detector == "pca":
        return "pca_spe" if metric == "spe" else "pca_t2"
    if detector == "river":
        return "river"
    if data.get("z_score") is not None and data.get("anomaly_score") is None:
        return "zscore"
    return None
