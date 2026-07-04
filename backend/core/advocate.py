"""
The Advocate: the customer-facing reasoning layer. Uses Gemini via
structured function-calling to parse intent and compose replies.

Hard rule, enforced by construction rather than just convention: the
Advocate never calculates a rupee amount. extract_financial_intent() only
extracts an amount the CUSTOMER already stated in their own message;
compose_agent_reply() only phrases outcomes that core/sip_calculator.py,
core/reviewer.py, and core/boundary.py have already decided. If a proposal
originates from the Advocate itself (the proactive nudge path), the amount
still comes from calculate_suggested_sip_paise(), not from this module.
"""

import json
import os
from google import genai
from google.genai import types

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

_EXTRACT_FUNCTION = types.FunctionDeclaration(
    name="extract_financial_intent",
    description=(
        "Extract the customer's financial intent from their message. Always "
        "call this exactly once, even for vague or unrelated messages — in "
        "that case set intent to 'general_query'. If the customer mentions "
        "equities, stocks, or an equity fund, set product to 'EQUITY_SIP'; "
        "otherwise default to 'SIP'."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "intent": types.Schema(
                type="STRING",
                enum=["start_sip", "check_balance", "general_query"],
            ),
            "amount": types.Schema(
                type="NUMBER",
                description="Monthly amount in INR the CUSTOMER stated. Omit if none given — never guess.",
            ),
            "product": types.Schema(type="STRING", enum=["SIP", "EQUITY_SIP"]),
        },
        required=["intent"],
    ),
)
_EXTRACT_TOOL = types.Tool(function_declarations=[_EXTRACT_FUNCTION])


def extract_financial_intent(user_message: str) -> dict:
    try:
        response = _client.models.generate_content(
            model=MODEL,
            contents=f"Customer message: {user_message!r}",
            config=types.GenerateContentConfig(
                tools=[_EXTRACT_TOOL],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY", allowed_function_names=["extract_financial_intent"]
                    )
                ),
                temperature=0,
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.function_call and part.function_call.name == "extract_financial_intent":
                args = dict(part.function_call.args)
                return {
                    "intent": args.get("intent", "general_query"),
                    "amount": args.get("amount"),
                    "product": args.get("product"),
                }
        return {"intent": "general_query", "amount": None, "product": None}
    except Exception as e:
        print(f"[advocate] extraction failed: {e}")
        return {"intent": "general_query", "amount": None, "product": None}


_OBSERVATION_GUIDE = """You are Ledger's Advocate. You are opening a
conversation proactively. Write ONE to TWO sentences, warm and specific,
naming what you noticed using the customer's actual numbers. Do NOT propose
a rupee amount here — that comes from a separate, deterministic step. Never
invent numbers not given to you."""


def generate_observation(balance_paise: int, life_events: list[str]) -> str:
    if not life_events:
        return ""
    balance_rupees = balance_paise / 100
    prompt = (
        f"{_OBSERVATION_GUIDE}\n\nBalance: ₹{balance_rupees:,.0f}\n"
        f"Flagged signals: {', '.join(life_events)}\n\nWrite the observation now."
    )
    try:
        response = _client.models.generate_content(
            model=MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.4)
        )
        return response.text.strip()
    except Exception as e:
        print(f"[advocate] observation generation failed: {e}")
        return f"You've had ₹{balance_rupees:,.0f} sitting in savings, and it looks like there's room to put some of it to work."


_REPLY_VOICE_GUIDE = """You are Ledger's Advocate. Speak warmly and
directly, no jargon. Always use the customer's actual numbers from the
context given — never invent figures. Keep replies to 2-3 sentences.

Outcome-specific tone:
- ACTED: confirm what was done, one concrete next detail.
- BLOCKED: treat this as a feature. Plainly state which limit was hit and
  ask if they'd like to adjust or proceed differently. Never apologetic.
- NEGOTIATED: explain the original amount was above a limit, and that a
  smaller compliant amount is being offered instead — frame it as solving
  the problem, not just refusing it.
- REVIEWED_REJECTED: explain the proposal didn't clear the bank's own
  suitability policy (separate from their personal limit) and why.
- REAUTH_REQUIRED: explain the auto-execute limit has reached its ceiling
  and further increases need their fresh, explicit confirmation.
- GENERAL: respond helpfully and briefly."""


def compose_agent_reply(outcome_type: str, context: dict) -> str:
    prompt = f"{_REPLY_VOICE_GUIDE}\n\nOutcome type: {outcome_type}\nContext: {json.dumps(context)}\n\nWrite the reply now."
    try:
        response = _client.models.generate_content(
            model=MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.4)
        )
        text = response.text.strip()
        return text
    except Exception as e:
        print(f"[advocate] reply composition failed: {e}")
        return _fallback_reply(outcome_type, context)


def _fallback_reply(outcome_type: str, context: dict) -> str:
    """Hardcoded fallbacks so a flaky API call never blocks the demo."""
    if outcome_type == "ACTED":
        return f"Done — your ₹{context.get('amount', 0):,.0f} SIP is active."
    if outcome_type == "BLOCKED":
        return f"This is above your ₹{context.get('limit', 0):,.0f} limit, so I'm pausing here."
    if outcome_type == "NEGOTIATED":
        return f"₹{context.get('original_amount', 0):,.0f} was above your limit — I can start at ₹{context.get('offered_amount', 0):,.0f} instead. Proceed?"
    if outcome_type == "REVIEWED_REJECTED":
        return f"This proposal didn't clear our suitability policy: {context.get('reason', '')}"
    if outcome_type == "REAUTH_REQUIRED":
        return "Your auto-execute limit has reached its ceiling. Raising it further needs your explicit confirmation."
    return "I'm monitoring your account. Ask me to set up a SIP or check your audit log."
