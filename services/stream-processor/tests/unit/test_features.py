"""Sinyal özellik çıkarımı — saf mantık, bilinen girdilerle doğrulanır (bkz. 05, 15)."""

import math

import numpy as np
import pytest
from stream_processor.domain.bearing_frequencies import (
    CHARACTERISTIC_HZ,
    SAMPLE_RATE_HZ,
)
from stream_processor.domain.features import extract_features

_ZERO_FFT = dict.fromkeys(CHARACTERISTIC_HZ, 0.0)


@pytest.mark.unit
def test_square_wave_has_known_features() -> None:
    # [1,-1,1,-1]: ortalama 0, std 1 -> rms 1, peak 1, crest 1, kurtosis 1
    features = extract_features([1.0, -1.0, 1.0, -1.0])

    assert features.rms == 1.0
    assert features.kurtosis == 1.0
    assert features.crest_factor == 1.0
    assert features.peak == 1.0
    assert features.fft_band_energy == _ZERO_FFT


@pytest.mark.unit
def test_rms_is_root_mean_square() -> None:
    features = extract_features([3.0, 4.0])

    assert features.rms == pytest.approx(math.sqrt(12.5))


@pytest.mark.unit
def test_peak_uses_absolute_amplitude() -> None:
    features = extract_features([-5.0, 2.0, 1.0])

    assert features.peak == 5.0


@pytest.mark.unit
def test_crest_factor_is_peak_over_rms() -> None:
    # rms = sqrt((0+0+0+16)/4) = 2, peak = 4 -> crest = 2
    features = extract_features([0.0, 0.0, 0.0, 4.0])

    assert features.rms == pytest.approx(2.0)
    assert features.crest_factor == pytest.approx(2.0)


@pytest.mark.unit
def test_gaussian_noise_kurtosis_is_near_three() -> None:
    # Pearson tanımı: normal dağılım ~3 (excess değil). Eşikler bu ölçeğe göre yorumlanır.
    generator = np.random.default_rng(42)
    samples = generator.normal(0.0, 1.0, 200_000).tolist()

    features = extract_features(samples)

    assert features.kurtosis == pytest.approx(3.0, abs=0.1)


@pytest.mark.unit
def test_impulsive_signal_raises_kurtosis() -> None:
    # Darbeli sinyal (yüzey çatlağı benzeri) kurtosis'i normalin belirgin üstüne çıkarır.
    samples = [0.01] * 1000
    samples[100] = 50.0
    samples[500] = -50.0

    features = extract_features(samples)

    assert features.kurtosis > 10.0


@pytest.mark.unit
def test_silent_signal_does_not_divide_by_zero() -> None:
    # Sessiz sensör pipeline'ı çökertmez; tanımsız oranlar 0 döner.
    features = extract_features([0.0, 0.0, 0.0])

    assert features.rms == 0.0
    assert features.kurtosis == 0.0
    assert features.crest_factor == 0.0
    assert features.peak == 0.0
    assert features.fft_band_energy == _ZERO_FFT


@pytest.mark.unit
def test_constant_signal_has_zero_kurtosis() -> None:
    # Sapma yok -> std sıfır; kurtosis tanımsız yerine 0.
    features = extract_features([5.0, 5.0, 5.0])

    assert features.kurtosis == 0.0
    assert features.rms == pytest.approx(5.0)


@pytest.mark.unit
def test_empty_samples_are_rejected() -> None:
    with pytest.raises(ValueError, match="bos"):
        extract_features([])


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_samples_are_rejected(bad_value: float) -> None:
    # Bozuk okuma sessizce özelliğe dönüşmez; çağıran DLQ'ya yollar (bkz. 06, 07).
    with pytest.raises(ValueError, match="sonlu"):
        extract_features([0.1, bad_value, 0.2])


@pytest.mark.unit
def test_pure_tone_at_bpfo_dominates_bpfo_band() -> None:
    n = int(SAMPLE_RATE_HZ)
    time = np.arange(n, dtype=np.float64) / SAMPLE_RATE_HZ
    samples = np.sin(2.0 * np.pi * CHARACTERISTIC_HZ["bpfo"] * time).tolist()
    features = extract_features(samples)

    assert set(features.fft_band_energy) == {"bpfo", "bpfi", "bsf"}
    assert features.fft_band_energy["bpfo"] > 10.0 * features.fft_band_energy["bpfi"]
    assert features.fft_band_energy["bpfo"] > 10.0 * features.fft_band_energy["bsf"]


@pytest.mark.unit
def test_pure_tone_at_bpfi_dominates_bpfi_band() -> None:
    n = int(SAMPLE_RATE_HZ)
    time = np.arange(n, dtype=np.float64) / SAMPLE_RATE_HZ
    samples = np.sin(2.0 * np.pi * CHARACTERISTIC_HZ["bpfi"] * time).tolist()
    features = extract_features(samples)

    assert features.fft_band_energy["bpfi"] > 10.0 * features.fft_band_energy["bpfo"]
