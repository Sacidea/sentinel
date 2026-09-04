"""Tepe belirginligi teshisi — sentetik ton + yan bant (ADR-0015)."""

import numpy as np
import pytest
from stream_processor.domain.bearing_frequencies import IMS_ZA2115
from stream_processor.domain.diagnosis import (
    DEFAULT_BPFO_MARGIN,
    DEFAULT_INNER_MARGIN,
    DEFAULT_MIN_SCORE,
    diagnose_prominence,
    peak_prominence,
)


def _grid(max_hz: float = 2000.0, df: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    freqs = np.arange(0.0, max_hz + df, df, dtype=np.float64)
    mag = np.ones_like(freqs)
    return freqs, mag


def _add_peak(freqs: np.ndarray, mag: np.ndarray, center: float, height: float) -> None:
    index = int(np.argmin(np.abs(freqs - center)))
    mag[index] = height


def _add_harmonics(
    freqs: np.ndarray, mag: np.ndarray, fundamental: float, height: float, count: int = 5
) -> None:
    for order in range(1, count + 1):
        _add_peak(freqs, mag, fundamental * float(order), height)


@pytest.mark.unit
def test_flat_spectrum_is_uncertain() -> None:
    freqs, mag = _grid()
    result = diagnose_prominence(freqs, mag)
    assert result.label == "uncertain"
    assert result.scores.bpfo < DEFAULT_MIN_SCORE


@pytest.mark.unit
def test_bpfo_harmonics_without_sidebands_are_bpfo() -> None:
    freqs, mag = _grid()
    _add_harmonics(freqs, mag, IMS_ZA2115.bpfo_hz, 40.0)
    result = diagnose_prominence(freqs, mag)
    assert result.label == "bpfo"
    assert result.scores.bpfo > result.scores.bpfi
    assert result.scores.bpfo > result.scores.bsf


@pytest.mark.unit
def test_bpfi_harmonics_plus_shaft_sidebands_are_bpfi() -> None:
    freqs, mag = _grid()
    kin = IMS_ZA2115
    _add_harmonics(freqs, mag, kin.bpfi_hz, 40.0)
    for order in (1, 2):
        _add_peak(freqs, mag, kin.bpfi_hz + order * kin.shaft_hz, 25.0)
        _add_peak(freqs, mag, kin.bpfi_hz - order * kin.shaft_hz, 25.0)
    result = diagnose_prominence(freqs, mag)
    assert result.label == "bpfi"


@pytest.mark.unit
def test_two_bsf_plus_ftf_sidebands_are_bsf() -> None:
    freqs, mag = _grid()
    kin = IMS_ZA2115
    _add_harmonics(freqs, mag, kin.two_bsf_hz, 40.0)
    for order in (1, 2):
        _add_peak(freqs, mag, kin.two_bsf_hz + order * kin.ftf_hz, 25.0)
        _add_peak(freqs, mag, kin.two_bsf_hz - order * kin.ftf_hz, 25.0)
    result = diagnose_prominence(freqs, mag)
    assert result.label == "bsf"


@pytest.mark.unit
def test_tied_inner_scores_are_bpfi_or_bsf() -> None:
    freqs, mag = _grid()
    kin = IMS_ZA2115
    _add_harmonics(freqs, mag, kin.bpfi_hz, 30.0)
    _add_harmonics(freqs, mag, kin.two_bsf_hz, 30.0)
    result = diagnose_prominence(freqs, mag)
    assert result.label == "bpfi_veya_bsf"


@pytest.mark.unit
def test_broadband_lift_is_not_a_tone() -> None:
    """Kaplin benzeri: taban birlikte yukselir, belirginlik ~1 kalir."""
    freqs, mag = _grid()
    mag[:] = 50.0
    result = diagnose_prominence(freqs, mag)
    assert result.label == "uncertain"
    assert peak_prominence(freqs, mag, IMS_ZA2115.bpfo_hz) == pytest.approx(1.0, rel=0.05)


@pytest.mark.unit
def test_mismatch_shape_is_rejected() -> None:
    with pytest.raises(ValueError, match="sekilde"):
        diagnose_prominence(np.array([0.0, 1.0]), np.array([1.0]))


@pytest.mark.unit
def test_set2_defaults_are_named_constants() -> None:
    assert DEFAULT_MIN_SCORE == 20.0
    assert DEFAULT_BPFO_MARGIN == 2.0
    assert DEFAULT_INNER_MARGIN == 1.3


@pytest.mark.unit
def test_decide_from_scores_matches_diagnose_on_flat() -> None:
    from stream_processor.domain.diagnosis import DiagnosisScores, decide_from_scores

    result = decide_from_scores(DiagnosisScores(bpfo=1.0, bpfi=1.0, bsf=1.0))
    assert result.label == "uncertain"
