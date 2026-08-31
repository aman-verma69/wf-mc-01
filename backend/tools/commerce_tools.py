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


PRODUCT_KEYWORDS = {
    "headphone",
    "headphones",
    "earbud",
    "earbuds",
    "earphone",
    "earphones",
    "speaker",
    "smartwatch",
    "watch",
    "laptop",
    "phone",
    "tablet",
    "mouse",
    "keyboard",
    "monitor",
    "camera",
    "shoe",
    "shirt",
    "bag",
    "charger",
    "adapter",
}

ARTICLE_TOKENS = (
    "best",
    "top",
    "guide",
    "buying",
    "review",
    "reviews",
    "comparison",
    "compare",
    "ranking",
    "rankings",
    "list",
    "roundup",
    "article",
    "blog",
    "under",
    "under 5000",
)


def _is_article_like(title: str, url: str | None, content: str | None) -> bool:
    text = " ".join(filter(None, [title, content or "", url or ""])).lower()
    if not text:
        return True

    parsed = urlparse(url or "")
    path = (parsed.path or "").lower()
    if any(token in path for token in ("blog", "article", "guide", "review", "comparison", "list", "best-")):
        return True

    title_tokens = re.split(r"[^a-z0-9]+", title.lower())
    if any(token in title_tokens for token in ("best", "top", "guide", "review", "comparison", "blog", "rankings", "roundup", "list")):
        return True

    if re.search(r"\b(?:best|top|guide|review|comparison|buying|list|roundup)\b.*\b(?:headphone|earbud|phone|laptop|shoe|shirt)\b", text):
        return True

    if re.search(r"\b(?:under|below|within|upto|up to|less than|budget)\s*(?:rs\.?|inr|₹)?\s*\d+(?:[\s,\.]\d+)*\b", text):
        if "₹" not in text and "rs" not in text and "inr" not in text:
            return True

    return False


def extract_inr_price(value: str | None) -> int | None:
    """Extract a price in INR currency units (not paise) from a raw string."""
    if not value:
        return None

    text = value.lower().replace("₹", "rs ")

    for pattern in (
        r"(?:rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d+)?)",
        r"(?:price|mrp|m\.r\.p|starts at|from|at)\s*(?:rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d+)?)",
    ):
        match = re.search(pattern, text)
        if match:
            num = match.group(1).replace(",", "")
            try:
                return int(float(num))
            except ValueError:
                return None

    return None


def _is_product_like(title: str, content: str | None, url: str | None) -> bool:
    text = " ".join(filter(None, [title, content or "", url or ""])).lower()
    if not text:
        return False

    if _is_article_like(title, url, content):
        return False

    has_product_keyword = any(token in text for token in PRODUCT_KEYWORDS)
    has_model_signal = bool(re.search(r"\b[a-z0-9]+[-_][a-z0-9]+\b|\b(?:wh|air|rockerz|elite|x|e|m|a)[a-z0-9-]+\b", title.lower()))
    has_merchant_signal = bool(url and "/" in url and not any(token in (urlparse(url).path or "").lower() for token in ("blog", "article", "guide", "review", "compare", "list")))

    return has_product_keyword or has_model_signal or has_merchant_signal


def normalize_search_results(search_response: dict | None) -> list[dict]:
    """Normalize Tavily search results into the app's strict product card shape."""
    if not isinstance(search_response, dict):
        return []

    results = search_response.get("results") or []
    products: list[dict] = []

    for item in results:
        if not isinstance(item, dict):
            continue

        title = (item.get("title") or "").strip()
        url = item.get("url")
        content = item.get("content") or ""
        source = item.get("source") or (urlparse(url).netloc if url else "search")

        if not title:
            continue
        if not _is_product_like(title, content, url):
            continue

        image_url = item.get("image_url") or item.get("thumbnail") or (search_response.get("images") or [None])[0]
        price = item.get("price")
        if price is None:
            price = extract_inr_price(f"{title} {content}")
        else:
            try:
                price = int(float(str(price).replace(",", "")))
            except (TypeError, ValueError):
                price = extract_inr_price(str(price))

        if price is None and re.search(r"\b(?:under|below|within|upto|up to|less than|budget)\s*(?:rs\.?|inr|₹)?\s*\d+(?:[\s,\.]\d+)*\b", f"{title} {content}", flags=re.IGNORECASE):
            price = None

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
            "image_url": image_url if isinstance(image_url, str) and image_url.startswith(("http://", "https://")) else None,
            "source": source,
            "product_url": url,
            "availability": availability,
            "metadata": {
                "content": content[:500],
                "score": item.get("score"),
                "is_product_candidate": True,
                "source_type": "product",
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
            "description": "Start a checkout for a customer's trusted cart. The final amount is derived from cart state, not from any model-supplied amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "amount_paise": {"type": "integer", "description": "Ignored for charge calculation; total is calculated from the trusted cart."},
                    "cart_snapshot": {"type": "object", "description": "Trusted cart snapshot with product prices in paise"},
                },
                "required": ["customer_id", "cart_snapshot"],
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
        try:
            result = tavily_search(arguments["query"])
        except Exception as exc:  # pragma: no cover - safety net for network failures
            result = {
                "results": [],
                "error": {
                    "type": type(exc).__name__,
                    "code": "product_search_unavailable",
                    "message": "Live product search is temporarily unavailable. Please try again shortly.",
                    "retryable": True,
                },
            }

        if result.get("error"):
            error = result["error"]
            error_code = error.get("code") or "product_search_unavailable"
            return {
                "ok": False,
                "error": error_code,
                "result": result,
                "products": [],
                "reason": error.get("message"),
                "retryable": error.get("retryable", False),
                "error_type": error.get("type"),
            }

        products = normalize_search_results(result)
        return {"ok": True, "error": None, "result": result, "products": products}

    if name == "initiate_checkout":
        try:
            order = await initiate_checkout(
                db,
                actor=actor,
                customer_id=arguments["customer_id"],
                amount_paise=arguments.get("amount_paise"),
                cart_snapshot=arguments["cart_snapshot"],
                delegation_scope=delegation_scope,
            )
            return {"ok": True, "order_id": order.id, "status": order.status.value}
        except CheckoutBlocked as e:
            return {"ok": False, "reason": e.reason, "decision": "blocked"}
        except CheckoutAwaitingConfirmation as e:
            return {"ok": False, "order_id": e.order_id, "reason": e.reason, "decision": "escalated"}

    return {"ok": False, "reason": f"Unknown tool: {name}"}
