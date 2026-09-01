import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


class OrderStatus(str, enum.Enum):
    CREATED = "created"
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # guardrail held it for a human
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    EVIDENCE_SUBMITTED = "evidence_submitted"
    WON = "won"
    LOST = "lost"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    role: Mapped[str] = mapped_column(String, default="customer", nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    response_status: Mapped[int | None] = mapped_column(nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="INR", nullable=False)
    physical_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, default="reserved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    items: Mapped[dict] = mapped_column(JSON, default=dict)
    total_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    razorpay_order_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)  # always store paise, never float rupees
    currency: Mapped[str] = mapped_column(String, default="INR")
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.CREATED)
    cart_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # line items at time of order
    created_by_agent: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "buyer_agent"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_webhook_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    razorpay_dispute_id: Mapped[str] = mapped_column(String, unique=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), index=True)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus), default=DisputeStatus.OPEN)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    respond_by: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Every agent action and every guardrail decision gets written here,
    whether it was allowed, blocked, or escalated for human confirmation."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    actor: Mapped[str] = mapped_column(String)  # e.g. "buyer_agent", "guardrail", "human:merchant_1"
    action: Mapped[str] = mapped_column(String)  # e.g. "checkout.initiate", "payment.capture"
    decision: Mapped[str] = mapped_column(String)  # "allowed" | "blocked" | "escalated"
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
