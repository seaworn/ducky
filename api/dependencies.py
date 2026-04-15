from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bpmn.engine import BpmnEngine, create_bpmn_engine
from bpmn.store import SqlAlchemyDatabaseStore
from db.database import Database

db = Database()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with db.session() as session:
        yield session


DependsAsyncSession = Annotated[AsyncSession, Depends(get_session)]


def get_bpmn_engine(session: DependsAsyncSession) -> BpmnEngine:
    store = SqlAlchemyDatabaseStore(session)
    return create_bpmn_engine(store)


DependsBpmnEngine = Annotated[BpmnEngine, Depends(get_bpmn_engine)]
