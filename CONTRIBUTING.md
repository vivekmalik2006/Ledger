# Contributing

This is a hackathon submission (SBI Hackathon @ Global Fintech Fest 2026),
currently maintained by a small team. If you're a judge or reviewer poking
around: thank you for reading this far — see `docs/ARCHITECTURE.md` for the
design rationale behind the less obvious choices.

## Development setup

See the "Running it locally" section in the [README](README.md).

## Before submitting a change

- Run `pytest -v` from `backend/` — all deterministic core modules
  (`sip_calculator`, `reviewer`, `boundary`, `audit_chain`) must stay fully
  covered. If you touch the money math, add a test that would fail without
  your change.
- Run `npm run lint` from `frontend/` to type-check before committing.
- If you change `Permission` or `AuditLog` fields in
  `backend/database/models.py`, note it in `docs/ARCHITECTURE.md`'s
  "What's implemented vs. roadmap" table — schema drift from documentation
  is exactly the kind of thing that erodes trust in an audit system.

## Code boundaries worth preserving

- `core/advocate.py` (the LLM layer) must never compute a rupee amount
  from scratch — only parse a customer-stated amount or phrase an
  already-decided outcome. If you find yourself adding arithmetic to this
  file, it belongs in `core/sip_calculator.py` instead.
- `core/reviewer.py` must remain free of any LLM call. Its entire value is
  being a structurally independent, deterministic check.
- Any new state that can be logged to `AuditLog` must go through
  `core/audit_chain.py::append_audit_log()` — never construct an
  `AuditLog` row directly, or the hash chain breaks.
