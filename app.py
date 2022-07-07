from typing import Optional

from fastapi import FastAPI, Body, Depends
from fastapi.middleware.cors import CORSMiddleware

from db.models import BpmnProcess, BpmnProcessInstance
from db.repos import RepoManager, get_repo_manager
from bpmn.bpmn_runner import BpmnRunner, get_bpmn_runner
from routers import bpmn_process_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
    allow_credentials=True,
)
app.include_router(bpmn_process_router)


@app.get('/')
async def root():
    return {'message': 'Hello! Welcome to MyFastAPI'}


@app.post('/test_bpmn/{process}/{instance}')
@app.post('/test_bpmn/{process}')
@app.post('/test_bpmn')
async def test(
        process_id: int = 1,
        process_instance_id: Optional[int] = None,
        data: Optional[dict] = Body(None),
        bpmn_runner: BpmnRunner = Depends(get_bpmn_runner),
        repo_manager: RepoManager = Depends(get_repo_manager)):
    if process_instance_id is None:
        process = await repo_manager.get_repo(BpmnProcess).get(process_id)
        process_instance = await bpmn_runner.create_process_instance(process, data)
    else:
        process_instance = await repo_manager.get_repo(BpmnProcessInstance).get(process_instance_id)
        process_instance = await bpmn_runner.run_to_next_state(process_instance, data)
    # print(instance)
    return {}
