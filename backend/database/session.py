from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config.settings import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=(settings.APP_ENV == "development"))
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
