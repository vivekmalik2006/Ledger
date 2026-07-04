"""
SQLAlchemy models for Ledger.

Schema notes:
- Money is stored as Integer (paise, i.e. amount * 100) rather than Float.
  Floating point is unsafe for currency math; this is a deliberate choice,
  not an oversight.
- Permission.max_auto_amount is the CURRENT adaptive auto-execute limit —
  it can rise over time (see core/boundary.py::adjust_trust). It is
  separate from absolute_ceiling, which the customer alone can raise.
- AuditLog rows are hash-chained (prev_hash -> row_hash) for tamper
  evidence. See core/audit_chain.py for the hashing logic.
"""

import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    steward_id = Column(String, unique=True, nullable=False)  # e.g. "priya"
    name = Column(String, nullable=False)

    balance_paise = Column(Integer, default=0)
    avg_monthly_surplus_paise = Column(Integer, default=0)

    risk_profile = Column(String, default="Moderate")  # Conservative | Moderate | Aggressive
    life_events = Column(JSON, default=list)  # e.g. ["idle_savings_90_days"]


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Current adaptive auto-execute limit. Rises with clean history, never
    # silently exceeds absolute_ceiling_paise.
    max_auto_amount_paise = Column(Integer, default=500000)  # ₹5,000 default

    # Hard ceiling only the customer can move. adjust_trust() will never
    # push max_auto_amount_paise past this value.
    absolute_ceiling_paise = Column(Integer, default=1000000)  # ₹10,000 default

    allowed_products = Column(JSON, default=lambda: ["SIP"])

    # Separate from max_auto_amount_paise (per-transaction ceiling). This
    # caps the SUM of autonomous actions in a rolling 30-day window, so a
    # customer can't be hit with their per-transaction limit every single
    # day and have it add up to something they never actually authorized.
    monthly_cumulative_cap_paise = Column(Integer, default=1500000)  # ₹15,000 default

    # Tracks consecutive clean autonomous actions since the last trust
    # adjustment, used by adjust_trust() to decide when to raise the limit.
    consecutive_clean_actions = Column(Integer, default=0)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    action = Column(String, nullable=False)   # e.g. "CREATE_SIP"
    reason = Column(String, nullable=False)
    rule_checked = Column(String, nullable=False)
    status = Column(String, nullable=False)
    # ACTED | BLOCKED | DECLINED | NEGOTIATED | SUCCESS_MANUAL_OVERRIDE |
    # REAUTH_REQUIRED | LIMIT_ADJUSTED

    amount_paise = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Hash chain: row_hash = SHA256(prev_hash + canonical row content).
    # prev_hash of the first row for a user is a fixed genesis string.
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False)
