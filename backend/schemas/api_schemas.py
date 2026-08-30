from pydantic import BaseModel


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


class AgentChatResponse(BaseModel):
    agent: str
    reply: str
    products: list[ProductCard] = []
    ok: bool = True
    error: str | None = None


class ConfirmCheckoutRequest(BaseModel):
    order_id: str
    confirmed_by: str


class RefundRequest(BaseModel):
    razorpay_payment_id: str
    amount_paise: int | None = None
    reason: str = ""
