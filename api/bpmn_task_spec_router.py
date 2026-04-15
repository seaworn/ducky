from typing import List

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException

from api import schemas
from api.dependencies import DependsAsyncSession
from db import models

router = APIRouter(prefix="/{workflow_spec_id}/bpmn_task_spec", tags=["bpmn_task_spec"])


@router.get("", response_model=List[schemas.BpmnTaskSpec])
async def all(workflow_spec_id: int, session: DependsAsyncSession):
    async with session.begin():
        stmt = sa.select(models.BpmnTaskSpec).where(
            models.BpmnTaskSpec.workflow_spec_id == workflow_spec_id
        )
        res = await session.scalars(stmt)
        return res.all()


@router.get("/{id}", response_model=schemas.BpmnTaskSpec)
async def get(id: int, session: DependsAsyncSession):
    async with session.begin():
        task_spec = await session.get(models.BpmnTaskSpec, id)
        if task_spec is None:
            raise HTTPException(404, f"Task spec not found: {id=}")
        return task_spec
