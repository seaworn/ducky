from typing import Optional

from fastapi import FastAPI, APIRouter, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware

from db.models import BpmnProcess, BpmnProcessInstance
from db.repos import RepoManager, get_repo_manager
from bpmn import BpmnRunner, get_bpmn_runner
from routers import bpmn_process_router
from routers import bpmn_process_instance_router
from schemas import BpmnProcessInstanceSchema

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
    allow_credentials=True,
)

app.include_router(bpmn_process_router)
app.include_router(bpmn_process_instance_router)


@app.get('/', tags=['Root'])
async def root():
    return {'message': 'Welcome to FastAPI'}


test = APIRouter(prefix='/test', tags=['Test'])


@test.post('/create_process_instance/{id}', response_model=BpmnProcessInstanceSchema)
async def create_process_instance(
        id: int,
        bpmn_runner: BpmnRunner = Depends(get_bpmn_runner),
        repo_manager: RepoManager = Depends(get_repo_manager)
):
    process = await repo_manager.get_repo(BpmnProcess).get(id)
    if process is None:
        raise HTTPException(404, f'Process with id {id} not found')
    return await bpmn_runner.create_process_instance(process)


@test.post('/run_process_instance/{id}', response_model=BpmnProcessInstanceSchema)
async def run_process_instance(
        id: Optional[int] = None,
        data: Optional[dict] = Body(None),
        bpmn_runner: BpmnRunner = Depends(get_bpmn_runner),
        repo_manager: RepoManager = Depends(get_repo_manager)
):
    process_instance = await repo_manager.get_repo(BpmnProcessInstance).get(id)
    if process_instance is None:
        raise HTTPException(
            404, f'Process instance with id {id} not found')
    return await bpmn_runner.run(process_instance, data)

app.include_router(test)
