# app/db/session.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from redis.asyncio import Redis
from app.core.config import settings

# --- PostgreSQL (Async) ---
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "dev"),  # Log SQL in dev
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    """
    FastAPI dependency for getting an async DB session.
    """
    async with AsyncSessionLocal() as session:
        yield session


# --- Redis (Async) ---
redis_client = Redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> Redis:
    """
    Dependency for getting the Redis client.
    """
    return redis_client
