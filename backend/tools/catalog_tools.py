from backend.database.db import row, rows

async def search_products(query: str, max_price: int | None = None):
    terms = [t for t in query.lower().split() if len(t) > 2 and t not in {"under", "find", "with", "headphones"}]
    products = rows("SELECT * FROM products WHERE stock > 0")
    if max_price:
        products = [p for p in products if p["price"] <= max_price]
    return [p for p in products if not terms or any(t in (p["name"] + p["description"] + p["category"]).lower() for t in terms)]

async def get_product(product_id: str):
    return row("SELECT * FROM products WHERE id = ?", (product_id,))

async def check_inventory(product_id: str, quantity: int):
    product = await get_product(product_id)
    return bool(product and product["stock"] >= quantity)
