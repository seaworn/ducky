from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Body, HTTPException

from api import schemas
from api.dependencies import DependsAsyncSession, DependsBpmnEngine
from db import models

router = APIRouter(prefix="/bpmn_workflow", tags=["bpmn_workflow"])


@router.get("", response_model=list[schemas.BpmnWorkflow])
async def all(session: DependsAsyncSession):
    async with session.begin():
        stmt = sa.select(models.BpmnWorkflow)
        res = await session.scalars(stmt)
        return res.all()


@router.get("/{id}", response_model=schemas.BpmnWorkflow)
async def get(id: int, session: DependsAsyncSession):
    async with session.begin():
        workflow = await session.get(models.BpmnWorkflow, id)
        if workflow is None:
            raise HTTPException(404, f"Workflow not found: {id=}")
        return workflow


@router.post("/{id}/run", response_model=schemas.BpmnWorkflow)
async def run_workflow(
    id: int,
    session: DependsAsyncSession,
    engine: DependsBpmnEngine,
    data: Annotated[dict | None, Body()] = None,
):
    async with session.begin():
        workflow = await session.get(models.BpmnWorkflow, id)
        if workflow is None:
            raise HTTPException(404, f"Workflow not found: {id=}")
        await engine.continue_workflow(workflow.id, data)
        return workflow
