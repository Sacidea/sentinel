"""Sinyal özellik çıkarımı: RMS, kurtosis, crest factor, peak, FFT bant (bkz. planning/15).

Saf mantık — I/O yok. NumPy yalnız hesap için kullanılır.

Kurtosis **Pearson** tanımıyla hesaplanır (dördüncü standartlaştırılmış moment): normal dağılım
için ~3. Rulman izlemede eşikler bu ölçeğe göre yorumlandığı için excess (Fisher) tanımı
kullanılmaz; 3 civarı sağlıklı, belirgin yükseliş darbeli bozulma işaretidir.

FFT bant enerjisi teşhis etmez; Z-Score/IF/PCA/River girdisi değildir (ADR-0010).
Envelope bantları burada yok: canlı boruya girmez (ADR-0012/0013).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from stream_processor.domain.bearing_frequencies import SAMPLE_RATE_HZ
from stream_processor.domain.spectrum import rfft_band_energy


@dataclass(frozen=True)
class SignalFeatures:
    """Bir titreşim penceresinden çıkarılan özellikler."""

    rms: float
    kurtosis: float
    crest_factor: float
    peak: float
    fft_band_energy: dict[str, float] = field(default_factory=dict)


def extract_features(
    samples: Sequence[float],
    *,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
) -> SignalFeatures:
    """Özellikleri hesaplar.

    Raises:
        ValueError: Örnek listesi boşsa veya sonlu olmayan (NaN/inf) değer içeriyorsa.
            Bozuk okuma sessizce özelliğe dönüşmez; çağıran DLQ'ya yollar (bkz. 06, 07).
    """
    if len(samples) == 0:
        raise ValueError("Ozellik cikarimi icin ornek listesi bos olamaz.")

    signal = np.asarray(samples, dtype=np.float64)
    if not np.all(np.isfinite(signal)):
        raise ValueError("Ornekler sonlu olmali; NaN/inf iceren pencere islenmez.")

    rms = float(np.sqrt(np.mean(signal**2)))
    peak = float(np.max(np.abs(signal)))
    # Sessiz sensörde (rms 0) veya sabit sinyalde (std 0) oran tanımsız; pipeline çökmez.
    crest_factor = peak / rms if rms > 0.0 else 0.0

    deviation = signal - np.mean(signal)
    std = float(np.sqrt(np.mean(deviation**2)))
    kurtosis = float(np.mean(deviation**4) / std**4) if std > 0.0 else 0.0

    return SignalFeatures(
        rms=rms,
        kurtosis=kurtosis,
        crest_factor=crest_factor,
        peak=peak,
        fft_band_energy=rfft_band_energy(signal, sample_rate_hz=sample_rate_hz),
    )
