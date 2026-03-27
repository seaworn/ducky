from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from loguru import logger

from api.dependencies import DependsBpmnEngine, DependsRepositoryManager
from api.schemas import BpmnProcessInstanceSchema
from db.models import BpmnProcessInstanceRepository

router = APIRouter(prefix="/bpmn_process_instances", tags=["bpmn_process_instance"])


@router.get("", response_model=list[BpmnProcessInstanceSchema])
async def all(repos: DependsRepositoryManager):
    logger.debug("Fetching all processes instances...")
    repo = repos.get(BpmnProcessInstanceRepository)
    res = await repo.all()
    return res


@router.get("/{id}", response_model=BpmnProcessInstanceSchema)
async def get(id: int, repos: DependsRepositoryManager):
    logger.debug(f"Fetching process instance...: {id=}")
    repo = repos.get(BpmnProcessInstanceRepository)
    res = await repo.get(id)
    return res


@router.post("/{id}/run", response_model=BpmnProcessInstanceSchema)
async def run(
    id: int,
    repos: DependsRepositoryManager,
    engine: DependsBpmnEngine,
    data: Annotated[dict | None, Body()] = None,
):
    logger.debug(f"Running process instance...: {id=}")
    repo = repos.get(BpmnProcessInstanceRepository)
    process_instance = await repo.get(id)
    if process_instance is None:
        raise HTTPException(404, f"Process instance not found: {id=}")
    wf = engine.resume_workflow(
        process_instance.serialization, data, process_instance.task_id
    )
    serialization = engine.serialize_workflow(wf)
    task_id = wf.get_next_task_id()
    await repo.update(process_instance, serialization=serialization, task_id=task_id)
    return process_instance
