import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.database.db import init_db, execute, rows
from backend.audit.logger import audit
from backend.agent.agent import decide
from backend.catalog.catalog_service import search_products, get_product
from backend.tools.cart_tools import add_to_cart, remove_from_cart, get_cart, calculate_total
from backend.services.checkout_service import prepare_checkout
from backend.security.policies import validate_checkout
from backend.payments.razorpay_service import create_order
from backend.payments.verification import verify_demo_payment, verify_razorpay_payment

# Project-level configuration is loaded first; backend/.env remains supported for local setups.
load_dotenv(Path.cwd() / ".env")
load_dotenv(Path(__file__).with_name(".env"))

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
    catalog, cart_now = await search_products(""), await get_cart(session)
    prior = rows("SELECT metadata FROM audit_events WHERE session_id=? AND event_type='USER_MESSAGE' ORDER BY id DESC LIMIT 6", (session,))
    history = [json.loads(item["metadata"]).get("message", "") for item in reversed(prior)]
    decision = await decide(message, catalog, cart_now, history)
    intent = decision.intent; audit(session, "INTENT_DETECTED", metadata=decision.model_dump())
    if intent == "SEARCH_PRODUCTS":
        products = await search_products(decision.query or message); audit(session, "PRODUCT_SEARCHED", metadata={"count": len(products)})
        text = decision.response or ("I found these matching products." if products else "I couldn't find a matching in-stock product. Try describing the item differently.")
        return reply(text, intent=intent, products=products, cart=cart_now)
    if intent == "GET_PRODUCT_DETAILS":
        product = await get_product(decision.product_id) if decision.product_id else None
        if not product: return reply("Which product would you like details about?", intent=intent)
        audit(session, "PRODUCT_SELECTED", metadata={"product_id": product["id"]})
        return reply(decision.response or f"Here are the live details for {product['name']}.", intent=intent, products=[product], cart=cart_now)
    if intent == "ADD_TO_CART":
        product = await get_product(decision.product_id) if decision.product_id else None
        if not product: return reply("I couldn't find that product. Try selecting one from the results.", intent=intent)
        cart = await add_to_cart(session, product["id"], decision.quantity)
        audit(session, "CART_UPDATED", metadata={"product_id": product["id"], "quantity": decision.quantity})
        return reply(decision.response or f"Added {product['name']} to your cart.", intent=intent, cart=cart)
    if intent == "REMOVE_FROM_CART":
        if decision.product_id and any(item["id"] == decision.product_id for item in cart_now):
            cart_now = await remove_from_cart(session, decision.product_id); audit(session, "CART_UPDATED", metadata={"product_id": decision.product_id})
            return reply(decision.response or "Cart updated.", intent=intent, cart=cart_now)
        return reply("Tell me which item in your cart you want to remove.", intent=intent, cart=cart_now)
    if intent == "VIEW_CART": return reply(decision.response or "Here is your current cart.", intent=intent, cart=cart_now, total=await calculate_total(session))
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
    if intent == "CHECK_PAYMENT_STATUS":
        order = rows("SELECT id, amount, status, payment_id FROM orders WHERE session_id=? ORDER BY rowid DESC LIMIT 1", (session,))
        text = decision.response or ("Your latest order is " + order[0]["status"].lower() + "." if order else "You do not have an order yet.")
        return reply(text, intent=intent, order=order[0] if order else None)
    return reply(decision.response or "I can help you discover products, compare them, and manage your cart.", intent=intent, cart=cart_now)

@app.post("/api/cart")
async def cart_add(body: CartRequest):
    cart = await add_to_cart(body.session_id, body.product_id)
    if not cart: raise HTTPException(400, "Product is unavailable")
    audit(body.session_id, "CART_UPDATED", metadata={"product_id": body.product_id})
    return {"cart": cart}
@app.get("/api/catalog")
async def catalog():
    return {"products": await search_products("")}
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
