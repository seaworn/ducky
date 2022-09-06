from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = 'sqlite+aiosqlite:///db.sqlite'
engine = create_async_engine(DATABASE_URL, future=True, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base(engine)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal.begin() as session:
        yield session
