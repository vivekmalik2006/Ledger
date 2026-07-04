import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sip_calculator import calculate_suggested_sip_paise


def test_zero_surplus_returns_zero():
    assert calculate_suggested_sip_paise(0) == 0


def test_negative_surplus_returns_zero():
    assert calculate_suggested_sip_paise(-50000) == 0


def test_typical_surplus_rounds_to_nearest_500():
    # 22,000 * 0.35 = 7,700 -> rounds to nearest 500 -> 7,500
    result_paise = calculate_suggested_sip_paise(22_000_00)
    assert result_paise == 7_500_00


def test_small_surplus_floors_at_minimum():
    # Even a tiny positive surplus should never suggest less than ₹1,000
    result_paise = calculate_suggested_sip_paise(100_00)
    assert result_paise == 1_000_00


def test_deterministic_same_input_same_output():
    a = calculate_suggested_sip_paise(18_000_00)
    b = calculate_suggested_sip_paise(18_000_00)
    assert a == b
