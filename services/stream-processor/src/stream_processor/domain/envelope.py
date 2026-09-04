"""Hilbert envelope bant enerjisi — saf kural, I/O yok (ADR-0012/0013).

Ham spektrum teshisi kapandi. Envelope: rezonans bandi (2–10 kHz) + analitik
genlik + ayni BPFO/BPFI/BSF kovalar. snapshot_pipeline cagirmaz; canli
`fault_type` yok. Esikler Set 2 taramasindan sonra `ENVELOPE_*` sabitlerine
yazilir; sihirli default iddiasi yok.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from stream_processor.domain.bearing_frequencies import (
    CHARACTERISTIC_HZ,
    ENVELOPE_BANDPASS_HI_HZ,
    ENVELOPE_BANDPASS_LO_HZ,
    SAMPLE_RATE_HZ,
)
from stream_processor.domain.spectrum import rfft_band_energy

# Set 2 envelope tarama (ADR-0013). companion_z, b4 max companion (21.3) ustu;
# plato ~25–100. Ham-FFT 8 kopya degil.
ENVELOPE_ABS_Z = 12.0
ENVELOPE_DOMINANCE = 3.0
ENVELOPE_COMPANION_Z = 25.0


def envelope_band_energy(
    samples: Sequence[float],
    *,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
    lo_hz: float = ENVELOPE_BANDPASS_LO_HZ,
    hi_hz: float = ENVELOPE_BANDPASS_HI_HZ,
) -> dict[str, float]:
    """Band-pass + Hilbert genlik spektrumu bant enerjisi.

    Raises:
        ValueError: Bos veya NaN/inf pencere (extract_features ile ayni sozlesme).
    """
    if len(samples) == 0:
        raise ValueError("Ozellik cikarimi icin ornek listesi bos olamaz.")
    signal = np.asarray(samples, dtype=np.float64)
    if not np.all(np.isfinite(signal)):
        raise ValueError("Ornekler sonlu olmali; NaN/inf iceren pencere islenmez.")
    empty = dict.fromkeys(CHARACTERISTIC_HZ, 0.0)
    if signal.size < 2 or sample_rate_hz <= 0.0:
        return empty
    envelope = _demean_envelope(signal, sample_rate_hz=sample_rate_hz, lo_hz=lo_hz, hi_hz=hi_hz)
    return rfft_band_energy(envelope, sample_rate_hz=sample_rate_hz)


def envelope_magnitude_spectrum(
    samples: Sequence[float],
    *,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
    lo_hz: float = ENVELOPE_BANDPASS_LO_HZ,
    hi_hz: float = ENVELOPE_BANDPASS_HI_HZ,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Band-pass + Hilbert zarf; Hann * rFFT genlik. Teshis buradan okur, enerji kovasi degil."""
    if len(samples) == 0:
        raise ValueError("Ozellik cikarimi icin ornek listesi bos olamaz.")
    signal = np.asarray(samples, dtype=np.float64)
    if not np.all(np.isfinite(signal)):
        raise ValueError("Ornekler sonlu olmali; NaN/inf iceren pencere islenmez.")
    n_samples = int(signal.size)
    if n_samples < 2 or sample_rate_hz <= 0.0:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)
    envelope = _demean_envelope(signal, sample_rate_hz=sample_rate_hz, lo_hz=lo_hz, hi_hz=hi_hz)
    windowed = envelope * np.hanning(n_samples)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sample_rate_hz)
    magnitude = np.abs(np.fft.rfft(windowed))
    return freqs, magnitude


def _demean_envelope(
    signal: NDArray[np.float64],
    *,
    sample_rate_hz: float,
    lo_hz: float,
    hi_hz: float,
) -> NDArray[np.float64]:
    centered = signal - float(np.mean(signal))
    filtered = _rfft_bandpass(centered, sample_rate_hz=sample_rate_hz, lo_hz=lo_hz, hi_hz=hi_hz)
    envelope = _hilbert_envelope(filtered)
    return envelope - float(np.mean(envelope))


def _rfft_bandpass(
    signal: NDArray[np.float64],
    *,
    sample_rate_hz: float,
    lo_hz: float,
    hi_hz: float,
) -> NDArray[np.float64]:
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate_hz)
    spectrum[(freqs < lo_hz) | (freqs > hi_hz)] = 0.0
    return np.fft.irfft(spectrum, n=int(signal.size))


def _hilbert_envelope(signal: NDArray[np.float64]) -> NDArray[np.float64]:
    """Analitik sinyal genligi (FFT Hilbert, SciPy yok)."""
    n_samples = int(signal.size)
    spectrum = np.fft.fft(signal)
    multiplier = np.zeros(n_samples, dtype=np.float64)
    multiplier[0] = 1.0
    if n_samples % 2 == 0:
        multiplier[n_samples // 2] = 1.0
        multiplier[1 : n_samples // 2] = 2.0
    else:
        multiplier[1 : (n_samples + 1) // 2] = 2.0
    analytic = np.fft.ifft(spectrum * multiplier)
    return np.abs(analytic)
