"""FFT bant teshisi — saf kurallar, Set 2 kalibrasyonuna gore (ADR-0011)."""

import pytest
from stream_processor.domain.fft_diagnosis import (
    DEFAULT_ABS_Z,
    DEFAULT_COMPANION_Z,
    DEFAULT_DOMINANCE,
    FftBandBaseline,
    band_z_scores,
    diagnose_fft_bands,
)


def _baseline() -> FftBandBaseline:
    return FftBandBaseline(
        mean={"bpfo": 1.0e4, "bpfi": 3.0e3, "bsf": 3.5e3},
        std={"bpfo": 5.0e3, "bpfi": 5.0e2, "bsf": 6.0e2},
    )


@pytest.mark.unit
def test_healthy_snapshot_is_uncertain() -> None:
    energy = {"bpfo": 1.1e4, "bpfi": 3.1e3, "bsf": 3.4e3}
    assert diagnose_fft_bands(energy, _baseline()) == "uncertain"


@pytest.mark.unit
def test_isolated_bpfo_spike_is_uncertain_coupling() -> None:
    """Kaplin: BPFO kovasi sisar, BPFI/BSF yerinde — enerji 'baskın' olsa da belirsiz."""
    energy = {"bpfo": 5.0e5, "bpfi": 3.2e3, "bsf": 3.4e3}
    z_scores = band_z_scores(energy, _baseline())
    assert z_scores["bpfo"] > DEFAULT_ABS_Z
    assert energy["bpfo"] > DEFAULT_DOMINANCE * max(energy["bpfi"], energy["bsf"])
    assert max(z_scores["bpfi"], z_scores["bsf"]) < DEFAULT_COMPANION_Z
    assert diagnose_fft_bands(energy, _baseline()) == "uncertain"


@pytest.mark.unit
def test_outer_race_bpfo_with_companion_rise() -> None:
    energy = {"bpfo": 5.0e5, "bpfi": 2.0e4, "bsf": 1.5e4}
    assert diagnose_fft_bands(energy, _baseline()) == "bpfo"


@pytest.mark.unit
def test_inner_race_bpfi_when_dominant_and_companion() -> None:
    energy = {"bpfo": 5.5e4, "bpfi": 2.0e5, "bsf": 8.0e3}
    assert diagnose_fft_bands(energy, _baseline()) == "bpfi"


@pytest.mark.unit
def test_ratio_inflation_without_absolute_z_is_uncertain() -> None:
    """Kucuk baseline + kucuk mutlak artis: oran siser, z dusuk kalir."""
    tight = FftBandBaseline(
        mean={"bpfo": 100.0, "bpfi": 90.0, "bsf": 90.0},
        std={"bpfo": 50.0, "bpfi": 40.0, "bsf": 40.0},
    )
    energy = {"bpfo": 400.0, "bpfi": 95.0, "bsf": 92.0}
    assert (energy["bpfo"] / tight.mean["bpfo"]) == pytest.approx(4.0)
    assert diagnose_fft_bands(energy, tight) == "uncertain"


@pytest.mark.unit
def test_missing_band_is_rejected() -> None:
    with pytest.raises(ValueError, match="eksik"):
        diagnose_fft_bands({"bpfo": 1.0, "bpfi": 1.0}, _baseline())


@pytest.mark.unit
def test_set2_defaults_are_the_calibrated_constants() -> None:
    assert DEFAULT_ABS_Z == 12.0
    assert DEFAULT_DOMINANCE == 3.0
    assert DEFAULT_COMPANION_Z == 8.0
