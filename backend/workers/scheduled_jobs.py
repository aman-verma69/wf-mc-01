"""
Scheduled/background jobs — things that aren't triggered by an HTTP
request. Wire this up with a scheduler of your choice (APScheduler, Celery
beat, arq cron, or a plain cron job calling a CLI entrypoint). Kept as
plain async functions here so it's scheduler-agnostic.
"""
from datetime import datetime, timedelta

from sqlalchemy import select

from backend.database.models import Dispute, DisputeStatus
from backend.database.session import AsyncSessionLocal


async def check_dispute_deadlines() -> None:
    """Flags disputes whose respond_by deadline is within 24h and still open.
    Wire the flagged output to notification_service.notify_dispute_opened
    or a dedicated urgent-reminder function.
    """
    async with AsyncSessionLocal() as db:
        soon = datetime.utcnow() + timedelta(hours=24)
        result = await db.execute(
            select(Dispute).where(Dispute.status == DisputeStatus.OPEN, Dispute.respond_by <= soon)
        )
        urgent = result.scalars().all()
        for dispute in urgent:
            # TODO: send urgent reminder via notification_service
            print(f"URGENT: dispute {dispute.id} respond_by {dispute.respond_by}")


async def run_abandoned_cart_sweep() -> None:
    """Placeholder for growth_agent-triggered cart recovery sweep.
    Real implementation should query orders in AWAITING_CONFIRMATION or
    a dedicated cart table older than N hours, then hand off to
    growth_agent / campaign_agent for recovery outreach.
    """
    # TODO: implement once cart persistence model is finalized
    pass
