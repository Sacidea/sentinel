"""Hilbert envelope bant enerjisi — saf mantik (ADR-0013)."""

import numpy as np
import pytest
from stream_processor.domain.bearing_frequencies import (
    CHARACTERISTIC_HZ,
    SAMPLE_RATE_HZ,
)
from stream_processor.domain.envelope import (
    ENVELOPE_ABS_Z,
    ENVELOPE_COMPANION_Z,
    ENVELOPE_DOMINANCE,
    envelope_band_energy,
    envelope_magnitude_spectrum,
)


def _tone_am(*, carrier_hz: float, mod_hz: float, n: int) -> list[float]:
    time = np.arange(n, dtype=np.float64) / SAMPLE_RATE_HZ
    modulation = 1.0 + 0.8 * np.sin(2.0 * np.pi * mod_hz * time)
    carrier = np.sin(2.0 * np.pi * carrier_hz * time)
    return (modulation * carrier).tolist()


@pytest.mark.unit
def test_am_at_bpfo_dominates_envelope_bpfo() -> None:
    """5 kHz tasiyici, BPFO genlik modulasyonu — ham FFT BPFO gormez, envelope gorur."""
    n_samples = int(SAMPLE_RATE_HZ)
    samples = _tone_am(carrier_hz=5000.0, mod_hz=CHARACTERISTIC_HZ["bpfo"], n=n_samples)
    energy = envelope_band_energy(samples)
    assert set(energy) == {"bpfo", "bpfi", "bsf"}
    assert energy["bpfo"] > 10.0 * energy["bpfi"]
    assert energy["bpfo"] > 10.0 * energy["bsf"]


@pytest.mark.unit
def test_am_at_bpfi_dominates_envelope_bpfi() -> None:
    n_samples = int(SAMPLE_RATE_HZ)
    samples = _tone_am(carrier_hz=5000.0, mod_hz=CHARACTERISTIC_HZ["bpfi"], n=n_samples)
    energy = envelope_band_energy(samples)
    assert energy["bpfi"] > 10.0 * energy["bpfo"]
    assert energy["bpfi"] > 10.0 * energy["bsf"]


@pytest.mark.unit
def test_silent_envelope_is_zero() -> None:
    energy = envelope_band_energy([0.0, 0.0, 0.0, 0.0])
    assert energy == dict.fromkeys(CHARACTERISTIC_HZ, 0.0)


@pytest.mark.unit
def test_empty_envelope_is_rejected() -> None:
    with pytest.raises(ValueError, match="bos"):
        envelope_band_energy([])


@pytest.mark.unit
def test_non_finite_envelope_is_rejected() -> None:
    with pytest.raises(ValueError, match="sonlu"):
        envelope_band_energy([0.1, float("nan"), 0.2])


@pytest.mark.unit
def test_set2_envelope_defaults_are_calibrated() -> None:
    assert ENVELOPE_ABS_Z == 12.0
    assert ENVELOPE_DOMINANCE == 3.0
    assert ENVELOPE_COMPANION_Z == 25.0


@pytest.mark.unit
def test_am_envelope_spectrum_peaks_near_bpfo() -> None:
    n_samples = int(SAMPLE_RATE_HZ)
    samples = _tone_am(carrier_hz=5000.0, mod_hz=CHARACTERISTIC_HZ["bpfo"], n=n_samples)
    freqs, magnitude = envelope_magnitude_spectrum(samples)
    assert freqs.size == magnitude.size
    peak_hz = float(freqs[int(np.argmax(magnitude[1:]) + 1)])
    assert peak_hz == pytest.approx(CHARACTERISTIC_HZ["bpfo"], rel=0.02)
