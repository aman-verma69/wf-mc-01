"""
The guardrail gate. Every agent-initiated checkout/payment call MUST pass
through check_checkout_request() before services/checkout.py or
services/payment.py touch Razorpay. Keep this file boring and rule-based —
no LLM calls here. If you're tempted to add "smart" judgment, that
judgment belongs in an agent BEFORE this gate, not inside it.
"""
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.audit_logger import log_action
from backend.config.settings import get_settings

settings = get_settings()


class GateDecision(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    ESCALATED = "escalated"  # needs human confirmation before proceeding


@dataclass
class CheckoutRequest:
    actor: str  # which agent is requesting this, e.g. "buyer_agent"
    customer_id: str
    amount_paise: int
    currency: str = "INR"
    delegation_scope: list[str] | None = None  # what this agent/session is allowed to do
    metadata: dict | None = None


@dataclass
class GateResult:
    decision: GateDecision
    reason: str


def _check_delegation_scope(request: CheckoutRequest) -> GateResult | None:
    if request.delegation_scope is not None and "checkout" not in request.delegation_scope:
        return GateResult(GateDecision.BLOCKED, "Agent's delegation scope does not include checkout")
    return None


def _check_spend_limit(request: CheckoutRequest) -> GateResult | None:
    if request.amount_paise > settings.MAX_AUTONOMOUS_SPEND_PAISE:
        if settings.REQUIRE_HUMAN_CONFIRMATION_ABOVE_LIMIT:
            return GateResult(
                GateDecision.ESCALATED,
                f"Amount {request.amount_paise} paise exceeds autonomous limit "
                f"{settings.MAX_AUTONOMOUS_SPEND_PAISE} paise — human confirmation required",
            )
        return GateResult(GateDecision.BLOCKED, "Amount exceeds autonomous spend limit")
    return None


async def check_checkout_request(db: AsyncSession, request: CheckoutRequest) -> GateResult:
    """Runs every rule in order; first non-ALLOWED result wins.
    Every outcome — including ALLOWED — is written to the audit log.
    """
    checks = [_check_delegation_scope, _check_spend_limit]

    result = GateResult(GateDecision.ALLOWED, "Passed all guardrail checks")
    for check in checks:
        outcome = check(request)
        if outcome is not None:
            result = outcome
            break

    await log_action(
        db,
        actor="guardrail",
        action="checkout.gate_check",
        decision=result.decision.value,
        reason=result.reason,
        context={
            "requesting_agent": request.actor,
            "customer_id": request.customer_id,
            "amount_paise": request.amount_paise,
        },
    )
    return result
