from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError
from fastapi import Depends

from db import Base, get_session


class Repo:
    """Data Access Layer"""

    def __init__(self, model: Base, session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def all(self) -> List[Base]:
        return (await self.session.execute(select(self.model))).scalars().all()

    async def get(self, id: int) -> Base:
        return await self.session.get(self.model, id)

    async def find_one_by(self, params: Dict[str, Any]):
        return (await self.session.execute(select(self.model).filter_by(**params))).scalar_one_or_none()

    async def create(self, params: Dict[str, Any]) -> Base:
        try:
            model = self.model(**params)
            self.session.add(model)
            await self.session.commit()
            return model
        except DBAPIError as e:
            await self.session.rollback()
            raise e

    async def update(self, id: int, params: Dict[str, Any]) -> Base:
        try:
            await self.session.execute(update(self.model).where(self.model.id == id).values(**params))
            await self.session.commit()
            return self.get(id)
        except DBAPIError as e:
            await self.session.rollback()
            raise e


class BpmnProcessRepo(Repo):
    pass


class BpmnProcessInstanceRepo(Repo):
    pass


def has_repo(repo_class: Optional[str] = None) -> Callable[[Base], Base]:
    def f(model):
        nonlocal repo_class
        if repo_class is None:
            repo_class = model.__name__ + 'Repo'
        repo = globals().get(repo_class)
        if repo is None:
            raise NameError(f"Repo class '{repo_class}' is not defined")
        model.__repo__ = repo
        return model
    return f


class RepoManager:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def get_repo(self, model: Base) -> Repo:
        return model.__repo__(model, self.session)


def get_repo_manager(session: AsyncSession = Depends(get_session)) -> RepoManager:
    return RepoManager(session)
