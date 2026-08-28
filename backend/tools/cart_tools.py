from backend.database.db import execute, rows
from backend.tools.catalog_tools import get_product

async def get_cart(session_id):
    return rows("""SELECT p.id, p.name, p.description, p.price, p.stock, c.quantity, p.price * c.quantity AS line_total
                   FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.session_id=?""", (session_id,))

async def add_to_cart(session_id, product_id, quantity=1):
    product = await get_product(product_id)
    if not product or product["stock"] < quantity:
        return None
    execute("INSERT INTO cart_items VALUES (?, ?, ?) ON CONFLICT(session_id, product_id) DO UPDATE SET quantity=quantity+excluded.quantity", (session_id, product_id, quantity))
    return await get_cart(session_id)

async def remove_from_cart(session_id, product_id):
    execute("DELETE FROM cart_items WHERE session_id=? AND product_id=?", (session_id, product_id))
    return await get_cart(session_id)

async def calculate_total(session_id):
    return sum(item["line_total"] for item in await get_cart(session_id))
