from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    agent_key: str = "buyer"
    message: str
    customer_id: str


class AgentChatResponse(BaseModel):
    agent: str
    reply: str


class ConfirmCheckoutRequest(BaseModel):
    order_id: str
    confirmed_by: str  # merchant/human identifier


class RefundRequest(BaseModel):
    razorpay_payment_id: str
    amount_paise: int | None = None
    reason: str = ""
