import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.database.db import init_db, execute, rows
from backend.services.audit_service import audit
from backend.agents.intent_agent import classify, price_cap
from backend.tools.catalog_tools import search_products
from backend.tools.cart_tools import add_to_cart, remove_from_cart, get_cart, calculate_total
from backend.services.checkout_service import prepare_checkout
from backend.services.policy_service import validate_checkout
from backend.services.payment_service import create_order, verify_demo_payment, verify_razorpay_payment

@asynccontextmanager
async def lifespan(app):
    init_db(); yield
app = FastAPI(title="AI Commerce Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel): message: str; session_id: str = "demo-user"
class CartRequest(BaseModel): product_id: str; session_id: str = "demo-user"
class PaymentVerification(BaseModel): order_id: str; payment_id: str; signature: str; session_id: str = "demo-user"

def reply(text, **extra): return {"message": text, **extra}

@app.post("/api/chat")
async def chat(body: ChatRequest):
    session, message = body.session_id, body.message
    audit(session, "USER_MESSAGE", metadata={"message": message})
    intent = await classify(message); audit(session, "INTENT_DETECTED", metadata={"intent": intent})
    if intent == "SEARCH_PRODUCTS":
        products = await search_products(message, price_cap(message)); audit(session, "PRODUCT_SEARCHED", metadata={"count": len(products)})
        return reply("Here are matching in-stock products. Prices and stock are live backend data.", intent=intent, products=products, cart=await get_cart(session))
    if intent == "ADD_TO_CART":
        products = await search_products(message.replace("add", "")); product = products[0] if products else None
        if not product: return reply("I couldn't find that product. Try selecting one from the results.", intent=intent)
        cart = await add_to_cart(session, product["id"])
        audit(session, "CART_UPDATED", metadata={"product_id": product["id"]})
        return reply(f"Added {product['name']} to your cart.", intent=intent, cart=cart)
    if intent == "REMOVE_FROM_CART":
        cart = await get_cart(session)
        target = next((i for i in cart if i["name"].lower().replace(" anc", "") in message.lower() or i["id"] in message.lower()), None)
        if target: cart = await remove_from_cart(session, target["id"]); audit(session, "CART_UPDATED")
        return reply("Cart updated.", intent=intent, cart=cart)
    if intent == "VIEW_CART": return reply("Your cart total is calculated by the backend.", intent=intent, cart=await get_cart(session), total=await calculate_total(session))
    if intent == "PREPARE_CHECKOUT":
        draft = await prepare_checkout(session)
        if not draft: return reply("Your cart is empty—add a product before checkout.", intent=intent)
        audit(session, "CHECKOUT_PREPARED", metadata=draft)
        return reply(f"Exact total: ₹{draft['total']}. Reply Confirm to authorize this exact amount.", intent=intent, checkout=draft, requires_confirmation=True)
    if intent == "CONFIRM_PURCHASE":
        audit(session, "USER_CONFIRMED")
        approved, result = await validate_checkout(session); audit(session, "POLICY_CHECKED", "approved" if approved else "blocked", None if approved else result)
        if not approved:
            execute("UPDATE checkout_drafts SET status='INVALIDATED' WHERE session_id=?", (session,)); audit(session, "TRANSACTION_BLOCKED", "blocked", result)
            return reply(result, intent=intent, blocked=True)
        payment = await create_order(session, result["total"]); audit(session, "PAYMENT_ORDER_CREATED", order_id=payment["order_id"])
        if payment["mode"] == "demo":
            pid = await verify_demo_payment(payment["order_id"]); audit(session, "PAYMENT_SUCCESS", order_id=payment["order_id"]); audit(session, "PAYMENT_VERIFIED", order_id=payment["order_id"])
            return reply("Demo payment verified server-side. Purchase complete.", intent=intent, payment={**payment, "payment_id": pid, "verified": True})
        return reply("Razorpay Test Mode order created. Complete payment in the checkout modal.", intent=intent, payment=payment)
    return reply("I can help search products, manage your cart, and checkout.", intent=intent)

@app.post("/api/cart")
async def cart_add(body: CartRequest):
    cart = await add_to_cart(body.session_id, body.product_id)
    if not cart: raise HTTPException(400, "Product is unavailable")
    audit(body.session_id, "CART_UPDATED", metadata={"product_id": body.product_id})
    return {"cart": cart}
@app.get("/api/cart/{session_id}")
async def cart(session_id): return {"cart": await get_cart(session_id), "total": await calculate_total(session_id)}
@app.post("/api/demo/price-change")
async def price_change():
    execute("UPDATE products SET price=2799 WHERE id='soundmax-pro'")
    return {"message": "SoundMax Pro price is now ₹2799. Confirming an earlier ₹2499 quote will be blocked."}
@app.post("/api/payment/verify")
async def payment_verify(body: PaymentVerification):
    verified = await verify_razorpay_payment(body.order_id, body.payment_id, body.signature)
    if not verified:
        audit(body.session_id, "PAYMENT_FAILURE", "failed", "Razorpay signature verification failed", body.order_id)
        raise HTTPException(400, "Payment could not be verified")
    audit(body.session_id, "PAYMENT_SUCCESS", order_id=body.order_id)
    audit(body.session_id, "PAYMENT_VERIFIED", order_id=body.order_id)
    return {"verified": True}
@app.get("/api/audit/{session_id}")
async def events(session_id): return {"events": rows("SELECT * FROM audit_events WHERE session_id=? ORDER BY id DESC", (session_id,))}
