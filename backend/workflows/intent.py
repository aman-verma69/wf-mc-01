import re


def extract_price_ceiling_paise(message: str) -> int | None:
    """Extract a maximum price ceiling from a shopper request in INR paise."""
    if not message:
        return None

    text = (message or "").lower().replace("₹", "rs ")

    patterns = [
        r"(?:under|below|less than|max(?:imum)?|budget|upto|up to|within)\s*(?:rs\.?\s*)?(\d+(?:[\s,\.]\d+)*)",
        r"(?:rs\.?\s*|inr\s*)(\d+(?:[\s,\.]\d+)*)\s*(?:or less|max|maximum)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw_value = match.group(1)
            amount = float(raw_value.replace(",", "").replace(" ", ""))
            return int(amount * 100)

    return None


def classify_intent(agent_hint: str | None, message: str) -> str:
    """
    Lightweight deterministic intent routing.

    The selected agent's LLM will understand the detailed user request.
    This function only decides which agent should receive the request.
    """

    # Respect a valid explicit agent selection.
    hint = (agent_hint or "").strip().lower()

    agent_intent_map = {
        "buyer": "initiate_checkout",
        "catalog": "search_catalog",
        "customer": "order_status",
        "analytics": "analytics",
        "growth": "growth",
        "campaign": "campaign",
    }

    if hint in agent_intent_map:
        return agent_intent_map[hint]

    text = (message or "").lower()

    if not text.strip():
        return "general"

    # Existing orders / support
    if any(token in text for token in [
        "where is my order",
        "track my order",
        "track order",
        "order status",
        "status of my order",
        "delivery status",
        "refund",
        "cancel my order",
        "cancel order",
        "return my order",
        "return order",
    ]):
        return "order_status"

    # Checkout / buying
    if any(token in text for token in [
        "checkout",
        "buy it",
        "buy this",
        "purchase",
        "place order",
        "confirm purchase",
        "i'll take",
        "i will take",
        "pay now",
        "proceed to checkout",
        "complete order",
        "add to cart",
    ]):
        return "initiate_checkout"

    # Catalog / product discovery
    if any(token in text for token in [
        "recommend",
        "suggest",
        "show me",
        "find",
        "look for",
        "search",
        "compare",
        "which one",
        "best",
        "under",
        "below",
        "budget",
        "earbuds",
        "headphones",
        "shirt",
        "t-shirt",
        "shoe",
        "laptop",
        "phone",
        "product",
    ]):
        return "search_catalog"

    # Marketing campaigns
    if any(token in text for token in [
        "campaign",
        "send reminder",
        "outreach",
        "email blast",
        "audience",
        "promotion",
        "promotional",
    ]):
        return "campaign"

    # Analytics
    if any(token in text for token in [
        "sales",
        "conversion",
        "revenue",
        "trend",
        "analytics",
        "performance",
        "metrics",
        "how much did we sell",
    ]):
        return "analytics"

    # Growth
    if any(token in text for token in [
        "growth",
        "abandoned cart",
        "retention",
        "upsell",
        "cross-sell",
        "cross sell",
    ]):
        return "growth"

    return "general"