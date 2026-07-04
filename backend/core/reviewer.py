"""
The Reviewer: a deterministic policy check, independent of the Advocate.

This is deliberately NOT a second LLM call. Two language models can share
the same blind spot; a fixed policy table cannot drift the way a prompt
can. The Reviewer sees inputs the Advocate never receives (the customer's
risk_profile and a static suitability policy) — that's what makes this a
real second perspective rather than the same reasoning repeated.

The Reviewer answers exactly one question: "does this proposal violate
BANK policy, independent of whatever limit the customer personally set?"
The customer's own limit is a separate, later check (see core/boundary.py).
"""

from dataclasses import dataclass

# Fraction of average monthly surplus that ANY proposal may not exceed,
# regardless of what the customer's own auto-execute limit allows. This is
# a bank-side suitability guardrail, not a customer-configurable value.
MAX_SURPLUS_FRACTION = 0.50

# Products considered unsuitable for a Conservative risk profile. In a real
# deployment this would be a bank-maintained policy table, not a constant —
# named here explicitly so the boundary is visible and auditable.
AGGRESSIVE_PRODUCTS = {"EQUITY_SIP"}


@dataclass
class ReviewResult:
    approved: bool
    reason: str
    policy_max_paise: int | None = None  # populated when a fallback is computable


def review_proposal(
    *,
    product: str,
    amount_paise: int,
    risk_profile: str,
    avg_monthly_surplus_paise: int,
) -> ReviewResult:
    """
    Deterministic suitability check. Called BEFORE the customer's own
    permission boundary — a proposal must clear both independently.
    """
    if risk_profile == "Conservative" and product in AGGRESSIVE_PRODUCTS:
        return ReviewResult(
            approved=False,
            reason=f"{product} is not offered to Conservative risk profiles under bank suitability policy.",
            policy_max_paise=0,  # no fallback amount makes an unsuitable product suitable
        )

    policy_max = int(avg_monthly_surplus_paise * MAX_SURPLUS_FRACTION)

    if amount_paise > policy_max:
        return ReviewResult(
            approved=False,
            reason=(
                f"₹{amount_paise / 100:,.0f} exceeds the bank's suitability guideline of "
                f"50% of average monthly surplus (₹{policy_max / 100:,.0f}), independent of "
                f"the customer's own configured limit."
            ),
            policy_max_paise=policy_max,
        )

    return ReviewResult(approved=True, reason="Within suitability policy.")
