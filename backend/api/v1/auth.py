from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_customer
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.database.models import Customer, gen_uuid
from backend.database.session import get_db
from backend.schemas.api_schemas import AuthTokenResponse, CustomerResponse, LoginRequest, RegisterRequest


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.strip().lower()
    existing = await db.scalar(select(Customer).where(Customer.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email is already registered")

    customer = Customer(id=gen_uuid(), email=email, password_hash=hash_password(request.password))
    db.add(customer)
    try:
        await db.commit()
        await db.refresh(customer)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered") from exc
    return CustomerResponse(id=customer.id, email=customer.email, created_at=customer.created_at, is_active=customer.is_active, role=customer.role)


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.strip().lower()
    customer = await db.scalar(select(Customer).where(Customer.email == email))
    if customer is None or not customer.is_active or not verify_password(request.password, customer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    return AuthTokenResponse(access_token=create_access_token(customer.id))


@router.get("/me", response_model=CustomerResponse)
async def me(customer: Customer = Depends(get_current_customer)):
    return CustomerResponse(id=customer.id, email=customer.email, created_at=customer.created_at, is_active=customer.is_active, role=customer.role)