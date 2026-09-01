from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import decode_access_token
from backend.database.models import Customer
from backend.database.session import get_db


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        customer_id = payload.get("sub")
        if not isinstance(customer_id, str) or not customer_id:
            raise unauthorized
    except Exception as exc:
        raise unauthorized from exc

    customer = await db.get(Customer, customer_id)
    if customer is None or not customer.is_active:
        raise unauthorized
    return customer