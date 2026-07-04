import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.reviewer import review_proposal


def test_approves_within_surplus_fraction():
    result = review_proposal(
        product="SIP", amount_paise=5_000_00, risk_profile="Moderate",
        avg_monthly_surplus_paise=20_000_00,
    )
    assert result.approved is True


def test_rejects_amount_exceeding_surplus_fraction():
    # 50% of 20,000 = 10,000. Proposing 15,000 should be rejected.
    result = review_proposal(
        product="SIP", amount_paise=15_000_00, risk_profile="Moderate",
        avg_monthly_surplus_paise=20_000_00,
    )
    assert result.approved is False
    assert result.policy_max_paise == 10_000_00


def test_conservative_profile_rejects_equity_regardless_of_amount():
    # Even a tiny, easily-affordable amount should be rejected for product
    # unsuitability — no fallback amount can fix a product mismatch.
    result = review_proposal(
        product="EQUITY_SIP", amount_paise=100_00, risk_profile="Conservative",
        avg_monthly_surplus_paise=50_000_00,
    )
    assert result.approved is False
    assert result.policy_max_paise == 0


def test_moderate_profile_allows_equity():
    result = review_proposal(
        product="EQUITY_SIP", amount_paise=5_000_00, risk_profile="Moderate",
        avg_monthly_surplus_paise=20_000_00,
    )
    assert result.approved is True


def test_boundary_exactly_at_fifty_percent_is_allowed():
    # amount == policy_max should pass (strictly greater-than is what rejects)
    result = review_proposal(
        product="SIP", amount_paise=10_000_00, risk_profile="Moderate",
        avg_monthly_surplus_paise=20_000_00,
    )
    assert result.approved is True
