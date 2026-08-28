"""Katman 2 ML — SENTETIK vektorler. Set 2 dosyasi OKUNMAZ (bkz. ims_set2_ml_calibration)."""

import numpy as np
import pytest
from stream_processor.domain.detectors import DetectionStatus
from stream_processor.domain.features import SignalFeatures
from stream_processor.domain.ml_detectors import (
    IsolationForestDetector,
    PcaDetector,
    RiverHalfSpaceTreesDetector,
    _healthy_thresholds,
    feature_vector,
)


def _features(
    rms: float, kurtosis: float = 3.2, crest: float = 3.0, peak: float = 0.22
) -> SignalFeatures:
    return SignalFeatures(rms=rms, kurtosis=kurtosis, crest_factor=crest, peak=peak)


def _healthy(index: int) -> SignalFeatures:
    """Sentetik saglikli; ozellikler bagimsiz jitter (1D cizgi degil)."""
    return _features(
        0.08 + (index % 7) * 1e-4,
        3.2 + (index % 5) * 1e-3,
        3.0 + (index % 11) * 1e-3,
        0.22 + (index % 3) * 1e-4,
    )


@pytest.mark.unit
def test_feature_vector_order_is_rms_kurtosis_crest_peak() -> None:
    vector = feature_vector(_features(1.0, 2.0, 3.0, 4.0))
    assert list(vector) == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.unit
def test_healthy_thresholds_are_quantiles_of_train_scores() -> None:
    scores = np.arange(100, dtype=np.float64)
    warning, critical = _healthy_thresholds(scores, warning_quantile=0.90, critical_quantile=0.99)
    assert warning == pytest.approx(float(np.quantile(scores, 0.90)))
    assert critical == pytest.approx(float(np.quantile(scores, 0.99)))


@pytest.mark.unit
def test_isolation_forest_warms_up_then_flags_extreme() -> None:
    detector = IsolationForestDetector(baseline_window=24, random_state=0)
    for index in range(23):
        result = detector.observe("bearing_1", "x", _healthy(index))
        assert result.status is DetectionStatus.WARMING_UP
        assert result.detector == "isolation_forest"

    frozen = detector.observe("bearing_1", "x", _healthy(23))
    assert frozen.status is DetectionStatus.WARMING_UP

    spiked = detector.observe("bearing_1", "x", _features(8.0, 25.0, 20.0, 12.0))
    assert spiked.status in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    assert spiked.detector == "isolation_forest"
    assert spiked.triggered_metric == "feature_vector"
    assert spiked.score_kind in {"if_score", "extent"}


@pytest.mark.unit
def test_pca_flags_extreme_on_hotelling_or_spe() -> None:
    detector = PcaDetector(baseline_window=24, n_components=2)
    for index in range(23):
        assert (
            detector.observe("bearing_1", "x", _healthy(index)).status is DetectionStatus.WARMING_UP
        )

    frozen = detector.observe("bearing_1", "x", _healthy(23))
    assert frozen.status is DetectionStatus.WARMING_UP

    spiked = detector.observe("bearing_1", "x", _features(8.0, 25.0, 20.0, 12.0))
    assert spiked.status in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    assert spiked.detector == "pca"
    assert spiked.triggered_metric in {"hotelling_t2", "spe"}
    assert spiked.score_kind in {"pca_t2", "pca_spe"}


@pytest.mark.unit
def test_river_freezes_after_warmup_and_scores() -> None:
    detector = RiverHalfSpaceTreesDetector(baseline_window=24, seed=0)
    for index in range(23):
        assert (
            detector.observe("bearing_1", "x", _healthy(index)).status is DetectionStatus.WARMING_UP
        )

    frozen = detector.observe("bearing_1", "x", _healthy(23))
    assert frozen.status is DetectionStatus.WARMING_UP
    assert frozen.detector == "river"

    spiked = detector.observe("bearing_1", "x", _features(8.0, 25.0, 20.0, 12.0))
    assert spiked.detector == "river"
    assert spiked.status in (
        DetectionStatus.NORMAL,
        DetectionStatus.WARNING,
        DetectionStatus.CRITICAL,
    )
    if spiked.status in (DetectionStatus.WARNING, DetectionStatus.CRITICAL):
        assert spiked.score_kind == "river"


@pytest.mark.unit
def test_ml_series_are_independent_per_machine() -> None:
    detector = IsolationForestDetector(baseline_window=8, random_state=0)
    for index in range(8):
        detector.observe("bearing_1", "x", _healthy(index))

    other = detector.observe("bearing_2", "x", _features(8.0, 25.0, 20.0, 12.0))
    assert other.status is DetectionStatus.WARMING_UP


@pytest.mark.unit
def test_invalid_ml_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="baseline"):
        IsolationForestDetector(baseline_window=1)
    with pytest.raises(ValueError, match="baseline"):
        PcaDetector(baseline_window=2)
    with pytest.raises(ValueError, match="nicelik"):
        IsolationForestDetector(baseline_window=8, warning_quantile=1.5)
    with pytest.raises(ValueError, match="niceligi"):
        PcaDetector(baseline_window=8, warning_quantile=0.99, critical_quantile=0.90)
