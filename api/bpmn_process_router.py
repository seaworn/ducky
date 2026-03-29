from typing import Annotated, List

from fastapi import APIRouter, Body, HTTPException
from loguru import logger

from api.dependencies import DependsBpmnEngine, DependsRepositoryManager
from api.schemas import BpmnProcessInstanceSchema, BpmnProcessSchema
from db.models import (
    BpmnProcess,
    BpmnProcessInstance,
    BpmnProcessInstanceRepository,
    BpmnProcessRepository,
)

router = APIRouter(prefix="/bpmn_processes", tags=["bpmn_process"])


@router.get("", response_model=List[BpmnProcessSchema])
async def all(repos: DependsRepositoryManager):
    logger.debug("Fetching all processes...")
    repo = repos.get(BpmnProcessRepository)
    res = await repo.all()
    return res


@router.get("/{id}", response_model=BpmnProcessSchema)
async def get(id: int, repos: DependsRepositoryManager):
    logger.debug(f"Fetching processes...: {id=}")
    repo = repos.get(BpmnProcessRepository)
    res = await repo.get(id)
    return res


@router.post("", response_model=BpmnProcessSchema)
async def create(schema: BpmnProcessSchema, repos: DependsRepositoryManager):
    logger.debug("Creating process...")
    repo = repos.get(BpmnProcessRepository)
    process = BpmnProcess(**schema.model_dump())
    res = await repo.add(process)
    return res


@router.patch("/{id}", response_model=BpmnProcessSchema)
async def update(
    id: int,
    schema: BpmnProcessSchema,
    repos: DependsRepositoryManager,
):
    logger.debug(f"Updating process...: {id=}")
    repo = repos.get(BpmnProcessRepository)
    process = await repo.get(id)
    if process is None:
        raise HTTPException(404, f"Process not found: {id=}")
    res = await repo.update(process, **schema.model_dump())
    return res


@router.delete("/{id}")
async def delete(id: int, repos: DependsRepositoryManager):
    logger.debug(f"Deleting process...: {id=}")
    repo = repos.get(BpmnProcessRepository)
    process = await repo.get(id)
    if process is None:
        raise HTTPException(404, f"Process not found: {id=}")
    await repo.delete(process)
    return True


@router.post("/{id}/create_instance", response_model=BpmnProcessInstanceSchema)
async def create_instance(
    id: int,
    repos: DependsRepositoryManager,
    engine: DependsBpmnEngine,
    data: Annotated[dict | None, Body()] = None,
):
    logger.debug(f"Creating process instance...: {id=}")
    process_repo = repos.get(BpmnProcessRepository)
    process = await process_repo.get(id)
    if process is None:
        raise HTTPException(404, f"Process not found: {id=}")
    engine.add_bpmn(process.xml_definition)
    wf = engine.start_workflow(process.name, data)
    serialization = engine.serialize_workflow(wf)
    task_id = wf.get_next_task_id()
    completed = wf.is_completed()
    process_instance = BpmnProcessInstance(
        bpmn_process_id=process.id,
        serialization=serialization,
        task_id=task_id,
        completed=completed,
    )
    process_instance_repo = repos.get(BpmnProcessInstanceRepository)
    await process_instance_repo.add(process_instance)
    return process_instance
