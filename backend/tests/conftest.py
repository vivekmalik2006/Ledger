import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, User, Permission


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(db_session):
    user = User(
        steward_id="test_user", name="Test User", balance_paise=100_000_00,
        avg_monthly_surplus_paise=20_000_00, risk_profile="Moderate",
        life_events=["idle_savings_90_days"],
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def sample_permission(db_session, sample_user):
    perm = Permission(
        user_id=sample_user.id,
        max_auto_amount_paise=10_000_00,
        absolute_ceiling_paise=20_000_00,
        monthly_cumulative_cap_paise=30_000_00,
        allowed_products=["SIP"],
        consecutive_clean_actions=0,
    )
    db_session.add(perm)
    db_session.flush()
    return perm
