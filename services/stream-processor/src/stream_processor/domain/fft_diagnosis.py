"""FFT bant teshisi — saf kural, I/O yok. Canli yazmaz (ADR-0011 otopsi, ADR-0012).

Ham-rFFT denendi; kaplin/Set 1 siniri goruldu; teshis envelope'a birakildi.
Kod silinmez. snapshot_pipeline cagirmaz.

Iki kosul AND (Set 2 kalibrasyonu):
(a) Mutlak yukselis: aday bandin z'si kendi baseline'ina gore esigi asar.
(b) Spektral hakimiyet: aday enerji olarak diger iki karakteristigi basar
    VE en az bir diger bant da baseline'ini asar. Yalniz (b)'nin enerji orani
    kaplin tuzagini elemez — etiketsiz kanallarda BPFO kovasi tek basina sisar,
    BPFI/BSF yerinde kalir; 'baskın' gorunur. Esik taramasi: ims_set2_fft_diagnosis.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from stream_processor.domain.bearing_frequencies import CHARACTERISTIC_HZ

FaultBand = Literal["bpfo", "bpfi", "bsf"]
FftDiagnosis = Literal["bpfo", "bpfi", "bsf", "uncertain"]
BANDS: tuple[FaultBand, ...] = ("bpfo", "bpfi", "bsf")

# IMS Set 2 tarama (ADR-0011). Baska sete tasinmaz.
DEFAULT_ABS_Z = 12.0
DEFAULT_DOMINANCE = 3.0
DEFAULT_COMPANION_Z = 8.0
_MIN_STD = 1e-12


@dataclass(frozen=True)
class FftBandBaseline:
    """Ilk saglikli pencereden (BASELINE_WINDOW) mean/std; kaymaz."""

    mean: Mapping[str, float]
    std: Mapping[str, float]


def band_z_scores(energy: Mapping[str, float], baseline: FftBandBaseline) -> dict[str, float]:
    """(E - mean) / std; std tabani _MIN_STD."""
    scores: dict[str, float] = {}
    for name in BANDS:
        spread = max(float(baseline.std[name]), _MIN_STD)
        scores[name] = (float(energy[name]) - float(baseline.mean[name])) / spread
    return scores


def diagnose_fft_bands(
    energy: Mapping[str, float],
    baseline: FftBandBaseline,
    *,
    abs_z: float = DEFAULT_ABS_Z,
    dominance: float = DEFAULT_DOMINANCE,
    companion_z: float = DEFAULT_COMPANION_Z,
) -> FftDiagnosis:
    """Aday bant (a)+(b) gecerse o bant; hicbiri gecmezse belirsiz. Zorlama yok."""
    _validate_energy(energy)
    z_scores = band_z_scores(energy, baseline)
    passed: list[tuple[float, FaultBand]] = []
    for band in BANDS:
        if not _absolute_rise(z_scores[band], abs_z):
            continue
        if not _spectral_dominance(band, energy, z_scores, dominance, companion_z):
            continue
        passed.append((z_scores[band], band))
    if not passed:
        return "uncertain"
    passed.sort(reverse=True)
    return passed[0][1]


def _absolute_rise(z_score: float, abs_z: float) -> bool:
    return z_score >= abs_z


def _spectral_dominance(
    band: FaultBand,
    energy: Mapping[str, float],
    z_scores: Mapping[str, float],
    dominance: float,
    companion_z: float,
) -> bool:
    others = [name for name in BANDS if name != band]
    other_energy = max(float(energy[name]) for name in others)
    if float(energy[band]) < dominance * max(other_energy, _MIN_STD):
        return False
    return max(z_scores[name] for name in others) >= companion_z


def _validate_energy(energy: Mapping[str, float]) -> None:
    missing = [name for name in CHARACTERISTIC_HZ if name not in energy]
    if missing:
        raise ValueError(f"fft_band_energy eksik anahtar: {missing}")
