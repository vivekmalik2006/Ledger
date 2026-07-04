"""
Seeds three demo personas, deliberately tuned so the deterministic pipeline
lands on a different, reproducible outcome for each — no randomness, same
result every run.

  Priya  -> proactive nudge clears both Reviewer and boundary -> ACTED
  Vivek  -> proactive nudge exceeds his personal limit -> NEGOTIATED down
            to his limit, which then clears -> ACTED at the lower amount
  Arjun  -> Conservative risk profile. Typing a message like "start an
            equity SIP of 5000" during the demo triggers a hard, NON-
            negotiated Reviewer rejection — no fallback amount can make an
            unsuitable PRODUCT suitable, unlike an amount that's merely
            too large. His personal limit is generous, making clear the
            block is a suitability call independent of his own limit.

Run from backend/: python -m scripts.populate_demo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, User, Permission

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ledger.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


PERSONAS = [
    {
        "steward_id": "priya", "name": "Priya", "balance_paise": 50_000_00,
        "avg_monthly_surplus_paise": 22_000_00, "risk_profile": "Moderate",
        "life_events": ["idle_savings_90_days", "no_investment_account"],
        "max_auto_amount_paise": 25_000_00, "absolute_ceiling_paise": 50_000_00,
        "monthly_cumulative_cap_paise": 40_000_00,
    },
    {
        "steward_id": "vivek", "name": "Vivek", "balance_paise": 75_000_00,
        "avg_monthly_surplus_paise": 18_000_00, "risk_profile": "Moderate",
        "life_events": ["idle_savings_90_days"],
        "max_auto_amount_paise": 5_000_00, "absolute_ceiling_paise": 15_000_00,
        "monthly_cumulative_cap_paise": 10_000_00,
    },
    {
        "steward_id": "arjun", "name": "Arjun", "balance_paise": 1_20_000_00,
        "avg_monthly_surplus_paise": 26_000_00, "risk_profile": "Conservative",
        "life_events": ["large_idle_balance"],
        # Conservative risk profile + an explicit equity request (e.g. typing
        # "start an equity SIP of 5000" during the demo) triggers a hard,
        # non-negotiated Reviewer rejection — no fallback amount can make an
        # unsuitable PRODUCT suitable, unlike an amount that's merely too
        # large. His personal limit stays generous to make clear the block
        # is a suitability call, independent of what his own limit allows.
        "max_auto_amount_paise": 50_000_00, "absolute_ceiling_paise": 75_000_00,
        "monthly_cumulative_cap_paise": 60_000_00,
    },
]


def populate():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)

        for p in PERSONAS:
            user = db.query(User).filter(User.steward_id == p["steward_id"]).first()
            if not user:
                user = User(
                    steward_id=p["steward_id"], name=p["name"], balance_paise=p["balance_paise"],
                    avg_monthly_surplus_paise=p["avg_monthly_surplus_paise"],
                    risk_profile=p["risk_profile"], life_events=p["life_events"],
                )
                db.add(user)
                db.flush()
                print(f"Added user: {p['name']} (id={user.id})")
            else:
                user.balance_paise = p["balance_paise"]
                user.avg_monthly_surplus_paise = p["avg_monthly_surplus_paise"]
                user.risk_profile = p["risk_profile"]
                user.life_events = p["life_events"]
                print(f"Updated user: {p['name']} (id={user.id})")

            perm = db.query(Permission).filter(Permission.user_id == user.id).first()
            if not perm:
                perm = Permission(
                    user_id=user.id,
                    max_auto_amount_paise=p["max_auto_amount_paise"],
                    absolute_ceiling_paise=p["absolute_ceiling_paise"],
                    monthly_cumulative_cap_paise=p["monthly_cumulative_cap_paise"],
                    allowed_products=["SIP"],
                )
                db.add(perm)
            else:
                perm.max_auto_amount_paise = p["max_auto_amount_paise"]
                perm.absolute_ceiling_paise = p["absolute_ceiling_paise"]
                perm.monthly_cumulative_cap_paise = p["monthly_cumulative_cap_paise"]

        db.commit()
        print("Seed complete.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate()
