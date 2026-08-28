from backend.database.db import row, rows

async def search_products(query: str, max_price: int | None = None):
    terms = [t for t in query.lower().split() if len(t) > 2 and t not in {"under", "find", "with", "headphones"}]
    products = rows("SELECT * FROM products WHERE stock > 0")
    if max_price:
        products = [p for p in products if p["price"] <= max_price]
    if not terms:
        return products
    ranked = []
    for product in products:
        searchable = (product["name"] + " " + product["description"] + " " + product["category"]).lower()
        score = sum(term in searchable for term in terms)
        if score:
            ranked.append((score, product))
    # Keep the best semantic keyword matches: “wireless keyboard” should not surface headphones
    # merely because they are also wireless.
    best_score = max((score for score, _ in ranked), default=0)
    return [product for score, product in ranked if score == best_score]

async def get_product(product_id: str):
    return row("SELECT * FROM products WHERE id = ?", (product_id,))

async def check_inventory(product_id: str, quantity: int):
    product = await get_product(product_id)
    return bool(product and product["stock"] >= quantity)
