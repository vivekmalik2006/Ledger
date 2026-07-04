# Architecture

## Pipeline overview

Every proposal — whether it originates from the customer typing a message
(`POST /api/chat`) or from Ledger noticing something on its own
(`GET /api/session/start/{user_id}`) — runs through the exact same function:
`evaluate_proposal()` in `backend/main.py`. This is deliberate: proactive and
reactive proposals must be held to identical rules, or "bounded autonomy"
is just a slogan.

```
Observe (Advocate or parsed message)
        |
        v
   Propose amount
   (deterministic math — core/sip_calculator.py — NEVER the LLM)
        |
        v
   Reviewer check (core/reviewer.py)
   independent of the customer's own limit
        |
   +----+----+
   | reject  | approve
   v         v
 negotiate   Boundary check (core/boundary.py)
 (ONE        customer's own limit + 30-day cumulative cap
 attempt,    |
 re-enters   +----+----+
 this same   | reject  | approve
 pipeline)   v         v
           negotiate   ACT
           (same as    |
           above)      v
                    adjust_trust()
                    may raise auto-execute limit,
                    hard-capped by absolute_ceiling
```

## Why the Reviewer is not a second LLM call

Two language models sharing the same architecture can share the same blind
spot — a prompt-level check is not a structurally independent check. The
Reviewer (`core/reviewer.py`) is a deterministic rules engine with **no LLM
involvement at all**. It evaluates inputs the Advocate never receives (the
customer's `risk_profile`, a fixed suitability policy table), which is what
makes it a genuine second perspective rather than the same reasoning
repeated with different instructions.

## Why money is never calculated by the LLM

`core/advocate.py` calls Gemini for exactly two things: parsing a customer's
stated intent out of free text, and phrasing an already-decided outcome in
natural language. Every rupee figure in the system originates from
`core/sip_calculator.py` (a fixed formula) or from an amount the customer
explicitly typed themselves. This is a hard constraint enforced by module
boundaries, not just a prompt instruction — the Advocate module has no code
path that produces a number the deterministic layer didn't already decide.

## Hash-chained audit log

Implemented in `core/audit_chain.py`. Each row's `row_hash` is
`SHA256(previous_row's row_hash + this row's content)`. Tampering with any
past row's content changes its hash, which no longer matches what the next
row's `prev_hash` claims — breaking the chain from that point forward.
`GET /api/audit/{user_id}/verify` recomputes the entire chain from stored
content and reports the first broken link, if any.

This is intentionally NOT blockchain infrastructure — a single, well-tested
hashing function achieves the same tamper-evidence property for this use
case without the operational overhead.

## Adaptive trust, hard-capped

`core/boundary.py::adjust_trust()` raises a customer's `max_auto_amount_paise`
by a fixed increment after `TRUST_INCREMENT_THRESHOLD` consecutive clean
autonomous actions. It is structurally incapable of pushing that limit past
`Permission.absolute_ceiling_paise` — see `test_adjust_trust_never_exceeds_
absolute_ceiling` in `backend/tests/test_boundary.py`, which asserts this
directly rather than trusting the implementation by inspection. Reaching
the ceiling produces a `REAUTH_REQUIRED` audit event instead of a further
increase.

## Money representation

All amounts are stored and computed as `Integer` paise (rupees × 100), not
`Float`. Floating-point rounding errors compound in financial math; this is
a deliberate choice made at the schema level (`database/models.py`), not an
optimization applied later.

## What's implemented vs. roadmap

**Implemented and tested:**
- Deterministic SIP calculation, Reviewer suitability policy, boundary
  checks (per-transaction + 30-day cumulative), adaptive trust with hard
  ceiling, hash-chained audit log — all covered by unit tests in
  `backend/tests/`.
- Full pipeline wiring in `main.py`, including the one-attempt negotiated
  fallback.
- Frontend: chat interface, live-polling audit trail with a working
  "verify chain" button that calls the real verification endpoint.

**Explicitly not implemented yet (hackathon-stage honesty):**
- Real authentication (currently a plain `user_id` in the request body —
  see `docs/COMPLIANCE.md` and the README's "Known limitations" section).
- A real re-authentication flow for `REAUTH_REQUIRED` (currently logged as
  an event; there's no OTP/confirmation UI wired to it yet).
- Database migrations (Alembic) — schema changes currently require
  recreating the dev database.
- Vernacular/regional language support (roadmap item, not built).
