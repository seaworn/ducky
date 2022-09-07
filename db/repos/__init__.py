from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from db import Base, get_session


class Repo:
    """Data Access Layer"""

    def __init__(self, *, model: Base, session: AsyncSession) -> None:
        self.Model = model
        self.session = session

    async def all(self) -> List[Base]:
        return (await self.session.execute(select(self.Model))).scalars().all()

    async def get(self, id: int) -> Base:
        return await self.session.get(self.Model, id)

    async def find_one(self, params: Dict[str, Any]):
        return (await self.session.execute(select(self.Model).filter_by(**params))).scalar_one_or_none()

    async def create(self, params: Dict[str, Any]) -> Base:
        model = self.Model(**params)
        self.session.add(model)
        return model

    async def update(self, id: int, params: Dict[str, Any]) -> Base:
        await self.session.execute(update(self.Model).where(self.Model.id == id).values(**params))
        return await self.get(id)

    async def delete(self, id: int) -> int:
        return (await self.session.execute(delete(self.Model).where(self.Model.id == id))).rowcount


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

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    def get_repo(self, model: Base) -> Repo:
        repo = getattr(model, '__repo__', None)
        if repo and issubclass(repo, Repo):
            return repo(model=model, session=self.session)
        raise TypeError(f'Repository for {model.__name__} is not properly configured')


def get_repo_manager(session: AsyncSession = Depends(get_session)) -> RepoManager:
    return RepoManager(session=session)
