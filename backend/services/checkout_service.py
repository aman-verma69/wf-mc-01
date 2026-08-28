import asyncio, json
from backend.database.db import execute
from backend.tools.cart_tools import get_cart, calculate_total
from backend.tools.catalog_tools import get_product, check_inventory

async def prepare_checkout(session_id):
    cart = await get_cart(session_id)
    if not cart: return None
    fresh, inventory = await asyncio.gather(
        asyncio.gather(*(get_product(i["id"]) for i in cart)),
        asyncio.gather(*(check_inventory(i["id"], i["quantity"]) for i in cart)),
    )
    if not all(inventory): return {"blocked": True, "reason": "One or more items are out of stock."}
    total = sum(p["price"] * item["quantity"] for p, item in zip(fresh, cart))
    draft = {"items": [{"product_id": p["id"], "name": p["name"], "quoted_price": p["price"], "quantity": item["quantity"]} for p, item in zip(fresh, cart)], "total": total, "currency": "INR"}
    execute("INSERT INTO checkout_drafts VALUES (?, ?, 'AWAITING_CONFIRMATION') ON CONFLICT(session_id) DO UPDATE SET draft_json=excluded.draft_json, status='AWAITING_CONFIRMATION'", (session_id, json.dumps(draft)))
    return draft
