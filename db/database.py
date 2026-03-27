from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import Base
from db.repository import RepositoryManager

engine = create_async_engine("sqlite+aiosqlite:///db.sqlite3", echo=True)
AsyncSessionLocal = async_sessionmaker(engine, autoflush=True, expire_on_commit=False)


class Database:
    """
    Manages session lifecycle, and vends repository managers.
    """

    async def create_tables(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def repository_manager(self) -> AsyncIterator[RepositoryManager]:
        """
        Usage:
            ```python
            async with self.repository_manager() as repos:
                x_repo = repos.get(XRepository)
                x1 = await x_repo.get(pk=1)
            ```
        """
        async with AsyncSessionLocal() as session:
            yield RepositoryManager(session)
