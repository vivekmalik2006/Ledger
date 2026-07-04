"""
Hash-chained audit logging.

Each row's hash is SHA256(previous_row_hash + canonical_row_content).
Tampering with any past row changes its hash, which no longer matches what
the NEXT row's prev_hash claims — breaking the chain from that point
forward. This is deliberately simple (no blockchain infrastructure needed)
and it's provable live: edit a row directly in the DB, run verify_chain(),
watch it fail.
"""

import hashlib
from sqlalchemy.orm import Session

from database.models import AuditLog

GENESIS_HASH = "0" * 64  # prev_hash for the first row in a user's chain


def _canonical_row_string(user_id: int, action: str, reason: str, status: str, amount_paise: int | None) -> str:
    return f"{user_id}|{action}|{reason}|{status}|{amount_paise}"


def compute_row_hash(prev_hash: str, user_id: int, action: str, reason: str, status: str, amount_paise: int | None) -> str:
    payload = prev_hash + _canonical_row_string(user_id, action, reason, status, amount_paise)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_audit_log(
    db: Session,
    *,
    user_id: int,
    action: str,
    reason: str,
    rule_checked: str,
    status: str,
    amount_paise: int | None = None,
) -> AuditLog:
    """Appends a new hash-chained row. Always use this instead of
    constructing AuditLog directly — it's what guarantees the chain links."""
    last_row = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    prev_hash = last_row.row_hash if last_row else GENESIS_HASH

    row_hash = compute_row_hash(prev_hash, user_id, action, reason, status, amount_paise)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        reason=reason,
        rule_checked=rule_checked,
        status=status,
        amount_paise=amount_paise,
        prev_hash=prev_hash,
        row_hash=row_hash,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_chain(db: Session, user_id: int) -> dict:
    """
    Recomputes every row's hash from its stored content and checks it
    against both the row's own stored row_hash and the next row's
    prev_hash. Returns {"intact": bool, "broken_at_id": int | None}.
    """
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user_id)
        .order_by(AuditLog.id.asc())
        .all()
    )

    expected_prev = GENESIS_HASH
    for row in rows:
        recomputed = compute_row_hash(
            expected_prev, row.user_id, row.action, row.reason, row.status, row.amount_paise
        )
        if row.prev_hash != expected_prev or row.row_hash != recomputed:
            return {"intact": False, "broken_at_id": row.id}
        expected_prev = row.row_hash

    return {"intact": True, "broken_at_id": None}
