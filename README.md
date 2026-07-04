# Ledger

**The self-checking AI co-pilot for digital wealth adoption.**

Built for SBI Hackathon @ Global Fintech Fest 2026 — Agentic AI & Emerging
Tech, Digital Adoption.

> Every other agentic AI demo shows you an action. Ledger shows you a
> boundary that checks itself, negotiates instead of dead-ending, and grows
> its own authority only within a ceiling the human drew — with a
> tamper-evident record of all of it.

---

## What this is

Ledger notices idle savings in a customer's account and proactively starts
a conversation about investing — but the interesting part isn't the
nudge, it's what happens after:

1. **A proposing AI (the Advocate) and an independent, deterministic
   Reviewer** — not one model checking itself twice. The Reviewer sees
   inputs the Advocate never gets: the customer's risk profile and a fixed
   bank suitability policy.
2. **Blocked proposals don't dead-end.** The system computes and offers the
   largest compliant alternative, which is re-evaluated through the exact
   same pipeline — no special-cased shortcut.
3. **Clean autonomous history gradually raises the customer's auto-execute
   limit — hard-capped.** No amount of clean history can push the limit
   past a ceiling only the customer can move.
4. **Every decision is written to a hash-chained audit log.** Tampering
   with any past entry is provably detectable — see
   `GET /api/audit/{user_id}/verify`.

Full reasoning behind each of these choices, including what we deliberately
did **not** build (a second LLM as the Reviewer, an unbounded trust curve),
is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Compliance positioning

Ledger is not an investment adviser — it executes rules the
customer pre-authorized, the same legal shape as a standing instruction.
Full reasoning in [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md).

## Status: idea-submission stage

This repository demonstrates the **core deterministic engine** — the parts
that carry the actual trust claims — fully implemented and tested. It is
not a polished end-to-end product yet; see "Known limitations" below for
an honest accounting of what's built versus what's roadmap.

| Component | Status |
|---|---|
| SIP calculator (deterministic) | ✅ Built + tested |
| Reviewer (suitability policy engine) | ✅ Built + tested |
| Boundary engine (limits, cumulative cap, adaptive trust) | ✅ Built + tested |
| Hash-chained audit log | ✅ Built + tested |
| Advocate (Gemini-backed reasoning) | ✅ Built |
| Full pipeline wiring (FastAPI) | ✅ Built |
| Frontend (chat + live audit trail) | ✅ Built |
| Authentication | ❌ Not implemented |
| Database migrations | ❌ Not implemented |
| Re-auth flow for `REAUTH_REQUIRED` | ❌ Logged only, no UI yet |

## Architecture at a glance

```
Customer message  ─┐
                    ├──> Advocate (Gemini) ──> proposed amount
Proactive nudge   ──┘         determined by deterministic
                               sip_calculator.py, never the LLM
                                       │
                                       v
                    Reviewer (deterministic, independent of Advocate)
                                       │
                            ┌──────────┴──────────┐
                        rejected                approved
                            │                       │
                    negotiate fallback      Boundary check (customer's limit)
                    (one attempt, re-runs           │
                    through this pipeline)  ┌────────┴────────┐
                                          rejected          approved
                                             │                  │
                                      negotiate fallback      ACT
                                                              + adjust_trust()
                                       │
                                       v
                          Hash-chained audit log (all outcomes)
```

## Repository layout

```
backend/
  main.py              # FastAPI app, wires the full pipeline
  core/
    advocate.py        # Gemini-backed reasoning — language only, never money
    reviewer.py         # Deterministic suitability policy engine
    boundary.py          # Customer limits, cumulative cap, adaptive trust
    sip_calculator.py     # Deterministic SIP amount formula
    audit_chain.py          # Hash-chained audit log
  database/
    models.py            # SQLAlchemy schema (money stored as integer paise)
  scripts/
    populate_demo.py     # Seeds 3 personas tuned to hit ACT / NEGOTIATE / hard-reject
  tests/                  # pytest suite covering every deterministic module
frontend/
  src/
    components/           # ChatPanel, AuditTrail, PersonaSwitcher
    hooks/useLedgerChat.ts # Chat session state + proactive nudge trigger
    lib/api.ts              # Typed API client
docs/
  ARCHITECTURE.md          # Design rationale, pipeline detail
  COMPLIANCE.md             # Regulatory positioning, written out in full
```

## Running it locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in GEMINI_API_KEY
python -m scripts.populate_demo
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
pytest -v
```

The deterministic core (`sip_calculator`, `reviewer`, `boundary`,
`audit_chain`) is fully covered, including a test that actually tampers
with a database row and confirms `verify_chain()` catches it — see
`backend/tests/test_audit_chain.py::test_tampering_with_a_row_breaks_the_chain`.

## Demo script

Three seeded personas (`backend/scripts/populate_demo.py`), each tuned to
reliably hit a different outcome — no randomness, same result every run:

- **Priya** — proactive nudge clears both the Reviewer and her limit ->
  **ACTED**.
- **Vivek** — proactive nudge exceeds his personal limit -> **NEGOTIATED**
  down to his limit, which then clears -> **ACTED** at the lower amount.
- **Arjun** — Conservative risk profile. Type a message like *"start an
  equity SIP of 5000"* -> hard, non-negotiated **Reviewer rejection** — no
  fallback amount can fix a product suitability mismatch, unlike an amount
  that's merely too large.

## Known limitations

Stated directly rather than discovered by a reviewer reading the code:

- **No authentication.** `user_id` is a plain field in the request body.
  A production deployment would sit behind the bank's existing SSO/OTP —
  this prototype does not implement that layer.
- **`POST /api/chat/approve` trusts client-supplied amounts.** It should
  validate against the original blocked proposal server-side (e.g. via a
  `pending_action_id`) rather than trusting whatever the client echoes
  back. Not yet implemented.
- **No database migrations.** Schema changes currently require dropping
  and reseeding the dev database. Alembic is the obvious next step.
- **The Reviewer's policy table is illustrative, not exhaustive** — see
  `docs/COMPLIANCE.md` for what a production suitability framework would
  need to add.
- **No idempotency keys** on state-changing endpoints — a retried request
  could double-log an outcome.

## License

MIT — see [`LICENSE`](LICENSE).
