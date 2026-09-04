"""Rulman karakteristik frekanslari — IMS Rexnord ZA-2115.

NASA 2nd test: ~2000 RPM, 20.480 Hz ornekleme.

Kinematik (Qiu/IMS, ZA-2115): n=16, d=0.331 in, D=2.815 in, alpha=15.17 deg.
Formulden BSF ~140 Hz; 2*BSF ~280 Hz. ADR-0010 enerji kovasi `bsf=278` **2xBSF**
(tek sayili BSF harmonikleri o kovada yok). Teshis (`diagnosis.py`) temel BSF
ve 2xBSF'yi ayri kullanir. CHARACTERISTIC_HZ degerleri bit-ayni kalir — canli
`fft_band_energy` ve mevcut testler degismez.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians
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

# Rexnord ZA-2115 geometri (IMS). Aci derece.
ZA2115_N_ROLLING: Final[int] = 16
ZA2115_BALL_DIAMETER_IN: Final[float] = 0.331
ZA2115_PITCH_DIAMETER_IN: Final[float] = 2.815
ZA2115_CONTACT_ANGLE_DEG: Final[float] = 15.17
IMS_SHAFT_RPM: Final[float] = 2000.0

# ADR-0010 enerji kovaları (1.+2.+3. H, ±5 Hz). `bsf` burada 2xBSF (~280 Hz);
# temel BSF (~140 Hz) bu dict'te yok. Degerleri degistirme — kayitli spektrum
# ve testler bu merkeze kilitli.
CHARACTERISTIC_HZ: Final[dict[str, float]] = {
    "bpfo": 236.0,
    "bpfi": 297.0,
    "bsf": 278.0,  # 2xBSF, temel BSF degil
}


@dataclass(frozen=True)
class BearingKinematics:
    """Mil hizi + dort karakteristik (Hz). Teshis bunu kullanir, enerji kovasi degil."""

    shaft_hz: float
    bpfo_hz: float
    bpfi_hz: float
    bsf_hz: float
    two_bsf_hz: float
    ftf_hz: float


def za2115_kinematics(*, shaft_rpm: float = IMS_SHAFT_RPM) -> BearingKinematics:
    """BPFO/BPFI/BSF/FTF = f(n, d/D, alpha, fr). 278 Hz kovasini uretmez."""
    if shaft_rpm <= 0.0:
        raise ValueError("mil hizi pozitif olmali.")
    shaft_hz = shaft_rpm / 60.0
    pitch = ZA2115_PITCH_DIAMETER_IN
    ball = ZA2115_BALL_DIAMETER_IN
    if pitch <= 0.0 or ball <= 0.0:
        raise ValueError("ZA-2115 caplari pozitif olmali.")
    ratio = (ball / pitch) * cos(radians(ZA2115_CONTACT_ANGLE_DEG))
    rolling = float(ZA2115_N_ROLLING)
    bpfo = (rolling / 2.0) * shaft_hz * (1.0 - ratio)
    bpfi = (rolling / 2.0) * shaft_hz * (1.0 + ratio)
    bsf = (pitch / (2.0 * ball)) * shaft_hz * (1.0 - ratio * ratio)
    ftf = 0.5 * shaft_hz * (1.0 - ratio)
    return BearingKinematics(
        shaft_hz=shaft_hz,
        bpfo_hz=bpfo,
        bpfi_hz=bpfi,
        bsf_hz=bsf,
        two_bsf_hz=2.0 * bsf,
        ftf_hz=ftf,
    )


IMS_ZA2115: Final[BearingKinematics] = za2115_kinematics()
