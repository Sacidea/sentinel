"""Envelope spektrumunda tepe belirginligi teshisi — saf, I/O yok (ADR-0015, kapandi).

Girdi: zarf spektrumu (Hz, genlik). Enerji kovasi / Z-Score / IF yok.
Canli `fault_type` yok; snapshot_pipeline cagirmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from stream_processor.domain.bearing_frequencies import IMS_ZA2115, BearingKinematics

DiagnosisLabel = Literal["bpfo", "bpfi", "bsf", "bpfi_veya_bsf", "uncertain"]

SLIP_FRACTION = 0.02
NOISE_HALF_HZ = 50.0
HARMONIC_COUNT = 5
SIDEBAND_ORDERS: tuple[int, ...] = (1, 2)
_MIN_FLOOR = 1e-18

# Set 2 kalibrasyonu (ims_envelope_prominence_diagnosis.md). Set 1'e retune yok.
DEFAULT_MIN_SCORE = 20.0
DEFAULT_BPFO_MARGIN = 2.0
DEFAULT_INNER_MARGIN = 1.3


@dataclass(frozen=True)
class DiagnosisScores:
    bpfo: float
    bpfi: float
    bsf: float


@dataclass(frozen=True)
class DiagnosisResult:
    label: DiagnosisLabel
    scores: DiagnosisScores
    reason: str


def diagnose_prominence(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    kinematics: BearingKinematics = IMS_ZA2115,
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    bpfo_margin: float = DEFAULT_BPFO_MARGIN,
    inner_margin: float = DEFAULT_INNER_MARGIN,
) -> DiagnosisResult:
    """Hiyerarsi: once BPFO; degilse BPFI vs BSF; ayirilamazsa bpfi_veya_bsf."""
    _validate_spectrum(freqs, magnitude)
    scores = prominence_scores(freqs, magnitude, kinematics)
    return decide_from_scores(
        scores,
        min_score=min_score,
        bpfo_margin=bpfo_margin,
        inner_margin=inner_margin,
    )


def decide_from_scores(
    scores: DiagnosisScores,
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    bpfo_margin: float = DEFAULT_BPFO_MARGIN,
    inner_margin: float = DEFAULT_INNER_MARGIN,
) -> DiagnosisResult:
    """Hiyerarsik etiket; spektrum tekrar hesaplanmaz (ortalama skor icin)."""
    return _decide(
        scores,
        min_score=min_score,
        bpfo_margin=bpfo_margin,
        inner_margin=inner_margin,
    )


def prominence_scores(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    kinematics: BearingKinematics = IMS_ZA2115,
) -> DiagnosisScores:
    """skor_bpfo = H(BPFO); bpfi = H(BPFI)+yan(fr); bsf = H(2*BSF)+yan(FTF)."""
    bpfo = _harmonic_score(freqs, magnitude, kinematics.bpfo_hz)
    bpfi = _harmonic_score(freqs, magnitude, kinematics.bpfi_hz) + _sideband_score(
        freqs, magnitude, kinematics.bpfi_hz, kinematics.shaft_hz
    )
    bsf = _harmonic_score(freqs, magnitude, kinematics.two_bsf_hz) + _sideband_score(
        freqs, magnitude, kinematics.two_bsf_hz, kinematics.ftf_hz
    )
    return DiagnosisScores(bpfo=bpfo, bpfi=bpfi, bsf=bsf)


def peak_prominence(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    center_hz: float,
    *,
    slip_fraction: float = SLIP_FRACTION,
    noise_half_hz: float = NOISE_HALF_HZ,
) -> float:
    """±slip tepe / ±noise_half medyan taban. Tepe binleri tabandan cikarilir."""
    if center_hz <= 0.0:
        return 0.0
    peak_amp = _peak_in_slip(freqs, magnitude, center_hz, slip_fraction)
    if peak_amp <= 0.0:
        return 0.0
    peak_hz = _peak_frequency(freqs, magnitude, center_hz, slip_fraction)
    floor = _noise_floor(freqs, magnitude, peak_hz, noise_half_hz, slip_fraction)
    return peak_amp / max(floor, _MIN_FLOOR)


def _harmonic_score(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    fundamental_hz: float,
) -> float:
    nyquist = float(freqs[-1]) if freqs.size else 0.0
    total = 0.0
    for order in range(1, HARMONIC_COUNT + 1):
        center = fundamental_hz * float(order)
        if center <= 0.0 or center >= nyquist:
            continue
        total += peak_prominence(freqs, magnitude, center)
    return total


def _sideband_score(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    carrier_hz: float,
    modulation_hz: float,
) -> float:
    if modulation_hz <= 0.0:
        return 0.0
    nyquist = float(freqs[-1]) if freqs.size else 0.0
    total = 0.0
    for order in SIDEBAND_ORDERS:
        delta = float(order) * modulation_hz
        for center in (carrier_hz + delta, carrier_hz - delta):
            if center <= 0.0 or center >= nyquist:
                continue
            total += peak_prominence(freqs, magnitude, center)
    return total


def _peak_in_slip(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    center_hz: float,
    slip_fraction: float,
) -> float:
    mask = _slip_mask(freqs, center_hz, slip_fraction)
    if not np.any(mask):
        return 0.0
    return float(np.max(magnitude[mask]))


def _peak_frequency(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    center_hz: float,
    slip_fraction: float,
) -> float:
    mask = _slip_mask(freqs, center_hz, slip_fraction)
    if not np.any(mask):
        return center_hz
    band_mag = magnitude[mask]
    band_freq = freqs[mask]
    return float(band_freq[int(np.argmax(band_mag))])


def _slip_mask(
    freqs: NDArray[np.float64], center_hz: float, slip_fraction: float
) -> NDArray[np.bool_]:
    half = center_hz * slip_fraction
    return (freqs >= center_hz - half) & (freqs <= center_hz + half)


def _noise_floor(
    freqs: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    peak_hz: float,
    noise_half_hz: float,
    slip_fraction: float,
) -> float:
    neighborhood = (freqs >= peak_hz - noise_half_hz) & (freqs <= peak_hz + noise_half_hz)
    exclude = _slip_mask(freqs, peak_hz, slip_fraction)
    noise = neighborhood & ~exclude
    if not np.any(noise):
        noise = neighborhood
    if not np.any(noise):
        return _MIN_FLOOR
    return float(np.median(magnitude[noise]))


def _decide(
    scores: DiagnosisScores,
    *,
    min_score: float,
    bpfo_margin: float,
    inner_margin: float,
) -> DiagnosisResult:
    inner_peak = max(scores.bpfi, scores.bsf)
    if scores.bpfo >= min_score and scores.bpfo >= bpfo_margin * max(inner_peak, _MIN_FLOOR):
        return DiagnosisResult(
            label="bpfo",
            scores=scores,
            reason="bpfo harmonik belirginligi digerlerinden ayri",
        )
    if inner_peak < min_score:
        return DiagnosisResult(
            label="uncertain",
            scores=scores,
            reason="hicbir sinif min_score marjini gecmedi",
        )
    if scores.bpfi >= min_score and scores.bpfi >= inner_margin * max(scores.bsf, _MIN_FLOOR):
        return DiagnosisResult(
            label="bpfi",
            scores=scores,
            reason="bpfi harmonik+yanbant bsf'den ayri",
        )
    if scores.bsf >= min_score and scores.bsf >= inner_margin * max(scores.bpfi, _MIN_FLOOR):
        return DiagnosisResult(
            label="bsf",
            scores=scores,
            reason="2xbsf harmonik+ftf yanbant bpfi'den ayri",
        )
    return DiagnosisResult(
        label="bpfi_veya_bsf",
        scores=scores,
        reason="ic bilezik/bilye marji yetmedi; bpfo degil",
    )


def _validate_spectrum(freqs: NDArray[np.float64], magnitude: NDArray[np.float64]) -> None:
    if freqs.shape != magnitude.shape or freqs.ndim != 1:
        raise ValueError("freqs ve magnitude ayni 1B sekilde olmali.")
    if freqs.size < 2:
        raise ValueError("spektrum en az iki bin olmali.")
    if not np.all(np.isfinite(freqs)) or not np.all(np.isfinite(magnitude)):
        raise ValueError("spektrum sonlu olmali.")
