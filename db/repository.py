from typing import Any, Sequence

from sqlalchemy import ColumnElement, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

# ---
# Generic base repository (Unit of Work wrapper)
# ---


class Repository[_ModelType: DeclarativeBase]:
    """
    A repository holds a reference to an SQLAlchemy session and the model class it manages.
    Subclass this to add domain-specific query methods.

    Usage:
        ```python
        class XRepository(Repository[X]):
            model = X
        ```
    """

    # model: ClassVar[type[Any]]
    model: type[_ModelType]  # defined by subclasses

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---
    # Convenience wrappers around common session operations
    # ---

    async def add(self, model: _ModelType) -> _ModelType:
        async with self.session.begin():
            self.session.add(model)
            return model

    async def create(self, **kwargs: Any) -> _ModelType:
        async with self.session.begin():
            model = self.model(**kwargs)
            self.session.add(model)
            return model

    async def get(self, pk: int, raise_for_none=False) -> _ModelType | None:
        async with self.session.begin():
            if raise_for_none:
                return await self.session.get_one(self.model, pk)
            return await self.session.get(self.model, pk)

    async def all(self) -> Sequence[_ModelType]:
        async with self.session.begin():
            stmt = select(self.model)
            res = await self.session.scalars(stmt)
            return res.all()

    async def filter(self, *filters: ColumnElement[bool]) -> Sequence[_ModelType]:
        async with self.session.begin():
            stmt = select(self.model).where(*filters)
            res = await self.session.scalars(stmt)
            return res.all()

    async def one(
        self, *filters: ColumnElement[bool], raise_for_none=False
    ) -> _ModelType | None:
        async with self.session.begin():
            stmt = select(self.model).where(*filters)
            res = await self.session.scalars(stmt)
            if raise_for_none:
                return res.one()
            return res.one_or_none()

    async def update(self, model: int | _ModelType, **kwargs: Any) -> _ModelType:
        async with self.session.begin():
            if isinstance(model, int):
                model = await self.session.get_one(self.model, model)
            for k, v in kwargs.items():
                setattr(model, k, v)
            return model

    async def update_or_create(self, **kwargs: Any) -> _ModelType:
        async with self.session.begin():
            model = self.model(**kwargs)
            model = await self.session.merge(model)
            return model

    async def bulk_update(
        self, *filters: ColumnElement[bool], **kwargs: Any
    ) -> Sequence[_ModelType]:
        async with self.session.begin():
            stmt = (
                update(self.model)
                .where(*filters)
                .values(**kwargs)
                .execution_options(synchronize_session="fetch")
            )
            res = await self.session.execute(stmt)
            return res.rowcount  # pyright: ignore [reportAttributeAccessIssue]

    async def delete(self, model: int | _ModelType) -> None:
        async with self.session.begin():
            if isinstance(model, int):
                model = await self.session.get_one(self.model, model)
            return await self.session.delete(model)

    async def bulk_delete(self, *filters: ColumnElement[bool]) -> int:
        async with self.session.begin():
            stmt = (
                delete(self.model)
                .where(*filters)
                .execution_options(synchronize_session="fetch")
            )
            res = await self.session.execute(stmt)
            return res.rowcount  # pyright: ignore [reportAttributeAccessIssue]


# ---
# Central repository manager
# ---


class RepositoryManager:
    """
    Manages the creation and caching of model repositories.
    """

    _cache: dict[str, Any] = {}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def get[_RepositoryType: Repository](
        self, cls: type[_RepositoryType]
    ) -> _RepositoryType:
        """
        Factory for an instance of the given repository *cls*.
        Cache it for subsequent access.
        """

        key = ".".join([cls.__module__, cls.__name__])
        repo = self._cache.get(key)
        if repo is not None:
            return repo
        repo = cls(self.session)
        self._cache[key] = repo
        return repo
