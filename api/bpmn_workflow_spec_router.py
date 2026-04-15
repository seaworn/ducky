import shutil
import uuid
from typing import Annotated, List

import sqlalchemy as sa
from fastapi import APIRouter, Body, Form, HTTPException

from api import schemas
from api.dependencies import DependsAsyncSession, DependsBpmnEngine
from api.settings import settings
from db import models

router = APIRouter(prefix="/bpmn_workflow_spec", tags=["bpmn_workflow_spec"])


@router.get("", response_model=List[schemas.BpmnWorkflowSpec])
async def all(session: DependsAsyncSession):
    async with session.begin():
        stmt = sa.select(models.BpmnWorkflowSpec)
        res = await session.scalars(stmt)
        return res.all()


@router.get("/{id}", response_model=schemas.BpmnWorkflowSpec)
async def get(id: int, session: DependsAsyncSession):
    async with session.begin():
        workflow_spec = await session.get(models.BpmnWorkflowSpec, id)
        if workflow_spec is None:
            raise HTTPException(404, f"Workflow spec not found: {id=}")
        return workflow_spec


@router.post("", response_model=schemas.BpmnWorkflowSpec)
async def create(
    session: DependsAsyncSession,
    engine: DependsBpmnEngine,
    data: Annotated[
        schemas.BpmnWorkflowSpecForm, Form(media_type="multipart/form-data")
    ],
):
    bpmn_files = []
    for upload_file in data.bpmn_files:
        path = settings.UPLOAD_DIR / f"{uuid.uuid4()}.bpmn"
        with path.open("wb") as f:
            shutil.copyfileobj(upload_file.file, f)
            bpmn_files.append(path)
    dmn_files = []
    if data.dmn_files:
        for upload_file in data.dmn_files:
            path = settings.UPLOAD_DIR / f"{uuid.uuid4()}.dmn"
            with path.open("wb") as f:
                shutil.copyfileobj(upload_file.file, f)
                dmn_files.append(path)
    async with session.begin():
        workflow_spec_id = await engine.add_workflow_spec(
            data.name, bpmn_files, dmn_files
        )
        workflow_spec = await session.get_one(models.BpmnWorkflowSpec, workflow_spec_id)
        return workflow_spec


@router.patch("/{id}", response_model=schemas.BpmnWorkflowSpec)
async def update(
    id: int, schema: schemas.BpmnWorkflowSpec, session: DependsAsyncSession
):
    async with session.begin():
        workflow_spec = await session.get(models.BpmnWorkflowSpec, id)
        if workflow_spec is None:
            raise HTTPException(404, f"Workflow spec not found: {id=}")
        for key, value in schema.model_dump().items():
            setattr(workflow_spec, key, value)
        await session.commit()
        return workflow_spec


@router.delete("/{id}")
async def delete(id: int, session: DependsAsyncSession):
    async with session.begin():
        workflow_spec = await session.get(models.BpmnWorkflowSpec, id)
        if workflow_spec is None:
            raise HTTPException(404, f"Workflow spec not found: {id=}")
        await session.delete(workflow_spec)
        return True


@router.post("/{id}/create_workflow", response_model=schemas.BpmnWorkflow)
async def create_workflow_instance(
    id: int,
    session: DependsAsyncSession,
    engine: DependsBpmnEngine,
    data: Annotated[dict | None, Body()] = None,
):
    async with session.begin():
        workflow_spec = await session.get(models.BpmnWorkflowSpec, id)
        if workflow_spec is None:
            raise HTTPException(404, f"Workflow spec not found: {id=}")
        process_id = await engine.create_workflow(workflow_spec.name, data)
        process = await session.get_one(models.BpmnWorkflow, process_id)
        return process
