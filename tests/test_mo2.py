import numpy as np

from respirometry_py.mo2 import calc_MO2
from respirometry_py.conversions import conv_o2


def test_calc_MO2_linear_signal():
    # Synthetic: O2 increases linearly in umol/L translating to kPa via conv_o2
    temp_C = 25.0
    sal = 35.0
    volume_L = 1.0

    time_min = np.linspace(0, 60, 61)
    # Choose slope in kPa/min directly, then convert to umol/L for inputs
    slope_kPa_per_min_true = 0.01
    pO2_kPa = slope_kPa_per_min_true * time_min
    o2_umolL = np.array([
        conv_o2(p, from_unit="kPa", to_unit="umol_per_L", temp_C=temp_C, sal_ppt=sal)
        for p in pO2_kPa
    ])

    res = calc_MO2(time_min, o2_umolL, temp_C=temp_C, sal_ppt=sal, chamber_volume_L=volume_L)

    assert abs(res.slope_kPa_per_min - slope_kPa_per_min_true) < 1e-4
    assert res.mo2_umol_per_hr > 0.0
