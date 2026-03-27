from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.bpmn_process_instance_router import router as bpmn_process_instance_router
from api.bpmn_process_router import router as bpmn_process_router

app = FastAPI()

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


app.include_router(bpmn_process_router)
app.include_router(bpmn_process_instance_router)
