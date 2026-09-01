from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.audit_logger import log_action
from backend.database.models import InventoryReservation, Product


def available_quantity(product: Product) -> int:
    return max(0, product.physical_quantity - product.reserved_quantity)


def serialize_product(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "merchant_id": product.merchant_id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price_paise": product.price_paise,
        "currency": product.currency,
        "physical_quantity": product.physical_quantity,
        "reserved_quantity": product.reserved_quantity,
        "available_quantity": available_quantity(product),
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


async def adjust_inventory(db: AsyncSession, *, product: Product, add_quantity: int, actor: str) -> Product:
    if add_quantity < 0:
        raise ValueError("Stock adjustment cannot be negative")
    product.physical_quantity += add_quantity
    await db.commit()
    await db.refresh(product)
    await log_action(db, actor=actor, action="inventory.adjusted", decision="allowed", context={"product_id": product.id, "quantity_added": add_quantity, "physical_quantity": product.physical_quantity})
    return product


async def reserve_order_inventory(db: AsyncSession, *, order_id: str, cart: dict[str, Any]) -> dict[str, Any]:
    snapshot_items: list[dict[str, Any]] = []
    for item in cart.get("items") or []:
        product_id = str(item.get("product_id") or "")
        product = await db.scalar(select(Product).where(Product.id == product_id).with_for_update())
        if product is None:
            snapshot_items.append(item)
            continue
        quantity = int(item.get("quantity") or 0)
        if not product.is_active:
            raise ValueError(f"Product {product.sku} is inactive")
        if quantity <= 0 or available_quantity(product) < quantity:
            raise ValueError(f"Insufficient stock for product {product.sku}")
        product.reserved_quantity += quantity
        reservation = InventoryReservation(order_id=order_id, product_id=product.id, quantity=quantity, status="reserved")
        db.add(reservation)
        snapshot_items.append({"product_id": product.id, "sku": product.sku, "name": product.name, "quantity": quantity, "unit_price_paise": product.price_paise, "currency": product.currency})
    snapshot = {"customer_id": cart.get("customer_id"), "items": snapshot_items}
    snapshot["total_paise"] = sum(item["quantity"] * item["unit_price_paise"] for item in snapshot_items)
    return snapshot


async def finalize_order_inventory(db: AsyncSession, *, order_id: str) -> None:
    rows = (await db.execute(select(InventoryReservation).where(InventoryReservation.order_id == order_id).with_for_update())).scalars().all()
    changed = False
    for reservation in rows:
        if reservation.status != "reserved":
            continue
        product = await db.scalar(select(Product).where(Product.id == reservation.product_id).with_for_update())
        if product is None:
            continue
        product.physical_quantity -= reservation.quantity
        product.reserved_quantity -= reservation.quantity
        reservation.status = "finalized"
        changed = True
    if changed:
        await db.commit()
        await log_action(db, actor="inventory_service", action="inventory.finalized", decision="allowed", context={"order_id": order_id})


async def release_order_inventory(db: AsyncSession, *, order_id: str) -> None:
    rows = (await db.execute(select(InventoryReservation).where(InventoryReservation.order_id == order_id).with_for_update())).scalars().all()
    changed = False
    for reservation in rows:
        if reservation.status != "reserved":
            continue
        product = await db.scalar(select(Product).where(Product.id == reservation.product_id).with_for_update())
        if product is not None:
            product.reserved_quantity = max(0, product.reserved_quantity - reservation.quantity)
        reservation.status = "released"
        changed = True
    if changed:
        await db.commit()
        await log_action(db, actor="inventory_service", action="inventory.released", decision="allowed", context={"order_id": order_id})