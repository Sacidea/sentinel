"""Katman 2 ML detektörleri — saf skorlama, I/O yok (bkz. planning/02, 15).

IsolationForest / PCA / River, Z-Score ile aynı soğuk başlangıcı kullanır: ilk N vektör
öğrenilir ve **sabitlenir**. Run-to-failure'da online güncelleme baseline'ı bozar
(boiling frog); River HalfSpaceTrees de warmup'tan sonra freeze edilir.

Girdi: RMS, kurtosis, crest factor, peak (FFT bantları henüz yok).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from stream_processor.domain.detectors import DetectionResult, DetectionStatus
from stream_processor.domain.features import SignalFeatures

_FEATURE_KEYS = ("rms", "kurtosis", "crest_factor", "peak")
_MIN_VARIANCE = 1e-12
# Uretim varsayilani (ADR-0008, Set 2 IF+zarf taramasi). PCA ayni nicelikte FP=3.
DEFAULT_ML_WARNING_QUANTILE = 0.995
DEFAULT_ML_CRITICAL_QUANTILE = 0.999
_SEVERITY_RANK = {
    DetectionStatus.CRITICAL: 2,
    DetectionStatus.WARNING: 1,
    DetectionStatus.NORMAL: 0,
    DetectionStatus.WARMING_UP: 0,
}


class _RiverScorer(Protocol):
    def learn_one(self, x: dict[str, float]) -> object: ...

    def score_one(self, x: dict[str, float]) -> float: ...


def feature_vector(features: SignalFeatures) -> NDArray[np.float64]:
    """Katman 2'nin izlediği dört zaman-alanı özelliği."""
    return np.array(
        [features.rms, features.kurtosis, features.crest_factor, features.peak],
        dtype=np.float64,
    )


def _as_point(vector: NDArray[np.float64]) -> dict[str, float]:
    return {key: float(vector[index]) for index, key in enumerate(_FEATURE_KEYS)}


def _validate_quantiles(warning_quantile: float, critical_quantile: float) -> None:
    if not 0.0 < warning_quantile <= 1.0 or not 0.0 < critical_quantile <= 1.0:
        raise ValueError("nicelik (0, 1] araliginda olmali.")
    if warning_quantile > critical_quantile:
        raise ValueError("warning niceligi critical niceliginden buyuk olamaz.")


def _healthy_thresholds(
    scores: NDArray[np.float64],
    *,
    warning_quantile: float,
    critical_quantile: float,
) -> tuple[float, float] | None:
    """Eğitim skorlarının niceliği. Çarpan/pay yok; eşik veriden türer.

    `score > warning` WARNING, `score > critical` CRITICAL. Eğitim noktalarının
    çoğu NORMAL kalır (nicelik < 1). N küçükken 0.99 max'a yaklaşır — bu yüzden
    birim testler sentetiktir; Set 2 taraması ayrıdır.
    """
    if scores.size < 2:
        return None
    warning = float(np.quantile(scores, warning_quantile))
    critical = float(np.quantile(scores, critical_quantile))
    return warning, critical


def _classify(score: float, warning: float, critical: float) -> DetectionStatus:
    if score > critical:
        return DetectionStatus.CRITICAL
    if score > warning:
        return DetectionStatus.WARNING
    return DetectionStatus.NORMAL


def _result(
    status: DetectionStatus,
    *,
    detector: str,
    metric: str,
    value: float,
    score: float,
    score_kind: str = "",
) -> DetectionResult:
    if status is DetectionStatus.WARMING_UP:
        return DetectionResult(status=status, scores=(), detector=detector)
    if status is DetectionStatus.NORMAL:
        return DetectionResult(status=status, scores=(), detector=detector)
    return DetectionResult(
        status=status,
        scores=(),
        triggered_metric=metric,
        triggered_value=value,
        triggered_z=score,
        detector=detector,
        score_kind=score_kind,
    )


@dataclass
class _WarmupTrack:
    vectors: list[NDArray[np.float64]] = field(default_factory=list)
    frozen: bool = False
    skipped: bool = False
    warning: float = 0.0
    critical: float = 0.0
    extent_warning: float = 0.0
    extent_critical: float = 0.0
    scaler: RobustScaler | None = None
    forest: IsolationForest | None = None
    pca: PCA | None = None
    eigenvalues: NDArray[np.float64] | None = None
    t2_warning: float = 0.0
    t2_critical: float = 0.0
    spe_warning: float = 0.0
    spe_critical: float = 0.0
    river_model: _RiverScorer | None = None


class IsolationForestDetector:
    """Etiketsiz çok değişkenli aykırı; warmup sonrası freeze (planning/02)."""

    def __init__(
        self,
        *,
        baseline_window: int,
        random_state: int = 42,
        warning_quantile: float = DEFAULT_ML_WARNING_QUANTILE,
        critical_quantile: float = DEFAULT_ML_CRITICAL_QUANTILE,
        use_extent: bool = True,
    ) -> None:
        if baseline_window < 2:
            raise ValueError("baseline_window en az 2 olmali.")
        _validate_quantiles(warning_quantile, critical_quantile)
        self._baseline_window = baseline_window
        self._random_state = random_state
        self._warning_quantile = warning_quantile
        self._critical_quantile = critical_quantile
        self._use_extent = use_extent
        self._tracks: dict[tuple[str, str], _WarmupTrack] = {}

    def observe(self, machine_id: str, axis: str, features: SignalFeatures) -> DetectionResult:
        track = self._tracks.setdefault((machine_id, axis), _WarmupTrack())
        vector = feature_vector(features)
        if not track.frozen:
            track.vectors.append(vector)
            if len(track.vectors) < self._baseline_window:
                return _result(
                    DetectionStatus.WARMING_UP,
                    detector="isolation_forest",
                    metric="",
                    value=0.0,
                    score=0.0,
                )
            self._freeze_forest(track)
            return _result(
                DetectionStatus.WARMING_UP,
                detector="isolation_forest",
                metric="",
                value=0.0,
                score=0.0,
            )
        if track.skipped or track.scaler is None or track.forest is None:
            return _result(
                DetectionStatus.NORMAL, detector="isolation_forest", metric="", value=0.0, score=0.0
            )
        scaled = track.scaler.transform(vector.reshape(1, -1))
        score = float(-track.forest.decision_function(scaled)[0])
        status = _classify(score, track.warning, track.critical)
        triggered = score
        score_kind = "if_score"
        if self._use_extent:
            extent = float(np.max(np.abs(scaled[0])))
            extent_status = _classify(extent, track.extent_warning, track.extent_critical)
            if _SEVERITY_RANK[extent_status] > _SEVERITY_RANK[status]:
                status = extent_status
                triggered = extent
                score_kind = "extent"
        return _result(
            status,
            detector="isolation_forest",
            metric="feature_vector",
            value=triggered,
            score=triggered,
            score_kind=score_kind,
        )

    def _freeze_forest(self, track: _WarmupTrack) -> None:
        matrix = np.vstack(track.vectors)
        scaler = RobustScaler()
        scaled = scaler.fit_transform(matrix)
        if float(np.max(np.std(scaled, axis=0))) <= _MIN_VARIANCE:
            track.frozen = True
            track.skipped = True
            return
        forest = IsolationForest(
            n_estimators=64,
            contamination=0.01,
            random_state=self._random_state,
        )
        forest.fit(scaled)
        scores = -forest.decision_function(scaled)
        kwargs = {
            "warning_quantile": self._warning_quantile,
            "critical_quantile": self._critical_quantile,
        }
        thresholds = _healthy_thresholds(scores, **kwargs)
        extent_thresholds = _healthy_thresholds(np.max(np.abs(scaled), axis=1), **kwargs)
        track.frozen = True
        if thresholds is None or (self._use_extent and extent_thresholds is None):
            track.skipped = True
            return
        track.scaler = scaler
        track.forest = forest
        track.warning, track.critical = thresholds
        if extent_thresholds is not None:
            track.extent_warning, track.extent_critical = extent_thresholds
        track.vectors.clear()


class PcaDetector:
    """PCA + Hotelling T² / SPE; warmup sonrası freeze (planning/02)."""

    def __init__(
        self,
        *,
        baseline_window: int,
        n_components: int = 2,
        warning_quantile: float = DEFAULT_ML_WARNING_QUANTILE,
        critical_quantile: float = DEFAULT_ML_CRITICAL_QUANTILE,
    ) -> None:
        if baseline_window < 3:
            raise ValueError("baseline_window PCA icin en az 3 olmali.")
        if n_components < 1:
            raise ValueError("n_components en az 1 olmali.")
        _validate_quantiles(warning_quantile, critical_quantile)
        self._baseline_window = baseline_window
        self._n_components = n_components
        self._warning_quantile = warning_quantile
        self._critical_quantile = critical_quantile
        self._tracks: dict[tuple[str, str], _WarmupTrack] = {}

    def observe(self, machine_id: str, axis: str, features: SignalFeatures) -> DetectionResult:
        track = self._tracks.setdefault((machine_id, axis), _WarmupTrack())
        vector = feature_vector(features)
        if not track.frozen:
            track.vectors.append(vector)
            if len(track.vectors) < self._baseline_window:
                return _result(
                    DetectionStatus.WARMING_UP, detector="pca", metric="", value=0.0, score=0.0
                )
            self._freeze_pca(track)
            return _result(
                DetectionStatus.WARMING_UP, detector="pca", metric="", value=0.0, score=0.0
            )
        if track.skipped or track.scaler is None or track.pca is None or track.eigenvalues is None:
            return _result(DetectionStatus.NORMAL, detector="pca", metric="", value=0.0, score=0.0)
        scaled = track.scaler.transform(vector.reshape(1, -1))
        components = track.pca.transform(scaled)
        reconstructed = track.pca.inverse_transform(components)
        t2 = float(np.sum((components[0] ** 2) / track.eigenvalues))
        spe = float(np.sum((scaled[0] - reconstructed[0]) ** 2))
        t2_status = _classify(t2, track.t2_warning, track.t2_critical)
        spe_status = _classify(spe, track.spe_warning, track.spe_critical)
        if _SEVERITY_RANK[spe_status] > _SEVERITY_RANK[t2_status]:
            return _result(
                spe_status,
                detector="pca",
                metric="spe",
                value=spe,
                score=spe,
                score_kind="pca_spe",
            )
        return _result(
            t2_status,
            detector="pca",
            metric="hotelling_t2",
            value=t2,
            score=t2,
            score_kind="pca_t2",
        )

    def _freeze_pca(self, track: _WarmupTrack) -> None:
        matrix = np.vstack(track.vectors)
        scaler = RobustScaler()
        scaled = scaler.fit_transform(matrix)
        n_components = min(self._n_components, scaled.shape[0] - 1, scaled.shape[1])
        if n_components < 1 or float(np.max(np.std(scaled, axis=0))) <= _MIN_VARIANCE:
            track.frozen = True
            track.skipped = True
            return
        pca = PCA(n_components=n_components, svd_solver="full")
        components = pca.fit_transform(scaled)
        eigenvalues = np.maximum(pca.explained_variance_, _MIN_VARIANCE)
        reconstructed = pca.inverse_transform(components)
        t2 = np.sum((components**2) / eigenvalues, axis=1)
        spe = np.sum((scaled - reconstructed) ** 2, axis=1)
        kwargs = {
            "warning_quantile": self._warning_quantile,
            "critical_quantile": self._critical_quantile,
        }
        t2_thr = _healthy_thresholds(t2, **kwargs)
        spe_thr = _healthy_thresholds(spe, **kwargs)
        track.frozen = True
        if t2_thr is None and spe_thr is None:
            track.skipped = True
            return
        track.scaler = scaler
        track.pca = pca
        track.eigenvalues = eigenvalues
        if t2_thr is not None:
            track.t2_warning, track.t2_critical = t2_thr
        else:
            track.t2_warning, track.t2_critical = float("inf"), float("inf")
        if spe_thr is not None:
            track.spe_warning, track.spe_critical = spe_thr
        else:
            track.spe_warning, track.spe_critical = float("inf"), float("inf")
        track.vectors.clear()


class RiverHalfSpaceTreesDetector:
    """Online HalfSpaceTrees; warmup boyunca öğrenir, sonra freeze (boiling frog)."""

    def __init__(
        self,
        *,
        baseline_window: int,
        seed: int = 42,
        warning_quantile: float = DEFAULT_ML_WARNING_QUANTILE,
        critical_quantile: float = DEFAULT_ML_CRITICAL_QUANTILE,
    ) -> None:
        if baseline_window < 2:
            raise ValueError("baseline_window en az 2 olmali.")
        _validate_quantiles(warning_quantile, critical_quantile)
        self._baseline_window = baseline_window
        self._seed = seed
        self._warning_quantile = warning_quantile
        self._critical_quantile = critical_quantile
        self._tracks: dict[tuple[str, str], _WarmupTrack] = {}

    def observe(self, machine_id: str, axis: str, features: SignalFeatures) -> DetectionResult:
        from river.anomaly import HalfSpaceTrees

        track = self._tracks.setdefault((machine_id, axis), _WarmupTrack())
        vector = feature_vector(features)
        point = _as_point(vector)
        if not track.frozen:
            if track.river_model is None:
                track.river_model = HalfSpaceTrees(
                    n_trees=8,
                    height=6,
                    window_size=self._baseline_window,
                    seed=self._seed,
                )
            model = track.river_model
            model.learn_one(point)
            track.vectors.append(vector)
            if len(track.vectors) < self._baseline_window:
                return _result(
                    DetectionStatus.WARMING_UP,
                    detector="river",
                    metric="",
                    value=0.0,
                    score=0.0,
                )
            scores = np.array(
                [float(model.score_one(_as_point(row))) for row in track.vectors],
                dtype=np.float64,
            )
            thresholds = _healthy_thresholds(
                scores,
                warning_quantile=self._warning_quantile,
                critical_quantile=self._critical_quantile,
            )
            track.frozen = True
            track.vectors.clear()
            if thresholds is None:
                track.skipped = True
                return _result(
                    DetectionStatus.WARMING_UP, detector="river", metric="", value=0.0, score=0.0
                )
            track.warning, track.critical = thresholds
            return _result(
                DetectionStatus.WARMING_UP, detector="river", metric="", value=0.0, score=0.0
            )
        if track.skipped or track.river_model is None:
            return _result(
                DetectionStatus.NORMAL, detector="river", metric="", value=0.0, score=0.0
            )
        score = float(track.river_model.score_one(point))
        status = _classify(score, track.warning, track.critical)
        return _result(
            status,
            detector="river",
            metric="half_space_trees",
            value=score,
            score=score,
            score_kind="river",
        )
