from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.bpmn_task_router import router as bpmn_task_router
from api.bpmn_task_spec_router import router as bpmn_task_spec_router
from api.bpmn_workflow_router import router as bpmn_workflow_router
from api.bpmn_workflow_spec_router import router as bpmn_workflow_spec_router
from api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create upload dir
    settings.UPLOAD_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.get("/health", tags=["root"])
async def healthcheck():
    return {"message": "OK"}


app.include_router(bpmn_workflow_spec_router)
app.include_router(bpmn_workflow_router)
app.include_router(bpmn_task_spec_router)
app.include_router(bpmn_task_router)
