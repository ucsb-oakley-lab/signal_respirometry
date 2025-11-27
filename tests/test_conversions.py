import math
import pytest

from respirometry_py.conversions import conv_o2, conv_resp_unit


def test_conv_o2_symmetry_standard_conditions():
    temp_C = 25.0
    sal = 35.0
    # 1 kPa -> X umol/L -> back to ~1 kPa
    umolL = conv_o2(1.0, from_unit="kPa", to_unit="umol_per_L", temp_C=temp_C, sal_ppt=sal)
    kPa = conv_o2(umolL, from_unit="umol_per_L", to_unit="kPa", temp_C=temp_C, sal_ppt=sal)
    assert pytest.approx(kPa, rel=1e-6) == 1.0


def test_conv_resp_unit_ideal_gas_25C():
    # 1 umol/g/hr -> mL/mg/hr at 25 C and 101.325 kPa
    ml_mg_hr = conv_resp_unit(1.0, from_unit="umol_g_hr", to_unit="mL_mg_hr", temp_C=25.0, pressure_kPa=101.325)
    # Ideal molar volume ~ 24.47 L/mol => 24.47 uL/umol; then per g->mg divide by 1000
    expected_ml_mg_hr = (24.47 / 1000.0) / 1000.0  # mL per mg per umol/hr
    assert pytest.approx(ml_mg_hr, rel=0.05) == expected_ml_mg_hr


def test_conv_resp_unit_ul():
    ul_mg_hr = conv_resp_unit(2.0, from_unit="umol_g_hr", to_unit="uL_mg_hr", temp_C=20.0, pressure_kPa=101.325)
    assert ul_mg_hr > 0.0
