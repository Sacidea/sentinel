"""Z-Score anomali tespiti — senaryolar docs/planning/15-anomaly-design.md."""

import pytest
from stream_processor.domain.detectors import DetectionStatus, ZScoreDetector
from stream_processor.domain.features import SignalFeatures

# 0, 2, 0, 2 -> mean 1, pop. std 1. Böylece z = value - 1.
_VARIED = (0.0, 2.0, 0.0, 2.0)
_CONSTANT = (1.0, 1.0, 1.0, 1.0)


def _features(rms: float, kurtosis: float) -> SignalFeatures:
    return SignalFeatures(rms=rms, kurtosis=kurtosis, crest_factor=99.0, peak=99.0)


def _detector(**overrides: float | int) -> ZScoreDetector:
    params: dict[str, float | int] = {
        "baseline_window": 4,
        "ma_window": 1,
        "warning_threshold": 3.0,
        "critical_threshold": 5.0,
    }
    params.update(overrides)
    return ZScoreDetector(
        baseline_window=int(params["baseline_window"]),
        ma_window=int(params["ma_window"]),
        warning_threshold=float(params["warning_threshold"]),
        critical_threshold=float(params["critical_threshold"]),
    )


def _warmup(
    detector: ZScoreDetector,
    *,
    rms: tuple[float, ...] = _VARIED,
    kurtosis: tuple[float, ...] = _CONSTANT,
    machine_id: str = "bearing_1",
    axis: str = "x",
) -> None:
    for rms_value, kurtosis_value in zip(rms, kurtosis, strict=True):
        result = detector.observe(machine_id, axis, _features(rms_value, kurtosis_value))
        assert result.status is DetectionStatus.WARMING_UP


@pytest.mark.unit
def test_baseline_snapshots_are_warming_up_without_scores() -> None:
    detector = _detector()
    result = detector.observe("bearing_1", "x", _features(0.0, 1.0))

    assert result.status is DetectionStatus.WARMING_UP
    assert result.scores == ()
    assert result.triggered_metric is None


@pytest.mark.unit
def test_scoring_starts_after_baseline_window() -> None:
    detector = _detector()
    _warmup(detector)

    # İlk N yalnız baseline'ı besler; skor N+1'de başlar.
    result = detector.observe("bearing_1", "x", _features(1.0, 1.0))
    assert result.status is DetectionStatus.NORMAL
    assert any(score.metric == "rms" for score in result.scores)


@pytest.mark.unit
def test_known_z_score_matches_population_std() -> None:
    detector = _detector()
    _warmup(detector)
    result = detector.observe("bearing_1", "x", _features(4.0, 1.0))

    assert result.status is DetectionStatus.WARNING
    assert result.triggered_metric == "rms"
    assert result.triggered_z == pytest.approx(3.0)
    assert result.triggered_value == 4.0
    rms_score = next(score for score in result.scores if score.metric == "rms")
    assert rms_score.z_score == pytest.approx(3.0)


@pytest.mark.unit
def test_critical_when_smoothed_abs_z_reaches_five() -> None:
    detector = _detector()
    _warmup(detector)
    result = detector.observe("bearing_1", "x", _features(6.0, 1.0))

    assert result.status is DetectionStatus.CRITICAL
    assert result.triggered_z == pytest.approx(5.0)


@pytest.mark.unit
def test_drop_below_baseline_also_alarms() -> None:
    # Eşik mutlak değere bakılır; kurtosis düşüşü ileri arıza işaretidir.
    detector = _detector()
    _warmup(detector, rms=_CONSTANT, kurtosis=_VARIED)
    result = detector.observe("bearing_1", "x", _features(1.0, -2.0))

    assert result.status is DetectionStatus.WARNING
    assert result.triggered_metric == "kurtosis"
    assert result.triggered_z == pytest.approx(-3.0)


@pytest.mark.unit
def test_below_warning_is_normal() -> None:
    detector = _detector()
    _warmup(detector)
    result = detector.observe("bearing_1", "x", _features(3.9, 1.0))

    assert result.status is DetectionStatus.NORMAL
    assert result.triggered_metric is None
    assert next(score.z_score for score in result.scores if score.metric == "rms") == pytest.approx(
        2.9
    )


@pytest.mark.unit
def test_single_spike_does_not_alarm_until_ma_window_fills() -> None:
    detector = _detector(ma_window=3)
    _warmup(detector)

    first = detector.observe("bearing_1", "x", _features(11.0, 1.0))  # ham z=10
    second = detector.observe("bearing_1", "x", _features(1.0, 1.0))  # ham z=0

    assert first.status is DetectionStatus.NORMAL
    assert second.status is DetectionStatus.NORMAL

    # (10 + 0 + 0) / 3 ≈ 3.33 -> warning; tek sıçrama tek başına yetmez.
    third = detector.observe("bearing_1", "x", _features(1.0, 1.0))
    assert third.status is DetectionStatus.WARNING
    assert third.triggered_z == pytest.approx(10.0 / 3.0)


@pytest.mark.unit
def test_baseline_is_frozen_after_window() -> None:
    detector = _detector()
    _warmup(detector)
    detector.observe("bearing_1", "x", _features(4.0, 1.0))
    for _ in range(10):
        detector.observe("bearing_1", "x", _features(100.0, 1.0))

    # Kaymış olsaydı mean 1'de kalmaz, z=3 olmazdı (boiling frog).
    result = detector.observe("bearing_1", "x", _features(4.0, 1.0))
    assert next(score.z_score for score in result.scores if score.metric == "rms") == pytest.approx(
        3.0
    )


@pytest.mark.unit
def test_zero_std_metric_is_skipped() -> None:
    detector = _detector()
    _warmup(detector, rms=_CONSTANT, kurtosis=_CONSTANT)
    result = detector.observe("bearing_1", "x", _features(100.0, 100.0))

    assert result.status is DetectionStatus.NORMAL
    assert result.scores == ()


@pytest.mark.unit
def test_both_metrics_yield_single_highest_severity() -> None:
    detector = _detector()
    _warmup(detector, rms=_VARIED, kurtosis=_VARIED)
    result = detector.observe("bearing_1", "x", _features(4.0, 6.0))

    assert result.status is DetectionStatus.CRITICAL
    assert result.triggered_metric == "kurtosis"
    assert result.triggered_z == pytest.approx(5.0)
    assert {score.metric for score in result.scores} == {"rms", "kurtosis"}


@pytest.mark.unit
def test_same_severity_picks_larger_abs_smoothed_z() -> None:
    detector = _detector()
    _warmup(detector, rms=_VARIED, kurtosis=_VARIED)
    result = detector.observe("bearing_1", "x", _features(4.0, 5.0))

    assert result.status is DetectionStatus.WARNING
    assert result.triggered_metric == "kurtosis"
    assert abs(result.triggered_z or 0.0) == pytest.approx(4.0)


@pytest.mark.unit
def test_series_are_independent_per_machine_and_axis() -> None:
    detector = _detector()
    _warmup(detector, machine_id="bearing_1", axis="x")

    other = detector.observe("bearing_1", "y", _features(4.0, 1.0))
    still_cold = detector.observe("bearing_2", "x", _features(4.0, 1.0))
    ready = detector.observe("bearing_1", "x", _features(4.0, 1.0))

    assert other.status is DetectionStatus.WARMING_UP
    assert still_cold.status is DetectionStatus.WARMING_UP
    assert ready.status is DetectionStatus.WARNING


@pytest.mark.unit
def test_crest_and_peak_are_not_scored() -> None:
    detector = _detector()
    _warmup(detector)
    result = detector.observe("bearing_1", "x", _features(1.0, 1.0))

    assert {score.metric for score in result.scores} == {"rms"}


@pytest.mark.unit
def test_result_detector_name_is_zscore() -> None:
    detector = _detector()
    result = detector.observe("bearing_1", "x", _features(0.0, 1.0))

    assert result.detector == "zscore"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"baseline_window": 1}, "baseline"),
        ({"ma_window": 0}, "ma_window"),
        ({"warning_threshold": 5.0, "critical_threshold": 5.0}, "warning"),
        ({"warning_threshold": 0.0}, "esik"),
    ],
)
def test_invalid_config_is_rejected(kwargs: dict[str, float | int], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _detector(**kwargs)


@pytest.mark.unit
def test_non_finite_features_are_rejected() -> None:
    detector = _detector()
    with pytest.raises(ValueError, match="sonlu"):
        detector.observe("bearing_1", "x", _features(float("nan"), 1.0))
