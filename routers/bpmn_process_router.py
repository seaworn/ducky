from typing import List

from fastapi import APIRouter, Depends, Body
from loguru import logger

from db.models import BpmnProcess
from db.repos import RepoManager, get_repo_manager
from schemas import BpmnProcessSchema

router = APIRouter(prefix='/bpmn_processes', tags=['BpmnProcess'])


@router.get('', response_model=List[BpmnProcessSchema])
async def get_all(repo_manager: RepoManager = Depends(get_repo_manager)):
    logger.info("Fetching all processes...")
    repo = repo_manager.get_repo(BpmnProcess)
    return await repo.all()


@router.get('/{id}', response_model=BpmnProcessSchema)
async def get_one(id: int, repo_manager: RepoManager = Depends(get_repo_manager)):
    repo = repo_manager.get_repo(BpmnProcess)
    return await repo.get(id)


@router.post('', response_model=BpmnProcessSchema)
async def create(bpmn_process_schema: BpmnProcessSchema = Body(...), repo_manager: RepoManager = Depends(get_repo_manager)):
    logger.info('Creating process...')
    repo = repo_manager.get_repo(BpmnProcess)
    return await repo.create(dict(bpmn_process_schema))


@router.put('/{id}', response_model=BpmnProcessSchema)
async def update(id: int, bpmn_process_schema: BpmnProcessSchema = Body(...), repo_manager: RepoManager = Depends(get_repo_manager)):
    logger.info('Updating process...')
    repo = repo_manager.get_repo(BpmnProcess)
    return await repo.update(id, dict(bpmn_process_schema))


@router.delete('/{id}')
async def delete(id:int, repo_manager: RepoManager = Depends(get_repo_manager)):
    logger.info('Deleting process...')
    repo = repo_manager.get_repo(BpmnProcess)
    return await repo.delete(id)
