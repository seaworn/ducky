from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base

engine = create_async_engine("sqlite+aiosqlite:///db.sqlite3", echo=True)
AsyncSessionLocal = async_sessionmaker(engine, autoflush=True, expire_on_commit=False)


class Database:
    """
    Database wrapper - manages session lifecycle.
    """

    async def create_tables(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with AsyncSessionLocal() as session:
            yield session
