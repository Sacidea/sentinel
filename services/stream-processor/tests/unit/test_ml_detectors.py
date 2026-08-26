"""Katman 2 ML detektörleri — IsolationForest / PCA / River (planning/02, 15)."""

import pytest
from stream_processor.domain.detectors import DetectionStatus
from stream_processor.domain.features import SignalFeatures
from stream_processor.domain.ml_detectors import (
    IsolationForestDetector,
    PcaDetector,
    RiverHalfSpaceTreesDetector,
    feature_vector,
)


def _features(
    rms: float, kurtosis: float = 3.2, crest: float = 3.0, peak: float = 0.22
) -> SignalFeatures:
    return SignalFeatures(rms=rms, kurtosis=kurtosis, crest_factor=crest, peak=peak)


def _healthy(index: int) -> SignalFeatures:
    jitter = index * 1e-5
    return _features(0.08 + jitter, 3.2 + jitter, 3.0 + jitter, 0.22 + jitter)


@pytest.mark.unit
def test_feature_vector_order_is_rms_kurtosis_crest_peak() -> None:
    vector = feature_vector(_features(1.0, 2.0, 3.0, 4.0))
    assert list(vector) == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.unit
def test_isolation_forest_warms_up_then_flags_extreme() -> None:
    detector = IsolationForestDetector(baseline_window=24, random_state=0)
    for index in range(23):
        result = detector.observe("bearing_1", "x", _healthy(index))
        assert result.status is DetectionStatus.WARMING_UP
        assert result.detector == "isolation_forest"

    frozen = detector.observe("bearing_1", "x", _healthy(23))
    assert frozen.status is DetectionStatus.WARMING_UP

    ready = detector.observe("bearing_1", "x", _healthy(24))
    assert ready.status is DetectionStatus.NORMAL

    spiked = detector.observe("bearing_1", "x", _features(8.0, 25.0, 20.0, 12.0))
    assert spiked.status in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    assert spiked.detector == "isolation_forest"
    assert spiked.triggered_metric == "feature_vector"


@pytest.mark.unit
def test_pca_flags_extreme_on_hotelling_or_spe() -> None:
    detector = PcaDetector(baseline_window=24, n_components=2)
    for index in range(23):
        assert (
            detector.observe("bearing_1", "x", _healthy(index)).status is DetectionStatus.WARMING_UP
        )

    frozen = detector.observe("bearing_1", "x", _healthy(23))
    assert frozen.status is DetectionStatus.WARMING_UP

    ready = detector.observe("bearing_1", "x", _healthy(24))
    assert ready.status is DetectionStatus.NORMAL

    spiked = detector.observe("bearing_1", "x", _features(8.0, 25.0, 20.0, 12.0))
    assert spiked.status in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    assert spiked.detector == "pca"
    assert spiked.triggered_metric in {"hotelling_t2", "spe"}


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
