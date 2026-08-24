"""Sentinel servisleri arasinda paylasilan event semalari.

Bu semalar tek kaynak; tum servisler buradan import eder (AGENTS.md kurali).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    schema_version: int = 1


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
    schema_version: int = 1


class AnomalyDetected(BaseModel):
    """Tespit edilen bir anomali olayi."""

    event_id: UUID
    occurred_at: datetime
    machine_id: str
    axis: str | None = None
    metric: str  # ornek: "kurtosis", "rms"
    value: float
    z_score: float
    severity: Literal["warning", "critical"]
    is_complete: bool
    detector: str  # "zscore" / "isolation_forest" / "pca"
    schema_version: int = 1
