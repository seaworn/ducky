from typing import List

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException

from api import schemas
from api.dependencies import DependsAsyncSession
from db import models

router = APIRouter(prefix="/{workflow_id}/bpmn_task", tags=["bpmn_task"])


@router.get("", response_model=List[schemas.BpmnTask])
async def all(workflow_id: int, session: DependsAsyncSession):
    async with session.begin():
        stmt = sa.select(models.BpmnTask).where(
            models.BpmnTask.workflow_id == workflow_id
        )
        res = await session.scalars(stmt)
        return res.all()


@router.get("/{id}", response_model=schemas.BpmnTask)
async def get(id: int, session: DependsAsyncSession):
    async with session.begin():
        task = await session.get(models.BpmnTask, id)
        if task is None:
            raise HTTPException(404, f"Task not found: {id=}")
        return task
