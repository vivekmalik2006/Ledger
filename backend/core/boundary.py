"""
The boundary engine: checks a proposal against the CUSTOMER's own
configured limits (as opposed to core/reviewer.py, which checks bank
policy). Also owns adaptive trust — the mechanism by which clean history
gradually raises a customer's auto-execute limit, hard-capped by a ceiling
only the customer can move.

Design constraint, stated explicitly because it matters for the pitch: no
function in this file can ever move max_auto_amount_paise past
absolute_ceiling_paise. Reaching that ceiling raises a REAUTH_REQUIRED
event instead of a further increase.
"""

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import AuditLog, Permission

# How many consecutive clean autonomous actions before the auto-execute
# limit is nudged upward.
TRUST_INCREMENT_THRESHOLD = 5

# How much to raise the limit by, per adjustment.
TRUST_INCREMENT_PAISE = 100000  # ₹1,000

CUMULATIVE_WINDOW_DAYS = 30


@dataclass
class BoundaryResult:
    allowed: bool
    reason: str
    limit_paise: int | None = None


def check_permission_boundary(
    db: Session, user_id: int, permission: Permission, product: str, amount_paise: int
) -> BoundaryResult:
    if product not in permission.allowed_products:
        return BoundaryResult(
            allowed=False,
            reason=f"'{product}' is not in the customer's currently authorized product list.",
        )

    if amount_paise > permission.max_auto_amount_paise:
        return BoundaryResult(
            allowed=False,
            reason=(
                f"₹{amount_paise / 100:,.0f} exceeds the customer's auto-execute limit of "
                f"₹{permission.max_auto_amount_paise / 100:,.0f}."
            ),
            limit_paise=permission.max_auto_amount_paise,
        )

    cumulative = _rolling_autonomous_total_paise(db, user_id)
    if cumulative + amount_paise > permission.monthly_cumulative_cap_paise:
        return BoundaryResult(
            allowed=False,
            reason=(
                f"This would bring autonomous actions in the last {CUMULATIVE_WINDOW_DAYS} days to "
                f"₹{(cumulative + amount_paise) / 100:,.0f}, above the customer's monthly cap of "
                f"₹{permission.monthly_cumulative_cap_paise / 100:,.0f}. A limit is a monthly budget, "
                f"not a per-transaction loophole to repeat."
            ),
            limit_paise=max(0, permission.monthly_cumulative_cap_paise - cumulative),
        )

    return BoundaryResult(allowed=True, reason="Within customer-configured limits.")


def _rolling_autonomous_total_paise(db: Session, user_id: int) -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=CUMULATIVE_WINDOW_DAYS)
    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user_id,
            AuditLog.status == "ACTED",
            AuditLog.timestamp >= cutoff,
        )
        .all()
    )
    return sum(r.amount_paise or 0 for r in rows)


def adjust_trust(db: Session, permission: Permission) -> dict | None:
    """
    Call after a clean ACTED outcome. Increments the consecutive-clean
    counter; once it crosses TRUST_INCREMENT_THRESHOLD, raises the
    auto-execute limit by TRUST_INCREMENT_PAISE — UNLESS doing so would
    exceed absolute_ceiling_paise, in which case it returns a
    REAUTH_REQUIRED signal instead and does not adjust the limit further.

    Returns a dict describing what happened (for audit logging), or None
    if no adjustment was due yet.
    """
    permission.consecutive_clean_actions += 1

    if permission.consecutive_clean_actions < TRUST_INCREMENT_THRESHOLD:
        return None

    permission.consecutive_clean_actions = 0
    proposed_new_limit = permission.max_auto_amount_paise + TRUST_INCREMENT_PAISE

    if proposed_new_limit > permission.absolute_ceiling_paise:
        return {
            "event": "REAUTH_REQUIRED",
            "reason": (
                f"Auto-execute limit has reached the customer's absolute ceiling of "
                f"₹{permission.absolute_ceiling_paise / 100:,.0f}. Further increases require "
                f"fresh explicit re-authorization — the system cannot expand its own authority."
            ),
        }

    old_limit = permission.max_auto_amount_paise
    permission.max_auto_amount_paise = proposed_new_limit
    return {
        "event": "LIMIT_ADJUSTED",
        "reason": (
            f"5 consecutive clean autonomous actions — auto-execute limit raised from "
            f"₹{old_limit / 100:,.0f} to ₹{proposed_new_limit / 100:,.0f}, within the customer's "
            f"₹{permission.absolute_ceiling_paise / 100:,.0f} ceiling."
        ),
    }
