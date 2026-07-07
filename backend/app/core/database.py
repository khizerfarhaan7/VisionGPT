from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Create database engine using asyncpg driver URL
engine = create_async_engine(
    settings.async_database_url,
    echo=True if settings.ENVIRONMENT == "development" else False,
    pool_pre_ping=True,
    future=True
)

# Async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base declarative class
class Base(DeclarativeBase):
    pass

# Dependency to yield async database sessions to endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
