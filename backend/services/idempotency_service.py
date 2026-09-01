"""Database-backed request deduplication for externally visible writes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import get_settings
from backend.database.models import IdempotencyRecord, gen_uuid


class IdempotencyConflict(Exception):
    pass


class IdempotencyInProgress(Exception):
    pass


def replay_body(record: IdempotencyRecord) -> tuple[int, dict[str, Any]] | None:
    if record.status not in {"completed", "failed"} or record.response_status is None or record.response_body is None:
        return None
    return record.response_status, record.response_body


def request_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def reserve(
    db: AsyncSession,
    *,
    key: str,
    operation: str,
    customer_id: str | None,
    payload: dict[str, Any],
) -> IdempotencyRecord:
    normalized_key = (key or "").strip()
    if not normalized_key:
        raise ValueError("Idempotency-Key must not be empty")
    if len(normalized_key) > 255:
        raise ValueError("Idempotency-Key is too long")

    payload_hash = request_hash(payload)
    existing = await db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == normalized_key))
    if existing is not None:
        _validate_reuse(existing, operation=operation, customer_id=customer_id, payload_hash=payload_hash)
        if existing.status == "completed" or existing.status == "failed":
            return existing
        if existing.created_at and datetime.utcnow() - existing.created_at > timedelta(seconds=get_settings().IDEMPOTENCY_PROCESSING_TIMEOUT_SECONDS):
            existing.status = "failed"
            existing.response_status = 409
            existing.response_body = {"detail": "The previous idempotent request did not complete; use a new Idempotency-Key"}
            existing.completed_at = datetime.utcnow()
            await db.commit()
            return existing
        raise IdempotencyInProgress("The request with this Idempotency-Key is still processing")

    record = IdempotencyRecord(
        id=gen_uuid(),
        key=normalized_key,
        operation=operation,
        customer_id=customer_id,
        request_hash=payload_hash,
        status="processing",
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        existing = await db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == normalized_key))
        if existing is None:
            raise exc
        _validate_reuse(existing, operation=operation, customer_id=customer_id, payload_hash=payload_hash)
        if existing.status in {"completed", "failed"}:
            return existing
        raise IdempotencyInProgress("The request with this Idempotency-Key is still processing") from exc
    return record


def _validate_reuse(record: IdempotencyRecord, *, operation: str, customer_id: str | None, payload_hash: str) -> None:
    if record.operation != operation or record.customer_id != customer_id or record.request_hash != payload_hash:
        raise IdempotencyConflict("Idempotency-Key was already used for a different request")


async def complete(
    db: AsyncSession,
    record: IdempotencyRecord,
    *,
    response_status: int,
    response_body: dict[str, Any],
    resource_id: str | None = None,
    status: str = "completed",
) -> None:
    record.status = status
    record.response_status = response_status
    record.response_body = response_body
    record.resource_id = resource_id
    record.completed_at = datetime.utcnow()
    await db.commit()
