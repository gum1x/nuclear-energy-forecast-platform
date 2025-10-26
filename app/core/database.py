import asyncio
from typing import AsyncGenerator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

async_database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_engine(settings.database_url, echo=settings.debug)
async_engine = create_async_engine(async_database_url, echo=settings.debug)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()
metadata = MetaData()

def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    try:
        async with async_engine.begin() as conn:
            from app.models import Base
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise

async def close_db():
    await async_engine.dispose()
    engine.dispose()
    logger.info("Database connections closed")