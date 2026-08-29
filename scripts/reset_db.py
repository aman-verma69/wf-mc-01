"""Drops and recreates all tables. DESTRUCTIVE — dev use only."""
import asyncio

from backend.database.models import Base
from backend.database.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Tables dropped and recreated.")


if __name__ == "__main__":
    asyncio.run(main())
