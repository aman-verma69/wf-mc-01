import asyncio, json
from backend.database.db import row
from backend.tools.catalog_tools import get_product, check_inventory

SPENDING_LIMIT = 10000

async def validate_checkout(session_id):
    draft_row = row("SELECT * FROM checkout_drafts WHERE session_id=?", (session_id,))
    if not draft_row or draft_row["status"] != "AWAITING_CONFIRMATION": return False, "No active checkout requires confirmation."
    draft = json.loads(draft_row["draft_json"])
    products = await asyncio.gather(*(get_product(i["product_id"]) for i in draft["items"]))
    inventory = await asyncio.gather(*(check_inventory(i["product_id"], i["quantity"]) for i in draft["items"]))
    checks = [all(products), all(inventory), draft["total"] <= SPENDING_LIMIT,
              not row("SELECT id FROM orders WHERE session_id=? AND amount=? AND status='PAID'", (session_id, draft["total"]))]
    if not all(checks): return False, "Policy validation failed: unavailable item, limit, or duplicate payment."
    for item, product in zip(draft["items"], products):
        if item["quoted_price"] != product["price"]:
            return False, f"Price changed for {product['name']} from ₹{item['quoted_price']} to ₹{product['price']}. Your previous approval was invalidated."
    return True, draft
