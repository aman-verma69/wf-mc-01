import re

INTENTS = ("SEARCH_PRODUCTS", "GET_PRODUCT_DETAILS", "ADD_TO_CART", "REMOVE_FROM_CART", "VIEW_CART", "PREPARE_CHECKOUT", "CONFIRM_PURCHASE", "CHECK_PAYMENT_STATUS")

async def classify(message: str):
    text = message.lower().strip()
    if text in {"confirm", "confirm purchase", "yes, confirm"}: return "CONFIRM_PURCHASE"
    if any(x in text for x in ("buy", "checkout", "purchase")): return "PREPARE_CHECKOUT"
    if any(x in text for x in ("cart", "basket")): return "VIEW_CART"
    if text.startswith("remove"): return "REMOVE_FROM_CART"
    if text.startswith("add"): return "ADD_TO_CART"
    if any(x in text for x in ("detail", "about", "spec")): return "GET_PRODUCT_DETAILS"
    return "SEARCH_PRODUCTS"

def price_cap(message):
    match = re.search(r"(?:under|below|less than)\s*(?:₹|rs\.?|inr)?\s*(\d+)", message.lower())
    return int(match.group(1)) if match else None
