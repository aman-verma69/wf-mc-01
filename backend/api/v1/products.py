from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_customer, get_current_merchant
from backend.database.models import Customer, Product, gen_uuid
from backend.audit.audit_logger import log_action
from backend.database.session import get_db
from backend.schemas.api_schemas import InventoryAdjustmentRequest, ProductCreateRequest, ProductResponse, ProductUpdateRequest
from backend.services.catalog_service import adjust_inventory, serialize_product
from backend.services.idempotency_service import IdempotencyConflict, IdempotencyInProgress, complete, replay_body, reserve


router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(request: ProductCreateRequest, db: AsyncSession = Depends(get_db), merchant: Customer = Depends(get_current_merchant)):
    product = Product(id=gen_uuid(), merchant_id=merchant.id, sku=request.sku.strip(), name=request.name.strip(), description=request.description, price_paise=request.price_paise, currency=request.currency, physical_quantity=request.initial_stock)
    db.add(product)
    try:
        await db.commit()
        await db.refresh(product)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="SKU is already registered") from exc
    await log_action(db, actor=f"merchant:{merchant.id}", action="product.created", decision="allowed", context={"product_id": product.id, "sku": product.sku})
    return serialize_product(product)


@router.get("", response_model=list[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    products = (await db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.created_at.desc()))).scalars().all()
    return [serialize_product(product) for product in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    product = await db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, request: ProductUpdateRequest, db: AsyncSession = Depends(get_db), merchant: Customer = Depends(get_current_merchant)):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.merchant_id != merchant.id:
        raise HTTPException(status_code=403, detail="Product does not belong to this merchant")
    for field in ("name", "description", "price_paise", "is_active"):
        value = getattr(request, field)
        if value is not None:
            setattr(product, field, value.strip() if field == "name" else value)
    await db.commit()
    await db.refresh(product)
    await log_action(db, actor=f"merchant:{merchant.id}", action="product.updated", decision="allowed", context={"product_id": product.id})
    return serialize_product(product)


@router.patch("/{product_id}/inventory", response_model=ProductResponse)
async def adjust_product_inventory(product_id: str, request: InventoryAdjustmentRequest, db: AsyncSession = Depends(get_db), merchant: Customer = Depends(get_current_merchant), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    product = await db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.merchant_id != merchant.id:
        raise HTTPException(status_code=403, detail="Product does not belong to this merchant")
    record = None
    if idempotency_key is not None:
        try:
            record = await reserve(db, key=idempotency_key, operation="inventory.adjust", customer_id=merchant.id, payload={"product_id": product_id, "add_quantity": request.add_quantity})
        except (ValueError, IdempotencyConflict) as exc:
            raise HTTPException(status_code=409 if isinstance(exc, IdempotencyConflict) else 400, detail=str(exc)) from exc
        except IdempotencyInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc), headers={"Retry-After": "1"}) from exc
        replay = replay_body(record)
        if replay is not None:
            return JSONResponse(status_code=replay[0], content=replay[1], headers={"Idempotent-Replay": "true"})
    product = await adjust_inventory(db, product=product, add_quantity=request.add_quantity, actor=f"merchant:{merchant.id}")
    response_body = serialize_product(product)
    if record is not None:
        await complete(db, record, response_status=200, response_body=response_body, resource_id=product.id)
    return response_body