"""rFFT bant enerjisi — ham spektrum ve envelope spektrumu ortak kovalar.

Teshis yok. Merkezler `CHARACTERISTIC_HZ` (ADR-0010).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from stream_processor.domain.bearing_frequencies import (
    BAND_HALF_WIDTH_HZ,
    CHARACTERISTIC_HZ,
    HARMONICS,
)


def rfft_band_energy(signal: NDArray[np.float64], *, sample_rate_hz: float) -> dict[str, float]:
    """rfft gucu: her karakteristik icin 1.+2.+3. harmonik, ±BAND_HALF_WIDTH_HZ."""
    empty = dict.fromkeys(CHARACTERISTIC_HZ, 0.0)
    if signal.size < 2 or sample_rate_hz <= 0.0:
        return empty
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate_hz)
    power = np.abs(spectrum) ** 2
    nyquist = sample_rate_hz / 2.0
    bands: dict[str, float] = {}
    for name, fundamental in CHARACTERISTIC_HZ.items():
        total = 0.0
        for harmonic in HARMONICS:
            center = fundamental * float(harmonic)
            if center > nyquist:
                continue
            lo = center - BAND_HALF_WIDTH_HZ
            hi = center + BAND_HALF_WIDTH_HZ
            mask = (freqs >= lo) & (freqs <= hi)
            if np.any(mask):
                total += float(np.sum(power[mask]))
        bands[name] = total
    return bands
