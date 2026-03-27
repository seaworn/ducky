from typing import Annotated, AsyncIterator

from fastapi import Depends

from bpmn.engine import BpmnEngine, create_bpmn_engine
from db.database import Database
from db.repository import RepositoryManager

db = Database()


async def get_repository_manager() -> AsyncIterator[RepositoryManager]:
    async with db.repository_manager() as repos:
        yield repos


DependsRepositoryManager = Annotated[RepositoryManager, Depends(get_repository_manager)]


def get_bpmn_engine() -> BpmnEngine:
    return create_bpmn_engine()


DependsBpmnEngine = Annotated[BpmnEngine, Depends(get_bpmn_engine)]
