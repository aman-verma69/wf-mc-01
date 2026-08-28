import hashlib, hmac, os, uuid
from backend.database.db import execute

async def create_order(session_id, amount):
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    key_id, secret = os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")
    if key_id and secret:
        import razorpay
        client = razorpay.Client(auth=(key_id, secret))
        remote = client.order.create({"amount": amount * 100, "currency": "INR", "receipt": order_id})
        order_id = remote["id"]
        mode = "razorpay"
    else:
        mode = "demo"
    execute("INSERT INTO orders VALUES (?, ?, ?, 'CREATED', NULL)", (order_id, session_id, amount))
    return {"order_id": order_id, "amount": amount, "currency": "INR", "mode": mode, "key_id": key_id}

async def verify_demo_payment(order_id):
    payment_id = f"pay_demo_{hashlib.sha1(order_id.encode()).hexdigest()[:10]}"
    execute("UPDATE orders SET status='PAID', payment_id=? WHERE id=?", (payment_id, order_id))
    return payment_id

async def verify_razorpay_payment(order_id, payment_id, signature):
    """Verify Razorpay's checkout signature before marking any order paid."""
    secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not secret:
        return False
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    execute("UPDATE orders SET status='PAID', payment_id=? WHERE id=? AND status='CREATED'", (payment_id, order_id))
    return True
