"""Trusted cart utilities for the commerce workflow.

These functions keep cart shape deterministic and ensure totals are calculated from
backend-owned cart data rather than from model-generated price guesses.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Cart


def normalize_cart(cart: dict[str, Any] | None, *, customer_id: str | None = None) -> dict[str, Any]:
    """Coerce a cart-like payload into a strict, validated shape."""
    source = cart or {}
    if not isinstance(source, dict):
        source = {}

    normalized = {
        "customer_id": customer_id or str(source.get("customer_id") or ""),
        "items": [],
        "total_paise": 0,
    }

    for raw_item in source.get("items") or []:
        if not isinstance(raw_item, dict):
            continue

        product_id = str(raw_item.get("product_id") or raw_item.get("id") or raw_item.get("sku") or "").strip()
        if not product_id:
            continue

        quantity = int(raw_item.get("quantity") or 1)
        if quantity <= 0:
            continue

        unit_price_paise = raw_item.get("unit_price_paise")
        if unit_price_paise is None:
            unit_price_paise = raw_item.get("price_paise")
        if unit_price_paise is None:
            unit_price_paise = raw_item.get("price")
        if unit_price_paise is None:
            unit_price_paise = 0

        try:
            unit_price_paise = int(unit_price_paise)
        except (TypeError, ValueError):
            unit_price_paise = 0

        item = {
            "product_id": product_id,
            "name": str(raw_item.get("name") or raw_item.get("product_name") or product_id),
            "quantity": quantity,
            "unit_price_paise": unit_price_paise,
            "currency": str(raw_item.get("currency") or "INR"),
        }
        normalized["items"].append(item)

    normalized["total_paise"] = calculate_cart_total_paise(normalized)
    return normalized


def convert_product_to_cart_item(product: dict[str, Any], *, quantity: int = 1) -> dict[str, Any]:
    """Convert a trusted product payload into a cart line item."""
    if not isinstance(product, dict):
        raise ValueError("Product must be a dictionary")

    product_id = str(product.get("id") or product.get("product_id") or product.get("sku") or "").strip()
    if not product_id:
        raise ValueError("Product is missing a trusted identifier")

    price_value = product.get("price")
    if price_value is None:
        price_value = product.get("unit_price_paise")
    if price_value is None:
        price_value = product.get("price_paise")

    try:
        unit_price_paise = int(price_value)
    except (TypeError, ValueError):
        raise ValueError("Product is missing a trusted price in paise")

    qty = int(quantity or 1)
    if qty <= 0:
        raise ValueError("Cart quantity must be positive")

    return {
        "product_id": product_id,
        "name": str(product.get("name") or product.get("title") or product_id),
        "quantity": qty,
        "unit_price_paise": unit_price_paise,
        "currency": str(product.get("currency") or "INR"),
    }


def calculate_cart_total_paise(cart: dict[str, Any] | None) -> int:
    """Compute total for a normalized cart.

    Prices are treated as trusted backend values already expressed in paise.
    """
    if not isinstance(cart, dict):
        return 0

    total = 0
    for item in cart.get("items") or []:
        if not isinstance(item, dict):
            continue
        qty = int(item.get("quantity") or 0)
        unit_price = item.get("unit_price_paise")
        try:
            unit_price = int(unit_price)
        except (TypeError, ValueError):
            continue
        total += qty * unit_price
    return total


def add_item_to_cart(cart: dict[str, Any] | None, item: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_cart(cart or {}, customer_id=(cart or {}).get("customer_id"))
    if not isinstance(item, dict):
        raise ValueError("Cart item must be a dictionary")

    product_id = str(item.get("product_id") or item.get("id") or "").strip()
    if not product_id:
        raise ValueError("Cart item is missing product_id")

    quantity = int(item.get("quantity") or 1)
    if quantity <= 0:
        raise ValueError("Cart quantity must be positive")

    for existing in normalized["items"]:
        if existing["product_id"] == product_id:
            existing["quantity"] += quantity
            existing["unit_price_paise"] = int(existing.get("unit_price_paise") or 0)
            break
    else:
        normalized["items"].append({
            "product_id": product_id,
            "name": str(item.get("name") or product_id),
            "quantity": quantity,
            "unit_price_paise": int(item.get("unit_price_paise") or item.get("price") or 0),
            "currency": str(item.get("currency") or "INR"),
        })

    normalized["total_paise"] = calculate_cart_total_paise(normalized)
    return normalized


def update_cart_item_quantity(cart: dict[str, Any] | None, product_id: str, quantity: int) -> dict[str, Any]:
    normalized = normalize_cart(cart or {}, customer_id=(cart or {}).get("customer_id"))
    target_qty = int(quantity or 0)
    if target_qty < 0:
        raise ValueError("Quantity cannot be negative")

    for item in normalized["items"]:
        if item["product_id"] == product_id:
            if target_qty == 0:
                normalized["items"] = [existing for existing in normalized["items"] if existing["product_id"] != product_id]
                break
            item["quantity"] = target_qty
            break
    else:
        raise ValueError(f"Product {product_id} not found in cart")

    normalized["total_paise"] = calculate_cart_total_paise(normalized)
    return normalized


def remove_item_from_cart(cart: dict[str, Any] | None, product_id: str) -> dict[str, Any]:
    normalized = normalize_cart(cart or {}, customer_id=(cart or {}).get("customer_id"))
    normalized["items"] = [item for item in normalized["items"] if item["product_id"] != product_id]
    normalized["total_paise"] = calculate_cart_total_paise(normalized)
    return normalized


async def get_or_create_cart(db: AsyncSession, *, customer_id: str) -> Cart:
    if not customer_id:
        raise ValueError("customer_id is required")

    cart = await db.scalar(
        select(Cart).where(Cart.customer_id == customer_id, Cart.status == "active").order_by(Cart.updated_at.desc())
    )
    if cart is None:
        cart = Cart(customer_id=customer_id, items={"items": [], "customer_id": customer_id, "total_paise": 0}, total_paise=0)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    return cart


def serialize_cart(cart: Cart | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(cart, Cart):
        payload = cart.items or {"items": [], "customer_id": cart.customer_id, "total_paise": cart.total_paise}
        if not isinstance(payload, dict):
            payload = {"items": [], "customer_id": cart.customer_id, "total_paise": cart.total_paise}
        normalized = normalize_cart(payload, customer_id=cart.customer_id)
        return normalized

    if cart is None:
        return {"customer_id": "", "items": [], "total_paise": 0}

    normalized = normalize_cart(cart, customer_id=(cart or {}).get("customer_id"))
    return normalized


async def get_cart(db: AsyncSession, *, customer_id: str) -> dict[str, Any]:
    cart = await get_or_create_cart(db, customer_id=customer_id)
    return serialize_cart(cart)


async def add_item_to_db_cart(db: AsyncSession, *, customer_id: str, item: dict[str, Any]) -> dict[str, Any]:
    cart = await get_or_create_cart(db, customer_id=customer_id)
    payload = serialize_cart(cart)
    payload["customer_id"] = customer_id
    current = payload.get("items") or []
    product_id = str(item.get("product_id") or item.get("id") or item.get("sku") or "").strip()
    if not product_id:
        raise ValueError("Cart item is missing product_id")

    qty = int(item.get("quantity") or 1)
    if qty <= 0:
        raise ValueError("Cart quantity must be positive")

    unit_price_paise = item.get("unit_price_paise")
    if unit_price_paise is None:
        unit_price_paise = item.get("price_paise")
    if unit_price_paise is None:
        unit_price_paise = item.get("price")
    if unit_price_paise is None:
        raise ValueError("Cart item is missing a trusted unit_price_paise")

    unit_price_paise = int(unit_price_paise)
    item_payload = {
        "product_id": product_id,
        "name": str(item.get("name") or item.get("product_name") or product_id),
        "quantity": qty,
        "unit_price_paise": unit_price_paise,
        "currency": str(item.get("currency") or "INR"),
    }

    matched = False
    for existing in current:
        if existing["product_id"] == product_id:
            existing["quantity"] += qty
            existing["unit_price_paise"] = unit_price_paise
            matched = True
            break
    if not matched:
        current.append(item_payload)

    payload["items"] = current
    payload["total_paise"] = calculate_cart_total_paise(payload)
    cart.items = payload
    cart.total_paise = payload["total_paise"]
    await db.commit()
    await db.refresh(cart)
    return serialize_cart(cart)


async def update_db_cart_item(db: AsyncSession, *, customer_id: str, product_id: str, quantity: int) -> dict[str, Any]:
    cart = await get_or_create_cart(db, customer_id=customer_id)
    payload = serialize_cart(cart)
    current = payload.get("items") or []
    target_qty = int(quantity or 0)
    if target_qty < 0:
        raise ValueError("Quantity cannot be negative")

    found = False
    updated_items = []
    for item in current:
        if item["product_id"] == product_id:
            found = True
            if target_qty == 0:
                continue
            item["quantity"] = target_qty
            updated_items.append(item)
        else:
            updated_items.append(item)

    if not found:
        raise ValueError(f"Product {product_id} not found in cart")

    payload["items"] = updated_items
    payload["total_paise"] = calculate_cart_total_paise(payload)
    cart.items = payload
    cart.total_paise = payload["total_paise"]
    await db.commit()
    await db.refresh(cart)
    return serialize_cart(cart)


async def remove_db_cart_item(db: AsyncSession, *, customer_id: str, product_id: str) -> dict[str, Any]:
    cart = await get_or_create_cart(db, customer_id=customer_id)
    payload = serialize_cart(cart)
    payload["items"] = [item for item in (payload.get("items") or []) if item["product_id"] != product_id]
    payload["total_paise"] = calculate_cart_total_paise(payload)
    cart.items = payload
    cart.total_paise = payload["total_paise"]
    await db.commit()
    await db.refresh(cart)
    return serialize_cart(cart)


async def clear_db_cart(db: AsyncSession, *, customer_id: str) -> dict[str, Any]:
    cart = await get_or_create_cart(db, customer_id=customer_id)
    cart.items = {"items": [], "customer_id": customer_id, "total_paise": 0}
    cart.total_paise = 0
    await db.commit()
    await db.refresh(cart)
    return serialize_cart(cart)
