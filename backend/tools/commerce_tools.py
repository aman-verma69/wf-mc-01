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
from backend.services.cart_service import add_item_to_db_cart, get_cart, remove_db_cart_item, update_db_cart_item
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


def parse_indian_price(value: str | int | float | None) -> int | None:
    """Parse Indian rupee prices like ₹3.9k, ₹5k, ₹4,999, ₹3990.

    Return rupees, not paise. Prices that are clearly budget ceilings such as
    'under ₹5k' are intentionally rejected as product pricing.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(float(value)))

    text = str(value).lower().replace("₹", "rs ").replace("inr", "rs ")
    if re.search(r"\b(?:under|below|less than|upto|up to|within|budget|max(?:imum)?)\b", text):
        return None

    patterns = [
        r"(?:^|[^a-z0-9])rs\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:\s*(k))?\b",
        r"(?:^|[^a-z0-9])rs\s+(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:\s*(k))?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1).replace(",", ""))
            if match.group(2) == "k":
                amount *= 1000
            return int(round(amount))

    return None


def extract_inr_price(value: str | None) -> int | None:
    """Backward-compatible wrapper around parse_indian_price."""
    return parse_indian_price(value)


def _is_research_context(title: str, content: str | None, url: str | None) -> bool:
    text = " ".join(filter(None, [title, content or "", url or ""])).lower()
    if not text:
        return False

    if "reddit.com" in (url or "").lower() or "reddit" in text:
        return True

    path = (urlparse(url or "").path or "").lower()
    if any(token in path for token in ("blog", "article", "guide", "review", "compare", "list", "category", "collection", "shop", "collections", "products", "offers", "deals", "sale")):
        return True

    if any(token in text for token in ("reddit", "forum discussion", "buying guide", "roundup", "review", "blog post", "comparison guide", "top picks")):
        return True

    return False


def _extract_product_names(text: str) -> list[str]:
    text = text or ""
    candidates: list[str] = []
    seen: set[str] = set()

    rejected_tokens = {
        "wireless", "headphones", "earbuds", "earphones", "audio", "buy", "shop",
        "review", "compare", "guide", "category", "collection", "sale", "deal",
        "premium", "sound", "under", "budget", "offers", "deals", "best", "top",
    }

    model_patterns = [
        r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3}\s+\d{3,4}(?:\s+[A-Z][A-Za-z0-9-]+)?)\b",
        r"\b(?:[A-Za-z]+(?:\s+[A-Za-z]+){0,2}\s+\d{3,4}(?:\s+[A-Z][A-Za-z0-9-]+)?)\b",
    ]
    for pattern in model_patterns:
        for match in re.finditer(pattern, text):
            candidate = match.group(0).strip()
            lower = candidate.lower()
            if len(candidate.split()) < 2:
                continue
            if any(token in lower for token in ("wireless headphones", "headphones under", "premium sound", "under", "budget")):
                continue
            tokens = re.split(r"\s+", candidate.strip())
            if any(token.lower() in rejected_tokens for token in tokens):
                continue
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)

    return candidates


def _is_product_like(title: str, content: str | None, url: str | None) -> bool:
    text = " ".join(filter(None, [title, content or "", url or ""])).lower()
    if not text:
        return False

    if _is_research_context(title, content, url):
        return False

    if any(token in (urlparse(url or "").path or "").lower() for token in ("blog", "article", "guide", "review", "compare", "list", "category", "collection", "shop", "offers", "sale", "deals")):
        return False

    title_signal = (title or "").strip()
    product_names = _extract_product_names(title_signal) or _extract_product_names(content or "")
    explicit_product = bool(product_names)
    has_product_keyword = any(token in text for token in PRODUCT_KEYWORDS)
    has_model_signal = bool(re.search(r"\b[a-z0-9]+[-_][a-z0-9]+\b|\b(?:wh|air|rockerz|elite|x|e|m|a)[a-z0-9-]+\b", title.lower()))
    has_merchant_signal = bool(url and "/" in url and not any(token in (urlparse(url).path or "").lower() for token in ("blog", "article", "guide", "review", "compare", "list")))

    if explicit_product:
        return True

    return (has_product_keyword or has_model_signal) and not re.search(r"\b(?:buy|shop|collection|category|deal|offer|sale|best|top|guide|review|comparison|list|under)\b", title.lower())


def _build_product_from_result(item: dict, *, preferred_name: str | None = None, preferred_url: str | None = None, preferred_price: int | None = None, preferred_image: str | None = None) -> dict | None:
    title = (preferred_name or item.get("title") or "").strip()
    if not title:
        return None

    url = preferred_url or item.get("url")
    content = item.get("content") or ""
    source = item.get("source") or (urlparse(url).netloc if url else "search")
    price = preferred_price if preferred_price is not None else parse_indian_price(item.get("price") or f"{title} {content}")

    if price is None and re.search(r"(?:rs|inr|₹)", f"{title} {content}", flags=re.IGNORECASE):
        price = parse_indian_price(f"{title} {content}")

    if price is None and not re.search(r"(?:rs|inr|₹)", f"{title} {content}", flags=re.IGNORECASE):
        # Missing price is acceptable; do not fabricate it.
        pass

    image_url = preferred_image or item.get("image_url") or item.get("thumbnail") or item.get("image")
    if image_url is not None and not isinstance(image_url, str):
        image_url = None
    if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
        pass
    else:
        image_url = None

    return {
        "id": item.get("id") or str(url or title),
        "name": title,
        "price": price,
        "unit_price_paise": price * 100 if price is not None else None,
        "currency": "INR",
        "image_url": image_url,
        "source": source,
        "product_url": url,
        "availability": "unknown",
        "metadata": {
            "content": content[:500],
            "score": item.get("score"),
            "is_product_candidate": True,
            "source_type": "product",
        },
    }


def normalize_search_results(search_response: dict | None) -> list[dict]:
    """Normalize Tavily search results into the app's strict product card shape.

    Current Tavily config in backend/integrations/tavily/client.py does not
    request image data; if a result does not include a trustworthy image URL,
    image_url stays null instead of fabricating one.
    """
    if not isinstance(search_response, dict):
        return []

    results = search_response.get("results") or []
    products: list[dict] = []
    seen_ids: set[str] = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        title = (item.get("title") or "").strip()
        url = item.get("url")
        content = item.get("content") or ""
        source = item.get("source") or (urlparse(url).netloc if url else "search")

        if not title:
            continue

        if title and _is_product_like(title, content, url):
            product = _build_product_from_result(item)
            if product is not None:
                product_id = product["id"]
                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    products.append(product)
            continue

        if _is_research_context(title, content, url):
            continue

        explicit_names = _extract_product_names(title)
        if explicit_names:
            for name in explicit_names[:3]:
                product = _build_product_from_result(item, preferred_name=name, preferred_url=url, preferred_image=None)
                if product is None:
                    continue
                product_id = f"{source}:{name}:{url or ''}"
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                products.append(product)
            continue

        if not _is_product_like(title, content, url):
            continue

        product = _build_product_from_result(item)
        if product is None:
            continue
        product_id = product["id"]
        if product_id in seen_ids:
            continue
        seen_ids.add(product_id)
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
            "name": "view_cart",
            "description": "Read the persisted customer cart from the backend, not from workflow memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": "Read the persisted customer cart from the backend, not from workflow memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add a trusted product line item to the persisted customer cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "product_id": {"type": "string"},
                    "name": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unit_price_paise": {"type": "integer"},
                    "currency": {"type": "string"},
                },
                "required": ["customer_id", "product_id", "name", "quantity", "unit_price_paise"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_cart",
            "description": "Update a cart item quantity for a persisted customer cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 0},
                },
                "required": ["customer_id", "product_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": "Remove a product from the persisted customer cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "product_id": {"type": "string"},
                },
                "required": ["customer_id", "product_id"],
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

    if name in {"get_cart", "view_cart"}:
        customer_id = arguments["customer_id"]
        cart = await get_cart(db, customer_id=customer_id)
        return {"ok": True, "cart": cart}

    if name == "add_to_cart":
        customer_id = arguments["customer_id"]
        payload = {
            "product_id": arguments["product_id"],
            "name": arguments["name"],
            "quantity": arguments.get("quantity", 1),
            "unit_price_paise": arguments["unit_price_paise"],
            "currency": arguments.get("currency", "INR"),
        }
        cart = await add_item_to_db_cart(db, customer_id=customer_id, item=payload)
        return {"ok": True, "cart": cart}

    if name == "update_cart":
        customer_id = arguments["customer_id"]
        cart = await update_db_cart_item(db, customer_id=customer_id, product_id=arguments["product_id"], quantity=arguments["quantity"])
        return {"ok": True, "cart": cart}

    if name == "remove_from_cart":
        customer_id = arguments["customer_id"]
        cart = await remove_db_cart_item(db, customer_id=customer_id, product_id=arguments["product_id"])
        return {"ok": True, "cart": cart}

    if name == "initiate_checkout":
        try:
            # Checkout must use the current persisted cart, never a snapshot
            # reconstructed by the model.
            persisted_cart = (
                await get_cart(db, customer_id=arguments["customer_id"])
                if db is not None
                else arguments.get("cart_snapshot")
            )
            order = await initiate_checkout(
                db,
                actor=actor,
                customer_id=arguments["customer_id"],
                amount_paise=arguments.get("amount_paise"),
                cart_snapshot=persisted_cart,
                delegation_scope=delegation_scope,
            )
            return {"ok": True, "order_id": order.id, "status": order.status.value}
        except CheckoutBlocked as e:
            return {"ok": False, "reason": e.reason, "decision": "blocked"}
        except CheckoutAwaitingConfirmation as e:
            return {"ok": False, "order_id": e.order_id, "reason": e.reason, "decision": "escalated"}

    return {"ok": False, "reason": f"Unknown tool: {name}"}
