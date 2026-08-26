"""Z-Score anomali tespiti (Katman 1) — saf mantık, I/O yok (bkz. planning/15).

Baseline ilk N snapshot'tan öğrenilip **sabitlenir**. Kayan pencere kullanılmaz: run-to-failure
veride baseline bozulan veriyle kayarsa yavaş arıza görünmez (boiling frog).

Yalnız RMS ve kurtosis skorlanır. Crest/peak çıkarılır ama burada yok sayılır.
Z ham haliyle işaretlidir; eşik yumuşatılmış |z| üzerindendir. Alarm, MA penceresi dolmadan
çalmaz — tek gürültülü örnek Telegram'ı yakmasın diye.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Literal

from stream_processor.domain.features import SignalFeatures

SCORED_METRICS: tuple[Literal["rms", "kurtosis"], ...] = ("rms", "kurtosis")
DETECTOR_NAME = "zscore"
# IMS Set 2 kalibrasyonu (ADR-0006, ml/notebooks/ims_set2_zscore_calibration.md):
# NASA README: ariza testi sonunda bearing 1 dis bilezik; lead time son dosyaya gore.
# 3.0 etiketlenmemis bearing_2'de erken alarm; 5.0/8.0 etiketsiz FP=0,
# bearing_1 lead ~74.5 saat (index 536 -> 983, 10 dk aralik). Yalniz Set 2.
DEFAULT_ZSCORE_WARNING = 5.0
DEFAULT_ZSCORE_CRITICAL = 8.0
# Popülasyon std'si sayısal olarak sıfırsa metrik atlanır; epsilon ile şişirme yok.
_MIN_BASELINE_STD = 1e-12


class DetectionStatus(Enum):
    """Bir snapshot'ın Z-Score değerlendirmesi."""

    WARMING_UP = "warming_up"
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


Severity = Literal["warning", "critical"]
MetricName = Literal["rms", "kurtosis"]


@dataclass(frozen=True)
class MetricScore:
    """Tek bir özelliğin ham ve yumuşatılmış Z-Score'u."""

    metric: MetricName
    value: float
    z_score: float
    smoothed_z: float
    severity: Severity | None


@dataclass(frozen=True)
class DetectionResult:
    """`observe` çıktısı; event üretimi application katmanına aittir."""

    status: DetectionStatus
    scores: tuple[MetricScore, ...]
    triggered_metric: str | None = None
    triggered_value: float | None = None
    triggered_z: float | None = None
    detector: str = DETECTOR_NAME


@dataclass(frozen=True)
class BaselineSnapshot:
    """Donmuş bir `(machine_id, axis, metric)` baseline'ı; uygulama kalıcı yazar."""

    machine_id: str
    axis: str
    metric: MetricName
    mean: float
    std: float


@dataclass
class _MetricTrack:
    warmup: list[float]
    recent_z: deque[float]
    mean: float | None = None
    std: float | None = None
    skipped: bool = False
    frozen: bool = False


class ZScoreDetector:
    """`(machine_id, axis)` başına sabit baseline ve hareketli ortalama tutar."""

    def __init__(
        self,
        *,
        baseline_window: int,
        ma_window: int,
        warning_threshold: float,
        critical_threshold: float,
    ) -> None:
        if baseline_window < 2:
            raise ValueError("baseline_window en az 2 olmali; std icin varyans gerekir.")
        if ma_window < 1:
            raise ValueError("ma_window en az 1 olmali.")
        if warning_threshold <= 0.0 or critical_threshold <= 0.0:
            raise ValueError("Z-Score esikleri pozitif olmali.")
        if warning_threshold >= critical_threshold:
            raise ValueError("warning esigi critical esiginden kucuk olmali.")

        self._baseline_window = baseline_window
        self._ma_window = ma_window
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._series: dict[tuple[str, str], dict[MetricName, _MetricTrack]] = {}
        self._pending_frozen: list[BaselineSnapshot] = []

    def observe(self, machine_id: str, axis: str, features: SignalFeatures) -> DetectionResult:
        """Bir snapshot'ın özelliklerini baseline'a ekler veya skorlar."""
        values = _finite_metric_values(features)
        tracks = self._series.setdefault((machine_id, axis), self._new_tracks())
        still_warming = not all(track.frozen for track in tracks.values())

        for metric, value in values.items():
            track = tracks[metric]
            if track.frozen:
                continue
            track.warmup.append(value)
            if len(track.warmup) >= self._baseline_window:
                self._freeze_track(machine_id, axis, metric, track)

        if still_warming:
            return DetectionResult(status=DetectionStatus.WARMING_UP, scores=())

        scored: list[MetricScore] = []
        for metric in SCORED_METRICS:
            score = self._score_metric(tracks[metric], metric, values[metric])
            if score is not None:
                scored.append(score)
        scores = tuple(scored)
        triggered = _pick_triggered(scores)
        if triggered is None:
            return DetectionResult(status=DetectionStatus.NORMAL, scores=scores)
        status = (
            DetectionStatus.CRITICAL
            if triggered.severity == "critical"
            else DetectionStatus.WARNING
        )
        return DetectionResult(
            status=status,
            scores=scores,
            triggered_metric=triggered.metric,
            triggered_value=triggered.value,
            triggered_z=triggered.smoothed_z,
        )

    def _new_tracks(self) -> dict[MetricName, _MetricTrack]:
        return {
            metric: _MetricTrack(warmup=[], recent_z=deque(maxlen=self._ma_window))
            for metric in SCORED_METRICS
        }

    def seed_baseline(self, snapshot: BaselineSnapshot) -> None:
        """Kayıtlı baseline'ı yükler; warmup atlanır (restart'ta boiling frog olmasın)."""
        tracks = self._series.setdefault((snapshot.machine_id, snapshot.axis), self._new_tracks())
        track = tracks[snapshot.metric]
        track.mean = snapshot.mean
        track.std = snapshot.std
        track.skipped = snapshot.std <= _MIN_BASELINE_STD
        track.frozen = True
        track.warmup.clear()

    def drain_frozen(self) -> tuple[BaselineSnapshot, ...]:
        """Son observe'da yeni donan baseline'lar; bir kez okunur."""
        frozen = tuple(self._pending_frozen)
        self._pending_frozen.clear()
        return frozen

    def _freeze_track(
        self,
        machine_id: str,
        axis: str,
        metric: MetricName,
        track: _MetricTrack,
    ) -> None:
        mean = sum(track.warmup) / len(track.warmup)
        variance = sum((sample - mean) ** 2 for sample in track.warmup) / len(track.warmup)
        std = variance**0.5
        track.mean = mean
        track.std = std
        track.skipped = std <= _MIN_BASELINE_STD
        track.frozen = True
        self._pending_frozen.append(
            BaselineSnapshot(
                machine_id=machine_id,
                axis=axis,
                metric=metric,
                mean=mean,
                std=std,
            )
        )

    def _score_metric(
        self,
        track: _MetricTrack,
        metric: MetricName,
        value: float,
    ) -> MetricScore | None:
        if track.skipped or track.mean is None or track.std is None:
            return None
        z_score = (value - track.mean) / track.std
        track.recent_z.append(z_score)
        smoothed_z = sum(track.recent_z) / len(track.recent_z)
        severity: Severity | None = None
        if len(track.recent_z) >= self._ma_window:
            severity = _classify_severity(
                abs(smoothed_z),
                warning_threshold=self._warning_threshold,
                critical_threshold=self._critical_threshold,
            )
        return MetricScore(
            metric=metric,
            value=value,
            z_score=z_score,
            smoothed_z=smoothed_z,
            severity=severity,
        )


def _finite_metric_values(features: SignalFeatures) -> dict[MetricName, float]:
    values: dict[MetricName, float] = {"rms": features.rms, "kurtosis": features.kurtosis}
    if not all(isfinite(value) for value in values.values()):
        raise ValueError("Ozellikler sonlu olmali; NaN/inf skorlanmaz.")
    return values


def _classify_severity(
    abs_smoothed_z: float,
    *,
    warning_threshold: float,
    critical_threshold: float,
) -> Severity | None:
    if abs_smoothed_z >= critical_threshold:
        return "critical"
    if abs_smoothed_z >= warning_threshold:
        return "warning"
    return None


def _pick_triggered(scores: tuple[MetricScore, ...]) -> MetricScore | None:
    """Aynı anda iki metrik tetiklerse tek sonuç: en yüksek severity, sonra |z|."""
    rank = {"critical": 2, "warning": 1}
    candidates = [score for score in scores if score.severity is not None]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda score: (rank[score.severity or "warning"], abs(score.smoothed_z)),
    )
