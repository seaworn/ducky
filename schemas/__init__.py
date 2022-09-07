from pydantic import BaseModel


class BpmnProcessSchema(BaseModel):
    name: str
    xml_definition: str

    class Config:
        orm_mode = True


class BpmnProcessInstanceSchema(BaseModel):
    bpmn_process_id: int
    current_task: str

    class Config:
        orm_mode = True
