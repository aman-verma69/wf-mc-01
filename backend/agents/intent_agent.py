"""Open-ended conversational planner. It can suggest actions; backend services enforce them."""
import json
import os
import re
from typing import Literal
from pydantic import BaseModel, Field

INTENTS = ("SEARCH_PRODUCTS", "GET_PRODUCT_DETAILS", "ADD_TO_CART", "REMOVE_FROM_CART", "VIEW_CART", "PREPARE_CHECKOUT", "CONFIRM_PURCHASE", "CHECK_PAYMENT_STATUS", "CHAT")

class IntentDecision(BaseModel):
    intent: Literal["SEARCH_PRODUCTS", "GET_PRODUCT_DETAILS", "ADD_TO_CART", "REMOVE_FROM_CART", "VIEW_CART", "PREPARE_CHECKOUT", "CONFIRM_PURCHASE", "CHECK_PAYMENT_STATUS", "CHAT"]
    query: str = ""
    product_id: str | None = None
    quantity: int = Field(default=1, ge=1, le=10)
    response: str = ""

SYSTEM = """You are the language layer for an ecommerce assistant. Decide the user's intended action and return JSON only.
Use only product IDs included in LIVE CATALOG and only for a clearly identified product. Never state or estimate price, stock, discounts, totals, or payment status; those are supplied by the server. For general shopping questions use CHAT and give a concise helpful response. A purchase can only be confirmed when the user explicitly gives an unambiguous confirmation. Never turn 'yes' or a casual acknowledgement into CONFIRM_PURCHASE.
Allowed intents: SEARCH_PRODUCTS, GET_PRODUCT_DETAILS, ADD_TO_CART, REMOVE_FROM_CART, VIEW_CART, PREPARE_CHECKOUT, CONFIRM_PURCHASE, CHECK_PAYMENT_STATUS, CHAT.
For search, put useful search terms in query. For product operations, set product_id only if it appears in the catalog/cart context."""

def _fallback(message: str, catalog: list[dict], cart: list[dict]) -> IntentDecision:
    """Keeps fundamental shopping actions usable when no LLM key has been configured."""
    text = message.lower().strip()
    if re.fullmatch(r"(?:confirm|confirm purchase|i confirm|yes,? confirm)", text): return IntentDecision(intent="CONFIRM_PURCHASE")
    if any(word in text for word in ("checkout", "buy now", "place order")): return IntentDecision(intent="PREPARE_CHECKOUT")
    if "cart" in text or "basket" in text: return IntentDecision(intent="VIEW_CART")
    for item in catalog + cart:
        if item["id"] in text or item["name"].lower().replace(" anc", "") in text:
            if text.startswith("add"): return IntentDecision(intent="ADD_TO_CART", product_id=item["id"])
            if text.startswith(("remove", "delete")): return IntentDecision(intent="REMOVE_FROM_CART", product_id=item["id"])
    return IntentDecision(intent="SEARCH_PRODUCTS", query=message)

async def decide(message: str, catalog: list[dict], cart: list[dict], history: list[str]) -> IntentDecision:
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not base_url and not api_key:
        return _fallback(message, catalog, cart)
    from openai import AsyncOpenAI
    context = json.dumps({"live_catalog": catalog, "cart": cart, "recent_user_messages": history[-6:]}, ensure_ascii=False)
    client = AsyncOpenAI(api_key=api_key or "local", base_url=base_url)
    try:
        result = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-oss:20b"),
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER: {message}"},
            ],
            response_format={"type": "json_schema", "json_schema": {"name": "commerce_decision", "strict": True, "schema": IntentDecision.model_json_schema()}},
        )
        return IntentDecision.model_validate_json(result.choices[0].message.content or "{}")
    except Exception:
        return _fallback(message, catalog, cart)
