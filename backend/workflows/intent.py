import re


def extract_price_ceiling_paise(message: str) -> int | None:
    """Extract a maximum price ceiling from a shopper request in INR paise.

    Examples:
    - 'show me earbuds under 4000' -> 400000
    - 'anything below rs. 1,200' -> 120000
    - 'no price mentioned' -> None
    """
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
            normalized = raw_value.replace(",", "").replace(" ", "")
            if "." in normalized:
                amount = float(normalized)
            else:
                amount = float(normalized)
            return int(amount * 100)

    return None


def classify_intent(agent_hint: str | None, message: str) -> str:
    """Classify an incoming user message into a workflow intent.

    This keeps the routing layer simple, deterministic, and testable while still
    allowing the workflow to override the inferred route when a preferred agent is
    explicitly supplied.
    """
    text = (message or "").lower()
    if not text:
        return "general"

    if any(token in text for token in [
        "where is my order",
        "track my order",
        "order status",
        "status of my order",
        "refund",
        "cancel my order",
        "cancel order",
        "return my order",
    ]):
        return "order_status"

    if any(token in text for token in [
        "checkout",
        "buy it",
        "purchase",
        "place order",
        "confirm purchase",
        "i'll take",
        "pay now",
        "proceed to checkout",
        "complete order",
    ]):
        return "initiate_checkout"

    if any(token in text for token in [
        "recommend",
        "show me",
        "find",
        "look for",
        "search",
        "compare",
        "under ",
        "below ",
        "budget",
        "earbuds",
        "headphones",
        "shirt",
        "t-shirt",
        "shoe",
        "laptop",
        "phone",
    ]):
        return "search_catalog"

    if any(token in text for token in [
        "campaign",
        "send reminder",
        "outreach",
        "email blast",
        "audience",
    ]):
        return "campaign"

    if any(token in text for token in [
        "sales",
        "conversion",
        "revenue",
        "trend",
        "analytics",
        "performance",
    ]):
        return "analytics"

    if any(token in text for token in [
        "growth",
        "abandoned cart",
        "retention",
        "upsell",
        "recommendation",
    ]):
        return "growth"

    if agent_hint == "customer" and any(token in text for token in [
        "order",
        "refund",
        "cancel",
        "status",
        "shipment",
    ]):
        return "order_status"

    return "general"
