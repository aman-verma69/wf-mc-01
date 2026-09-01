from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CustomerResponse(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime
    is_active: bool


class ProductCard(BaseModel):
    id: str | None = None
    name: str
    price: float | int | str | None = None
    currency: str = "INR"
    image_url: str | None = None
    source: str = "catalog"
    product_url: str | None = None
    availability: str = "unknown"
    metadata: dict = {}


class AgentChatRequest(BaseModel):
    agent_key: str | None = None
    message: str
    customer_id: str | None = None


class DelegationRequest(BaseModel):
    type: str = "delegation_request"
    target_agent: str
    reason: str
    task: str
    context_keys: list[str] = []


class AgentResult(BaseModel):
    status: str = "completed"
    reply: str
    products: list[ProductCard] = []
    data: dict = {}
    actions: list[str] = []
    tool_calls: list[str] = []
    delegation_request: DelegationRequest | None = None


class AgentChatResponse(BaseModel):
    agent: str
    reply: str
    products: list[ProductCard] = []
    ok: bool = True
    error: str | None = None


class CartItemCreateRequest(BaseModel):
    product_id: str
    name: str
    quantity: int = 1
    unit_price_paise: int | None = None
    price_paise: int | None = None
    currency: str = "INR"


class CartItemUpdateRequest(BaseModel):
    quantity: int


class CartClearResponse(BaseModel):
    customer_id: str
    items: list[dict] = []
    total_paise: int = 0


class CartResponse(BaseModel):
    customer_id: str
    items: list[dict] = []
    total_paise: int = 0


class CheckoutInitiateRequest(BaseModel):
    customer_id: str | None = None
    actor: str = "api"


class CheckoutInitiateResponse(BaseModel):
    order_id: str
    customer_id: str
    amount_paise: int
    currency: str = "INR"
    status: str
    razorpay_order_id: str | None = None


class ConfirmCheckoutRequest(BaseModel):
    order_id: str
    confirmed_by: str


class OrderStatusResponse(BaseModel):
    order_id: str
    customer_id: str
    status: str
    amount_paise: int
    currency: str = "INR"
    cart_snapshot: dict = {}
    razorpay_order_id: str | None = None


class CustomerOrderListResponse(BaseModel):
    orders: list[OrderStatusResponse] = []


class RefundRequest(BaseModel):
    customer_id: str | None = None
    order_id: str | None = None
    razorpay_payment_id: str | None = None
    amount_paise: int | None = None
    reason: str = ""


class CancelOrderRequest(BaseModel):
    customer_id: str | None = None
    reason: str = "customer_request"
