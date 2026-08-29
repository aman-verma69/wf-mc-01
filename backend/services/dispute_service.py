from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.audit_logger import log_action
from backend.database.models import Dispute, DisputeStatus, Payment
from backend.integrations.razorpay.client import submit_dispute_evidence


async def handle_dispute_created(db: AsyncSession, entity: dict) -> None:
    razorpay_dispute_id = entity["id"]
    razorpay_payment_id = entity["payment_id"]

    existing = await db.scalar(select(Dispute).where(Dispute.razorpay_dispute_id == razorpay_dispute_id))
    if existing is not None:
        return

    payment = await db.scalar(select(Payment).where(Payment.razorpay_payment_id == razorpay_payment_id))
    if payment is None:
        await log_action(db, actor="dispute_service", action="dispute.created", decision="blocked",
                          reason="No matching local payment", context={"razorpay_payment_id": razorpay_payment_id})
        return

    dispute = Dispute(
        razorpay_dispute_id=razorpay_dispute_id,
        payment_id=payment.id,
        reason_code=entity.get("reason_code"),
        status=DisputeStatus.OPEN,
    )
    db.add(dispute)
    await db.commit()

    await log_action(db, actor="dispute_service", action="dispute.created", decision="allowed",
                      context={"dispute_id": dispute.id, "razorpay_dispute_id": razorpay_dispute_id})

    # A merchant-facing notification should go out here — see notification_service.
    from backend.services.notification_service import notify_dispute_opened
    await notify_dispute_opened(db, dispute)


async def submit_evidence(db: AsyncSession, *, actor: str, dispute_id: str, evidence: dict) -> dict:
    dispute = await db.get(Dispute, dispute_id)
    if dispute is None:
        raise ValueError(f"Dispute {dispute_id} not found")

    result = submit_dispute_evidence(dispute.razorpay_dispute_id, evidence)
    dispute.status = DisputeStatus.EVIDENCE_SUBMITTED
    await db.commit()

    await log_action(db, actor=actor, action="dispute.evidence_submitted", decision="allowed",
                      context={"dispute_id": dispute.id})
    return result


async def handle_dispute_resolved(db: AsyncSession, entity: dict, won: bool) -> None:
    razorpay_dispute_id = entity["id"]
    dispute = await db.scalar(select(Dispute).where(Dispute.razorpay_dispute_id == razorpay_dispute_id))
    if dispute is None:
        return

    dispute.status = DisputeStatus.WON if won else DisputeStatus.LOST
    await db.commit()

    await log_action(db, actor="dispute_service", action="dispute.resolved", decision="allowed",
                      context={"dispute_id": dispute.id, "won": won})
