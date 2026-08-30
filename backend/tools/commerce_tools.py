"""
LLM-callable tool wrappers. Rule for this file: NO business logic lives
here — every function just validates shape and calls into services/ or
integrations/. If you find yourself writing an if/else that decides
whether a payment should happen, that belongs in policy/guardrail.py,
not here.

These are the OpenAI/Grok-style tool schemas + their Python implementations,
used by backend/agents/*.
"""
import re
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.tavily.client import search as tavily_search
from backend.services.checkout_service import CheckoutAwaitingConfirmation, CheckoutBlocked, initiate_checkout


def extract_inr_price(value: str | None) -> int | None:
    """Extract a price in INR currency units (not paise) from a raw string."""
    if not value:
        return None

    text = value.lower().replace("₹", "rs ")
    match = re.search(r"(?:rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d+)?)", text)
    if not match:
        match = re.search(r"([0-9][0-9,]*(?:\.\d+)?)\s*(?:rs|inr)", text)
    if not match:
        return None

    num = match.group(1).replace(",", "")
    try:
        return int(float(num))
    except ValueError:
        return None


def normalize_search_results(search_response: dict | None) -> list[dict]:
    """Normalize Tavily search results into the app's strict product card shape."""
    if not isinstance(search_response, dict):
        return []

    results = search_response.get("results") or []
    products: list[dict] = []

    for item in results:
        if not isinstance(item, dict):
            continue

        title = (item.get("title") or "Product").strip()
        url = item.get("url")
        content = item.get("content") or ""
        source = item.get("source") or (urlparse(url).netloc if url else "search")
        image_url = item.get("image_url") or item.get("thumbnail") or (search_response.get("images") or [None])[0]
        price = item.get("price")
        if price is None:
            price = extract_inr_price(f"{title} {content}")
        else:
            try:
                price = int(float(str(price).replace(",", "")))
            except (TypeError, ValueError):
                price = extract_inr_price(str(price))

        availability = "unknown"
        text = f"{title} {content}".lower()
        if "out of stock" in text or "sold out" in text:
            availability = "out_of_stock"
        elif "in stock" in text or "available" in text:
            availability = "in_stock"

        product = {
            "id": item.get("id") or str(url or title),
            "name": title,
            "price": int(price) if isinstance(price, (int, float)) else None,
            "currency": "INR",
            "image_url": image_url,
            "source": source,
            "product_url": url,
            "availability": availability,
            "metadata": {
                "content": content[:500],
                "score": item.get("score"),
            },
        }
        products.append(product)

    return products

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current product, pricing, or trend information via Tavily.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_checkout",
            "description": "Start a checkout for a customer's cart. Goes through the guardrail gate — may be blocked or escalated for human confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "amount_paise": {"type": "integer", "description": "Total amount in paise (smallest INR unit)"},
                    "cart_snapshot": {"type": "object", "description": "Line items and quantities"},
                },
                "required": ["customer_id", "amount_paise", "cart_snapshot"],
            },
        },
    },
]


async def run_tool(
    db: AsyncSession,
    *,
    actor: str,
    name: str,
    arguments: dict,
    delegation_scope: list[str] | None = None,
) -> dict:
    """Dispatch a tool call by name. Called from workflows/commerce_workflow.py
    after an agent's LLM response includes a tool_call.
    """
    if name == "search_web":
        result = tavily_search(arguments["query"])
        products = normalize_search_results(result)
        return {"ok": True, "result": result, "products": products}

    if name == "initiate_checkout":
        try:
            order = await initiate_checkout(
                db,
                actor=actor,
                customer_id=arguments["customer_id"],
                amount_paise=arguments["amount_paise"],
                cart_snapshot=arguments["cart_snapshot"],
                delegation_scope=delegation_scope,
            )
            return {"ok": True, "order_id": order.id, "status": order.status.value}
        except CheckoutBlocked as e:
            return {"ok": False, "reason": e.reason, "decision": "blocked"}
        except CheckoutAwaitingConfirmation as e:
            return {"ok": False, "order_id": e.order_id, "reason": e.reason, "decision": "escalated"}

    return {"ok": False, "reason": f"Unknown tool: {name}"}
