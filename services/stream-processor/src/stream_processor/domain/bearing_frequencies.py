"""Rulman karakteristik frekanslari — IMS Set 2 Rexnord ZA-2115.

NASA 2nd test: ~2000 RPM, 20.480 Hz ornekleme. BPFO/BPFI/BSF merkezleri bu
geometri+devir icin; baska rulman/sette gecerli sayilmaz.

Teshis (hangi bant arizayi kanitlar) burada yok. Yalniz bant merkezi ve genislik.
"""

from __future__ import annotations

from typing import Final

# IMS snapshot: 20.480 nokta / 1 sn pencere.
SAMPLE_RATE_HZ: Final[float] = 20480.0
# Her harmonik etrafinda toplanan yari-genislik (Hz).
BAND_HALF_WIDTH_HZ: Final[float] = 5.0
HARMONICS: Final[tuple[int, ...]] = (1, 2, 3)

# Envelope: darbe trenini rezonans bandinda demodule et (ADR-0012/0013).
# Nyquist 10.240 Hz; ust kenar onun altinda kalir.
ENVELOPE_BANDPASS_LO_HZ: Final[float] = 2000.0
ENVELOPE_BANDPASS_HI_HZ: Final[float] = 10000.0

# Rexnord ZA-2115 (IMS Set 2): dis bilezik / ic bilezik / bilye gecis.
CHARACTERISTIC_HZ: Final[dict[str, float]] = {
    "bpfo": 236.0,
    "bpfi": 297.0,
    "bsf": 278.0,
}
