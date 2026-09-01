from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.schemas.api_schemas import CartItemCreateRequest, CartItemUpdateRequest, CartResponse, OrderStatusResponse
from backend.services.cart_service import add_item_to_db_cart, clear_db_cart, get_cart, remove_db_cart_item, update_db_cart_item
from backend.services.order_service import get_customer_orders

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_id}/cart", response_model=CartResponse)
async def get_customer_cart(customer_id: str, db: AsyncSession = Depends(get_db)):
    cart = await get_cart(db, customer_id=customer_id)
    return CartResponse(**cart)


@router.post("/{customer_id}/cart/items", response_model=CartResponse)
async def add_customer_cart_item(customer_id: str, request: CartItemCreateRequest, db: AsyncSession = Depends(get_db)):
    item = {
        "product_id": request.product_id,
        "name": request.name,
        "quantity": request.quantity,
        "unit_price_paise": request.unit_price_paise if request.unit_price_paise is not None else request.price_paise,
        "currency": request.currency,
    }
    cart = await add_item_to_db_cart(db, customer_id=customer_id, item=item)
    return CartResponse(**cart)


@router.patch("/{customer_id}/cart/items/{product_id}", response_model=CartResponse)
async def update_customer_cart_item(customer_id: str, product_id: str, request: CartItemUpdateRequest, db: AsyncSession = Depends(get_db)):
    cart = await update_db_cart_item(db, customer_id=customer_id, product_id=product_id, quantity=request.quantity)
    return CartResponse(**cart)


@router.delete("/{customer_id}/cart/items/{product_id}", response_model=CartResponse)
async def delete_customer_cart_item(customer_id: str, product_id: str, db: AsyncSession = Depends(get_db)):
    cart = await remove_db_cart_item(db, customer_id=customer_id, product_id=product_id)
    return CartResponse(**cart)


@router.delete("/{customer_id}/cart", response_model=CartResponse)
async def clear_customer_cart(customer_id: str, db: AsyncSession = Depends(get_db)):
    cart = await clear_db_cart(db, customer_id=customer_id)
    return CartResponse(**cart)


@router.get("/{customer_id}/orders", response_model=list[OrderStatusResponse])
async def get_customer_orders_route(customer_id: str, db: AsyncSession = Depends(get_db)):
    orders = await get_customer_orders(db, customer_id=customer_id)
    return [OrderStatusResponse(**order) for order in orders]
