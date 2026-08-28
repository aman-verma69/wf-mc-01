import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend.catalog.products import PRODUCTS

DB_PATH = Path(__file__).parent / "commerce.db"

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT, description TEXT, price INTEGER, stock INTEGER, category TEXT);
        CREATE TABLE IF NOT EXISTS cart_items (session_id TEXT, product_id TEXT, quantity INTEGER, PRIMARY KEY(session_id, product_id));
        CREATE TABLE IF NOT EXISTS checkout_drafts (session_id TEXT PRIMARY KEY, draft_json TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, session_id TEXT, amount INTEGER, status TEXT, payment_id TEXT);
        CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, session_id TEXT, order_id TEXT, event_type TEXT, status TEXT, reason TEXT, metadata TEXT);
        """)
        db.executemany("""INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description,
            price=excluded.price, stock=excluded.stock, category=excluded.category""", PRODUCTS)

def rows(query, params=()):
    with connection() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]

def row(query, params=()):
    result = rows(query, params)
    return result[0] if result else None

def execute(query, params=()):
    with connection() as db:
        db.execute(query, params)
