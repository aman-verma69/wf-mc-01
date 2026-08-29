"""
LLM-callable tool wrappers. Rule for this file: NO business logic lives
here — every function just validates shape and calls into services/ or
integrations/. If you find yourself writing an if/else that decides
whether a payment should happen, that belongs in policy/guardrail.py,
not here.

These are the OpenAI/Grok-style tool schemas + their Python implementations,
used by backend/agents/*.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.tavily.client import search as tavily_search
from backend.services.checkout_service import CheckoutAwaitingConfirmation, CheckoutBlocked, initiate_checkout

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


async def run_tool(db: AsyncSession, *, actor: str, name: str, arguments: dict) -> dict:
    """Dispatch a tool call by name. Called from workflows/commerce_workflow.py
    after an agent's LLM response includes a tool_call.
    """
    if name == "search_web":
        result = tavily_search(arguments["query"])
        return {"ok": True, "result": result}

    if name == "initiate_checkout":
        try:
            order = await initiate_checkout(
                db,
                actor=actor,
                customer_id=arguments["customer_id"],
                amount_paise=arguments["amount_paise"],
                cart_snapshot=arguments["cart_snapshot"],
            )
            return {"ok": True, "order_id": order.id, "status": order.status.value}
        except CheckoutBlocked as e:
            return {"ok": False, "reason": e.reason, "decision": "blocked"}
        except CheckoutAwaitingConfirmation as e:
            return {"ok": False, "order_id": e.order_id, "reason": e.reason, "decision": "escalated"}

    return {"ok": False, "reason": f"Unknown tool: {name}"}
