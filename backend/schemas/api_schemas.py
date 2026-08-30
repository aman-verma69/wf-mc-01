from pydantic import BaseModel


class ProductCard(BaseModel):
    name: str
    price: str | None = None
    image_url: str | None = None
    url: str | None = None


class AgentChatRequest(BaseModel):
    agent_key: str = "buyer"
    message: str
    customer_id: str


class AgentChatResponse(BaseModel):
    agent: str
    reply: str
    products: list[ProductCard] = []


class ConfirmCheckoutRequest(BaseModel):
    order_id: str
    confirmed_by: str


class RefundRequest(BaseModel):
    razorpay_payment_id: str
    amount_paise: int | None = None
    reason: str = ""
