from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    actor: str,
    action: str,
    decision: str,
    reason: str | None = None,
    context: dict | None = None,
) -> AuditLog:
    """Write one immutable audit record. Called by the guardrail on every
    decision, and by services on every state-changing operation.
    Never skip this on the payment path, even for allowed actions —
    the point is a complete trail, not just a record of failures.
    """
    entry = AuditLog(
        actor=actor,
        action=action,
        decision=decision,
        reason=reason,
        context=context or {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
