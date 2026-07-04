"""
Ledger backend entrypoint.

Pipeline for any proposal (customer-initiated via /api/chat, or
agent-initiated via /api/session/start) is identical, implemented once in
evaluate_proposal() below:

    Reviewer (bank policy)  ->  Boundary (customer's own limit)
         |  reject                   |  reject
         v                           v
    negotiate fallback (ONE attempt, re-runs through this same function)
         |  still rejected
         v
    pause, ask customer directly

A successful ACTED outcome also runs adjust_trust(), which may raise the
customer's auto-execute limit — hard-capped by their own absolute ceiling.
"""

import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from dotenv import load_dotenv

from database.models import Base, User, Permission
from core.advocate import extract_financial_intent, compose_agent_reply, generate_observation
from core.sip_calculator import calculate_suggested_sip_paise
from core.reviewer import review_proposal
from core.boundary import check_permission_boundary, adjust_trust
from core.audit_chain import append_audit_log, verify_chain

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ledger.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Ledger Core Engine API")

# Explicit origins in production. Wildcard is fine for local hackathon dev
# ONLY when allow_credentials is False (the two are mutually exclusive per
# the CORS spec, and browsers will reject the combination otherwise).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def evaluate_proposal(
    db: Session,
    user: User,
    permission: Permission,
    product: str,
    amount_paise: int,
    action_label: str,
    _is_fallback_attempt: bool = False,
) -> dict:
    """The shared pipeline. See module docstring for the flow."""

    # --- Reviewer: bank suitability policy, independent of customer limit ---
    review = review_proposal(
        product=product,
        amount_paise=amount_paise,
        risk_profile=user.risk_profile,
        avg_monthly_surplus_paise=user.avg_monthly_surplus_paise,
    )

    if not review.approved:
        if not _is_fallback_attempt and review.policy_max_paise:
            fallback_amount = min(amount_paise, review.policy_max_paise)
            if fallback_amount >= 100000:  # don't negotiate down to something trivial
                return _negotiate_and_retry(
                    db, user, permission, product, amount_paise, fallback_amount, action_label
                )

        append_audit_log(
            db, user_id=user.id, action=action_label, reason=review.reason,
            rule_checked="SUITABILITY_POLICY", status="BLOCKED", amount_paise=amount_paise,
        )
        reply = compose_agent_reply("REVIEWED_REJECTED", {"reason": review.reason, "amount": amount_paise / 100})
        return {"speaker": "ai", "text": reply, "requires_approval": True,
                "context": {"action": action_label, "amount": amount_paise / 100, "product": product}}

    # --- Boundary: customer's own configured limit ---
    boundary = check_permission_boundary(db, user.id, permission, product, amount_paise)

    if not boundary.allowed:
        if not _is_fallback_attempt and boundary.limit_paise:
            fallback_amount = min(amount_paise, boundary.limit_paise)
            if fallback_amount >= 100000:
                return _negotiate_and_retry(
                    db, user, permission, product, amount_paise, fallback_amount, action_label
                )

        append_audit_log(
            db, user_id=user.id, action=action_label, reason=boundary.reason,
            rule_checked="CUSTOMER_BOUNDARY", status="BLOCKED", amount_paise=amount_paise,
        )
        reply = compose_agent_reply("BLOCKED", {"amount": amount_paise / 100, "limit": permission.max_auto_amount_paise / 100})
        return {"speaker": "ai", "text": reply, "requires_approval": True,
                "context": {"action": action_label, "amount": amount_paise / 100, "product": product}}

    # --- Clears both checks: execute ---
    append_audit_log(
        db, user_id=user.id, action=action_label,
        reason="Cleared suitability policy and customer boundary.",
        rule_checked="SUITABILITY_AND_BOUNDARY", status="ACTED", amount_paise=amount_paise,
    )

    trust_event = adjust_trust(db, permission)
    if trust_event:
        append_audit_log(
            db, user_id=user.id, action="TRUST_ADJUSTMENT", reason=trust_event["reason"],
            rule_checked="ADAPTIVE_TRUST_CEILING", status=trust_event["event"], amount_paise=None,
        )
    db.commit()

    reply = compose_agent_reply("ACTED", {"amount": amount_paise / 100, "product": product})
    return {"speaker": "ai", "text": reply, "requires_approval": False}


def _negotiate_and_retry(db, user, permission, product, original_amount_paise, fallback_amount_paise, action_label):
    append_audit_log(
        db, user_id=user.id, action=action_label,
        reason=f"₹{original_amount_paise/100:,.0f} blocked — negotiated down to ₹{fallback_amount_paise/100:,.0f}.",
        rule_checked="NEGOTIATED_FALLBACK", status="NEGOTIATED", amount_paise=fallback_amount_paise,
    )
    result = evaluate_proposal(
        db, user, permission, product, fallback_amount_paise, action_label, _is_fallback_attempt=True
    )
    if not result["requires_approval"]:
        # fallback cleared — rewrite the reply to acknowledge the negotiation
        reply = compose_agent_reply("NEGOTIATED", {
            "original_amount": original_amount_paise / 100,
            "offered_amount": fallback_amount_paise / 100,
        })
        result["text"] = reply
    return result


# --------------------------------------------------------------------------


class ChatRequest(BaseModel):
    user_id: int
    message: str


@app.post("/api/chat")
async def handle_agent_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    permission = db.query(Permission).filter(Permission.user_id == user.id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission profile not found")

    parsed = extract_financial_intent(payload.message)
    if parsed["intent"] != "start_sip" or parsed["amount"] is None:
        reply = compose_agent_reply("GENERAL", {"user_message": payload.message})
        return {"speaker": "ai", "text": reply, "requires_approval": False}

    amount_paise = int(parsed["amount"] * 100)
    product = parsed.get("product") or "SIP"
    return evaluate_proposal(db, user, permission, product, amount_paise, action_label="CREATE_SIP")


@app.get("/api/session/start/{user_id}")
async def start_session(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    permission = db.query(Permission).filter(Permission.user_id == user.id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission profile not found")

    if not user.life_events:
        return {"speaker": "ai", "text": f"Hi {user.name} — everything looks steady. Ask me anything.",
                "requires_approval": False}

    observation = generate_observation(user.balance_paise, user.life_events)
    suggested_paise = calculate_suggested_sip_paise(user.avg_monthly_surplus_paise)

    if suggested_paise <= 0:
        return {"speaker": "ai", "text": observation, "requires_approval": False}

    outcome = evaluate_proposal(db, user, permission, "SIP", suggested_paise, action_label="PROACTIVE_SIP_NUDGE")
    outcome["text"] = f"{observation} {outcome['text']}"
    return outcome


class ApprovalRequest(BaseModel):
    user_id: int
    approved: bool
    action: str
    amount: float
    product: str = "SIP"


@app.post("/api/chat/approve")
async def handle_approval(payload: ApprovalRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    amount_paise = int(payload.amount * 100)

    if not payload.approved:
        append_audit_log(
            db, user_id=user.id, action=payload.action,
            reason="Customer declined to proceed after a pause.",
            rule_checked="CUSTOMER_DECISION", status="DECLINED", amount_paise=amount_paise,
        )
        return {"speaker": "ai", "text": "Understood — I've stood down. No action taken.", "requires_approval": False}

    append_audit_log(
        db, user_id=user.id, action=payload.action,
        reason=f"Customer explicitly approved ₹{payload.amount:,.0f} despite an earlier pause.",
        rule_checked="CUSTOMER_DECISION", status="SUCCESS_MANUAL_OVERRIDE", amount_paise=amount_paise,
    )
    reply = compose_agent_reply("ACTED", {"amount": payload.amount, "product": payload.product})
    return {"speaker": "ai", "text": reply, "requires_approval": False}


@app.get("/api/audit/{user_id}")
async def get_audit_log(user_id: int, db: Session = Depends(get_db)):
    from database.models import AuditLog
    logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(AuditLog.id.desc()).all()
    return [
        {
            "id": log.id, "action": log.action, "reason": log.reason,
            "rule_checked": log.rule_checked, "status": log.status,
            "amount": (log.amount_paise / 100) if log.amount_paise is not None else None,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


@app.get("/api/audit/{user_id}/verify")
async def verify_audit_integrity(user_id: int, db: Session = Depends(get_db)):
    """Recomputes the hash chain and confirms no past row has been altered."""
    return verify_chain(db, user_id)
