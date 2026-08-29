"""
Creates tables (dev convenience — use Alembic migrations in production,
see backend/database/migrations/).
Run with: python -m scripts.seed_db
"""
import asyncio

from backend.database.models import Base
from backend.database.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")


if __name__ == "__main__":
    asyncio.run(main())
