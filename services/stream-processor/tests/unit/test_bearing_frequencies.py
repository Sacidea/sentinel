"""ZA-2115 kinematik — 278 Hz kovasinin 2xBSF oldugu."""

import pytest
from stream_processor.domain.bearing_frequencies import (
    CHARACTERISTIC_HZ,
    IMS_ZA2115,
    za2115_kinematics,
)


@pytest.mark.unit
def test_ims_shaft_is_2000_rpm() -> None:
    assert IMS_ZA2115.shaft_hz == pytest.approx(2000.0 / 60.0)


@pytest.mark.unit
def test_formula_bsf_is_near_140_not_278() -> None:
    """Kullanici suphesi: CHARACTERISTIC_HZ['bsf']=278 aslinda 2xBSF."""
    kin = IMS_ZA2115
    assert kin.bsf_hz == pytest.approx(139.92, rel=0.01)
    assert kin.two_bsf_hz == pytest.approx(2.0 * kin.bsf_hz)
    assert CHARACTERISTIC_HZ["bsf"] == pytest.approx(kin.two_bsf_hz, rel=0.02)
    assert CHARACTERISTIC_HZ["bsf"] != pytest.approx(kin.bsf_hz, rel=0.2)


@pytest.mark.unit
def test_formula_bpfo_bpfi_match_energy_bins() -> None:
    kin = IMS_ZA2115
    assert CHARACTERISTIC_HZ["bpfo"] == pytest.approx(kin.bpfo_hz, rel=0.01)
    assert CHARACTERISTIC_HZ["bpfi"] == pytest.approx(kin.bpfi_hz, rel=0.01)
    assert kin.ftf_hz == pytest.approx(kin.bpfo_hz / 16.0, rel=0.01)


@pytest.mark.unit
def test_energy_bin_values_are_unchanged() -> None:
    """Canli fft_band_energy merkezleri kilit — 236/297/278."""
    assert CHARACTERISTIC_HZ == {"bpfo": 236.0, "bpfi": 297.0, "bsf": 278.0}


@pytest.mark.unit
def test_zero_rpm_is_rejected() -> None:
    with pytest.raises(ValueError, match="pozitif"):
        za2115_kinematics(shaft_rpm=0.0)
