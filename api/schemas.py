from pydantic import BaseModel


class BpmnProcessSchema(BaseModel):
    id: int
    name: str
    xml_definition: str

    class Config:
        from_attributes = True


class BpmnProcessInstanceSchema(BaseModel):
    id: int
    bpmn_process_id: int
    serialization: str  # dict
    task_id: str

    class Config:
        from_attributes = True
