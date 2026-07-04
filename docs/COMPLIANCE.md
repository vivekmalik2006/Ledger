# Compliance Positioning

This document exists because at a SEBI-hosted hackathon, "what is this
system legally doing" is the first question a sharp reviewer will ask, and
it deserves a direct written answer rather than a slide bullet.

## What Ledger is not

Ledger is not an investment adviser under SEBI's Investment Adviser
Regulations. It does not:

- Originate a new, personalized investment recommendation the customer
  hasn't already authorized the shape of in advance.
- Select products outside what the bank is already SEBI-registered to
  distribute.
- Expand its own decision-making authority without the customer's fresh,
  explicit consent (see `REAUTH_REQUIRED` in `docs/ARCHITECTURE.md`).

## What Ledger is

Ledger executes a rule the customer configured in advance — legally
analogous to a standing instruction or e-NACH mandate, both of which banks
already operate without triggering Investment Adviser registration, because
the customer authorizes the parameters up front. Ledger's AI layer decides
only:

1. **When** to trigger an already-authorized rule (based on account
   signals), and
2. **Whether** a specific instance of it clears the bank's own suitability
   policy (via the Reviewer) and the customer's own configured limit (via
   the boundary check).

It never decides **what** the customer is allowed to invest in beyond the
product shelf and parameters they already set.

## Current implementation status

Being direct about where the prototype currently stands relative to this
framing, since a repository that matches its claims exactly is more
credible than one that overstates them:

- The Reviewer's suitability policy (`core/reviewer.py`) is a small,
  illustrative rule set (surplus-fraction cap, risk-profile/product
  matching) — a production deployment would replace this with the bank's
  actual, comprehensive suitability framework. The *architecture* (an
  independent, deterministic check before any autonomous action) is the
  contribution; the specific rules are a placeholder.
- There is no real product-shelf restriction enforced in code yet — the
  system currently only "knows" about `SIP` and `EQUITY_SIP` as product
  identifiers. A production version would validate against the bank's
  actual registered product catalog.
- Authentication is not implemented (see README "Known limitations"). Any
  production deployment would sit behind the bank's existing SSO/OTP
  infrastructure before this pipeline is reachable at all.

## Data handling

Account signals (balance, surplus, life events) are sent to Google's Gemini
API only for the Advocate's language tasks (intent parsing, phrasing) — never
for the Reviewer's suitability check or the boundary check, both of which run
entirely in local, deterministic code with no external calls. A production
deployment would need an explicit customer opt-in step before any account
data reaches a third-party API, aligned with the DPDP Act; this consent flow
is not yet built and is listed as a roadmap item, not a built feature.
