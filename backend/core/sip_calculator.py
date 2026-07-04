"""
Deterministic financial math, deliberately kept out of the LLM's hands.

The Advocate's job is to notice signals and communicate clearly. Deciding
how much money to propose is a plain arithmetic rule so the same inputs
always produce the same output — reproducible for demos and defensible to
a regulator-minded reviewer.
"""

SIP_SURPLUS_FRACTION = 0.35  # propose ~35% of average monthly surplus
ROUND_TO_NEAREST_PAISE = 50000  # round to nearest ₹500
MINIMUM_PROPOSAL_PAISE = 100000  # ₹1,000 floor


def calculate_suggested_sip_paise(avg_monthly_surplus_paise: int) -> int:
    """Returns a suggested monthly SIP amount in paise, or 0 if surplus <= 0."""
    if avg_monthly_surplus_paise <= 0:
        return 0

    raw = avg_monthly_surplus_paise * SIP_SURPLUS_FRACTION
    rounded = round(raw / ROUND_TO_NEAREST_PAISE) * ROUND_TO_NEAREST_PAISE
    return max(int(rounded), MINIMUM_PROPOSAL_PAISE)
