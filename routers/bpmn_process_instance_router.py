from typing import List

from fastapi import APIRouter, Depends, Body
from loguru import logger

from db.models import BpmnProcessInstance
from db.repos import RepoManager, get_repo_manager
from schemas import BpmnProcessInstanceSchema

router = APIRouter(prefix='/bpmn_process_instances', tags=['BpmnProcessInstance'])


@router.get('', response_model=List[BpmnProcessInstanceSchema])
async def get_all(repo_manager: RepoManager = Depends(get_repo_manager)):
    logger.info("Fetching all processes...")
    repo = repo_manager.get_repo(BpmnProcessInstance)
    return await repo.all()


@router.get('/{id}', response_model=BpmnProcessInstanceSchema)
async def get_one(id: int, repo_manager: RepoManager = Depends(get_repo_manager)):
    repo = repo_manager.get_repo(BpmnProcessInstance)
    return await repo.get(id)